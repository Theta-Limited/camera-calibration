# Camera Calibration Script

## Overview
This Python script is designed for camera calibration using a chessboard pattern. It computes the camera matrix and distortion coefficients, which are essential for correcting lens distortion and understanding the camera's intrinsic parameters. The script then outputs the calibration data as an entry in [json](https://en.wikipedia.org/wiki/JSON) format suitable for inclusion in OpenAthena's [droneModels.json](https://github.com/Theta-Limited/DroneModels) calibration database.

Included in this repository is the file [36in_x_48in_9col_12row_100mm_cv_poster.pdf](./36in_x_48in_9col_12row_100mm_cv_poster.pdf), which contains a chessboard pattern with a square size of 100mm sized to print on a 36" x 48" poster. It is recommended to turn this poster sideways for taking pictures with the camera you wish to calibrate.

You may also generate a pattern of a different size using this webpage:
https://calib.io/pages/camera-calibration-pattern-generator

Set the Target Type to `Checkerboard` and adjust width, height rows, columns and checker width as needed to fit your print format. Use these new values with the script as described below.

![Picture taken by Mini3Pro of the chessboard pattern printed on poster paper](./DJI_0218.JPG)

## Taking Calibration Images

The number of calibration images you use and the way you take them are crucial for achieving accurate camera calibration. Here's some guidance:

### Number of Calibration Images

- **Minimum Recommended**: At least 10-20 images.
- **Optimal Range**: 20-50 images. More images generally provide better results, but beyond a certain point, the improvement becomes marginal.
- **Variability**: It's not just the number but the variety in the images that matters. More varied images lead to better calibration.

### Tips for Taking Calibration Images

1. **Cover the Entire Field of View**:
   - Ensure that the chessboard is captured from different parts of the camera's field of view in various images. This includes corners and edges.
   - Avoid using only center-focused images.

2. **Vary the Orientation and Angle**:
   - Take pictures from various angles: some tilted up, down, left, right, and some rotated at slight angles.
   - This helps in accurately capturing the camera's lens distortions.

3. **Vary the Distance**:
   - Include shots from different distances – some close-up shots of the chessboard and some from farther away.
   - Ensure the chessboard is clearly visible and occupies a significant portion of the frame in each image.

4. **Avoid Reflections and Shadows**:
   - Ensure consistent lighting and avoid strong shadows or reflections on the chessboard, as these can interfere with corner detection.

5. **Use the full sensor**:
   - Most cameras crop pixels from top and bottom of their 4:3 image sensor to make it fit in widescreen 16:9. Set your drone camera to 4:3 to ensure you get full coverage of the image sensor

6. **Ensure the Entire Chessboard is Visible**:
   - All four corners of the pattern should be in the frame for each image.

7. **Consistent Chessboard Orientation**:
   - While varying angles and distances, keep the orientation of the chessboard consistent (e.g., always keep the same corner or side of the chessboard in the same relative position).

8. **Use a Stable Chessboard Setup**:
   - The chessboard should be flat and rigid. Any bending or flexing can distort the pattern and affect accuracy.

### Post-processing the Images

- **Check for Clarity**: Before running the calibration, visually inspect the images to ensure that the chessboard corners are clear and distinguishable. Delete images that don't meet these standards.

## Installation

### Requirements
- Python 3.x
- numpy
- opencv-python
- Pillow

Clone this project using git (or download as a zip file and extract it)
```
git clone https://github.com/Theta-Limited/camera-calibration.git
```

Enter the project directory, then install the necessary libraries using:
```bash
pip install -r requirements.txt # may be 'pip3' on some systems
```

## Usage
The script can be executed from the command line with the following arguments:
- `--image_dir`: The directory containing calibration images (default is the current working directory if not provided).
- `--square_size`: The size of one square on the chessboard, in millimeters.
- `--num_rows`: The total number of rows of squares on the chessboard (as counted normally).
- `--num_cols`: The total number of columns of squares on the chessboard (as counted normally).

### Command Line Syntax
```bash
python3 camera-calibration.py --image_dir path/to/images --square_size 100 --num_rows 9 --num_cols 12
```

Alternatively, if you do not specify the `--image_dir`, the script will use the current working directory:
```bash
python3 camera-calibration.py --square_size 100 --num_rows 9 --num_cols 12
```

## Important Notes
- **Square Size**: Input the size of the chessboard squares in millimeters.
- **Rows and Columns**: Input the number of rows and columns as you would count them normally on the chessboard. The script internally converts these to the number of corners, as required by OpenCV for calibration.
- **Chessboard Pattern**: Ensure that the entire chessboard is visible in the calibration images, taken from various angles and distances.

## Output
The script outputs the camera matrix and distortion coefficients to:
- Standard output as text in the terminal.
- A file of the name makeMODEL.json, where the camera make and model name are obtained from image EXIF metadata

Both are formatted as a json entry in the same format used in the [droneModels.json](https://github.com/Theta-Limited/DroneModels) database. Please email [support@theta.limited](mailto:support@theta.limited?subject=[GitHub]%20My%20Drone%20Calibration) or create a pull request in the [DroneModels](https://github.com/Theta-Limited/DroneModels) repo to contribute your calibration to the OpenAthena project:

[https://github.com/Theta-Limited/DroneModels](https://github.com/Theta-Limited/DroneModels)