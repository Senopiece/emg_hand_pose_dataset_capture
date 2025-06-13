import threading
import time


class SyntheticSerial:
    """Mock serial port for generating synthetic ADC data."""

    def __init__(self, channels: int = 6):
        self.current_count = 0
        self.buffer = bytearray()  # Use a bytearray to store bytes
        self.buffer_lock = threading.Lock()  # Lock for thread-safe access to the buffer
        self.data_available = threading.Condition(self.buffer_lock)
        self.channels = channels  # Example number of channels
        self.running = True

        # Start the worker thread to add bytes to the buffer
        self.worker_thread = threading.Thread(target=self._worker)
        self.worker_thread.start()

    def _worker(self):
        """Worker thread that adds 64 packets each 0.03125 second to the buffer (so that the rate 2048 packets per second)."""
        while self.running:
            start_time = time.time()  # Track the start time of the 1-second period

            # Generate a synthetic packet with incrementing values
            packets = bytearray()
            for _ in range(64):
                for channel in range(self.channels):
                    value = (self.current_count + channel * 64) % 4096
                    packets += value.to_bytes(2, byteorder="little")
                packets += b"\xff\xff"  # Delimiter
                self.current_count += 1

            # Add the packet bytes to the buffer (thread-safe)
            with self.buffer_lock:
                self.buffer.extend(packets)
                self.data_available.notify_all()

            # Calculate the remaining time to sleep to maintain the 1-second period
            elapsed_time = time.time() - start_time
            sleep_time = 0.03125 - elapsed_time

            if sleep_time > 0:
                time.sleep(sleep_time)  # Sleep for the remaining time

    @property
    def in_waiting(self):
        """Return the number of bytes waiting in the buffer."""
        with self.buffer_lock:
            return len(self.buffer)

    def read(self, size: int = 1):
        """Read bytes from the buffer."""
        with self.data_available:
            while len(self.buffer) < size:
                self.data_available.wait()  # Block until enough data is available
            result = self.buffer[:size]
            del self.buffer[:size]
            return result

    def close(self):
        """Stop the worker thread and clean up."""
        self.running = False
        self.worker_thread.join()
