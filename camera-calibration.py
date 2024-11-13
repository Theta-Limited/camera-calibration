import sys
import os
import numpy as np
import cv2
import glob
import argparse
import os
import csv

from PIL import Image
from PIL.ExifTags import TAGS

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

    # Extract focal length, make, and model
    focal_length_data = exif_data.get('FocalLength')
    if focal_length_data:
        focal_length = focal_length_data.numerator / focal_length_data.denominator
    else:
        focal_length = 0

    make = exif_data.get('Make', '').lower()  # lowercase make name to comply with OA droneModels.json convention
    model = exif_data.get('Model', '').upper()  # uppercase model name to comply with OA droneModels.json convention

    # sanitize make an model string
    make = make.replace('\u0000', '').strip()
    model = model.replace('\u0000', '').strip()

    return focal_length, make, model

def calculate_ccd_width_height_per_pixel(focal_length, mtx):
    fx = mtx[0, 0]
    fy = mtx[1, 1]
    ccd_width_mm_per_pixel = focal_length / fx
    ccd_height_mm_per_pixel = focal_length / fy
    return ccd_width_mm_per_pixel, ccd_height_mm_per_pixel

import json

def format_as_dronemodels_json(focal_length, make, model, mtx, dist, width_pixels, height_pixels, drone_comment):
    ccd_width_mm_per_pixel, ccd_height_mm_per_pixel = calculate_ccd_width_height_per_pixel(focal_length, mtx)

    calibration_data = {
        "makeModel": make.lower() + model.upper(),
        "isThermal": False,
        "ccdWidthMMPerPixel": str(ccd_width_mm_per_pixel) + "/1.0",
        "ccdHeightMMPerPixel": str(ccd_height_mm_per_pixel) + "/1.0",
        "widthPixels": width_pixels,
        "heightPixels": height_pixels,
        "lensType": "perspective",
        "radialR1": dist[0][0],
        "radialR2": dist[0][1],
        "radialR3": dist[0][4],
        "tangentialT1": dist[0][2],
        "tangentialT2": dist[0][3]
    }
    if drone_comment:
        calibration_data["comment"] = drone_comment

    return json.dumps(calibration_data, indent=4)


def calibrate_camera(args):
    image_dir, square_size, num_rows, num_cols = args.image_dir, args.square_size, args.num_rows, args.num_cols
    width_pixels = height_pixels = None

    focal_length = make = model = None
    if args.focal_length is not None and args.focal_length != 0.0:
        focal_length = args.focal_length
        if (focal_length <= 0.0):
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
    objp[:,:2] = np.mgrid[0:cols, 0:rows].T.reshape(-1, 2) * square_size

    objpoints = []  # 3d points in real-world space
    imgpoints = []  # 2d points in image plane

    # Read images
    image_types = ('*.jpg', '*.jpeg')
    image_paths = []
    for extension in image_types:
        image_paths.extend(glob.glob(os.path.join(image_dir, extension)))
        # Also include uppercase variants if not on Windows
        if sys.platform != "win32":
            image_paths.extend(glob.glob(os.path.join(image_dir, extension.upper())))

    for idx, image_path in enumerate(image_paths):
        print(f"Processing image {idx + 1}/{len(image_paths)}: {os.path.basename(image_path)}")
        img = cv2.imread(image_path)
        if img is None:
            continue
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)

        # Extract EXIF data from the first image
        if focal_length is None or make is None or model is None:
            exif_focal_length, exif_make, exif_model = get_exif_data(image_path)
            if focal_length is None and exif_focal_length is not None:
                focal_length = exif_focal_length
            while focal_length is None or focal_length <= 0.0:
                strin = input("Focal Length could not be obtained from image EXIF data, please input manually:")
                try:
                    focal_length = float(strin)
                except ValueError:
                    print("ERROR: " + strin + " is not a valid number! Please try again.")
            if make is None and exif_make is not None:
                make = exif_make
            while make is None or make == "":
                make = input("Camera Make (manufacturer) could not be obtained from image EXIF data, please input manually:").strip().lower()
            if model is None and exif_model is not None:
                model = exif_model
            while model is None or model == "":
                model = input("Camera Model (device name) could not be obtained from image EXIF data, please input manually:").strip().upper()
            height_pixels, width_pixels = gray.shape[:2]

        ret, corners = cv2.findChessboardCorners(gray, (cols, rows), None)
        if ret:
            objpoints.append(objp)
            corners2 = cv2.cornerSubPix(gray, corners, (11, 11), (-1, -1), criteria)
            imgpoints.append(corners2)

    ret, mtx, dist, rvecs, tvecs = cv2.calibrateCamera(objpoints, imgpoints, gray.shape[::-1], None, None)

    # # Save to .npz, CSV, and print to stdout
    # np.savez('calibration_data.npz', matrix=mtx, distortion=dist)

    # # Output to CSV file
    # with open('calibration_data.csv', 'w', newline='') as csvfile:
    #     writer = csv.writer(csvfile)
    #     writer.writerow(['Camera Matrix'])
    #     writer.writerows(mtx)
    #     writer.writerow(['Distortion Coefficients'])
    #     writer.writerow(dist.ravel())

    # # Print intrinsics matrix and distortion params to stdout
    # print("Camera Matrix:\n", mtx)
    # print("\nDistortion Coefficients:\n", dist.ravel())

    return focal_length, make, model, mtx, dist, width_pixels, height_pixels

def parse_arguments():
    parser = argparse.ArgumentParser(
        description='Camera Calibration Script for OpenAthena.',
        epilog='Example command:\n  python3 camera-calibration.py --image_dir path/to/images --square_size 100 --num_rows 9 --num_cols 12',
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument('-d', '--image_dir', type=str, default=os.getcwd(),
                        help='Directory of calibration images. Default is the current working directory.')
    parser.add_argument('-s', '--square_size', type=float, required=True,
                        help='Size of one square on the chessboard in millimeters.')
    parser.add_argument('-r', '--num_rows', type=int, required=True,
                        help='Total number of rows of squares on the chessboard.')
    parser.add_argument('-c', '--num_cols', type=int, required=True,
                        help='Total number of columns of squares on the chessboard.')
    parser.add_argument('-n', '--drone_comment', type=str, default="",
                        help='Human-readable text for the comment field for your drone model. Optional.')
    parser.add_argument('-f', '--focal_length', type=float, required=False,
                        help='Focal length (in mm) of the camera to be calibrated. Mandatory only if such data is not available within EXIF')
    parser.add_argument('-m', '--make', type=str, required=False,
                        help='Name of the manufacturer of the camera. Mandatory only if such is not available within EXIF metadata')
    parser.add_argument('-M', '--model', type=str, required=False,
                        help='model name of the camera. Mandatory only if such data is not available within EXIF metadata')


    return parser.parse_args()

if __name__ == "__main__":
    args = parse_arguments()
    drone_comment = args.drone_comment
    if not drone_comment:
        drone_comment = input("Enter human-readable text for the comment field for your drone model (leave blank to omit): ")

    focal_length, make, model, mtx, dist, width_pixels, height_pixels = calibrate_camera(args)

    # Convert the calibration data to JSON format
    calibration_json_data = format_as_dronemodels_json(focal_length, make, model, mtx, dist, width_pixels, height_pixels, drone_comment)
    # print to stdout
    print("Here you go!:")
    print(calibration_json_data)
    # save to file
    json_filename = f"{make.lower()}{model.upper()}.json"
    with open(json_filename, 'w') as json_file:
        json_file.write(calibration_json_data)
