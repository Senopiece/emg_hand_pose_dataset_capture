from multiprocessing.managers import SyncManager
import numpy as np
from .dataset_writer import DatasetWriter, HandEmgRecordingSegmentCollector
from webcam_hand_triangulation.capture.coupling_loop import FinalizableQueue
from webcam_hand_triangulation.capture.finalizable_queue import EmptyFinalized


def recording_loop(
    manager: SyncManager,
    command_channel: FinalizableQueue,
    filepath: str,
    processing_results: FinalizableQueue,
    hand_angles_fwd: FinalizableQueue,
    signal_fwd: FinalizableQueue,
):
    with DatasetWriter(filepath) as writer:
        segment_collector = HandEmgRecordingSegmentCollector()

        stop_action = None  # -1 - not set, 1 - save, 0 - cancel
        start_event = manager.Event()
        command_channel.put(start_event)

        while True:
            try:
                hand_angles: np.ndarray
                signal_chunk: np.ndarray
                coupling_fps: int
                hand_angles, signal_chunk, coupling_fps = processing_results.get()
            except EmptyFinalized:
                print("Force shutdown while recording. Latest record cancelled.")
                break

            if stop_action is not None:
                assert start_event is None
                should_save = stop_action.value

                if should_save == -1:
                    pass  # skip if not yet decided
                else:
                    if should_save:
                        writer.add_recording().add_segment(segment_collector.finalize())
                        print("Record saved.")
                    else:
                        segment_collector.reset()
                        print("Record cancelled.")

                    stop_action = None
                    start_event = manager.Event()
                    command_channel.put(start_event)

            if start_event is not None and start_event.is_set():
                assert stop_action is None

                if hand_angles is not None:
                    start_event = None
                    stop_action = manager.Value("b", -1)
                    command_channel.put(stop_action)
                    print("Recording started.")
                else:
                    start_event = manager.Event()
                    command_channel.put(start_event)
                    print("No hand detected. Record start was ignored.")

            if start_event is None:
                assert stop_action is not None
                if hand_angles is None:
                    segment_collector.reset()
                    stop_action = None
                    start_event = manager.Event()
                    command_channel.put(start_event)
                    print("No hand detected. Record cancelled.")
                else:
                    segment_collector.add(signal_chunk, hand_angles)

            signal_fwd.put((signal_chunk))
            hand_angles_fwd.put((hand_angles, coupling_fps))

            processing_results.task_done()
