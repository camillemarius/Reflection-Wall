"""Verbindung ESP-Pi, Seite Pi: Wiederholung, Nummern, Fristen, eigener Thread.

Gleiche Regeln wie esp/lib/core/src/PiLink.cpp. Ein Lock schuetzt Zustand und
Schreiben; gelesen wird ausserhalb der Sperre (nur der Thread liest).
"""
import collections
import concurrent.futures
import logging
import queue
import threading
import time
import typing
from typing import Callable

from app.link.codec import (
    MAX_LINE, DecodeError, EncodeError, Message, deadline_ms, decode, encode, role_of,
)

REPEAT_S = 0.25


class LinkBusy(RuntimeError):
    pass


class Port(typing.Protocol):
    def read_available(self) -> bytes: ...
    def write(self, data: bytes) -> None: ...


class PiLink:
    def __init__(self, port: Port, clock: Callable[[], float] = time.monotonic,
                 log: logging.Logger | None = None) -> None:
        self._port = port
        self._clock = clock
        self._log = log or logging.getLogger("link")
        self._lock = threading.Lock()
        self.incoming: "queue.Queue[Message]" = queue.Queue()
        self.discarded: "collections.Counter[str]" = collections.Counter()
        # Lesen (nur Thread bzw. poll)
        self._buf = bytearray()
        self._overflow = False
        # Zustand eigene Anfrage
        self._tx_seq = 0
        self._pending: Message | None = None
        self._pending_frame = b""
        self._future: concurrent.futures.Future | None = None
        self._start_t = 0.0
        self._last_sent = 0.0
        # Zustand Anfrage des ESP
        self._rx_seq: int | None = None
        self._in_progress = False
        self._last_reply = b""
        # Thread
        self._thread: threading.Thread | None = None
        self._stop = threading.Event()
        self._dead = False

    @property
    def alive(self) -> bool:
        return self._thread is not None and self._thread.is_alive()

    # --- Schreiben (unter Sperre) -------------------------------------------
    def _write(self, frame: bytes) -> None:
        self._log.debug("-> %s", frame.decode("ascii", "replace"))
        self._port.write(frame + b"\n")

    # --- Anfragen des Pi -----------------------------------------------------
    def request(self, command: str, data: str = "") -> "concurrent.futures.Future[Message | None]":
        with self._lock:
            if self._dead:
                fut = concurrent.futures.Future()
                fut.set_result(None)
                return fut
            if self._future is not None:
                raise LinkBusy("Anfrage offen")
            msg = Message(self._tx_seq, command, data)
            frame = encode(msg)  # EncodeError: Nummer bleibt frei
            self._tx_seq = (self._tx_seq + 1) & 0xFF
            now = self._clock()
            self._pending = msg
            self._pending_frame = frame
            self._future = concurrent.futures.Future()
            self._start_t = now
            self._last_sent = now
            fut = self._future
            self._write(frame)
            return fut

    # --- Antworten auf Anfragen des ESP -------------------------------------
    def reply(self, request: Message, command: str, data: str = "") -> bool:
        with self._lock:
            if not self._in_progress or request.seq != self._rx_seq:
                return False
            try:
                frame = encode(Message(request.seq, command, data))
            except EncodeError:
                return False
            self._last_reply = frame
            self._in_progress = False
            self._write(frame)
            return True

    # --- ein Durchgang -------------------------------------------------------
    def poll(self) -> None:
        chunk = self._port.read_available()  # ausserhalb der Sperre
        done: list[tuple[concurrent.futures.Future, Message | None]] = []
        with self._lock:
            self._feed(chunk, done)
            self._timers(done)
        for fut, result in done:  # ausserhalb der Sperre, damit Rueckrufe nicht blockieren
            fut.set_result(result)

    def _feed(self, chunk: bytes, done: list) -> None:
        for b in chunk:
            if b != 0x0A:
                if self._overflow:
                    continue
                if len(self._buf) >= MAX_LINE + 1:  # +1: \r vor \n
                    self._overflow = True
                    self._buf.clear()
                    continue
                self._buf.append(b)
                continue
            if self._overflow:
                self._overflow = False
                self._discard("TOO_LONG", b"")
                continue
            line = bytes(self._buf)
            self._buf.clear()
            if line.endswith(b"\r"):
                line = line[:-1]
            if not line:
                continue
            self._handle_line(line, done)

    def _discard(self, code: str, line: bytes) -> None:
        self.discarded[code] += 1
        text = line.decode("ascii", errors="replace")
        if code == "NO_START":
            self._log.info("ESP| %s", text)
        else:
            self._log.warning("verworfen (%s): %s", code, text)

    def _handle_line(self, line: bytes, done: list) -> None:
        try:
            msg = decode(line)
        except DecodeError as e:
            self._discard(e.code, line)
            return
        self._log.debug("<- %s", line.decode("ascii", "replace"))
        role = role_of(msg.command)
        if role == "response":
            if self._future is None or self._pending is None or msg.seq != self._pending.seq:
                return
            fut, self._future, self._pending = self._future, None, None
            done.append((fut, msg))
            return
        if self._rx_seq == msg.seq:
            if not self._in_progress and self._last_reply:
                self._write(self._last_reply)
            return
        self._rx_seq = msg.seq
        self._last_reply = b""
        if msg.command == "PING":
            self._in_progress = False
            self._last_reply = encode(Message(msg.seq, "PONG"))
            self._write(self._last_reply)
        elif role != "esp_request":
            self._in_progress = False
            self._last_reply = encode(Message(msg.seq, "ERROR", "UNKNOWN"))
            self._write(self._last_reply)
        else:
            self._in_progress = True
            self.incoming.put(msg)

    def _timers(self, done: list) -> None:
        if self._future is None:
            return
        now = self._clock()
        if now - self._start_t >= deadline_ms(self._pending.command) / 1000.0:
            fut, self._future, self._pending = self._future, None, None
            done.append((fut, None))
        elif now - self._last_sent >= REPEAT_S:
            self._last_sent = now
            self._write(self._pending_frame)

    # --- Thread --------------------------------------------------------------
    def _run(self) -> None:
        try:
            while not self._stop.is_set():
                self.poll()
        except Exception:
            self._log.exception("Verbindung zum ESP abgebrochen")
            with self._lock:
                self._dead = True
                fut, self._future, self._pending = self._future, None, None
            if fut is not None:
                fut.set_result(None)

    def start(self) -> None:
        self._stop.clear()
        self._thread = threading.Thread(target=self._run, name="pi-link", daemon=True)
        self._thread.start()

    def stop(self, timeout: float = 2.0) -> None:
        self._stop.set()
        if self._thread is not None:
            self._thread.join(timeout)
