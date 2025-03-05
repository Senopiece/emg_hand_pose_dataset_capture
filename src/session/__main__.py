import argparse
import multiprocessing
import os
import sys
import threading
from typing import Dict, List, Tuple
import numpy as np

os.environ["OPENCV_VIDEOIO_MSMF_ENABLE_HW_TRANSFORMS"] = "0"
import cv2

from webcam_hand_triangulation.capture.display_loop import display_loop
from webcam_hand_triangulation.capture.hand_3d_visualization_loop import (
    hand_3d_visualization_loop,
)
from webcam_hand_triangulation.capture.high_priority import set_high_priority
from webcam_hand_triangulation.capture.landmark_transforms import landmark_transforms
from webcam_hand_triangulation.capture.cap_reading_loop import cap_reading
from webcam_hand_triangulation.capture.finalizable_queue import (
    ProcessFinalizableQueue,
    ThreadFinalizableQueue,
)
from webcam_hand_triangulation.capture.ordering_loop import ordering_loop
from webcam_hand_triangulation.capture.wrapped import Wrapped
from webcam_hand_triangulation.capture.models import CameraParams
from webcam_hand_triangulation.capture.cam_conf import load_cameras_parameters

from .save_session_asker import confirmation_loop
from .signal_window_loop import signal_window_loop
from .requestable_toggle import RequestableToggle
from .recording_loop import recording_loop
from .processing_loop import processing_loop
from .emg_couple_loop import emg_coupling_loop


def main(
    # dataset
    dataset_path: str,
    # triangulation
    cameras_params: Dict[int, CameraParams],
    couple_fps: int,
    desired_window_size: Tuple[int, int],
    triangulation_workers_num: int,
    draw_origin_landmarks: bool,
    # emg
    serial_port: str,
    channels_num: int,
):
    set_high_priority()

    # Check camera parameters
    if len(cameras_params) < 2:
        print("Need at least two cameras with calibration data.")
        return

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
    curr_session_id = len(os.listdir(sessions_folder))

    # Define the current session folder path
    curr_session_folder = os.path.join(sessions_folder, str(curr_session_id))
    if os.path.exists(curr_session_folder):
        print(f"{os.path.normpath(curr_session_folder)} already exists.")
        return 1
    os.makedirs(curr_session_folder)

    ##########################################################################################
    ###                                     Pipeline                                       ###
    ##########################################################################################

    cameras_ids = list(cameras_params.keys())

    # Shared
    cams_stop_event = multiprocessing.Event()
    last_frame: List[Wrapped[Tuple[np.ndarray, int] | None]] = [
        Wrapped() for _ in cameras_ids
    ]

    # Capture cameras
    caps: List[threading.Thread] = [
        threading.Thread(
            target=cap_reading,
            args=(
                idx,
                cams_stop_event,
                my_last_frame,
                cam_param,
            ),
            daemon=True,
        )
        for my_last_frame, (idx, cam_param) in zip(last_frame, cameras_params.items())
    ]
    for process in caps:
        process.start()

    # Couple frames and emg
    emg_frames_queue = ThreadFinalizableQueue()
    coupling_worker = threading.Thread(
        target=emg_coupling_loop,
        args=(
            2,
            channels_num,
            serial_port,
            couple_fps,
            cams_stop_event,
            last_frame,
            emg_frames_queue,
        ),
        daemon=True,
    )
    coupling_worker.start()

    # Processing workers
    processing_results = ThreadFinalizableQueue()
    processed_queues = [ThreadFinalizableQueue() for _ in cameras_ids]
    processing_loops_pool = [
        threading.Thread(
            target=processing_loop,
            args=(
                [landmark_transforms[cp.track] for cp in cameras_params.values()],
                draw_origin_landmarks,
                desired_window_size,
                list(cameras_params.values()),
                emg_frames_queue,
                processing_results,
                processed_queues,
            ),
            daemon=True,
        )
        for _ in range(triangulation_workers_num)
    ]
    for process in processing_loops_pool:
        process.start()

    # Sort processing results
    ordered_processing_results = ThreadFinalizableQueue()
    results_sorter = threading.Thread(
        target=ordering_loop,
        args=(
            processing_results,
            ordered_processing_results,
        ),
        daemon=True,
    )
    results_sorter.start()

    # Record and decouple
    record_toggle = RequestableToggle()
    save_record_question_channel = ProcessFinalizableQueue()
    hand_points_queue = ProcessFinalizableQueue()
    signal_chunks_queue = ProcessFinalizableQueue()
    recorder = threading.Thread(
        target=recording_loop,
        args=(
            record_toggle,
            save_record_question_channel,
            curr_session_folder,
            channels_num,
            ordered_processing_results,
            hand_points_queue,
            signal_chunks_queue,
        ),
        daemon=True,
    )
    recorder.start()

    # Visualize signal
    signal_visualizer = multiprocessing.Process(
        target=signal_window_loop,
        args=(
            "Signal",
            channels_num,
            0,
            4096,
            cams_stop_event,
            signal_chunks_queue,
            record_toggle,
        ),
        daemon=True,
    )
    signal_visualizer.start()

    # Visualize 3d hand
    hand_3d_visualizer = multiprocessing.Process(
        target=hand_3d_visualization_loop,
        args=(
            desired_window_size,
            cams_stop_event,
            hand_points_queue,
        ),
        daemon=True,
    )
    hand_3d_visualizer.start()

    # A save asking worker
    confirmator = multiprocessing.Process(
        target=confirmation_loop,
        args=(save_record_question_channel,),
        daemon=True,
    )
    confirmator.start()

    # Sort processing workers output
    ordered_processed_queues = [ProcessFinalizableQueue() for _ in cameras_ids]
    display_ordering_loops = [
        threading.Thread(
            target=ordering_loop,
            args=(
                in_queue,
                out_queue,
            ),
            daemon=True,
        )
        for in_queue, out_queue in zip(processed_queues, ordered_processed_queues)
    ]
    for process in display_ordering_loops:
        process.start()

    # Displaying loops
    display_loops = [
        multiprocessing.Process(
            target=display_loop,
            args=(
                idx,
                cams_stop_event,
                frame_queue,
            ),
            daemon=True,
        )
        for idx, frame_queue in zip(cameras_ids, ordered_processed_queues)
    ]
    for process in display_loops:
        process.start()

    # Wait for a stop signal
    cams_stop_event.wait()

    # Free resources
    print("Freeing resources...")
    coupling_worker.join()

    for worker in caps:
        worker.join()

    coupling_worker.join()

    for worker in processing_loops_pool:
        worker.join()

    processing_results.finalize()
    for queue in processed_queues:
        queue.finalize()

    results_sorter.join()
    for worker in display_ordering_loops:
        worker.join()

    recorder.join()
    hand_points_queue.finalize()
    signal_chunks_queue.finalize()
    save_record_question_channel.finalize()

    signal_visualizer.join()
    confirmator.join()

    hand_3d_visualizer.join()
    for worker in display_loops:
        worker.join()

    cv2.destroyAllWindows()


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
        "--channels",
        type=int,
        default=6,
        help="Number of channels the EMG device is expected to send",
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
            triangulation_workers_num=args.workers,
            couple_fps=args.couple_fps,
            draw_origin_landmarks=args.origin_landmarks,
            serial_port=args.port,
            channels_num=args.channels,
        )
    )
