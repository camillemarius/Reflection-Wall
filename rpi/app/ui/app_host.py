# ui/app_host.py
# Rahmen fuer Anwendungen: Tasten, Stopp, Blockierendes ohne Haenger, Fehlerbild.
# Anwendungen rufen nie input(); sie bekommen einen AppContext.
import logging
import queue
import threading
from pathlib import Path
from typing import Any, Callable, Optional, Protocol

from app.driver.display.cells import normalize
from app.driver.display.text_layout import wrap
from app.ui.buttons import BT4, BT5
from app.ui.pages import paginate

log = logging.getLogger(__name__)

POLL_S = 0.05
DEFAULT_CONFIG_DIR = Path(__file__).resolve().parent.parent / "config"


class StopApp(Exception):
    """Beendet die Anwendung. Grund: "back" (BT4), "shutdown" oder "idle"."""

    def __init__(self, reason: str = "back") -> None:
        super().__init__(reason)
        self.reason = reason


class StopSignal:
    """Thread-sicheres Stoppsignal mit Grund; der erste Grund gilt."""

    def __init__(self) -> None:
        self._event = threading.Event()
        self._lock = threading.Lock()
        self._reason: Optional[str] = None

    def set(self, reason: str) -> None:
        with self._lock:
            if self._reason is None:
                self._reason = reason
        self._event.set()

    def is_set(self) -> bool:
        return self._event.is_set()

    @property
    def reason(self) -> Optional[str]:
        return self._reason

    def wait(self, timeout: Optional[float] = None) -> bool:
        return self._event.wait(timeout)


class AppContext:
    def __init__(self, display, buttons, activity, stop_event: StopSignal,
                 radar=None, config_dir=DEFAULT_CONFIG_DIR) -> None:
        self.display = display
        self.buttons = buttons
        self.activity = activity
        self.stop_event = stop_event
        self.radar = radar
        self.config_dir = Path(config_dir)

    def _check_stop(self) -> None:
        if self.stop_event.is_set():
            raise StopApp(self.stop_event.reason or "shutdown")

    def _press(self, button: int) -> int:
        self.activity.touch()
        if button == BT4:
            raise StopApp("back")
        return button

    def wait_button(self, timeout: Optional[float] = None) -> Optional[int]:
        """Naechste Taste; BT4 und das Stoppsignal werfen StopApp."""
        remaining = timeout
        while True:
            self._check_stop()
            step = POLL_S if remaining is None else min(POLL_S, remaining)
            button = self.buttons.get(step)
            if button is not None:
                return self._press(button)
            if remaining is not None:
                remaining -= step
                if remaining <= 0:
                    self._check_stop()
                    return None

    def run_blocking(self, fn: Callable[..., Any], *args) -> Any:
        """fn in einem Thread; BT4 oder Stopp brechen das Warten ab (Ergebnis verworfen)."""
        self._check_stop()
        stale_back = False
        while True:
            button = self.buttons.get(0)
            if button is None:
                break
            self.activity.touch()
            stale_back = stale_back or button == BT4
        if stale_back:
            raise StopApp("back")

        done = queue.Queue(maxsize=1)

        def work() -> None:
            try:
                done.put((True, fn(*args)))
            except BaseException as exc:  # an den Aufrufer weiterreichen
                done.put((False, exc))

        with self.activity.busy():
            threading.Thread(target=work, name="run-blocking", daemon=True).start()
            while True:
                try:
                    outcome = done.get(timeout=POLL_S)
                except queue.Empty:
                    outcome = None
                # Auch nach dem Ende der Arbeit: Tasten aus dem letzten Intervall
                # wirken nicht auf den naechsten Bildschirm.
                self._check_stop()
                self._drop_presses()
                if outcome is None:
                    continue
                ok, value = outcome
                if ok:
                    return value
                raise value

    def _drop_presses(self) -> None:
        """Wartende Tasten verwerfen; BT4 wirft StopApp("back")."""
        while True:
            button = self.buttons.get(0)
            if button is None:
                return
            self._press(button)

    def show_pages(self, text: str) -> None:
        pages = paginate(normalize(text))
        for number, page in enumerate(pages):
            self.display.show_lines(page)
            if number == len(pages) - 1:
                return
            while self.wait_button() != BT5:
                pass


class App(Protocol):
    name: str

    def run(self, ctx: AppContext) -> None: ...


def _error_title(name: str) -> list[str]:
    """FEHLER IN <NAME>, an Wortgrenzen auf hoechstens zwei Zeilen umgebrochen."""
    rows, _ = wrap("FEHLER IN " + normalize(name))
    return [row.rstrip() for row in rows if row.strip()][:2]


def run_app(app: App, ctx: AppContext) -> str:
    """Startet app. Rueckgabe: "back", "shutdown", "idle" oder "error"."""
    try:
        app.run(ctx)
        return "back"
    except StopApp as stop:
        return stop.reason
    except Exception:
        log.exception("Anwendung %s ist abgestuerzt", app.name)
    try:
        ctx.display.show_lines(_error_title(app.name) + ["BT4 ZURUECK"])
        while True:
            ctx.wait_button()
    except StopApp as stop:
        return "error" if stop.reason == "back" else stop.reason
