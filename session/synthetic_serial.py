import threading
import time


class SyntheticSerial:
    """Mock serial port for generating synthetic ADC data."""

    def __init__(self):
        self.current_count = 0
        self.buffer = bytearray()  # Use a bytearray to store bytes
        self.buffer_lock = threading.Lock()  # Lock for thread-safe access to the buffer
        self.channels = 6  # Example number of channels
        self.running = True

        # Start the worker thread to add bytes to the buffer
        self.worker_thread = threading.Thread(target=self._worker)
        self.worker_thread.start()

    def _worker(self):
        """Worker thread that adds 100 packets each 0.05 second to the buffer (so that the rate 2000 packets per second)."""
        while self.running:
            start_time = time.time()  # Track the start time of the 1-second period

            # Generate a synthetic packet with incrementing values
            packets = bytearray()
            for _ in range(100):
                for channel in range(self.channels):
                    value = (self.current_count + channel * 100) % 4096
                    packets += value.to_bytes(2, byteorder="little")
                packets += b"\xFF\xFF"  # Delimiter
                self.current_count += 1

            # Add the packet bytes to the buffer (thread-safe)
            with self.buffer_lock:
                self.buffer.extend(packets)

            # Calculate the remaining time to sleep to maintain the 1-second period
            elapsed_time = time.time() - start_time
            sleep_time = 0.05 - elapsed_time

            if sleep_time > 0:
                time.sleep(sleep_time)  # Sleep for the remaining time

    @property
    def in_waiting(self):
        """Return the number of bytes waiting in the buffer."""
        with self.buffer_lock:
            return len(self.buffer)

    def read(self, size: int = 1):
        """Read bytes from the buffer."""
        with self.buffer_lock:
            # Read up to `size` bytes from the buffer
            data = self.buffer[:size]
            # Remove the read bytes from the buffer
            self.buffer = self.buffer[size:]
        return bytes(data)

    def close(self):
        """Stop the worker thread and clean up."""
        self.running = False
        self.worker_thread.join()
