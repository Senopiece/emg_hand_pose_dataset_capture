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
        # 0: save segments and start new recording
        # 1: continue recording
        start_event = manager.Event()
        command_channel.put(start_event)

        frames_recorded = 0
        segments = []

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
                continue_recording = stop_action.value

                if continue_recording < 0:
                    pass  # skip if not yet decided
                else:
                    if continue_recording == 0:
                        print("Saving to the disk...")

                        # Save segment to the disk
                        rec = writer.add_recording()
                        for segment in segments:
                            rec.add_segment(segment)
                        segments.clear()
                        rec.add_segment(segment_collector.finalize())

                        # Drain frames that came while writing the segment
                        qsize = processing_results.qsize()
                        if qsize > 0:
                            print(f"Draining {qsize} frames that came while writing.")
                            for _ in range(processing_results.qsize()):
                                processing_results.get()
                                processing_results.task_done()

                        # The time is calculated assuming 32 fps
                        elapsed = frames_recorded / 32.0
                        minutes, seconds = divmod(int(elapsed), 60)
                        milliseconds = int((elapsed - int(elapsed)) * 1000)
                        print(
                            f"Recording {writer.recording_index} ({minutes:02}:{seconds:02}:{milliseconds:03}) saved."
                        )
                        frames_recorded = 0

                        # Set ready to start new recording
                        stop_action = None
                        start_event = manager.Event()
                        command_channel.put(start_event)

                    elif hand_angles is not None and not np.isnan(signal_chunk).any():
                        segments.append(segment_collector.finalize())
                        start_event = None
                        stop_action = manager.Value("b", -1)
                        command_channel.put(stop_action)
                        print("Continuing recording.")

                    else:
                        stop_action = manager.Value("b", -2)
                        command_channel.put(stop_action)
                        print(
                            "No hand detected or emg failure. Record continue was ignored."
                        )

            if start_event is not None and start_event.is_set():
                assert stop_action is None

                if hand_angles is not None and not np.isnan(signal_chunk).any():
                    start_event = None
                    stop_action = manager.Value("b", -1)
                    command_channel.put(stop_action)
                    print(f"Recording {writer.recording_index + 1} started.")
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
                        print("Hand or signal was lost.")
                    else:
                        frames_recorded += 1
                        segment_collector.add(signal_chunk, hand_angles)

            signal_fwd.put((signal_chunk))
            hand_angles_fwd.put((hand_angles, coupling_fps))

            processing_results.task_done()
