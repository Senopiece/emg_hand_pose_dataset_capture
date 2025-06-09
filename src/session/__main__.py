import argparse
import multiprocessing
import os
import sys
import threading
from typing import Dict, List, Set, Tuple
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

from .rec_window_loop import rec_window_loop
from .signal_window_loop import signal_window_loop
from .recording_loop import recording_loop
from .processing_loop import processing_loop
from .emg_couple_loop import emg_coupling_loop


def main(
    # datasets
    datasets_path: str,
    # triangulation
    cameras_params: Dict[int, CameraParams],
    desired_window_size: Tuple[int, int],
    triangulation_workers_num: int,
    display_cameras: bool,
    draw_origin_landmarks: bool,
    # emg
    serial_port: str,
    channels_num: int,
    hide_channels: Set[int],
):
    set_high_priority()

    # Validate hide_channels
    if not all(0 <= ch < channels_num for ch in hide_channels):
        invalid_channels = [ch for ch in hide_channels if ch >= channels_num or ch < 0]
        raise ValueError(
            f"Invalid channels in hide_channels: {invalid_channels}. All channels must be in range [0, {channels_num})"
        )

    # Check camera parameters
    if len(cameras_params) < 2:
        print("Need at least two cameras with calibration data.")
        return

    # Ensure the dataset path exists
    if not os.path.exists(datasets_path):
        create = (
            input(
                f"The dataset path '{datasets_path}' does not exist. Do you want to create it? (y/n): "
            )
            .strip()
            .lower()
        )
        if create == "y":
            os.makedirs(datasets_path)
        else:
            print("Dataset path creation declined. Exiting.")
            return 1

    # Count the number of files in the datasets folder
    curr_dataset_id = len(os.listdir(datasets_path))

    # Define the current dataset file path
    curr_dataset_filepath = os.path.join(datasets_path, str(curr_dataset_id) + ".zip")
    if os.path.exists(curr_dataset_filepath):
        print(f"{os.path.normpath(curr_dataset_filepath)} already exists.")
        return 1

    ##########################################################################################
    ###                                     Pipeline                                       ###
    ##########################################################################################

    with multiprocessing.Manager() as manager:
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
            for my_last_frame, (idx, cam_param) in zip(
                last_frame, cameras_params.items()
            )
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
                hide_channels,
                12,
                serial_port,
                cams_stop_event,
                last_frame,
                emg_frames_queue,
            ),
            daemon=True,
        )
        coupling_worker.start()

        # Processing workers
        processing_results = ThreadFinalizableQueue()
        processed_queues = (
            [ThreadFinalizableQueue() for _ in cameras_ids] if display_cameras else None
        )
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
        record_control_channel = ProcessFinalizableQueue()
        hand_angles_queue = ProcessFinalizableQueue()
        signal_chunks_queue = ProcessFinalizableQueue()
        recorder = threading.Thread(
            target=recording_loop,
            args=(
                manager,
                record_control_channel,
                curr_dataset_filepath,
                ordered_processing_results,
                hand_angles_queue,
                signal_chunks_queue,
            ),
            daemon=True,
        )
        recorder.start()

        # Visualize signal
        signal_visualizer = multiprocessing.Process(
            target=signal_window_loop,
            args=(
                "EMG",
                channels_num - len(hide_channels),
                cams_stop_event,
                signal_chunks_queue,
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
                hand_angles_queue,
            ),
            daemon=True,
        )
        hand_3d_visualizer.start()

        # A save asking worker
        rec_window = multiprocessing.Process(
            target=rec_window_loop,
            args=(
                cams_stop_event,
                record_control_channel,
            ),
            daemon=True,
        )
        rec_window.start()

        # Sort processing workers output
        ordered_processed_queues = None
        display_ordering_loops = None
        if processed_queues is not None:
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
                for in_queue, out_queue in zip(
                    processed_queues, ordered_processed_queues
                )
            ]
            for process in display_ordering_loops:
                process.start()

        # Displaying loops
        display_loops = None
        if ordered_processed_queues is not None:
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
        if processed_queues is not None:
            for queue in processed_queues:
                queue.finalize()

        results_sorter.join()
        if display_ordering_loops is not None:
            for worker in display_ordering_loops:
                worker.join()

        recorder.join()
        hand_angles_queue.finalize()
        signal_chunks_queue.finalize()
        record_control_channel.finalize()

        signal_visualizer.join()
        rec_window.join()

        hand_3d_visualizer.join()
        if display_loops is not None:
            for worker in display_loops:
                worker.join()

        cv2.destroyAllWindows()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Capture a dataset session")
    parser.add_argument(
        "-d",
        "--datasets_path",
        type=str,
        default="datasets",
        help="Path to where to append datasets",
    )
    parser.add_argument(
        "--channels",
        type=int,
        default=6,
        help="Number of channels the EMG device is expected to send",
    )
    parser.add_argument(
        "--hide_channels",
        type=lambda x: {int(i) for i in x.split(",")} if x else set(),
        default="",
        help="Comma-separated list of EMG channels to hide (e.g. '0,1,3')",
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
        "-dc",
        "--display_cameras",
        help="Preview what cameras are seeing",
        action="store_true",
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
            datasets_path=args.datasets_path,
            cameras_params=load_cameras_parameters(args.cfile),
            desired_window_size=desired_window_size,
            triangulation_workers_num=args.workers,
            display_cameras=args.display_cameras,
            draw_origin_landmarks=args.origin_landmarks,
            serial_port=args.port,
            channels_num=args.channels,
            hide_channels=args.hide_channels,
        )
    )
