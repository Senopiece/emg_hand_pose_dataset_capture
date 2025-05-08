## Main Usage Scenario

This repo is for recording hand-motion + emg dataset

> NOTE: using python 3.10

TODO: link to example datasets recorded with it

### 1. Make calibration pattern

See [section 1 of webcam hand triangulation](src/webcam_hand_triangulation/README.md#1-make-calibration-pattern)

### 2. Place cameras and make calibration

See [section 2 of webcam hand triangulation](src/webcam_hand_triangulation/README.md#2-place-cameras-and-make-calibration)

Make `cameras.def.json5` and run all `python -m calibrate` at the root of this repo (e.g. the folder this readme is located)
so that `cameras.calib.json5` will also be generated inside the root folder

Also, to make `python -m calibrate` work properly set
```
export PYTHONPATH=$(pwd)/src/webcam_hand_triangulation
```
at the root of the repo

### 3. Make emg recording hardware

> TODO: ref the repo with emg hardware

Plug in the hardware and determine is's port

### 4. Recording
How to record a dataset
1. Make sure all the hardware is ready - cameras are connected and calibrated and the emg recorder is connected
2. Install [requirements.txt](src/session/requirements.txt) into your venv or global python installation
2. Run `export PYTHONPATH=$(pwd)/src`
3. Run `python -m session -d datasets -p {emg_device_port}/synthetic` from the repository root - this will create a new session folder inside the dataset
4. Hope GUI is intuitive on capturing records - the datasets folder will be fulfilled with the dataset of records you made

TODO: irl example