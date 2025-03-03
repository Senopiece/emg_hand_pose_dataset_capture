import multiprocessing


class BoolPromise:
    def __init__(self):
        self._answer = multiprocessing.Value("b", -1)  # -1 represents not answered

    def get(self):
        if self._answer.value == -1:
            return None
        return bool(self._answer.value)

    def set(self, value: bool):
        self._answer.value = int(value)
