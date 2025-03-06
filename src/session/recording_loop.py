from multiprocessing.managers import SyncManager
import os
from typing import List
import numpy as np
from .hand_emg_record import HandEmgRecordWriter
from webcam_hand_triangulation.capture.coupling_loop import FinalizableQueue
from webcam_hand_triangulation.capture.finalizable_queue import EmptyFinalized


def recording_loop(
    manager: SyncManager,
    command_channel: FinalizableQueue,
    base_dir: str,
    num_channels: int,
    processing_results: FinalizableQueue,
    hand_points_fwd: FinalizableQueue,
    signal_fwd: FinalizableQueue,
):
    record_id = 0
    writer = None
    
    stop_action = None # -1 - not set, 1 - save, 0 - cancel
    start_event = manager.Event()
    command_channel.put(start_event)

    while True:
        try:
            hand_points: List[np.ndarray]
            signal_chunk: List[int]
            coupling_fps: int
            debt_size: int
            hand_points, signal_chunk, coupling_fps, debt_size = (
                processing_results.get()
            )
        except EmptyFinalized:
            if writer is not None:
                writer.cancel()
                print("Force shutdown while recording. Record canceled.")
            break

        if stop_action is not None:
            assert start_event is None
            assert writer is not None
            should_save = stop_action.value

            if should_save == -1:
                pass # skip if not yet decided
            else:
                if should_save:
                    writer.save()
                    record_id += 1
                else:
                    writer.cancel()
                writer = None
                stop_action = None

                start_event = manager.Event()
                command_channel.put(start_event)
        
        if start_event is not None and start_event.is_set():
            assert stop_action is None
            assert writer is None

            if len(hand_points) != 0:
                start_event = None
                writer = HandEmgRecordWriter(
                    os.path.join(base_dir, f"{record_id}.bin"), num_channels
                )
                stop_action = manager.Value("b", -1)
                command_channel.put(stop_action)
            else:
                start_event = manager.Event()
                command_channel.put(start_event)
                print("No hand detected. Record start ignored.")

        if writer is not None:
            if len(hand_points) == 0:
                writer.cancel()
                writer = None
                stop_action = None
                start_event = manager.Event()
                command_channel.put(start_event)
                print("No hand detected. Record canceled.")
            else:
                writer.add(signal_chunk, hand_points)

        signal_fwd.put((signal_chunk))
        hand_points_fwd.put((hand_points, coupling_fps, debt_size))

        processing_results.task_done()
