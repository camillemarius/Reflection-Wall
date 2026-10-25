# ui/buttons.py
# Tasten-Quellen: PiLink/Tastatur (Queue) und direkt vom Expander PCF8575.
import collections
import contextlib
import logging
import queue
import sys
import threading
import time
from typing import Optional, Protocol

log = logging.getLogger(__name__)

BT1, BT2, BT3, BT4, BT5, BT6 = 1, 2, 3, 4, 5, 6

EXPANDER_ADDRESS = 0x20
# Bitnummer im 16-Bit-Wert (erstes gelesenes Byte = unteres Byte), Reihenfolge BT1..BT6
BUTTON_BITS = ((BT1, 3), (BT2, 4), (BT3, 5), (BT4, 8), (BT5, 9), (BT6, 10))


class ExpanderError(Exception):
    pass


class ButtonSource(Protocol):
    def get(self, timeout: Optional[float]) -> Optional[int]: ...

    def drain(self) -> None: ...


class QueueButtons:
    """Thread-sichere Warteschlange von Tastennummern."""

    def __init__(self):
        self._q: "queue.Queue[int]" = queue.Queue()

    def put(self, n: int) -> None:
        self._q.put(n)

    def get(self, timeout: Optional[float]) -> Optional[int]:
        try:
            if timeout is None:
                return self._q.get()
            if timeout <= 0:
                return self._q.get_nowait()
            return self._q.get(timeout=timeout)
        except queue.Empty:
            return None

    def drain(self) -> None:
        while True:
            try:
                self._q.get_nowait()
            except queue.Empty:
                return


@contextlib.contextmanager
def _no_guard():
    yield


class _SmbusReader:
    """Liest 2 Bytes ohne Register vom PCF8575."""

    def __init__(self, bus):
        self._bus = bus

    def read(self, addr, count):
        from smbus2 import i2c_msg
        msg = i2c_msg.read(addr, count)
        self._bus.i2c_rdwr(msg)
        return bytes(msg)


class ExpanderButtons:
    """Jeder Pegelwechsel eines Taster-Bits gegenueber dem letzten Stand ist ein Druck.

    bus braucht read(addr, count) -> bytes; ohne bus wird smbus2 erst in start() geladen.
    """

    def __init__(self, bus=None, bus_guard=None, clock=time.monotonic, poll_s=0.05,
                 sleep=time.sleep):
        self._bus = bus
        self._guard = bus_guard or _no_guard
        self._clock = clock
        self._poll_s = poll_s
        self._sleep = sleep
        self._last: Optional[int] = None
        self._pending = collections.deque()

    def start(self) -> None:
        if self._bus is None:
            import smbus2
            self._bus = _SmbusReader(smbus2.SMBus(1))
        self._last = self._read()

    def _read_once(self) -> int:
        with self._guard():
            data = self._bus.read(EXPANDER_ADDRESS, 2)
        return data[0] | (data[1] << 8)

    def _read(self) -> int:
        try:
            return self._read_once()
        except OSError:
            pass
        try:
            return self._read_once()
        except OSError as exc:
            raise ExpanderError("Expander 0x%02X nicht lesbar: %s" % (EXPANDER_ADDRESS, exc)) from exc

    def _poll(self) -> None:
        value = self._read()
        changed = value ^ self._last
        self._last = value
        for number, bit in BUTTON_BITS:
            if changed & (1 << bit):
                self._pending.append(number)

    def get(self, timeout: Optional[float]) -> Optional[int]:
        if self._last is None:
            self.start()
        deadline = None if timeout is None else self._clock() + timeout
        while True:
            if self._pending:
                return self._pending.popleft()
            self._poll()
            if self._pending:
                continue
            if deadline is not None and self._clock() >= deadline:
                return None
            self._sleep(self._poll_s)

    def drain(self) -> None:
        self._pending.clear()
        if self._last is not None:
            # Bezug auf den aktuellen Stand setzen, damit Altes nicht nachkommt
            self._last = self._read()


class KeyboardButtons(QueueButtons):
    """PC-Modus: Ziffern 1-6 aus Zeilen von stdin, gelesen in einem Daemon-Thread."""

    def __init__(self, stream=None):
        super().__init__()
        self._stream = stream
        self._thread: Optional[threading.Thread] = None

    def start(self) -> None:
        self._thread = threading.Thread(target=self._run, name="keyboard-buttons", daemon=True)
        self._thread.start()

    def _run(self) -> None:
        stream = self._stream if self._stream is not None else sys.stdin
        for line in stream:
            for ch in line:
                if ch in "123456":
                    self.put(int(ch))
