import multiprocessing
import multiprocessing.synchronize
import time
from typing import List, Tuple
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
    payload_bits: int,
    serial_port: str,
    stop_event: multiprocessing.synchronize.Event,
    last_frame: List[Wrapped[Tuple[np.ndarray, int] | None]],
    coupled_emg_frames_queue: FinalizableQueue,
):
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
        blocking=True,
    ) as emg_capture:
        signal_buff = np.ndarray(shape=(0, channels), dtype=np.float32)

        while True:
            if stop_event.is_set():
                break

            err, signal_chunk = emg_capture.read_packets()

            # if signal_chunk.shape[0] != 0:
            #     # Keep it as low as possible
            #     # having > 64 is very bad
            #     print("signal_chunk size: ", signal_chunk.shape[0])

            if err:
                print(">>> Received a corrupted signal chunk!!")

            signal_buff = np.append(signal_buff, signal_chunk, axis=0)

            while signal_buff.shape[0] > W:
                signal_chunk = signal_buff[:W]
                signal_buff = signal_buff[W:]

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
