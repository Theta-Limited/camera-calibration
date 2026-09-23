# Calibration technical reference

For setup, taking photos, and running a calibration, start with the [README](./README.md). This optional reference covers the output format, fisheye conversion, diagnostics, and updating older calibration files.

## Command-line reference

| Argument | Meaning |
| --- | --- |
| `--image_dir` | Folder containing calibration images; defaults to the current working directory. |
| `--square_size` | Required: the measured side length of one printed square, in millimeters. |
| `--num_rows`, `--num_cols` | Required: number of rows and columns of squares, not internal corners. |
| `--lens_type` | `perspective` (default) or `fisheye`. |
| `--make`, `--model` | Camera manufacturer and model. Explicit values override image EXIF metadata. |
| `--focal_length` | Camera focal length in millimeters. An explicit value overrides image EXIF metadata. |
| `--drone_comment` | Optional description to include in the JSON entry. |

The script prompts for missing camera metadata and for an optional comment. To see the command-line help, run `python3 camera-calibration.py --help`.

## Output files and JSON format
The script writes the following files in the current working directory. Archive them before another run, which replaces files with the same names:

- `makeMODEL.json`: an entry for the [droneModels.json](https://github.com/Theta-Limited/DroneModels) database, using the camera make and model from EXIF metadata or your input. The same JSON is printed in the terminal.
- `calibration_data.npz`: a NumPy archive containing the original OpenCV camera matrix (`matrix`), distortion coefficients (`distortion`), lens type (`lens_type`), and calibration RMS (`reprojection_error`). Fisheye exports also include converted parameters with a `dronemodels_` prefix, such as `dronemodels_centerX`, and conversion diagnostics with a `fisheye_` prefix. Keep this file with its matching JSON so the original calibration can be inspected or converted again. The JSON records the image dimensions; the NPZ does not.
- `calibration_data.csv`: readable calibration values, plus the converted parameters and conversion diagnostics for a fisheye calibration. These are also printed in the terminal.

For example, here is a perspective JSON entry for a DJI Mini 3 Pro:
```JSON
    {
      "makeModel": "djiFC3582",
      "isThermal": false,
      "ccdWidthMMPerPixel": "0.0023883764/1.0",
      "ccdHeightMMPerPixel": "0.002379536/1.0",
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

For `fisheye` calibration, the JSON uses the PIX4D fields expected by OpenAthena. The following is an **illustrative ideal equidistant camera**, with OpenCV `fx = fy = 2000` pixels, zero OpenCV distortion coefficients, a 3 mm focal length, and principal point `(1990, 1510)`. It is not a measured camera calibration:
```JSON
    {
      "makeModel": "exampleFISHEYE",
      "isThermal": false,
      "ccdWidthMMPerPixel": "0.0015/1.0",
      "ccdHeightMMPerPixel": "0.0015/1.0",
      "widthPixels": 4000,
      "heightPixels": 3000,
      "lensType": "fisheye",
      "poly0": 0.0,
      "poly1": 1.0,
      "poly2": 0.0,
      "poly3": 0.0,
      "poly4": 0.0,
      "c": 3141.592653589793,
      "d": 0.0,
      "e": 0.0,
      "f": 3141.592653589793,
      "centerX": 1990.0,
      "centerY": 1510.0
    }
```

## Fisheye equations and units

Let `alpha` be the ray's angle from the optical axis in radians, and let `(nx, ny)` be its unit direction in the image plane. OpenCV's radial function is

```text
t(alpha) = alpha * (1 + k1*alpha² + k2*alpha⁴ + k3*alpha⁶ + k4*alpha⁸)
```

Here `k1` through `k4` are the four coefficients returned by `cv2.fisheye.calibrate`. See the [OpenCV fisheye camera model](https://docs.opencv.org/4.x/db/d58/group__calib3d__fisheye.html).

OpenAthena uses the [PIX4D fisheye equations](https://support.pix4d.com/hc/en-us/articles/202559089), with a **normalized angle** `q`, rather than radians as the polynomial argument:

```text
s = pi / 2
q = alpha / s
P(q) = q + poly2*q² + poly3*q³ + poly4*q⁴

[pixelX - centerX] = [c d] [P(q) * nx]
[pixelY - centerY]   [e f] [P(q) * ny]
```

The exporter fixes `poly0 = 0` and `poly1 = 1`, and fits `P(q)` to `t(s*q) / s` using 200 evenly spaced angles. The fit is constrained to match the source radius at the maximum fitted angle, so approximation error does not remove the outermost required radius from the supported domain. The affine matrix is `s * K[:2, :2]`, where `K` is the original OpenCV camera matrix. Thus `c = s*fx`, `d = s*K[0,1]`, `e = s*K[1,0]`, and `f = s*fy`. For an ordinary OpenCV camera matrix, `e` is zero. Nonzero skew is retained in `d`.

The polynomial's argument, result, and coefficients are dimensionless. The affine coefficients and `centerX = K[0,2]`, `centerY = K[1,2]` are measured in pixels at `widthPixels` by `heightPixels`. The principal point uses the OpenCV top-left origin, with X increasing right and Y increasing down; it is an absolute image position, not an offset from the image center. The exporter preserves these axes for OpenAthena. The script reads the native image raster without applying EXIF display rotation and rejects mixed image dimensions.

`centerX` and `centerY` are optional in OpenAthena: when absent, it assumes the image center, `(widthPixels / 2, heightPixels / 2)`. Calibration can reveal a different principal point, so the exporter includes the measured values to preserve the fitted model.

The `ccdWidthMMPerPixel` and `ccdHeightMMPerPixel` fields retain their existing definitions, `focal_length / fx` and `focal_length / fy`. They do not receive the `pi/2` scale factor. The script still requests a focal length in millimeters for these fields; OpenAthena's corrected fisheye ray calculation uses the pixel-space affine matrix directly.

Even when all four OpenCV distortion coefficients are zero, a fisheye camera follows an equidistant projection, not a perspective projection. Its exported `c` and `f` must still be `pi/2` times the OpenCV focal scales. When only `k1` is nonzero, the conversion is exact: `poly2 = poly4 = 0`, `poly3 = k1*(pi/2)²`. Otherwise the ninth-degree OpenCV model generally cannot be represented exactly by a quartic; the exporter fits an approximation.

## Fisheye fit range and diagnostics

The converter estimates the required angular range from the image's corner radii after undoing the full OpenCV affine matrix. It restricts inversion to the positive-slope radial branch connected to the optical axis and to the front hemisphere (`0 <= alpha <= pi/2`). If the source polynomial reaches a stationary point or folds before it can cover the required range, export fails. Corners beyond the front hemisphere are allowed, but are flagged as outside the fit. Such a corner can be part of a rectangular raster without being part of the usable fisheye image circle. Export also fails if the fitted quartic's slope is not strictly positive throughout the fit range. This check does not establish validity beyond that range.

Review the reported fit range, supported domain, and conversion errors. The two types of error answer different questions:

- **Calibration RMS**, in pixels, measures how well the fitted OpenCV model reproduces the observed chessboard corners.
- **Conversion residuals** compare the exported PIX4D approximation with that OpenCV model across the conversion range. They measure the additional approximation error introduced by the export, not agreement with measured scene geometry.

The conversion diagnostics are printed in the terminal and CSV, and saved in the NPZ with the `fisheye_` prefix:

| Diagnostic | Meaning |
| --- | --- |
| `fit_max_angle_deg` | Maximum fitted angle from the optical axis, in degrees. |
| `max_pixel_error_bound`, `rms_pixel_error_bound` | Maximum and RMS radial approximation errors converted to pixel error bounds using the largest singular value of the affine matrix. These bound error for any azimuth at the sampled angles. |
| `max_ray_error_deg`, `rms_ray_error_deg` | Maximum and RMS angular differences obtained by projecting with the source model and inverting the exported model, in degrees. |
| `image_corners_within_fit` | Whether all four raster corners fall within the fitted domain. A false value means some image pixels lack a supported front-hemisphere ray. |
| `sample_count` | Number of diagnostic angles, currently 4097, including both endpoints. |

These diagnostics use uniformly spaced angles from zero through `fit_max_angle_deg`. Their RMS values weight those angles equally, rather than weighting chessboard observations or image pixels. They are sampled diagnostics, not continuous error guarantees. They describe the export's fidelity to the OpenCV model; they do not measure ground-truth ray accuracy.

An accurately fitted polynomial is not evidence that the original calibration is accurate outside the part of the image covered by the chessboard observations. Near a radial turning point, small pixel errors can also produce much larger angular errors. Do not use unsupported corners or extrapolate beyond the reported range. OpenAthena can enforce its mathematical inverse domain, but the DroneModels entry does not store the calibration observations or their coverage.

For resized images, the affine coefficients and principal point must be transformed consistently with the image coordinates. A crop additionally shifts the principal point by the crop offset; changing only `widthPixels` and `heightPixels` does not describe a crop. Keep the exported dimensions tied to the images actually calibrated. Validate a calibration with independent image measurements and surveyed targets before drawing conclusions about terrain-raycast accuracy.

## Updating files from older versions of this script

Older fisheye exports fitted the polynomial in radians, copied the unscaled OpenCV affine matrix, and omitted the principal point. They are incompatible with the corrected PIX4D interpretation. Prefer rerunning this script on the original calibration images, which also recomputes the fit range and diagnostics. If retaining a previous OpenCV solution, its camera matrix and coefficients can be recovered from `calibration_data.npz` and passed to `convert_opencv_fisheye_to_dronemodels` with the original image dimensions.

For example, save the old JSON as `old-fisheye.json` alongside its matching `calibration_data.npz`, then run this Python code from the repository directory. It refits from the original full-precision OpenCV solution, prints conversion diagnostics, and writes a separate file:

```python
import json
from pathlib import Path
import runpy

import numpy as np

calibration = runpy.run_path("camera-calibration.py")
entry = json.loads(Path("old-fisheye.json").read_text())
with np.load("calibration_data.npz", allow_pickle=False) as saved:
    if entry["lensType"] != "fisheye" or saved["lens_type"].item() != "fisheye":
        raise ValueError("Both files must describe the same fisheye calibration")
    matrix = saved["matrix"]
    distortion = saved["distortion"]

width, height = entry["widthPixels"], entry["heightPixels"]
params = calibration["convert_opencv_fisheye_to_dronemodels"](
    matrix, distortion, width, height
)
diagnostics = calibration["fisheye_conversion_diagnostics"](
    matrix, distortion, width, height, params
)
print(json.dumps(diagnostics, indent=4))
entry.update(params)
Path("corrected-fisheye.json").write_text(json.dumps(entry, indent=4) + "\n")
```

The NPZ does not record the camera identity or image dimensions; ensure the files belong to the same calibration. Existing `corrected-fisheye.json` files are replaced by this example.

For an export known to have been produced by the old radians-based converter, the following change of variables preserves its existing quartic approximation:

```text
s = pi / 2
new_poly2 = old_poly2 * s
new_poly3 = old_poly3 * s²
new_poly4 = old_poly4 * s³
new_c = old_c * s
new_d = old_d * s
new_e = old_e * s
new_f = old_f * s
centerX = original_OpenCV_matrix[0,2]
centerY = original_OpenCV_matrix[1,2]
```

Keep `poly0 = 0`, `poly1 = 1`, dimensions, and the CCD-per-pixel fields unchanged. Recover the actual principal point from the original NPZ or CSV; the omitted values cannot be recovered from the old JSON alone. This rescaling repairs the units of the old approximation, but does not correct a poor fit or an invalid fit range. Do not apply it to a file already using PIX4D conventions, including existing DroneModels entries whose provenance is different.

## Tests

After installing the requirements, run the offline regression tests from this directory:

```bash
python3 -m unittest discover -s tests -v
```

