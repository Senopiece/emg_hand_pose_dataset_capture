import multiprocessing
import multiprocessing.synchronize
import time
from typing import List, Tuple
import cv2
import numpy as np
from session.emg_device import EmgDevice
from webcam_hand_triangulation.capture.fps_counter import FPSCounter
from webcam_hand_triangulation.capture.finalizable_queue import FinalizableQueue
from webcam_hand_triangulation.capture.wrapped import Wrapped


def emg_coupling_loop(
    bytes_per_channel: int,
    channels: int,
    serial_port: str,
    couple_fps: int,
    stop_event: multiprocessing.synchronize.Event,
    last_frame: List[Wrapped[Tuple[np.ndarray, int] | None]],
    coupled_emg_frames_queue: FinalizableQueue,
):
    target_frame_interval = 1 / couple_fps

    # Wait until at least one frame is available from all cameras
    while True:
        if all(a_last_frame.get() is not None for a_last_frame in last_frame):
            break
        time.sleep(0.1)

    fps_counter = FPSCounter()
    index = 0

    with EmgDevice(
        bytes_per_channel,
        channels,
        serial_port,
    ) as emg_capture:
        while True:
            start_time = time.time()

            if stop_event.is_set():
                break

            fps_counter.count()

            frames = []
            for frame in last_frame:
                v = frame.get()
                assert v is not None
                frame, fps = v
                frames.append((cv2.flip(frame, 1), fps))

            err, signal_chunk = emg_capture.read_packets()

            if err:
                print(">>> Received a corrupted signal chunk!!")

            # Send coupled frames + signal
            coupled_emg_frames_queue.put(
                (
                    index,
                    frames,
                    fps_counter.get_fps(),
                    signal_chunk,
                )
            )
            index += 1

            # Rate-limit to ~couple_fps FPS
            elapsed_time = time.time() - start_time
            if elapsed_time > target_frame_interval:
                time.sleep(target_frame_interval - elapsed_time)

        coupled_emg_frames_queue.finalize()
