import cv2
import numpy as np
from typing import Any, Callable, List, Tuple
from src.webcam_hand_triangulation.capture.hand_utils import rm_th_base
from webcam_hand_triangulation.capture.draw_utils import (
    draw_left_top,
    draw_origin_landmarks,
    draw_reprojected_landmarks,
)
from webcam_hand_triangulation.capture.finalizable_queue import (
    EmptyFinalized,
    FinalizableQueue,
)
from webcam_hand_triangulation.capture.models import CameraParams
from webcam_hand_triangulation.capture.processing_loop import (
    HandTriangulator,
    inverse_hand_angles_by_landmarks,
    normalize_hand,
)


def processing_loop(
    landmark_transforms: List[Callable[..., Any]],
    to_draw_origin_landmarks: bool,
    desired_window_size: Tuple[int, int],
    cameras_params: List[CameraParams],
    coupled_emg_frames_queue: FinalizableQueue,
    results_queue: FinalizableQueue,
    display_queues: List[FinalizableQueue] | None,
):
    triangulator = HandTriangulator(landmark_transforms, cameras_params)

    while True:
        try:
            elem = coupled_emg_frames_queue.get()
        except EmptyFinalized:
            break

        index: int = elem[0]
        indexed_frames: List[Tuple[np.ndarray, int]] = elem[1]
        coupling_fps: int = elem[2]
        signal_chunk: np.ndarray = elem[3]

        cap_fps: List[int] = [item[1] for item in indexed_frames]
        frames: List[np.ndarray] = [item[0] for item in indexed_frames]

        del indexed_frames

        landmarks, chosen_cams, points_3d = triangulator.triangulate(frames)

        results_queue.put(
            (
                index,
                (
                    (
                        inverse_hand_angles_by_landmarks(
                            normalize_hand(rm_th_base(points_3d))
                        ).astype(np.float32)
                        if points_3d
                        else None
                    ),
                    signal_chunk,
                    coupling_fps,
                ),
            )
        )

        if display_queues is not None:
            # Resize frames before drawing
            for i, frame in enumerate(frames):
                frames[i] = cv2.resize(
                    frame, desired_window_size, interpolation=cv2.INTER_AREA
                )

            # Draw original landmarks
            if to_draw_origin_landmarks:
                draw_origin_landmarks(landmarks, frames)

            # Draw reprojected landmarks
            draw_reprojected_landmarks(points_3d, frames, cameras_params, chosen_cams)

            # Draw cap fps for every pov
            for fps, frame in zip(cap_fps, frames):
                draw_left_top(0, f"Capture FPS: {fps}", frame)

            # Write results
            for display_queue, frame in zip(display_queues, frames):
                display_queue.put((index, frame))

        coupled_emg_frames_queue.task_done()

    triangulator.close()

    print("A processing loop is finished.")
