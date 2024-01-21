## Extra Info: Interpreting and Using These Values

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