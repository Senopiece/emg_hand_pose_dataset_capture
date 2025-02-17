import argparse
import os
import sys
from typing import Dict, Tuple

from webcam_hand_triangulation.capture.models import CameraParams
from webcam_hand_triangulation.capture.cam_conf import load_cameras_parameters

curr_session_id = 0
curr_record_id = 0


def main(
    # dataset
    dataset_path: str,
    # triangulation
    cameras_params: Dict[int, CameraParams],
    couple_fps: int,
    desired_window_size: Tuple[int, int],
    triangulation_workers: int,
    draw_origin_landmarks: bool,
    # emg
    serial_port: str,
    baud_rate: int,
):
    # Ensure the dataset path exists
    if not os.path.exists(dataset_path):
        create = (
            input(
                f"The dataset path '{dataset_path}' does not exist. Do you want to create it? (y/n): "
            )
            .strip()
            .lower()
        )
        if create == "y":
            os.makedirs(dataset_path)
        else:
            print("Dataset path creation declined. Exiting.")
            return 1

    # Define the sessions folder path
    sessions_folder = os.path.join(dataset_path, "sessions")
    if not os.path.exists(sessions_folder):
        os.makedirs(sessions_folder)

    # Count the number of files in the sessions folder
    global curr_session_id
    curr_session_id = len(os.listdir(sessions_folder))

    # Define the current session folder path
    curr_session_folder = os.path.join(sessions_folder, str(curr_session_id))
    if os.path.exists(curr_session_folder):
        print(f"{os.path.normpath(curr_session_folder)} already exists.")
        return 1
    os.makedirs(curr_session_folder)

    # Continue with the rest of your code...


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Capture a dataset session")
    parser.add_argument(
        "-d",
        "--dataset_path",
        type=str,
        help="Path the dataset path to store to",
        required=True,
    )
    parser.add_argument(
        "--cfile",
        type=str,
        default="cameras.calib.json5",
        help="Path to the cameras calibration file",
    )
    parser.add_argument(
        "--window_size",
        type=str,
        default="448x336",
        help="Size of a preview window",
    )
    parser.add_argument(
        "--workers",
        type=int,
        default=8,
        help="Size of triangulation workers pool",
    )
    parser.add_argument(
        "--couple_fps",
        type=int,
        default=30,
        help="Rate at which frames from cameras will be coupled",
    )
    parser.add_argument(
        "-ol", "--origin_landmarks", help="Draw origin landmarks", action="store_true"
    )
    parser.add_argument(
        "-p",
        "--port",
        type=str,
        required=True,
        help="Serial port name or 'synthetic' for synthetic data",
    )
    parser.add_argument("-b", "--baud", type=int, default=256000)
    args = parser.parse_args()

    desired_window_size = tuple(map(int, args.window_size.split("x")))
    if len(desired_window_size) != 2:
        print("Error: window_size must be a AxB value", file=sys.stderr)
        sys.exit(1)

    sys.exit(
        main(
            dataset_path=args.dataset_path,
            cameras_params=load_cameras_parameters(args.cfile),
            desired_window_size=desired_window_size,
            triangulation_workers=args.workers,
            couple_fps=args.couple_fps,
            draw_origin_landmarks=args.origin_landmarks,
            serial_port=args.port,
            baud_rate=args.baud,
        )
    )
