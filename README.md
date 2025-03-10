## Main Usage Scenario

This repo is for recording hand-motion + emg dataset

> NOTE: using python 3.11

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

The structure of the datasets is simplistic:
```
datasets/
  {dataset_name}/
    sessions/
      {N}/
        records/
          {N}.bin
```

Some metadata can be added manually
> for example a .md file in the root of the dataset - describing what hardware was used and some other local assumptions to take about this dataset - like that this dataset was recorded on one person, or that each session is a different person etc...

General assumptions:
1. A record is a realtime capture of simultaneous hand movements and emg - see [the code](src/session/hand_emg_record.py) for more info on format
2. A session is a number of records captured in one flow
3. A dataset contains sessions recorded on the same hardware

How to record a session
1. Make sure all the hardware is ready - cameras are connected and calibrated and the emg recorder is connected
2. Install [requirements.txt](src/session/requirements.txt) into your venv or global python installation
2. Run `export PYTHONPATH=$(pwd)/src`
3. Run `python -m session -d ./datasets/{dataset_name} -p {emg_device_port}` from the repository root - this will create a new session folder inside the dataset
4. Hope GUI is intuitive on capturing records - the session folder will be fulfilled with the records you made

TODO: irl example