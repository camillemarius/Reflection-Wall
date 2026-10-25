"""Testhilfen fuer die Verbindung ESP-Pi."""
import threading
import time


class FakeClock:
    def __init__(self) -> None:
        self.now = 0.0

    def __call__(self) -> float:
        return self.now

    def advance(self, seconds: float) -> None:
        self.now += seconds


class FakePort:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._rx = bytearray()
        self._tx = bytearray()
        self.fail: Exception | None = None
        self.write_error: Exception | None = None
        self.reads = 0

    def feed(self, data: bytes) -> None:
        with self._lock:
            self._rx += data

    def unread(self) -> int:
        """So viele Bytes hat der Link noch nicht gelesen."""
        with self._lock:
            return len(self._rx)

    def read_available(self) -> bytes:
        self.reads += 1
        if self.fail is not None:
            raise self.fail
        with self._lock:
            data = bytes(self._rx)
            self._rx.clear()
        if not data:
            time.sleep(0.001)
        return data

    def write(self, data: bytes) -> None:
        if self.write_error is not None:
            raise self.write_error
        with self._lock:
            self._tx += data

    def take_tx(self) -> bytes:
        with self._lock:
            data = bytes(self._tx)
            self._tx.clear()
        return data
