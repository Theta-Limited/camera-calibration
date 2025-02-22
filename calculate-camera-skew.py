#!/usr/bin/env python3
import argparse
import json
import cv2
import numpy as np
import math
from PIL import Image, ExifTags

def get_exif_focal_length(image_path):
    """
    Extract focal length (in mm) from the image's EXIF metadata.
    Returns focal_length as a float, or None if not found.
    """
    img = Image.open(image_path)
    exif = img._getexif()
    if exif is None:
        return None
    for tag, value in exif.items():
        decoded = ExifTags.TAGS.get(tag, tag)
        if decoded == 'FocalLength':
            try:
                return float(value)
            except Exception:
                # Fallback in case value is not directly convertible
                if hasattr(value, 'numerator') and hasattr(value, 'denominator'):
                    return value.numerator / value.denominator
                else:
                    return None
    return None

def get_exif_digital_zoom_ratio(image_path):
    """
    Extract digital zoom ratio from the image's EXIF metadata.
    Returns a float >= 1.0. Defaults to 1.0 if the tag is missing or invalid.
    """
    img = Image.open(image_path)
    exif = img._getexif()
    if exif is None:
        return 1.0
    for tag, value in exif.items():
        decoded = ExifTags.TAGS.get(tag, tag)
        if decoded == 'DigitalZoomRatio':
            try:
                ratio = float(value)
            except Exception:
                if hasattr(value, 'numerator') and hasattr(value, 'denominator'):
                    ratio = value.numerator / value.denominator
                else:
                    ratio = 1.0
            # Ensure ratio is not less than 1.0
            return ratio if ratio >= 1.0 else 1.0
    return 1.0

def parse_fraction(frac_str):
    """
    Parse a string fraction of the form 'a/b' and return the float result.
    """
    try:
        num, den = frac_str.split('/')
        return float(num) / float(den)
    except Exception as e:
        raise ValueError(f"Could not parse fraction from '{frac_str}': {e}")

def load_intrinsics(json_path):
    """
    Load camera intrinsic parameters from a JSON file.
    Expects at least 'ccdWidthMMPerPixel' and 'widthPixels' fields.
    """
    with open(json_path, 'r') as f:
        data = json.load(f)
    mm_per_pixel = parse_fraction(data["ccdWidthMMPerPixel"])
    width_pixels = data["widthPixels"]
    height_pixels = data.get("heightPixels", None)  # may be useful for y-axis computations
    return mm_per_pixel, width_pixels, height_pixels

def find_chessboard_center(image, pattern_size):
    """
    Detect the chessboard corners and compute the center (average of corners).
    pattern_size: tuple (num_inner_corners_x, num_inner_corners_y)
    Returns center as (cx, cy) in pixel coordinates.
    """
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    ret, corners = cv2.findChessboardCorners(gray, pattern_size, None)
    if not ret:
        raise ValueError("Chessboard pattern not found in image.")
    corners = np.squeeze(corners) # shape becomes (N,2)
    center = np.mean(corners, axis=0)
    return center

def compute_angle(offset, focal_pixels):
    """
    Compute the angle (in degrees) from the offset (in pixels) and focal length (in pixels).
    angle = arctan(opposite/adjacent)
    """
    return math.degrees(math.atan(offset / focal_pixels))

def process_image(image_path, json_path, pattern_size):
    """
    For a given image and its camera intrinsics (JSON), compute the pitch and yaw of the chessboard.
    Returns a tuple (pitch, yaw) in degrees.
    """
    # Load image
    image = cv2.imread(image_path)
    if image is None:
        raise ValueError(f"Image at {image_path} could not be loaded.")

    # Get actual image dimensions from the loaded image
    actual_height, actual_width = image.shape[:2]

    # Get focal length (in mm) and digital zoom ratio from EXIF
    focal_mm = get_exif_focal_length(image_path)
    if focal_mm is None or focal_mm <= 0.0:
        raise ValueError(f"Could not obtain a valid focal length from EXIF for {image_path}.")
    digital_zoom_ratio = get_exif_digital_zoom_ratio(image_path)

    # Load intrinsic parameters from JSON (ccd width, etc.)
    mm_per_pixel, ccdWidthPixels, ccdHeightPixels = load_intrinsics(json_path)
    if ccdWidthPixels is None or mm_per_pixel is None:
        raise ValueError(f"Intrinsic parameters missing in {json_path}.")

    # Compute scale ratio:
    # If the input image is scaled down relative to the original sensor size (CCD width),
    # adjust by the digital zoom ratio.
    scale_ratio = (actual_width * digital_zoom_ratio) / ccdWidthPixels

    # Compute effective focal length in pixel units.
    focal_pixels = (focal_mm / mm_per_pixel) * scale_ratio

    # Detect chessboard and compute its center
    chess_center = find_chessboard_center(image, pattern_size)

    # Assume the principal point is at the center of the full CCD resolution (from JSON)
    image_center = np.array([ccdWidthPixels / 2.0, ccdHeightPixels / 2.0])

    # Compute offsets (in pixels) from the principal point
    # dx corresponds to horizontal (yaw) and dy to vertical (pitch)
    offset = chess_center - image_center
    dx, dy = offset[0], offset[1]

    # Calculate angles (in degrees)
    yaw = compute_angle(dx, focal_pixels)
    pitch = compute_angle(dy, focal_pixels)

    return pitch, yaw

def parse_arguments():
    parser = argparse.ArgumentParser(
        description="Compute pitch and yaw offset between two cameras using a chessboard calibration pattern.",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter
    )
    parser.add_argument("--image1", required=True, help="Path to the reference (wide-angle) image.")
    parser.add_argument("--image2", required=True, help="Path to the second (telephoto) image.")
    parser.add_argument("--json1", required=True, help="Path to the JSON file with intrinsic parameters for image1.")
    parser.add_argument("--json2", required=True, help="Path to the JSON file with intrinsic parameters for image2.")
    parser.add_argument("--square_size", type=float, default=100, help="Size of one chessboard square (mm).")
    parser.add_argument("--num_rows", type=int, default=9, help="Number of rows (squares) on the chessboard.")
    parser.add_argument("--num_cols", type=int, default=12, help="Number of columns (squares) on the chessboard.")
    return parser.parse_args()

def main():
    args = parse_arguments()

    # OpenCV expects the pattern size as number of inner corners.
    # For a chessboard with num_rows squares there are (num_rows - 1) inner corners.
    pattern_size = (args.num_cols - 1, args.num_rows - 1)

    try:
        # Process reference image (camera 1)
        pitch1, yaw1 = process_image(args.image1, args.json1, pattern_size)
        print(f"Reference Camera (Image1): pitch = {pitch1:.3f}°, yaw = {yaw1:.3f}°")

        # Process second image (camera 2)
        pitch2, yaw2 = process_image(args.image2, args.json2, pattern_size)
        print(f"Telephoto Camera (Image2): pitch = {pitch2:.3f}°, yaw = {yaw2:.3f}°")

        # Compute the offset between camera 2 and camera 1.
        # This is the misalignment (pitch and yaw offset) of the second camera relative to the first.
        pitch_offset = pitch2 - pitch1
        yaw_offset = yaw2 - yaw1
        print("\nRelative Offset (Telephoto vs. Reference):")
        print(f"Pitch Offset: {pitch_offset:.3f}°")
        print(f"Yaw Offset:   {yaw_offset:.3f}°")
    except Exception as e:
        print("Error:", e)

if __name__ == "__main__":
    main()
