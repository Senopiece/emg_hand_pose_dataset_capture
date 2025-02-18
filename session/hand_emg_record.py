import struct
import os


# Writes coupled hand pose and emg
# NOTE: This coupling is intended to be such that
#       coupled emg is the emg that foreshadows the hand pose it's coupled with
# NOTE: this file does not provide the sampling frequency,
#       but only the relative of hands to emg sampling (assuming emg sampling is higher than hand sampling)
#        > also the hand sampling is intended to may be of varying framerate actually, but the emg sampling must be precise
#       the indented values are =2048Hz emg and ~30Hz hands
# NOTE: However the feeder may not do as intended, so be careful and check the feeder code also
class HandEmgRecordWriter:
    def __init__(self, filepath, emg_channels):
        self.filepath = filepath
        self.emg_channels = emg_channels
        self.file = open(filepath, "wb")

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        self.close()

    def close(self):
        if self.file:
            self.file.flush()
            os.fsync(self.file.fileno())
            self.file.close()
            self.file = None

    def add(self, emg, hand_pose):
        if not self.file:
            raise ValueError("File is not open for writing.")

        if len(hand_pose) != 21 or any(len(point) != 3 for point in hand_pose):
            raise ValueError("hand_pose must be an array of 21 3D points.")

        if not (0 <= len(emg) <= 255) or any(
            len(sample) != self.emg_channels for sample in emg
        ):
            raise ValueError(
                "emg must be a list of samples, each sample containing integers with length equal to emg_channels, and values between 0 and 65535."
            )

        emg_len_byte = struct.pack("B", len(emg))
        emg_bytes = b"".join(
            struct.pack(f"{self.emg_channels}H", *sample) for sample in emg
        )
        hand_pose_bytes = b"".join(struct.pack("3d", *point) for point in hand_pose)

        self.file.write(emg_len_byte + emg_bytes + hand_pose_bytes)


class HandEmgRecordReader:
    def __init__(self, filepath, emg_channels):
        self.filepath = filepath
        self.emg_channels = emg_channels
        self.file = open(filepath, "rb")

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        self.close()

    def close(self):
        if self.file:
            self.file.close()
            self.file = None

    def read(self):
        if not self.file:
            raise ValueError("File is not open for reading.")

        try:
            emg_len = struct.unpack("B", self.file.read(1))[0]
            emg = [
                list(
                    struct.unpack(
                        f"{self.emg_channels}H", self.file.read(self.emg_channels * 2)
                    )
                )
                for _ in range(emg_len)
            ]
            hand_pose = [struct.unpack("3d", self.file.read(3 * 8)) for _ in range(21)]

            return emg, hand_pose

        except struct.error:
            return None  # End of file


if __name__ == "__main__":
    # Example usage:
    FILENAME = "tmp.bin"
    EMG_CHANNELS = 2  # Example with 2 EMG channels

    with HandEmgRecordWriter(FILENAME, EMG_CHANNELS) as writer:
        writer.add([[10, 20], [30, 40]], [[0.0, 0.0, 0.0]] * 21)
        writer.add([[10, 20], [30, 40], [50, 60]], [[0.0, 0.0, 1.0]] * 21)

    with HandEmgRecordReader(FILENAME, EMG_CHANNELS) as reader:
        while True:
            record = reader.read()
            if record is None:
                break
            emg, hand_pose = record
            print("EMG:", emg)
            print("Hand Pose:", hand_pose)

    os.remove(FILENAME)
