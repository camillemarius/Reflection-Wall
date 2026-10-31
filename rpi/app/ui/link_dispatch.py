# ui/link_dispatch.py
# Verbindet die Anfragen des ESP (PiLink.incoming) mit dem Menue: Tasten, Sitzung und Ausschalten;
# dazu das Zitat der Nacht (GET).
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
QUOTE_PREFIX = "QUOTE|"  # Daten von GET: QUOTE|<Text vom Vortag>, leer = neue Kette


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
                 start_timer=_start_timer,
                 quote_maker: Callable[[str], tuple[str, str]] = None):
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
        self.hand_requested = threading.Event()  # SESSION|HAND nach NACHT (N3)
        self.shutdown_done = threading.Event()
        self._shutdown_lock = threading.Lock()
        self._quote_maker = quote_maker
        self._get_lock = threading.Lock()
        self._newest_get = None  # das neueste GET, solange der Arbeits-Thread rechnet
        # (Text vom Vortag, ("QUOTE", Text)): das letzte Zitat der Nacht in dieser Sitzung. Ein
        # ERROR bleibt nicht gemerkt: ein spaeterer Versuch in derselben Sitzung fragt neu.
        self._night_result = None
        self._session_over = False  # nach SHUTDOWN oder stop(): kein Ergebnis mehr merken

    def start(self) -> None:
        if self._thread is not None and self._thread.is_alive():
            return
        self._end.clear()
        self._thread = threading.Thread(target=self._run, name="link-dispatch", daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._end_night_session()
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
        elif msg.command == "GET":
            self._get(msg)
        else:
            self.other.put(msg)

    def _session(self, msg) -> None:
        if msg.data not in ("HAND", "NACHT"):
            self._link.reply(msg, "ERROR", "BAD_SESSION")
            return
        self._link.reply(msg, "OK")
        if self.session_event.is_set():
            if self.session_reason == "NACHT" and msg.data == "HAND":
                # BT2 in der Nacht (N3): ab jetzt eine Sitzung von Hand, main() startet das Menue
                log.info("SESSION|HAND nach NACHT: weiter mit dem Menue")
                self.session_reason = "HAND"
                self.hand_requested.set()
                return
            log.info("SESSION|%s noch einmal, ignoriert (Grund bleibt %s)",
                     msg.data, self.session_reason)
            return
        self.session_reason = msg.data
        self.session_event.set()

    def _get(self, msg) -> None:
        """GET|QUOTE|<Text vom Vortag>: das Zitat rechnet ein Arbeits-Thread, damit BUTTON,
        SESSION und SHUTDOWN weiterlaufen (R10). Kommt GET noch einmal, waehrend er rechnet (neue
        Nummer nach einem Reset des ESP, R8; jede Taste ist ein Reset), startet kein zweiter; die
        Antwort geht an das neueste GET. Der ESP beachtet ohnehin nur die Antwort auf sein
        neuestes, und PiLink nimmt nur diese an. Kommt es erst, nachdem er ein Zitat geliefert
        hat, und mit demselben Text vom Vortag, antwortet der Pi mit diesem Zitat, ohne zweite
        KI-Runde (Fall C: die Antwort auf das alte GET ging nicht mehr raus)."""
        if not msg.data.startswith(QUOTE_PREFIX):
            self._link.reply(msg, "ERROR", "BAD_GET")
            return
        if self._quote_maker is None:
            self._link.reply(msg, "ERROR", "KI")
            return
        yesterday = msg.data[len(QUOTE_PREFIX):]
        with self._get_lock:
            running = self._newest_get is not None
            known = self._night_result
            if not running and known is not None and known[0] == yesterday:
                answer = known[1]
            else:
                answer = None
                self._newest_get = msg
            if running:
                log.info("GET #%02X, waehrend das Zitat noch entsteht: die Antwort geht an "
                         "diese Nummer", msg.seq)
                return
            if answer is None:
                worker = threading.Thread(target=self._answer_get, args=(yesterday,),
                                          name="night-quote", daemon=True)
                try:
                    worker.start()
                except RuntimeError:
                    self._newest_get = None  # sonst bliebe jedes weitere GET ohne Antwort
                    log.exception("Arbeits-Thread fuer GET nicht gestartet")
                    answer = ("ERROR", "KI")
                else:
                    return
            else:
                log.info("GET #%02X: das Zitat dieser Sitzung ist schon da, keine zweite "
                         "KI-Runde", msg.seq)
        self._send_get_answer(msg, *answer)

    def _answer_get(self, yesterday) -> None:
        """Arbeits-Thread: fragt quote_maker und beantwortet das neueste GET, auch wenn
        quote_maker wirft (dann ERROR|KI): Ein GET bleibt nie ohne Antwort. Ein Zitat bleibt
        fuer diese Sitzung gemerkt (_get). Auch nach einer BaseException gilt kein GET mehr als
        offen; sonst bliebe jedes weitere ohne Antwort."""
        result = None
        try:
            try:
                command, data = self._quote_maker(yesterday)
            except Exception:
                log.exception("Zitat der Nacht nicht erstellt")
                command, data = "ERROR", "KI"
            result = (command, data)
        finally:
            with self._get_lock:  # danach startet ein neues GET einen neuen Thread
                msg, self._newest_get = self._newest_get, None
                if result is not None and result[0] == "QUOTE" and not self._session_over:
                    self._night_result = (yesterday, result)
        self._send_get_answer(msg, *result)

    def _send_get_answer(self, msg, command, data) -> None:
        log.info("Antwort auf GET #%02X: %s|%s", msg.seq, command, data)
        try:
            sent = self._link.reply(msg, command, data)
        except Exception:
            log.exception("Antwort auf GET #%02X nicht gesendet", msg.seq)
            return
        if not sent:
            # PiLink.reply gibt nur False: welcher Grund es war, sieht der Dispatcher nicht
            log.info("Antwort auf GET #%02X nicht gesendet: PiLink nimmt sie nicht an (die "
                     "Anfrage ist nicht mehr offen, die Leitung ist an das Radar abgegeben, oder "
                     "die Antwort laesst sich nicht kodieren)", msg.seq)

    def _end_night_session(self) -> None:
        """Die Sitzung ist zu Ende (SHUTDOWN oder stop): das gemerkte Ergebnis verfaellt."""
        with self._get_lock:
            self._session_over = True
            self._night_result = None

    def _shutdown(self, msg) -> None:
        if self.radar_writing.is_set():
            self._link.reply(msg, "BUSY")
            return
        self._end_night_session()
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
