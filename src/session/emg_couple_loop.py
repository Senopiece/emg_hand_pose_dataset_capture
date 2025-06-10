import multiprocessing
import multiprocessing.synchronize
import time
from typing import List, Set, Tuple
import cv2
import numpy as np
from session.dataset_writer import W
from session.emg_device import EmgDevice
from webcam_hand_triangulation.capture.fps_counter import FPSCounter
from webcam_hand_triangulation.capture.finalizable_queue import FinalizableQueue
from webcam_hand_triangulation.capture.wrapped import Wrapped


def emg_coupling_loop(
    bytes_per_channel: int,
    channels: int,
    hide_channels: Set[int],
    payload_bits: int,
    serial_port: str,
    stop_event: multiprocessing.synchronize.Event,
    last_frame: List[Wrapped[Tuple[np.ndarray, int] | None]],
    coupled_emg_frames_queue: FinalizableQueue,
):
    # Create mask for channels to keep
    keep_channels = [i for i in range(channels) if i not in hide_channels]

    # Wait until at least one frame is available from all cameras
    while True:
        if all(a_last_frame.get() is not None for a_last_frame in last_frame):
            break
        time.sleep(0.1)

    fps_counter = FPSCounter()
    index = 0

    with EmgDevice(
        bytes_per_channel,
        payload_bits,
        channels,
        serial_port,
    ) as emg_capture:
        emg_capture.position_head()

        while True:
            if stop_event.is_set():
                break

            try:
                signal_chunk = emg_capture.read_packets(W)
                signal_chunk = signal_chunk[:, keep_channels]
            except Exception as e:
                print(">>> Error reading EMG:", e)
                continue

            frames = []
            for frame in last_frame:
                v = frame.get()
                assert v is not None
                frame, fps = v
                frames.append((cv2.flip(frame, 1), fps))

            # Send coupled postfactum frames + signal
            coupled_emg_frames_queue.put(
                (
                    index,
                    frames,
                    fps_counter.get_fps(),
                    signal_chunk,
                )
            )
            index += 1
            fps_counter.count()

        coupled_emg_frames_queue.finalize()
