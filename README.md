TODO: how to setup, add to dataset, where to get a recorded dataset
TODO: howto use, howto install dependencies, arch graph

set PYTHONPATH=C:\Users\shich\Src\thesis\emg_hand_pose_dataset_capture\src\webcam_hand_triangulation
python -m calibrate
python -m capture

set PYTHONPATH=C:\Users\shich\Src\thesis\emg_hand_pose_dataset_capture\src
python -m session -d datasets/dataset1 -p synthetic