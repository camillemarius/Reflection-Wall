"""Radar-Umschaltung (F4): die UART des Dienstes vom ESP an das Radar und zurueck.

Hin:    MODE|RADAR, OK abwarten -> PiLink.pause() -> GPIO23 HIGH -> 115 200 Baud.
Zurueck: 74 880 Baud -> GPIO23 LOW -> PiLink.resume() -> MODE|NORMAL alle 0,25 s
        bis OK, hoechstens 30 s.
Benutzt den Port und GPIO23, die der Dienst schon hat; keine Anwendung oeffnet sie.
Als Kontextmanager laeuft leave() immer, auch wenn enter() mittendrin scheitert.
"""
import concurrent.futures
import logging
import time
from typing import Callable

from app.link.codec import deadline_ms
from app.link.pi_link import REPEAT_S, LinkBusy
from app.link.serial_port import ESP_BAUD

log = logging.getLogger(__name__)

RADAR_BAUD = 115200
NORMAL_TIMEOUT_S = 30.0
# PiLink beendet eine Anfrage nach ihrer Frist selbst; das hier ist nur die Sicherung
REQUEST_WAIT_S = deadline_ms("MODE") / 1000.0 + 1.0


class RadarSwitchError(RuntimeError):
    pass


class RadarUart:
    """Was UARTDevice/UARTHLK von einer UART brauchen, auf dem pyserial-Objekt des Dienstes."""

    def __init__(self, serial) -> None:
        self._serial = serial

    def select(self, device) -> None:
        pass  # umgeschaltet hat RadarSwitch

    def write(self, data: bytes) -> None:
        self._serial.write(data)
        self._serial.flush()

    def read(self, size: int = 1) -> bytes:
        return self._serial.read(size)

    def readline(self) -> bytes:
        return self._serial.readline()

    @property
    def available(self) -> int:
        return self._serial.in_waiting

    def read_all(self) -> bytes:
        return self._serial.read_all()


class RadarSwitch:
    def __init__(self, link, port, clock: Callable[[], float] = time.monotonic,
                 sleep: Callable[[float], None] = time.sleep,
                 normal_timeout_s: float = NORMAL_TIMEOUT_S) -> None:
        self._link = link
        self._port = port
        self._clock = clock
        self._sleep = sleep
        self._normal_timeout_s = normal_timeout_s
        self._forget()

    def _forget(self) -> None:
        # Jeder Schritt wird vor dem Versuch vermerkt: auch ein halber Schritt wird zurueckgenommen.
        self._esp_in_radar = False
        self._paused = False
        self._selected = False
        self._baud_changed = False

    @staticmethod
    def _answer(fut, timeout: float):
        try:
            return fut.result(timeout=max(0.0, timeout))
        except concurrent.futures.TimeoutError:
            return None

    def enter(self) -> RadarUart:
        fut = self._link.request("MODE", "RADAR")
        self._esp_in_radar = True  # das OK kann verloren gehen, obwohl der ESP umgeschaltet hat
        answer = self._answer(fut, REQUEST_WAIT_S)
        if answer is None:
            raise RadarSwitchError("ESP antwortet nicht auf MODE|RADAR")
        if answer.command != "OK":
            self._esp_in_radar = False
            raise RadarSwitchError("ESP lehnt MODE|RADAR ab: %s %s" % (answer.command, answer.data))
        self._paused = True
        self._link.pause()
        self._selected = True
        self._port.select_radar(True)
        self._baud_changed = True
        self._port.set_baud(RADAR_BAUD)
        self._port.serial.reset_input_buffer()  # Bytes von vor dem Umschalten sind nicht vom Radar
        return RadarUart(self._port.serial)

    def leave(self) -> bool:
        """Schaltet zurueck, was enter() umgeschaltet hat. True, wenn alles geklappt hat."""
        ok = True
        if self._baud_changed:
            ok &= self._step("74 880 Baud", lambda: self._port.set_baud(ESP_BAUD))
        if self._selected:
            ok &= self._step("GPIO23 LOW", lambda: self._port.select_radar(False))
        if self._paused:
            ok &= self._step("PiLink.resume", self._link.resume)
        if self._esp_in_radar:
            ok &= self._send_normal()
        self._forget()
        return ok

    @staticmethod
    def _step(name: str, action: Callable[[], None]) -> bool:
        try:
            action()
            return True
        except Exception:
            log.exception("Zurueckschalten: %s fehlgeschlagen", name)
            return False

    def _send_normal(self) -> bool:
        deadline = self._clock() + self._normal_timeout_s
        while True:
            try:
                fut = self._link.request("MODE", "NORMAL")
            except LinkBusy:
                pass
            else:
                answer = self._answer(fut, deadline - self._clock())
                if answer is not None and answer.command == "OK":
                    return True
            if self._clock() >= deadline:
                log.error("MODE|NORMAL nach %.0f s ohne OK", self._normal_timeout_s)
                return False
            self._sleep(REPEAT_S)

    def __enter__(self) -> RadarUart:
        try:
            return self.enter()
        except BaseException:
            self.leave()
            raise

    def __exit__(self, exc_type, exc, tb) -> bool:
        self.leave()
        return False
