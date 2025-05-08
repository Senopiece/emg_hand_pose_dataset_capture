from typing import Tuple
import numpy as np
import serial

from .synthetic_serial import SyntheticSerial


class EmgDevice:
    def __init__(
        self,
        bytes_per_channel: int,
        payload_bits: int,
        channels: int,
        serial_port: str,
        blocking=False,
    ):
        self.channels = channels
        self.bytes_per_channel = bytes_per_channel
        self.payload_bits = payload_bits
        self.packet_size = channels * bytes_per_channel
        self.buffer = bytearray()
        if serial_port == "synthetic":
            # Use synthetic data generator
            self.ser = SyntheticSerial()
            print("Starting synthetic data mode...")
        else:
            # Open real serial connection
            try:
                self.ser = serial.Serial(
                    serial_port, 256000, timeout=None if blocking else 0
                )

                # Increase serial input buffer size if supported (Windows/Linux only)
                if hasattr(self.ser, "set_buffer_size"):
                    self.ser.set_buffer_size(rx_size=4096)

                print(f"Listening on {serial_port}...")
            except Exception as e:
                raise ValueError(f"Serial connection error: {e}")

    def read_packets(self) -> Tuple[bool, np.ndarray]:
        err = False
        res = []

        try:
            # Read all available bytes from the serial buffer
            in_waiting = self.ser.in_waiting
            if in_waiting == 0:
                # Wait for data
                incoming = self.ser.read(1)

                # Read the rest
                in_waiting = self.ser.in_waiting
                if in_waiting != 0:
                    incoming += self.ser.read(in_waiting)
            else:
                # Read all what avaliable
                incoming = self.ser.read(in_waiting)

            if not incoming:
                return err, np.zeros((0, self.channels), dtype=np.float32)

            self.buffer.extend(incoming)

            # Process packets ending with FFFF
            while True:
                # Check if FFFF exists in the buffer
                delimiter_index = self.buffer.find(b"\xff" * self.bytes_per_channel)
                if delimiter_index == -1:
                    break  # No complete packet found yet

                # Extract the packet (up to but excluding [0xFF, 0xFF])
                packet = self.buffer[:delimiter_index]
                self.buffer = self.buffer[
                    delimiter_index + 2 :
                ]  # Remove the packet and delimiter

                # Process the packet
                try:
                    if len(packet) == self.packet_size:
                        res.append(
                            [
                                int.from_bytes(
                                    packet[
                                        self.bytes_per_channel
                                        * i : self.bytes_per_channel
                                        * (i + 1)
                                    ],
                                    byteorder="little",
                                )
                                for i in range(self.channels)
                            ]
                        )
                    else:
                        print(
                            f"Unexpected packet size: {len(packet)} (expected {self.packet_size}) - {packet}"
                        )
                        err = True  # None to indicate errors
                except Exception as e:
                    print(f"Packet processing error: {e}")
                    err = True  # None to indicate errors
        except Exception as e:
            print(f"Error while reading packets: {e}")
            err = True  # None to indicate errors

        if res:
            # Convert to numpy array
            res_array = np.array(res, dtype=np.float32)

            # Calculate the maximum value based on bytes_per_channel
            max_value = (1 << self.payload_bits) - 1

            # Normalize values between 0 and 1
            res_array = res_array / max_value
        else:
            res_array = np.zeros((0, self.channels), dtype=np.float32)

        return err, res_array

    def close(self):
        self.ser.close()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        self.close()
