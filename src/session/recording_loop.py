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

        stop_action = None
        # None: not yet started
        # -2: not set, questioning what to do with terminated recording
        # -1: not set, recording
        # 1: save
        # 0: cancel
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

                if should_save < 0:
                    pass  # skip if not yet decided
                else:
                    if should_save:
                        writer.add_recording().add_segment(segment_collector.finalize())
                        print("Record saved.")
                    else:
                        segment_collector.reset()
                        print("Record cancelled.")

                    # Drain frames that came while writing the record
                    qsize = processing_results.qsize()
                    if qsize > 0:
                        print(f"Draining {qsize} frames that came while writing.")
                        for _ in range(processing_results.qsize()):
                            processing_results.get()
                            processing_results.task_done()

                    # Set ready to start new recording
                    stop_action = None
                    start_event = manager.Event()
                    command_channel.put(start_event)

            if start_event is not None and start_event.is_set():
                assert stop_action is None

                if hand_angles is not None and not np.isnan(signal_chunk).any():
                    start_event = None
                    stop_action = manager.Value("b", -1)
                    command_channel.put(stop_action)
                    print("Recording started.")
                else:
                    start_event = manager.Event()
                    command_channel.put(start_event)
                    print("No hand detected or emg failure. Record start was ignored.")

            if start_event is None:
                assert stop_action is not None
                assert stop_action.value < 0

                # if not was questioned to save or cancel, continue collecting
                if stop_action.value != -2:
                    # alert if signal_chunk is having NaNs or hand was lost
                    if hand_angles is None or np.isnan(signal_chunk).any():
                        stop_action = manager.Value("b", -2)
                        command_channel.put(stop_action)
                        print(
                            "Hand or signal was lost. Questioning recording save or cancel."
                        )
                    else:
                        segment_collector.add(signal_chunk, hand_angles)

            signal_fwd.put((signal_chunk))
            hand_angles_fwd.put((hand_angles, coupling_fps))

            processing_results.task_done()
