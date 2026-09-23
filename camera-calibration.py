import argparse
import csv
import glob
import json
import os
import sys

import cv2
import numpy as np
from PIL import Image
from PIL.ExifTags import TAGS


LENS_TYPE_PERSPECTIVE = "perspective"
LENS_TYPE_FISHEYE = "fisheye"
LENS_TYPES = (LENS_TYPE_PERSPECTIVE, LENS_TYPE_FISHEYE)
FISHEYE_PARAMETER_KEYS = ("poly0", "poly1", "poly2", "poly3", "poly4",
                          "c", "d", "e", "f", "centerX", "centerY")


def get_exif_data(image_path):
    exif_data = {}
    img = Image.open(image_path)
    exif = img._getexif()
    if exif is not None:
        for tag, value in exif.items():
            decoded = TAGS.get(tag, tag)
            exif_data[decoded] = value
    else:
        return None, None, None

    focal_length_data = exif_data.get("FocalLength")
    if focal_length_data:
        focal_length = focal_length_data.numerator / focal_length_data.denominator
    else:
        focal_length = 0

    make = exif_data.get("Make", "").lower()  # lowercase to comply with OA droneModels.json convention
    model = exif_data.get("Model", "").upper()  # uppercase to comply with OA droneModels.json convention

    make = make.replace("\u0000", "").strip()
    model = model.replace("\u0000", "").strip()

    return focal_length, make, model


def calculate_ccd_width_height_per_pixel(focal_length, mtx):
    fx = mtx[0, 0]
    fy = mtx[1, 1]
    ccd_width_mm_per_pixel = focal_length / fx
    ccd_height_mm_per_pixel = focal_length / fy
    return ccd_width_mm_per_pixel, ccd_height_mm_per_pixel


def format_float(value, decimal_places=16):
    return f"{float(value):.{decimal_places}f}"


def get_float(value):
    return float(format_float(value))


def get_distortion_coefficients(dist, count):
    coefficients = np.zeros(count, dtype=np.float64)
    flattened = np.asarray(dist, dtype=np.float64).ravel()
    coefficients[:min(count, flattened.size)] = flattened[:count]
    return coefficients


def get_image_paths(image_dir):
    if not os.path.isdir(image_dir):
        sys.exit(f"FATAL ERROR: image directory does not exist or is not a directory: {image_dir}")

    image_types = ("*.jpg", "*.jpeg", "*.png")
    image_paths = []
    for extension in image_types:
        image_paths.extend(glob.glob(os.path.join(image_dir, extension)))
        if sys.platform != "win32":
            image_paths.extend(glob.glob(os.path.join(image_dir, extension.upper())))

    if len(image_paths) == 0:
        searched_patterns = []
        for extension in image_types:
            searched_patterns.append(os.path.join(image_dir, extension))
            if sys.platform != "win32":
                searched_patterns.append(os.path.join(image_dir, extension.upper()))
        sys.exit(
            "FATAL ERROR: no calibration image files were found in specified folder.\n"
            f"Image directory: {image_dir}\n"
            "Searched for:\n  " + "\n  ".join(searched_patterns)
        )

    return sorted(image_paths)


def prompt_for_missing_camera_metadata(image_path, gray, focal_length, make, model):
    exif_focal_length, exif_make, exif_model = get_exif_data(image_path)
    if focal_length is None and exif_focal_length is not None:
        focal_length = exif_focal_length
    while focal_length is None or focal_length <= 0.0:
        user_input = input("Focal Length could not be obtained from image EXIF data, please input manually:")
        try:
            focal_length = float(user_input)
        except ValueError:
            print("ERROR: " + user_input + " is not a valid number! Please try again.")

    if make is None and exif_make is not None:
        make = exif_make
    while make is None or make == "":
        make = input("Camera Make (manufacturer) could not be obtained from image EXIF data, please input manually:").strip().lower()

    if model is None and exif_model is not None:
        model = exif_model
    while model is None or model == "":
        model = input("Camera Model (device name) could not be obtained from image EXIF data, please input manually:").strip().upper()

    height_pixels, width_pixels = gray.shape[:2]
    image_size = gray.shape[::-1]

    return focal_length, make, model, image_size, width_pixels, height_pixels


def collect_calibration_points(args):
    image_dir = args.image_dir
    square_size = args.square_size
    num_rows = args.num_rows
    num_cols = args.num_cols
    width_pixels = height_pixels = None
    image_size = None

    focal_length = make = model = None
    if args.focal_length is not None and args.focal_length != 0.0:
        focal_length = args.focal_length
        if focal_length <= 0.0:
            sys.exit("FATAL ERROR: focal length <= 0.0 mm is not valid!")
    if args.make is not None and args.make != "":
        make = args.make.strip().lower()
    if args.model is not None and args.model != "":
        model = args.model.strip().upper()

    rows = num_rows - 1  # Convert number of squares to number of corners
    cols = num_cols - 1
    square_size = square_size / 1000.0  # Convert mm to meters

    criteria = (cv2.TERM_CRITERIA_EPS + cv2.TERM_CRITERIA_MAX_ITER, 30, 0.001)
    objp = np.zeros((rows * cols, 3), np.float32)
    objp[:, :2] = np.mgrid[0:cols, 0:rows].T.reshape(-1, 2) * square_size

    objpoints = []  # 3d points in real-world space
    imgpoints = []  # 2d points in image plane
    image_paths = get_image_paths(image_dir)

    for idx, image_path in enumerate(image_paths):
        print(f"Processing image {idx + 1}/{len(image_paths)}: {os.path.basename(image_path)}")
        # OpenAthena selects pixels in the raw raster, before EXIF orientation
        # is applied for display. Calibrate in that same coordinate system.
        img = cv2.imread(image_path, cv2.IMREAD_COLOR | cv2.IMREAD_IGNORE_ORIENTATION)
        if img is None:
            continue
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)

        if focal_length is None or make is None or model is None:
            focal_length, make, model, image_size, width_pixels, height_pixels = prompt_for_missing_camera_metadata(
                image_path,
                gray,
                focal_length,
                make,
                model,
            )
        elif image_size is None:
            height_pixels, width_pixels = gray.shape[:2]
            image_size = gray.shape[::-1]

        if gray.shape[::-1] != image_size:
            raise ValueError(f"Calibration images must have the same raw pixel dimensions: "
                             f"{image_path} is {gray.shape[::-1]}, expected {image_size}")

        ret, corners = cv2.findChessboardCorners(gray, (cols, rows), None)
        if ret:
            objpoints.append(objp.copy())
            corners2 = cv2.cornerSubPix(gray, corners, (11, 11), (-1, -1), criteria)
            imgpoints.append(corners2)

    if image_size is None:
        sys.exit("FATAL ERROR: no readable calibration images were found.")

    if len(objpoints) == 0:
        sys.exit("FATAL ERROR: chessboard corners were not detected in any calibration image.")

    return focal_length, make, model, objpoints, imgpoints, image_size, width_pixels, height_pixels


def calibrate_perspective_camera(objpoints, imgpoints, image_size):
    return cv2.calibrateCamera(objpoints, imgpoints, image_size, None, None)


def calibrate_fisheye_camera(objpoints, imgpoints, image_size):
    fisheye_objpoints = [
        np.asarray(points, dtype=np.float64).reshape(1, -1, 3)
        for points in objpoints
    ]
    fisheye_imgpoints = [
        np.asarray(points, dtype=np.float64).reshape(1, -1, 2)
        for points in imgpoints
    ]
    k = np.zeros((3, 3), dtype=np.float64)
    d = np.zeros((4, 1), dtype=np.float64)
    flags = cv2.fisheye.CALIB_RECOMPUTE_EXTRINSIC
    criteria = (cv2.TERM_CRITERIA_EPS + cv2.TERM_CRITERIA_MAX_ITER, 100, 1e-6)

    return cv2.fisheye.calibrate(
        fisheye_objpoints,
        fisheye_imgpoints,
        image_size,
        k,
        d,
        None,
        None,
        flags,
        criteria,
    )


def _validate_fisheye_calibration(mtx, dist, width_pixels, height_pixels):
    matrix = np.asarray(mtx, dtype=np.float64)
    distortion = np.asarray(dist, dtype=np.float64).ravel()
    if matrix.shape != (3, 3) or not np.all(np.isfinite(matrix)):
        raise ValueError("Fisheye camera matrix must be a finite 3-by-3 matrix")
    if (matrix[0, 0] <= 0 or matrix[1, 1] <= 0 or matrix[1, 0] != 0
            or not np.array_equal(matrix[2], [0.0, 0.0, 1.0])):
        raise ValueError("Expected an OpenCV intrinsic matrix with positive focal scales")
    if distortion.size != 4 or not np.all(np.isfinite(distortion)):
        raise ValueError("OpenCV fisheye calibration requires exactly four finite coefficients")
    for size in (width_pixels, height_pixels):
        if not np.isfinite(size) or size <= 0 or int(size) != size:
            raise ValueError("Calibration image dimensions must be positive integers")
    affine = matrix[:2, :2]
    normalized = affine / np.max(np.abs(affine))
    if abs(np.linalg.det(normalized)) <= 1e-14:
        raise ValueError("Fisheye affine matrix is singular or ill-conditioned")
    return matrix, distortion


def _opencv_fisheye_radius(theta, distortion):
    return theta * (1.0 + theta**2 * np.polynomial.polynomial.polyval(theta**2, distortion))


def _real_roots_in_interval(coefficients, upper):
    roots = np.polynomial.polynomial.polyroots(coefficients)
    return sorted(float(root.real) for root in roots
                  if abs(root.imag) <= 1e-10 * max(1.0, abs(root.real))
                  and 0.0 < root.real < upper)


def _opencv_fisheye_branch_limit(distortion):
    # theta_d'(theta) is a quartic in z=theta^2. Its extrema partition
    # that quartic into monotone intervals, so even a narrow fold is detected.
    derivative = np.concatenate(([1.0], distortion * [3.0, 5.0, 7.0, 9.0]))
    limit_squared = (np.pi / 2.0)**2
    critical = _real_roots_in_interval(
        np.polynomial.polynomial.polyder(derivative), limit_squared
    )
    lower = 0.0
    for upper in critical + [limit_squared]:
        if np.polynomial.polynomial.polyval(upper, derivative) <= 0.0:
            for _ in range(80):
                middle = (lower + upper) / 2.0
                if np.polynomial.polynomial.polyval(middle, derivative) > 0.0:
                    lower = middle
                else:
                    upper = middle
            return float(np.sqrt((lower + upper) / 2.0))
        lower = upper
    return np.pi / 2.0


def _fisheye_corner_radius(matrix, width_pixels, height_pixels):
    corners = np.array([[0.0, 0.0], [width_pixels - 1.0, 0.0],
                        [0.0, height_pixels - 1.0],
                        [width_pixels - 1.0, height_pixels - 1.0]])
    normalized = np.linalg.solve(matrix[:2, :2], (corners - matrix[:2, 2]).T)
    radius = float(np.max(np.hypot(normalized[0], normalized[1])))
    if not np.isfinite(radius) or radius <= 0.0:
        raise ValueError("Image does not define a finite, nonzero fisheye fitting range")
    return radius


def estimate_fisheye_theta_max(mtx, dist, width_pixels, height_pixels):
    """Estimate the raster's supported off-axis angle in radians, at most pi/2.

    Invert the full OpenCV affine transform (including skew), then the radial
    polynomial. undistortPoints is unsuitable here: it can clamp large radii
    or return failure sentinels that look like valid angles after atan().
    """
    matrix, distortion = _validate_fisheye_calibration(mtx, dist, width_pixels, height_pixels)
    radius = _fisheye_corner_radius(matrix, width_pixels, height_pixels)
    upper = _opencv_fisheye_branch_limit(distortion)
    maximum_radius = _opencv_fisheye_radius(upper, distortion)
    if not np.isfinite(maximum_radius) or maximum_radius <= 0.0:
        raise ValueError("OpenCV fisheye polynomial has no usable increasing branch")
    if radius >= maximum_radius:
        if upper < np.pi / 2.0:
            raise ValueError("OpenCV fisheye radial slope reaches zero before covering the image; "
                             "check the calibration for a stationary point or fold")
        # A circular fisheye image can have raster corners outside its supported
        # front hemisphere. Do not extrapolate the polynomial behind the camera.
        return upper
    lower = 0.0
    for _ in range(80):
        middle = (lower + upper) / 2.0
        if _opencv_fisheye_radius(middle, distortion) < radius:
            lower = middle
        else:
            upper = middle
    return (lower + upper) / 2.0


def _validate_pix4d_polynomial(parameters, q_max):
    coefficients = [parameters[f"poly{i}"] for i in range(5)]
    derivative = np.polynomial.polynomial.polyder(coefficients)
    critical = _real_roots_in_interval(np.polynomial.polynomial.polyder(derivative), q_max)
    slopes = np.polynomial.polynomial.polyval([0.0, *critical, q_max], derivative)
    if not np.all(np.isfinite(slopes)) or np.min(slopes) <= 0.0:
        raise ValueError("Fitted PIX4D polynomial is not strictly increasing over the fitting range; "
                         "a quartic cannot safely represent this calibration")


def convert_opencv_fisheye_to_dronemodels(mtx, dist, width_pixels, height_pixels):
    """Fit a PIX4D normalized-angle quartic to the OpenCV fisheye projection.

    PIX4D q = 2*theta/pi, rho = theta_d/pi*2, and A = (pi/2)*K[:2,:2].
    The quartic matches the source radius at the fitting endpoint to preserve
    coverage, particularly at the 90-degree front-hemisphere boundary.
    """
    matrix, distortion = _validate_fisheye_calibration(mtx, dist, width_pixels, height_pixels)
    theta_max = estimate_fisheye_theta_max(matrix, distortion, width_pixels, height_pixels)
    scale = np.pi / 2.0
    q_max = theta_max / scale
    if np.all(distortion[1:] == 0.0):
        # This submodel has an exact cubic representation; avoid injecting
        # least-squares roundoff into coefficients that are exactly zero.
        poly2, poly3, poly4 = 0.0, distortion[0] * scale**2, 0.0
    else:
        # Work in t=q/q_max to keep the least-squares system well scaled even
        # for a narrow field of view. Form rho-q directly to avoid cancellation.
        t = np.linspace(1.0 / 200.0, 1.0, 200)
        theta = theta_max * t
        q = q_max * t
        radial_delta = q * theta**2 * np.polynomial.polynomial.polyval(theta**2, distortion)
        endpoint_delta = radial_delta[-1]
        fit_matrix = np.column_stack((t**2 - t**4, t**3 - t**4))
        a2, a3 = np.linalg.lstsq(fit_matrix, radial_delta - endpoint_delta * t**4, rcond=None)[0]
        a4 = endpoint_delta - a2 - a3
        poly2, poly3, poly4 = a2 / q_max**2, a3 / q_max**3, a4 / q_max**4

    # Keep full float precision. Fixed decimal rounding can erase small
    # coefficients and change invertibility near a stationary point.
    parameters = {
        "poly0": 0.0,
        "poly1": 1.0,
        "poly2": float(poly2),
        "poly3": float(poly3),
        "poly4": float(poly4),
        "c": float(scale * matrix[0, 0]),
        "d": float(scale * matrix[0, 1]),
        "e": float(scale * matrix[1, 0]),
        "f": float(scale * matrix[1, 1]),
        "centerX": float(matrix[0, 2]),
        "centerY": float(matrix[1, 2]),
    }
    if not all(np.isfinite(value) for value in parameters.values()):
        raise ValueError("Non-finite PIX4D parameters after conversion")
    _validate_pix4d_polynomial(parameters, q_max)
    return parameters


def fisheye_conversion_diagnostics(mtx, dist, width_pixels, height_pixels, params=None):
    """Measure model-conversion error separately from checkerboard calibration RMS.

    Pixel errors are conservative bounds over image-circle azimuth: radial
    error times the largest singular value of the PIX4D affine matrix.
    Angular errors compare independently sampled source rays with the inverse
    of the exported quartic. Neither measures error against real-world truth.
    """
    matrix, distortion = _validate_fisheye_calibration(mtx, dist, width_pixels, height_pixels)
    if params is None:
        params = convert_opencv_fisheye_to_dronemodels(matrix, distortion, width_pixels, height_pixels)
    theta_max = estimate_fisheye_theta_max(matrix, distortion, width_pixels, height_pixels)
    scale = np.pi / 2.0
    q_max = theta_max / scale
    _validate_pix4d_polynomial(params, q_max)
    coefficients = [params[f"poly{i}"] for i in range(5)]
    theta = np.linspace(0.0, theta_max, 4097)
    q = theta / scale
    source_radius = _opencv_fisheye_radius(theta, distortion) / scale
    fitted_radius = np.polynomial.polynomial.polyval(q, coefficients)
    affine = np.array([[params["c"], params["d"]], [params["e"], params["f"]]])
    pixel_errors = np.abs(fitted_radius - source_radius) * np.linalg.svd(affine, compute_uv=False)[0]

    # The endpoint constraint supplies a bracket for every source sample.
    tolerance = 32.0 * np.spacing(max(source_radius[-1], fitted_radius[-1]))
    if source_radius[-1] > fitted_radius[-1] + tolerance:
        raise ValueError("PIX4D polynomial does not cover the source fitting range")
    lower = np.zeros_like(q)
    upper = np.full_like(q, q_max)
    for _ in range(60):
        middle = (lower + upper) / 2.0
        below = np.polynomial.polynomial.polyval(middle, coefficients) < source_radius
        lower = np.where(below, middle, lower)
        upper = np.where(below, upper, middle)
    angle_errors = np.degrees(np.abs((lower + upper) / 2.0 * scale - theta))
    corner_radius = _fisheye_corner_radius(matrix, width_pixels, height_pixels)
    source_limit = _opencv_fisheye_radius(theta_max, distortion)
    return {
        "fit_max_angle_deg": float(np.degrees(theta_max)),
        "max_pixel_error_bound": float(np.max(pixel_errors)),
        "rms_pixel_error_bound": float(np.sqrt(np.mean(pixel_errors**2))),
        "max_ray_error_deg": float(np.max(angle_errors)),
        "rms_ray_error_deg": float(np.sqrt(np.mean(angle_errors**2))),
        "image_corners_within_fit": bool(corner_radius <= source_limit + 32.0 * np.spacing(source_limit)),
        "sample_count": int(theta.size),
    }


def format_as_dronemodels_json(
    focal_length,
    make,
    model,
    mtx,
    dist,
    width_pixels,
    height_pixels,
    drone_comment,
    lens_type=LENS_TYPE_PERSPECTIVE,
):
    ccd_width_mm_per_pixel, ccd_height_mm_per_pixel = calculate_ccd_width_height_per_pixel(focal_length, mtx)

    calibration_data = {
        "makeModel": make.lower() + model.upper(),
        "isThermal": False,
        "ccdWidthMMPerPixel": str(ccd_width_mm_per_pixel) + "/1.0",
        "ccdHeightMMPerPixel": str(ccd_height_mm_per_pixel) + "/1.0",
        "widthPixels": width_pixels,
        "heightPixels": height_pixels,
        "lensType": lens_type,
    }

    if lens_type == LENS_TYPE_PERSPECTIVE:
        k1, k2, p1, p2, k3 = get_distortion_coefficients(dist, 5)
        calibration_data.update({
            "radialR1": get_float(k1),
            "radialR2": get_float(k2),
            "radialR3": get_float(k3),
            "tangentialT1": get_float(p1),
            "tangentialT2": get_float(p2),
        })
    elif lens_type == LENS_TYPE_FISHEYE:
        calibration_data.update(
            convert_opencv_fisheye_to_dronemodels(
                mtx,
                dist,
                width_pixels,
                height_pixels,
            )
        )
    else:
        sys.exit(f"FATAL ERROR: unsupported lens type: {lens_type}")

    if drone_comment:
        calibration_data["comment"] = drone_comment

    return json.dumps(calibration_data, indent=4)


def write_calibration_files(lens_type, reprojection_error, mtx, dist,
                            dronemodels_params=None, conversion_diagnostics=None):
    archive = dict(
        lens_type=lens_type,
        reprojection_error=reprojection_error,
        matrix=mtx,
        distortion=dist,
    )
    if dronemodels_params is not None:
        archive.update({f"dronemodels_{key}": value for key, value in dronemodels_params.items()})
    if conversion_diagnostics is not None:
        archive.update({f"fisheye_{key}": value for key, value in conversion_diagnostics.items()})
    np.savez("calibration_data.npz", **archive)

    with open("calibration_data.csv", "w", newline="") as csvfile:
        writer = csv.writer(csvfile)
        writer.writerow(["Lens Type", lens_type])
        writer.writerow(["Reprojection Error", reprojection_error])
        writer.writerow(["Camera Matrix"])
        writer.writerows(mtx)
        writer.writerow(["OpenCV Distortion Coefficients"])
        writer.writerow(dist.ravel())
        if dronemodels_params:
            writer.writerow(["DroneModels Fisheye Parameters"])
            for key in FISHEYE_PARAMETER_KEYS:
                writer.writerow([key, dronemodels_params[key]])
        if conversion_diagnostics:
            writer.writerow(["PIX4D Conversion Diagnostics (separate from calibration RMS)"])
            writer.writerows(conversion_diagnostics.items())

    print(f"Lens Type: {lens_type}")
    print("OpenCV calibration RMS reprojection error (pixels):\n", reprojection_error)
    print("Camera Matrix:\n", mtx)
    print("\nOpenCV Distortion Coefficients:\n", dist.ravel())
    if dronemodels_params:
        print("\nDroneModels Fisheye Parameters:")
        for key in FISHEYE_PARAMETER_KEYS:
            print(f"{key}: {dronemodels_params[key]}")
    if conversion_diagnostics:
        print("\nPIX4D conversion diagnostics (separate from calibration RMS):")
        for key, value in conversion_diagnostics.items():
            print(f"{key}: {value}")
        if not conversion_diagnostics["image_corners_within_fit"]:
            print("Raster corners extend outside the supported 90-degree off-axis range.")


def calibrate_camera(args):
    (
        focal_length,
        make,
        model,
        objpoints,
        imgpoints,
        image_size,
        width_pixels,
        height_pixels,
    ) = collect_calibration_points(args)

    conversion_diagnostics = None
    if args.lens_type == LENS_TYPE_PERSPECTIVE:
        ret, mtx, dist, rvecs, tvecs = calibrate_perspective_camera(objpoints, imgpoints, image_size)
        dronemodels_params = None
    else:
        ret, mtx, dist, rvecs, tvecs = calibrate_fisheye_camera(objpoints, imgpoints, image_size)
        dronemodels_params = convert_opencv_fisheye_to_dronemodels(
            mtx,
            dist,
            width_pixels,
            height_pixels,
        )
        conversion_diagnostics = fisheye_conversion_diagnostics(
            mtx, dist, width_pixels, height_pixels, dronemodels_params
        )

    write_calibration_files(args.lens_type, ret, mtx, dist, dronemodels_params, conversion_diagnostics)

    return focal_length, make, model, mtx, dist, width_pixels, height_pixels


def parse_arguments():
    parser = argparse.ArgumentParser(
        description="Camera Calibration Script for OpenAthena.",
        epilog=(
            "Example command:\n"
            "  python3 camera-calibration.py --lens_type perspective --image_dir path/to/images "
            "--square_size 100 --num_rows 9 --num_cols 12"
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "-d",
        "--image_dir",
        type=str,
        default=os.getcwd(),
        help="Directory of calibration images. Default is the current working directory.",
    )
    parser.add_argument(
        "-s",
        "--square_size",
        type=float,
        required=True,
        help="Size of one square on the chessboard in millimeters.",
    )
    parser.add_argument(
        "-r",
        "--num_rows",
        type=int,
        required=True,
        help="Total number of rows of squares on the chessboard.",
    )
    parser.add_argument(
        "-c",
        "--num_cols",
        type=int,
        required=True,
        help="Total number of columns of squares on the chessboard.",
    )
    parser.add_argument(
        "-n",
        "--drone_comment",
        type=str,
        default="",
        help="Human-readable text for the comment field for your drone model. Optional.",
    )
    parser.add_argument(
        "-l",
        "--lens_type",
        type=str,
        choices=LENS_TYPES,
        default=LENS_TYPE_PERSPECTIVE,
        help="Lens model to calibrate. Default is perspective.",
    )
    parser.add_argument(
        "-f",
        "--focal_length",
        type=float,
        required=False,
        help="Focal length (in mm) of the camera to be calibrated. Mandatory only if such data is not available within EXIF",
    )
    parser.add_argument(
        "-m",
        "--make",
        type=str,
        required=False,
        help="Name of the manufacturer of the camera. Mandatory only if such is not available within EXIF metadata",
    )
    parser.add_argument(
        "-M",
        "--model",
        type=str,
        required=False,
        help="model name of the camera. Mandatory only if such data is not available within EXIF metadata",
    )

    return parser.parse_args()


if __name__ == "__main__":
    args = parse_arguments()
    drone_comment = args.drone_comment
    if not drone_comment:
        drone_comment = input("Enter human-readable text for the comment field for your drone model (leave blank to omit): ")

    try:
        focal_length, make, model, mtx, dist, width_pixels, height_pixels = calibrate_camera(args)
    except (ValueError, cv2.error) as error:
        sys.exit(f"FATAL ERROR: calibration could not be exported: {error}")

    calibration_json_data = format_as_dronemodels_json(
        focal_length,
        make,
        model,
        mtx,
        dist,
        width_pixels,
        height_pixels,
        drone_comment,
        args.lens_type,
    )
    print("Here you go!:")
    print(calibration_json_data)

    json_filename = f"{make.lower()}{model.upper()}.json"
    with open(json_filename, "w") as json_file:
        json_file.write(calibration_json_data)
