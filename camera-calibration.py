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

    # Extract focal length, make, and model
    focal_length_data = exif_data.get('FocalLength')
    if focal_length_data:
        focal_length = focal_length_data.numerator / focal_length_data.denominator
    else:
        focal_length = 0

    make = exif_data.get('Make', '').lower()  # lowercase make name to comply with OA droneModels.json convention
    model = exif_data.get('Model', '').upper()  # uppercase model name to comply with OA droneModels.json convention

    return focal_length, make, model

def calculate_ccd_width_height_per_pixel(focal_length, mtx):
    fx = mtx[0, 0]
    fy = mtx[1, 1]
    ccd_width_mm_per_pixel = focal_length / fx
    ccd_height_mm_per_pixel = focal_length / fy
    return ccd_width_mm_per_pixel, ccd_height_mm_per_pixel

import json

def format_as_dronemodels_json(focal_length, make, model, mtx, dist, width_pixels, height_pixels, drone_name):
    ccd_width_mm_per_pixel, ccd_height_mm_per_pixel = calculate_ccd_width_height_per_pixel(focal_length, mtx)

    calibration_data = {
        "makeModel": make.lower() + model.upper(),
        "isThermal": "false",
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
    if drone_name:
        calibration_data["comment"] = drone_name

    return json.dumps(calibration_data, indent=4)


def calibrate_camera(image_dir, square_size, num_rows, num_cols):
    rows = num_rows - 1  # Convert number of squares to number of corners
    cols = num_cols - 1
    square_size = square_size / 1000.0  # Convert mm to meters

    criteria = (cv2.TERM_CRITERIA_EPS + cv2.TERM_CRITERIA_MAX_ITER, 30, 0.001)
    objp = np.zeros((rows * cols, 3), np.float32)
    objp[:,:2] = np.mgrid[0:cols, 0:rows].T.reshape(-1, 2) * square_size

    objpoints = []  # 3d points in real-world space
    imgpoints = []  # 2d points in image plane

    # Read images
    image_types = ('*.jpg', '*.JPG', '*.jpeg', '*.JPEG')
    image_paths = []
    for extension in image_types:
        image_paths.extend(glob.glob(os.path.join(image_dir, extension)))

    width_pixels = height_pixels = None
    focal_length = make = model = None

    for idx, image_path in enumerate(image_paths):
        print(f"Processing image {idx + 1}/{len(image_paths)}: {os.path.basename(image_path)}")
        img = cv2.imread(image_path)
        if img is None:
            continue
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)

        # Extract EXIF data from the first image
        if focal_length is None or make is None or model is None:
            focal_length, make, model = get_exif_data(image_path)
            if focal_length == 0.0:
                sys.exit("Focal Length could not be obtained from image EXIF data, please perform calculations manually")
            if make is None or make == "":
                make = "unknownmake"
            if model is None or model == "":
                model = "UNKNOWNMODEL"
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
    parser.add_argument('-n', '--drone_name', type=str, default="",
                        help='Human-readable name of the drone model. Optional.')


    return parser.parse_args()

if __name__ == "__main__":
    args = parse_arguments()
    drone_name = args.drone_name
    if not drone_name:
        drone_name = input("Enter a human-readable name for your drone model (leave blank to omit): ")

    focal_length, make, model, mtx, dist, width_pixels, height_pixels = calibrate_camera(
        args.image_dir, args.square_size, args.num_rows, args.num_cols
    )

    # Convert the calibration data to JSON format
    calibration_json_data = format_as_dronemodels_json(focal_length, make, model, mtx, dist, width_pixels, height_pixels, drone_name)
    # print to stdout
    print("Here you go!:")
    print(calibration_json_data)
    # save to file
    json_filename = f"{make.lower()}{model.upper()}.json"
    with open(json_filename, 'w') as json_file:
        json_file.write(calibration_json_data)
