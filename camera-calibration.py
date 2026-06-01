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
        img = cv2.imread(image_path)
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


def estimate_fisheye_theta_max(mtx, dist, width_pixels, height_pixels):
    points = np.array(
        [
            [0.0, 0.0],
            [width_pixels - 1.0, 0.0],
            [0.0, height_pixels - 1.0],
            [width_pixels - 1.0, height_pixels - 1.0],
            [width_pixels / 2.0, 0.0],
            [width_pixels / 2.0, height_pixels - 1.0],
            [0.0, height_pixels / 2.0],
            [width_pixels - 1.0, height_pixels / 2.0],
        ],
        dtype=np.float64,
    ).reshape(-1, 1, 2)

    try:
        undistorted = cv2.fisheye.undistortPoints(points, mtx, dist)
        radii = np.linalg.norm(undistorted.reshape(-1, 2), axis=1)
        theta_values = np.arctan(radii)
        theta_max = float(np.nanmax(theta_values))
    except cv2.error:
        fx = float(mtx[0, 0])
        fy = float(mtx[1, 1])
        cx = float(mtx[0, 2])
        cy = float(mtx[1, 2])
        normalized = np.array(
            [[(x - cx) / fx, (y - cy) / fy] for x, y in points.reshape(-1, 2)],
            dtype=np.float64,
        )
        theta_max = float(np.arctan(np.max(np.linalg.norm(normalized, axis=1))))

    if not np.isfinite(theta_max) or theta_max <= 0:
        theta_max = np.pi / 2.0

    return min(theta_max, np.pi * 0.99)


def convert_opencv_fisheye_to_dronemodels(mtx, dist, width_pixels, height_pixels):
    k1, k2, k3, k4 = get_distortion_coefficients(dist, 4)
    theta_max = estimate_fisheye_theta_max(mtx, dist, width_pixels, height_pixels)
    theta = np.linspace(theta_max / 200.0, theta_max, 200)

    # OpenCV fisheye uses theta_d = theta * (1 + k1*theta^2 + ... + k4*theta^8).
    # DroneModels/Pix4D stores a normalized quartic polynomial where poly1 is 1.
    theta_distorted = theta * (
        1.0
        + k1 * theta**2
        + k2 * theta**4
        + k3 * theta**6
        + k4 * theta**8
    )
    fit_matrix = np.column_stack((theta**2, theta**3, theta**4))
    poly2, poly3, poly4 = np.linalg.lstsq(
        fit_matrix,
        theta_distorted - theta,
        rcond=None,
    )[0]

    return {
        "poly0": get_float(0.0),
        "poly1": get_float(1.0),
        "poly2": get_float(poly2),
        "poly3": get_float(poly3),
        "poly4": get_float(poly4),
        "c": get_float(mtx[0, 0]),
        "d": get_float(mtx[0, 1]),
        "e": get_float(mtx[1, 0]),
        "f": get_float(mtx[1, 1]),
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


def write_calibration_files(lens_type, reprojection_error, mtx, dist, dronemodels_params=None):
    np.savez(
        "calibration_data.npz",
        lens_type=lens_type,
        reprojection_error=reprojection_error,
        matrix=mtx,
        distortion=dist,
    )

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
            for key in ("poly0", "poly1", "poly2", "poly3", "poly4", "c", "d", "e", "f"):
                writer.writerow([key, dronemodels_params[key]])

    print(f"Lens Type: {lens_type}")
    print("Reprojection Error:\n", reprojection_error)
    print("Camera Matrix:\n", mtx)
    print("\nOpenCV Distortion Coefficients:\n", dist.ravel())
    if dronemodels_params:
        print("\nDroneModels Fisheye Parameters:")
        for key in ("poly0", "poly1", "poly2", "poly3", "poly4", "c", "d", "e", "f"):
            print(f"{key}: {dronemodels_params[key]}")


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

    write_calibration_files(args.lens_type, ret, mtx, dist, dronemodels_params)

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

    focal_length, make, model, mtx, dist, width_pixels, height_pixels = calibrate_camera(args)

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
