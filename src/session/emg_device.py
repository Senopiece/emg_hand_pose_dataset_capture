from typing import Any
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
    ):
        self.channels = channels
        self.bytes_per_channel = bytes_per_channel
        self.payload_bits = payload_bits
        self.packet_size = channels * bytes_per_channel
        self.packet_with_delimiter_size = self.packet_size + self.bytes_per_channel
        self.delimiter_etalon = b"\xff" * self.bytes_per_channel
        self.max_value = (1 << self.payload_bits) - 1
        self.dtype = f"<u{self.bytes_per_channel}"  # Little-endian unsigned int

        if serial_port == "synthetic":
            # Use synthetic data generator
            self.ser = SyntheticSerial(channels)
            print("Starting synthetic data mode...")
        else:
            # Open real serial connection
            try:
                self.ser = serial.Serial(serial_port, 256000, timeout=None)

                # Increase serial input buffer size if supported (Windows/Linux only)
                if hasattr(self.ser, "set_buffer_size"):
                    self.ser.set_buffer_size(rx_size=4096)

                print(f"Listening on {serial_port}...")
            except Exception as e:
                raise ValueError(f"Serial connection error: {e}")

    def position_head(self):
        # Read a bunch of data that contains a \ff for sure (assuming uncorrupted)
        incoming = self.ser.read(2 * self.packet_with_delimiter_size)

        # get the last packet part
        delimiter_index = incoming.rfind(self.delimiter_etalon)
        if delimiter_index == -1:
            raise ValueError(
                f"Corrupted packet {incoming}, found delimiter at {delimiter_index}"
            )

        # eat up the rest of the packet so that head is at the right position
        self.ser.read(delimiter_index - self.packet_size)

    def read_packets(self, amount: int) -> np.ndarray:
        data = self.ser.read(amount * self.packet_with_delimiter_size)

        # Split the data into packets and delimiters
        packets: Any = [None] * amount
        for i in range(amount):
            start = i * self.packet_with_delimiter_size
            end = start + self.packet_with_delimiter_size
            packet_with_delimiter = data[start:end]

            # Check if the delimiter is correct
            delimiter = packet_with_delimiter[
                self.packet_size : self.packet_with_delimiter_size
            ]
            if delimiter != self.delimiter_etalon:
                raise ValueError("Malformed packet: Incorrect delimiter")

            # Extract the packet data
            packet_data = packet_with_delimiter[: self.packet_size]

            # Parse the packet data into a numpy array
            packet = np.frombuffer(packet_data, dtype=self.dtype)

            # Normalize the packet data to [0, 1]
            packet = packet.astype(np.float32) / self.max_value

            packets[i] = packet

        # Stack the packets into a single numpy array
        packets_array = np.vstack(packets)

        return packets_array

    def close(self):
        self.ser.close()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        self.close()
