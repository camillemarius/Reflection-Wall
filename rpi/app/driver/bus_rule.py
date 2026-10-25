"""Regel B auf dem Pi: der Pi haelt den I2C-Bus frei, wenn der ESP ihn nimmt.

Ein Tastendruck oder eine Radar-Flanke setzt den ESP zurueck; 60 bis 100 ms
spaeter nimmt er den Bus, liest den Expander und gibt ihn zurueck, ohne zu
fragen. Der Pi sieht INT_GPIO_EXP auf GPIO4 (LOW = ungelesene Aenderung) und
INT_HLK auf GPIO22. Der BusGuard laesst eine laufende Uebertragung in Ruhe,
beginnt aber keine neue, solange GPIO4 LOW ist, bis free_s nach dessen
steigender Flanke, und bis radar_pause_s nach einer steigenden Flanke auf
GPIO22 (R3: GPIO4 bleibt nach einer Radar-Flanke HIGH). Nach max_wait_s geht
es mit Warnung weiter. lgpio wird erst in start() geladen (R13: GPIO22 gehoert
dem Guard, radar_high() liefert ihn weiter).
"""
import logging
import threading
import time
from contextlib import contextmanager

log = logging.getLogger(__name__)

GPIO_CHIP = 0
EXPANDER_INT_GPIO = 4   # INT_GPIO_EXP, LOW = ungelesene Aenderung
RADAR_GPIO = 22         # INT_HLK, HIGH = Person
FREE_S = 0.005          # T_bus_frei
RADAR_PAUSE_S = 0.25
MAX_WAIT_S = 1.0
POLL_S = 0.001


class BusGuard:
    def __init__(self, lgpio_module=None, clock=time.monotonic,
                 sleep=time.sleep, free_s: float = FREE_S,
                 radar_pause_s: float = RADAR_PAUSE_S,
                 max_wait_s: float = MAX_WAIT_S) -> None:
        self._lgpio = lgpio_module
        self._clock = clock
        self._sleep = sleep
        self._free_s = free_s
        self._radar_pause_s = radar_pause_s
        self._max_wait_s = max_wait_s
        self._lock = threading.Lock()
        self._exp_rise = None
        self._radar_rise = None
        self._handle = None
        self._callbacks = []
        self._claimed = []

    def _load(self):
        if self._lgpio is not None:
            return self._lgpio
        import lgpio  # erst hier: auf dem PC nicht installiert
        return lgpio

    def start(self) -> None:
        if self._handle is not None:
            return
        try:
            lg = self._load()
            self._lgpio = lg
            handle = lg.gpiochip_open(GPIO_CHIP)
            self._handle = handle
            for gpio, pull in ((EXPANDER_INT_GPIO, lg.SET_PULL_UP),
                               (RADAR_GPIO, lg.SET_PULL_DOWN)):
                lg.gpio_claim_alert(handle, gpio, lg.BOTH_EDGES, pull)
                self._claimed.append(gpio)
                self._callbacks.append(
                    lg.callback(handle, gpio, lg.BOTH_EDGES, self._on_edge))
        except Exception as exc:  # ImportError, OSError, lgpio-Fehler
            log.warning("BusGuard ohne lgpio, wartet nie: %s", exc)
            self.stop()
            self._lgpio = None
            self._handle = None

    def _on_edge(self, chip, gpio, level, timestamp) -> None:
        # laeuft im lgpio-Thread; Zeit aus der eingespeisten Uhr
        if level != 1:
            return
        now = self._clock()
        with self._lock:
            if gpio == EXPANDER_INT_GPIO:
                self._exp_rise = now
            elif gpio == RADAR_GPIO:
                self._radar_rise = now

    def _must_wait(self, now: float) -> bool:
        try:
            exp_high = bool(self._lgpio.gpio_read(self._handle,
                                                  EXPANDER_INT_GPIO))
        except Exception:
            return False
        if not exp_high:
            return True
        with self._lock:
            exp_rise, radar_rise = self._exp_rise, self._radar_rise
        if exp_rise is not None and now < exp_rise + self._free_s:
            return True
        return radar_rise is not None and now < radar_rise + self._radar_pause_s

    def _wait(self) -> None:
        if self._handle is None:
            return
        start = self._clock()
        while self._must_wait(self._clock()):
            if self._clock() - start >= self._max_wait_s:
                log.warning("I2C-Bus nach %.1f s nicht frei, Uebertragung "
                            "beginnt trotzdem", self._max_wait_s)
                return
            self._sleep(POLL_S)

    @contextmanager
    def _transfer(self):
        self._wait()
        yield

    def __call__(self):
        return self._transfer()

    def radar_high(self) -> bool:
        if self._handle is None:
            return False
        try:
            return bool(self._lgpio.gpio_read(self._handle, RADAR_GPIO))
        except Exception:
            return False

    def stop(self) -> None:
        callbacks, self._callbacks = self._callbacks, []
        claimed, self._claimed = self._claimed, []
        handle, self._handle = self._handle, None
        for cb in callbacks:
            try:
                cb.cancel()
            except Exception:
                pass
        if handle is None or self._lgpio is None:
            return
        for gpio in claimed:
            try:
                self._lgpio.gpio_free(handle, gpio)
            except Exception:
                pass
        try:
            self._lgpio.gpiochip_close(handle)
        except Exception:
            pass
