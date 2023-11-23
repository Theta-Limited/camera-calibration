import numpy as np
import cv2
import glob
import argparse
import os
import csv

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

    for image_path in image_paths:
        img = cv2.imread(image_path)
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        ret, corners = cv2.findChessboardCorners(gray, (cols, rows), None)

        if ret:
            objpoints.append(objp)
            corners2 = cv2.cornerSubPix(gray, corners, (11, 11), (-1, -1), criteria)
            imgpoints.append(corners2)

    ret, mtx, dist, rvecs, tvecs = cv2.calibrateCamera(objpoints, imgpoints, gray.shape[::-1], None, None)

    # Save to .npz, CSV, and print to stdout
    np.savez('calibration_data.npz', matrix=mtx, distortion=dist)

    # Output to CSV file
    with open('calibration_data.csv', 'w', newline='') as csvfile:
        writer = csv.writer(csvfile)
        writer.writerow(['Camera Matrix'])
        writer.writerows(mtx)
        writer.writerow(['Distortion Coefficients'])
        writer.writerow(dist.ravel())

    # Print to stdout
    print("Camera Matrix:\n", mtx)
    print("\nDistortion Coefficients:\n", dist.ravel())

def parse_arguments():
    parser = argparse.ArgumentParser(description='Camera Calibration Script.')
    parser.add_argument('-d', '--image_dir', type=str, default=os.getcwd(),
                        help='Directory of calibration images. Default is the current working directory.')
    parser.add_argument('-s', '--square_size', type=float, required=True,
                        help='Size of one square on the chessboard in millimeters.')
    parser.add_argument('-r', '--num_rows', type=int, required=True,
                        help='Total number of rows of squares on the chessboard.')
    parser.add_argument('-c', '--num_cols', type=int, required=True,
                        help='Total number of columns of squares on the chessboard.')

    return parser.parse_args()

if __name__ == "__main__":
    args = parse_arguments()
    calibrate_camera(args.image_dir, args.square_size, args.num_rows, args.num_cols)
