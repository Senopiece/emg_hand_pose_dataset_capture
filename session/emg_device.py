from typing import List, Tuple
import serial

from .synthetic_serial import SyntheticSerial


class EmgDevice:
    def __init__(
        self,
        bytes_per_channel: int,
        channels: int,
        serial_port: str,
    ):
        self.channels = channels
        self.bytes_per_channel = bytes_per_channel
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
                    serial_port, 256000, timeout=0
                )  # Non-blocking read

                # Increase serial input buffer size if supported (Windows/Linux only)
                if hasattr(self.ser, "set_buffer_size"):
                    self.ser.set_buffer_size(rx_size=4096)

                print(f"Listening on {serial_port}...")
            except Exception as e:
                raise ValueError(f"Serial connection error: {e}")

    def read_packets(self) -> Tuple[bool, List[List[int]]]:
        err = False
        res = []

        try:
            # Read available bytes from the serial buffer
            incoming = self.ser.read(self.ser.in_waiting or 1)

            if not incoming:
                return err, res

            self.buffer.extend(incoming)

            # Process packets ending with FFFF
            while True:
                # Check if FFFF exists in the buffer
                delimiter_index = self.buffer.find(b"\xFF" * self.bytes_per_channel)
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

        return err, res

    def close(self):
        self.ser.close()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        self.close()
