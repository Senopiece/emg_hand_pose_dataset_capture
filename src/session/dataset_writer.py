from typing import NamedTuple
import numpy as np
import yaml
import io
import zipfile

# NOTE: `frame` here refers to hand pose angles

W = 64


class HandEmgRecordingSegment(NamedTuple):
    buff: bytes
    channels: int


class HandEmgRecordingSegmentCollector:
    _channels: int | None = None
    _bio: io.BytesIO

    def __init__(self) -> None:
        self._bio = io.BytesIO()

    # Assuming emg is captured before frame
    def add(
        self,
        emg: np.ndarray,  # (W, C), float32 expected
        frame: np.ndarray,  # (20,), float32 expected
    ):
        first = self._channels is None
        if first:
            self._channels = emg.shape[1]

        C = self._channels

        assert emg.dtype == np.float32, f"EMG dtype must be float32, got {emg.dtype}"
        assert frame.shape == (20,), f"Frame shape must be (20,), got {frame.shape}"
        assert (
            frame.dtype == np.float32
        ), f"Frame dtype must be float32, got {frame.dtype}"
        assert (
            emg.shape[0] == W and emg.shape[1] == C
        ), f"EMG shape must be ({W}, {C}), got {emg.shape}"

        # For the first couple, throw early emg
        if not first:
            self._bio.write(emg.flatten().tobytes())

        self._bio.write(frame.tobytes())

    def finalize(self):
        assert self._channels is not None, "Number of EMG channels is not set"

        res = HandEmgRecordingSegment(self._bio.getvalue(), self._channels)

        self.reset()

        return res

    def reset(self):
        self._bio = io.BytesIO()
        self._channels = None


class RecordingWriter:
    """
    A context for writing recording by segments

    Each segment is written in format:
    [ [<20 x float32: frame>, <W x C float32: emg>], [...], ... <20 x float32: sigma frame> ]
    """

    def __init__(self, context: "DatasetWriter", index: int):
        self.context = context
        self.index = index
        self.count = 0

    def add_segment(self, segment: HandEmgRecordingSegment):
        """
        Add a single recording segment to the ZIP archive.

        Args:
            segment: A list of HandEmgTuple samples. Each sample is stored with its frame
                       (20 float32 values) and its emg (W x C float32 values). The number of EMG
                       channels (C) is determined from the first sample and is assumed to be consistent.
        """
        if self.context.archive is None:
            raise RuntimeError("Archive is not open. Use 'with' statement to open it.")

        # Determine the number of EMG channels (C) from the first sample.
        C = segment.channels
        if self.context.C is None:
            # Store C for metadata
            self.context.C = C
            self.context.archive.writestr("metadata.yml", yaml.dump({"C": C}))

        elif self.context.C != C:
            raise ValueError("Inconsistent number of EMG channels across recordings.")

        # Save the segment
        self.context.archive.writestr(
            f"recordings/{self.index}/segments/{self.count}", segment.buff
        )
        self.count += 1


class DatasetWriter:
    """
    A context manager for writing segments to a ZIP archive in a proprietary binary format.

    Archive looks like this:

    dataset.zip/
      metadata.yml
      recordings/
        1/
          segments/
           1
           2
        2/
          segments/
            1
            2
    """

    def __init__(self, filename: str):
        self.filename = filename
        self.archive = None
        self.recording_index = -1
        self.C: int | None = None  # To store the number of EMG channels

    def __enter__(self):
        self.archive = zipfile.ZipFile(
            self.filename,
            mode="w",
            compression=zipfile.ZIP_DEFLATED,
            compresslevel=9,
        )
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        if self.archive is not None:
            self.archive.close()

    def add_recording(self):
        """
        NOTE: recording is actually written only after calling RecordingWriter.add,
              add_recording only allocates the recording index
        """
        self.recording_index += 1
        return RecordingWriter(self, self.recording_index)
