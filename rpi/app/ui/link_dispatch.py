# ui/link_dispatch.py
# Verbindet die Anfragen des ESP (PiLink.incoming) mit dem Menue: Tasten, Sitzung und Ausschalten.
import concurrent.futures
import logging
import queue
import threading
import time
from typing import Callable

from app.link.pi_link import LinkBusy

log = logging.getLogger(__name__)

RELEASE_WAIT_S = 2.0
POLL_S = 0.1
BUSY_RETRY_S = 0.25
DONE_RESEND_S = 10.0
# Ging das OK auf ein SHUTDOWN nicht raus, weil eine neuere Anfrage es ersetzt hat, faehrt das
# neuere SHUTDOWN herunter. Hat nach dieser Frist keins heruntergefahren, tut es der Pi trotzdem.
REPLACED_SHUTDOWN_FALLBACK_S = 3.0


def _start_timer(delay_s, action):
    """Ruft action nach delay_s einmal auf, in einem eigenen Thread; cancel() verhindert es."""
    timer = threading.Timer(delay_s, action)
    timer.daemon = True
    timer.start()
    return timer


class LinkDispatcher:
    def __init__(self, link, buttons, activity, stop, display_released,
                 on_shutdown: Callable[[], None] = lambda: None,
                 release_wait_s: float = RELEASE_WAIT_S,
                 clock: Callable[[], float] = time.monotonic,
                 sleep: Callable[[float], None] = time.sleep,
                 start_timer=_start_timer):
        self._link = link
        self._buttons = buttons
        self._activity = activity
        self._stop_signal = stop
        self._released = display_released
        self._on_shutdown = on_shutdown
        self._release_wait_s = release_wait_s
        self._clock = clock
        self._sleep = sleep
        self._start_timer = start_timer
        self._fallback_lock = threading.Lock()  # vor _shutdown_lock, nie umgekehrt
        self._fallback = None  # hoechstens ein Zeitgeber je Dispatcher
        self._end = threading.Event()
        self._thread = None
        self.radar_writing = threading.Event()
        self.other: "queue.Queue" = queue.Queue()
        self.session_event = threading.Event()
        self.session_reason = None
        self.shutdown_done = threading.Event()
        self._shutdown_lock = threading.Lock()

    def start(self) -> None:
        if self._thread is not None and self._thread.is_alive():
            return
        self._end.clear()
        self._thread = threading.Thread(target=self._run, name="link-dispatch", daemon=True)
        self._thread.start()

    def stop(self) -> None:
        with self._fallback_lock:  # wartet auf einen laufenden Rueckfall; danach kommt keiner mehr
            self._end.set()
            fallback = self._fallback
        if fallback is not None:
            fallback.cancel()
        thread = self._thread
        if thread is not None and thread is not threading.current_thread():
            thread.join(timeout=0.5)

    def _run(self) -> None:
        while not self._end.is_set():
            try:
                msg = self._link.incoming.get(timeout=POLL_S)
            except queue.Empty:
                continue
            try:
                self._handle(msg)
            except Exception:
                log.exception("Anfrage %s nicht verarbeitet", getattr(msg, "command", "?"))

    def _handle(self, msg) -> None:
        if msg.command == "BUTTON":
            if msg.data in ("1", "2", "3", "4", "5", "6"):
                self._link.reply(msg, "OK")
                self._activity.touch()
                self._buttons.put(int(msg.data))
            else:
                self._link.reply(msg, "ERROR", "BAD_BUTTON")
        elif msg.command == "SESSION":
            self._session(msg)
        elif msg.command == "SHUTDOWN":
            self._shutdown(msg)
        else:
            self.other.put(msg)

    def _session(self, msg) -> None:
        if msg.data not in ("HAND", "NACHT"):
            self._link.reply(msg, "ERROR", "BAD_SESSION")
            return
        self._link.reply(msg, "OK")
        if self.session_event.is_set():
            log.info("SESSION|%s noch einmal, ignoriert (Grund bleibt %s)",
                     msg.data, self.session_reason)
            return
        self.session_reason = msg.data
        self.session_event.set()

    def _shutdown(self, msg) -> None:
        if self.radar_writing.is_set():
            self._link.reply(msg, "BUSY")
            return
        self._stop_signal.set("shutdown")
        if not self._released.wait(self._release_wait_s):
            log.warning("Anzeige nach %.1f s nicht freigegeben", self._release_wait_s)
        if not self._link.reply(msg, "OK"):
            # Waehrend des Wartens kam eine neuere Anfrage (der ESP sendet SHUTDOWN nach einem
            # Reset neu, R8). PiLink kennt nur noch deren Nummer. Das neuere SHUTDOWN steht schon
            # in der Warteschlange: Es bekommt sein OK und faehrt erst danach herunter. Kaeme
            # power_off schon hier, beendete systemd den Dienst vor diesem OK. War die neuere
            # Anfrage kein SHUTDOWN, faehrt der Rueckfall nach der Frist herunter.
            log.info("OK auf SHUTDOWN #%02X nicht gesendet, die Anfrage ist nicht mehr offen; "
                     "herunterfahren wird das neuere SHUTDOWN", msg.seq)
            self._arm_fallback()
            return
        if not self.shut_down_once():
            log.info("SHUTDOWN noch einmal beantwortet, das Herunterfahren laeuft schon")

    def _arm_fallback(self) -> None:
        """Stellt den Zeitgeber auf REPLACED_SHUTDOWN_FALLBACK_S: hoechstens einmal, nie nach
        stop() und nicht, wenn der Pi schon herunterfaehrt."""
        with self._fallback_lock:
            if self._end.is_set() or self._fallback is not None or self.shutdown_done.is_set():
                return
            self._fallback = self._start_timer(REPLACED_SHUTDOWN_FALLBACK_S,
                                               self._fallback_shutdown)

    def _fallback_shutdown(self) -> None:
        """Die Frist ist um. Hat kein neueres SHUTDOWN heruntergefahren, faehrt der Pi jetzt
        herunter. Unter dem Lock, damit nach stop() nichts mehr anlaeuft."""
        with self._fallback_lock:
            if self._end.is_set() or self.shutdown_done.is_set():
                return
            log.warning("Nach %.1f s hat kein neueres SHUTDOWN heruntergefahren; der Pi faehrt "
                        "trotzdem herunter", REPLACED_SHUTDOWN_FALLBACK_S)
            self.shut_down_once()

    def shut_down_once(self) -> bool:
        """Ruft on_shutdown hoechstens einmal auf und setzt danach shutdown_done, auch wenn
        on_shutdown wirft. True nur beim ersten Aufruf. Ein SHUTDOWN kann mehrfach kommen (R8)."""
        with self._shutdown_lock:
            if self.shutdown_done.is_set():
                return False
            try:
                self._on_shutdown()
            except Exception:
                log.exception("Herunterfahren fehlgeschlagen")
            self.shutdown_done.set()
            return True

    def send_done(self, timeout_s: float = 30.0) -> bool:
        deadline = self._clock() + timeout_s
        while self._clock() < deadline:
            try:
                future = self._link.request("DONE")
            except LinkBusy:
                self._sleep(BUSY_RETRY_S)
                continue
            try:
                answer = future.result(timeout=max(0.0, deadline - self._clock()) + 1.0)
            except concurrent.futures.TimeoutError:
                answer = None
            if answer is not None and answer.command == "OK":
                return True
            self._sleep(DONE_RESEND_S)
        return False
