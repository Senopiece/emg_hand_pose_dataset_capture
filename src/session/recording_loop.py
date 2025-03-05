import os
from typing import List
import numpy as np
from .hand_emg_record import HandEmgRecordWriter
from .bool_promise import BoolPromise
from .requestable_toggle import RequestableToggle
from webcam_hand_triangulation.capture.coupling_loop import FinalizableQueue
from webcam_hand_triangulation.capture.finalizable_queue import EmptyFinalized


def recording_loop(
    record_toggle: RequestableToggle,
    save_record_question_channel: FinalizableQueue,
    base_dir: str,
    num_channels: int,
    processing_results: FinalizableQueue,
    hand_points_fwd: FinalizableQueue,
    signal_fwd: FinalizableQueue,
):
    record_id = 0
    writer = None
    ask_whether_to_save_record: None | BoolPromise = None

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
            break

        if ask_whether_to_save_record is not None:
            assert writer is not None
            should_save = ask_whether_to_save_record.get()

            if should_save is None:
                pass
            else:
                if should_save:
                    writer.save()
                    record_id += 1
                else:
                    writer.cancel()
                writer = None
                ask_whether_to_save_record = None
                record_toggle.request_toggle()

        if record_toggle.is_toggled():
            assert ask_whether_to_save_record is None
            if writer is None:
                writer = HandEmgRecordWriter(
                    os.path.join(base_dir, f"{record_id}.bin"), num_channels
                )
                record_toggle.request_toggle()
            elif writer is not None:
                ask_whether_to_save_record = BoolPromise()
                save_record_question_channel.put(ask_whether_to_save_record)
                record_toggle.reset_toggle()

        if writer is not None and ask_whether_to_save_record is None:
            writer.add(signal_chunk, hand_points)

        signal_fwd.put((signal_chunk))
        hand_points_fwd.put((hand_points, coupling_fps, debt_size))

        processing_results.task_done()
