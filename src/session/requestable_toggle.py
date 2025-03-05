import multiprocessing


class RequestableToggle:
    def __init__(self):
        self._toggled = multiprocessing.Value("b", False)
        self._toggle_requested = multiprocessing.Value("b", False)
        self._lock = multiprocessing.Lock()

    def request_toggle(self):
        """Marks a toggle request. Implicitly resets toggle."""
        with self._lock:
            self._toggle_requested.value = True        

    def toggle(self):
        """Completes the toggle request."""
        with self._lock:
            if self._toggle_requested.value:
                self._toggled.value = not self._toggled.value
                self._toggle_requested.value = False

    def is_toggled(self) -> bool:
        with self._lock:
            return self._toggled.value

    def toggle_requested(self) -> bool:
        with self._lock:
            return self._toggle_requested.value
