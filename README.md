# Camera Calibration Script

## Overview
This Python script is designed for camera calibration using a chessboard pattern. It computes the camera matrix and distortion coefficients, which are essential for correcting lens distortion and understanding the camera's intrinsic parameters.

Included in this repository is the file [36in_x_48in_9col_12row_100mm_cv_poster.pdf](./36in_x_48in_9col_12row_100mm_cv_poster.pdf), which contains a chessboard pattern with a square size of 100mm sized to print on a 36" x 48" poster. It is recommended to turn this poster sideways for taking pictures with the camera you wish to calibrate.

![Picture taken by Mini3Pro of the chessboard pattern printed on poster paper](./DJI_0218.JPG)

The number of calibration images you use and the way you take them are crucial for achieving accurate camera calibration. Here's some guidance:

## Taking Calibration Images

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

5. **Use High-Quality Images**:
   - Use the highest resolution possible for your camera. Avoid blurry or low-resolution images.

6. **Ensure the Entire Chessboard is Visible**:
   - The whole chessboard pattern should be in the frame for each image.

7. **Consistent Chessboard Orientation**:
   - While varying angles and distances, keep the orientation of the chessboard consistent (e.g., always keep the same corner or side of the chessboard in the same relative position).

8. **Use a Stable Chessboard Setup**:
   - The chessboard should be flat and rigid. Any bending or flexing can distort the pattern and affect accuracy.

9. **Document Environmental Conditions**:
   - If possible, note the environmental conditions like lighting, because changes in these conditions can affect the camera’s intrinsic parameters.

### Post-processing the Images

- **Check for Clarity**: Before running the calibration, visually inspect the images to ensure that the chessboard corners are clear and distinguishable.
- **Automated Corner Detection**: You might want to run a script to check if the corners are being correctly detected in all your images before proceeding to the full calibration.

## Installation

### Requirements
- Python 3.x
- numpy
- opencv-python

Clone this project using git (or download as a zip file and extract it)
```
git clone https://github.com/Theta-Limited/camera-calibration.git
```

Enter the project directory, then install the necessary libraries using:
```bash
pip install -r requirements.txt
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
- Standard output (console).
- A CSV file named `calibration_data.csv`.
- A NumPy `.npz` file named `calibration_data.npz`.

## Interpreting and Using These Values

- **Camera Calibration**: These parameters are used to understand the camera's internal characteristics, such as how it maps 3D points in the world onto the 2D image.
- **Image Undistortion**: You can use these parameters to correct for lens distortion in images captured by this camera. OpenCV provides functions like `cv2.undistort` to straighten the images based on these parameters.

### Camera Matrix

The camera matrix, often denoted as `mtx` in the script, is a 3x3 matrix that contains intrinsic parameters of the camera. It looks something like this:

|     |     |     |
| --- | --- | --- |
| f_x |  0  | c_x |
|  0  | f_y | c_y |
|  0  |  0  |  1  |

- **\( f_x, f_y \)**: These are the focal lengths of the camera expressed in pixel units. They represent the scaling of image coordinates in the x and y axes.
- **\( c_x, c_y \)**: These are the coordinates of the principal point, which is the intersection of the optical axis with the image plane. It is often close to the image center.

### Distortion Coefficients

The distortion coefficients (`dist` in the script) account for the radial and tangential lens distortion. This array typically has five components: (k_1, k_2, p_1, p_2, k_3).

- **\( k_1, k_2, k_3 \)**: These are radial distortion coefficients. Radial distortion causes straight lines to appear curved. It's more pronounced at the edges of the image and is a function of the distance from the center of the image.
- **\( p_1, p_2 \)**: These are tangential distortion coefficients. Tangential distortion occurs because the lens is not perfectly parallel to the image plane. It causes the image to appear tilted so that some areas in the image may look nearer than they are.

### Conversion of these values to [droneModels.json](https://github.com/Theta-Limited/DroneModels) format

#### Description of droneModels.json file format

OpenAthena™ products store information on many drone cameras in a file droneModels.json, maintained here:


[https://github.com/Theta-Limited/DroneModels](https://github.com/Theta-Limited/DroneModels)


Here is an example of a JSONObject for a particular make/model of drone:
```JSON
    {
      "makeModel": "djiFC3582",
      "isThermal": false,
      "ccdWidthMMPerPixel": "0.0023883764",
      "ccdHeightMMPerPixel": "0.002379536",
      "widthPixels": 4032,
      "heightPixels": 3024,
      "comment": "DJI Mini 3 Pro",
      "lensType": "perspective",
      "radialR1": 0.11416479395258083,
      "radialR2": -0.26230384345579,
      "radialR3": 0.22906477778853437,
      "tangentialT1": -0.004601610146546272,
      "tangentialT2": 0.0026292475166887
    }
```


In this object:
* `makeModel` represents the EXIF make and model String merged together, a unique String representing a specific drone model. The EXIF make String is made all lowercase, while the EXIF model String is made all uppercase.
* `focalLength` is an optional parameter which represents the distance between the focal point (the part of the lens that all light passes through) and the CCD/CMOS sensor which digitizes incoming light. This is only provided in rare cases when such data is unavailable in a camera model's image EXIF data.
* `isThermal` represents whether this particular JSONObject represents the thermal or color camera of a given drone. This is used to solve name collisions in the `makeModel` String that occur when both the thermal and color cameras of a drone report the same model name despite having different parameters.
* `ccdWidthMMPerPixel` represents the width of each pixel (in millimeters) of the drone camera's CCD/CMOS sensor which digitizes incoming light
* `ccdHeightMMPerPixel` represents the height of each pixel (in millimeters) of the drone camera's CCD/CMOS sensor which digitizes incoming light
* `widthPixels` represents the number of pixels in the width of a camera's uncropped, full resolution image
* `heightPixels` represents the number of pixels in the height of a camera's uncropped, full resolution image
* `comment` represents a comment from the author of the object which gives insight into the camera's corresponding drone model and properties
* `lensType` is one of two values: `perspective` or `fisheye`, used for applying the correct correction equations for distortion of incoming light by the camera lens. Read below for further details
* `radialR1` represents the first radial distortion coefficient for the camera's lens
* `radialR2` represents the second radial distortion coefficient for the camera's lens
* `radialR3` represents the third radial distortion coefficient for the camera's lens
* `tangentialT1` represents the first tangential distortion coefficient for the camera's lens
* `tangentialT2` represents the second tangential distortion coefficient for the camera's lens

#### Conversion of calibration_data.csv produced by this script into droneModels.json format

Output from this script in the filename `calibration_data.csv` will appear as such:

```
Camera Matrix
2805.2529685860704,0.0,2034.627323877116
0.0,2815.674941815058,1445.6706286054327
0.0,0.0,1.0
Distortion Coefficients
0.11416479395258083,-0.26230384345579,-0.004601610146546272,0.0026292475166887,0.22906477778853437
```

**\( f_x \)** in this example is 2805.25...

**\( f_y \)** in this example is 2815.67...

To obtain the values `ccdWidthMMPerPixel` and `ccdHeightMMPerPixel` for droneModels.json, use the following formulas:

ccdWidthMMPerPixel = focal_length / **\( f_x \)**


ccdHeightMMPerPixel = focal_length / **\( f_y \)**

Where `focal_length` is the focal length of the camera in millimeters, either as a known fixed value for the camera or obtainable from the tag Exif.Photo.FocalLength using this command:
```bash
exiv2 -P kt FILENAME.JPG
```

`radialR1` is the first value in Distortion Coefficients (0.114... in this example)

`radialR2` is the second value in Distortion Coefficients (-0.262... in this example)

`tangentialT1` is the third value in Distortion Coefficients (-0.004... in this example)

`tangentialT2` is the fouth value in Distortion Coefficients (0.002... in this example)

`radialR3` is the fifth value in Distortion Coefficients (0.229... in this example)
