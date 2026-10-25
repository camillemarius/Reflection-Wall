"""Automatisches Aus: Ablauf nach N Minuten ohne jede Aktivitaet (D2, F6).

Aktivitaet: Tastendruck und Speichern auf der Webseite (touch), Pi arbeitet
(busy), Radar sieht eine Person (person_present). Eine laufende Animation
allein zaehlt nicht.
"""
import os
import threading
import time
from contextlib import contextmanager
from typing import Callable

ENV_NAME = "AUTO_AUS_MINUTEN"
RADAR_GPIO = 22  # INT_HLK, HIGH = Person
GPIO_CHIP = 0


class Activity:
    def __init__(self, clock: Callable[[], float] = time.monotonic,
                 idle_minutes: int = 0,
                 person_present: Callable[[], bool] | None = None) -> None:
        self._clock = clock
        self._idle_s = max(0, idle_minutes) * 60
        self._person_present = person_present
        self._lock = threading.Lock()
        self._busy = 0
        self._last = clock()

    def touch(self) -> None:
        with self._lock:
            self._last = self._clock()

    @contextmanager
    def busy(self):
        with self._lock:
            self._busy += 1
        try:
            yield
        finally:
            with self._lock:
                self._busy -= 1
                self._last = self._clock()

    def expired(self) -> bool:
        # Regelmaessig abfragen: setzt den Zaehler zurueck, solange busy() oder eine Person da ist.
        if self._idle_s == 0:
            return False
        present = bool(self._person_present()) if self._person_present else False
        with self._lock:
            now = self._clock()
            if self._busy > 0 or present:
                self._last = now
                return False
            return now - self._last > self._idle_s


def idle_minutes_from_env(env=os.environ) -> int:
    try:
        minutes = int(str(env.get(ENV_NAME, "0")).strip())
    except ValueError:
        return 0
    return minutes if minutes > 0 else 0


class RadarPresence:
    def __init__(self, gpio: int = RADAR_GPIO, lgpio_module=None) -> None:
        self._gpio = gpio
        self._lgpio = lgpio_module
        self._handle: int | None = None
        self._unavailable = False

    def present(self) -> bool:
        if self._unavailable:
            return False
        if self._lgpio is None:
            try:
                import lgpio as lgpio_module  # erst hier: auf dem PC nicht installiert
            except ImportError:
                self._unavailable = True  # nicht bei jeder Abfrage neu versuchen
                return False
            self._lgpio = lgpio_module
        try:
            if self._handle is None:
                handle = self._lgpio.gpiochip_open(GPIO_CHIP)
                try:
                    # Pull-down: ohne Radar darf der Pin nicht zufaellig HIGH lesen
                    self._lgpio.gpio_claim_input(handle, self._gpio,
                                                 self._lgpio.SET_PULL_DOWN)
                except Exception:
                    self._lgpio.gpiochip_close(handle)
                    raise
                self._handle = handle
            return bool(self._lgpio.gpio_read(self._handle, self._gpio))
        except Exception:
            return False  # kein Radar lesbar: zaehlt nicht als Anwesenheit
