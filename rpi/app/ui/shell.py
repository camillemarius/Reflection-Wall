# ui/shell.py
# Bildschirmfolge: Hauptmenue, Einstellungen als Untermenue, eine Anwendung zur Zeit.
import threading
from typing import Optional, Sequence

from app.ui.app_host import App, AppContext, StopSignal, run_app
from app.ui.buttons import BT4, BT5, BT6
from app.ui.menu import Menu

SETTINGS_NAME = "EINSTELLUNGEN"
POLL_S = 0.05
_BACK = -1
_STOPPED = -2


class Shell:
    def __init__(self, display, buttons, apps: Sequence[App], settings: Sequence[App],
                 activity, stop_event: StopSignal) -> None:
        self._display = display
        self._buttons = buttons
        self._apps = list(apps)
        self._settings = list(settings)
        self._activity = activity
        self._stop = stop_event
        self._ctx = AppContext(display, buttons, activity, stop_event)
        self.display_released = threading.Event()

    def run(self) -> str:
        try:
            return self._run()
        finally:
            self.display_released.set()

    def _reason(self) -> str:
        return self._stop.reason or "shutdown"

    def _choose(self, menu: Menu, allow_back: bool) -> int:
        """Index des gewaehlten Punktes, _BACK oder _STOPPED."""
        self._display.show_lines(menu.lines())
        while True:
            if self._stop.is_set():
                return _STOPPED
            button = self._buttons.get(POLL_S)
            if button is None:
                continue
            self._activity.touch()
            if button == BT6:
                menu.down()
                self._display.show_lines(menu.lines())
            elif button == BT5:
                return menu.selected
            elif button == BT4 and allow_back:
                return _BACK

    def _launch(self, app: App) -> Optional[str]:
        """Startet app; gibt den Stoppgrund zurueck, wenn die Bildschirmfolge enden soll."""
        self._buttons.drain()
        result = run_app(app, self._ctx)
        if result in ("shutdown", "idle"):
            return result
        return None

    def _run(self) -> str:
        main = Menu([app.name for app in self._apps] + [SETTINGS_NAME])
        settings_index = len(self._apps)
        while True:
            choice = self._choose(main, allow_back=False)
            if choice == _STOPPED:
                return self._reason()
            if choice < settings_index:
                reason = self._launch(self._apps[choice])
                if reason:
                    return reason
                continue
            sub = Menu([app.name for app in self._settings])
            while True:
                choice = self._choose(sub, allow_back=True)
                if choice == _STOPPED:
                    return self._reason()
                if choice == _BACK:
                    break
                reason = self._launch(self._settings[choice])
                if reason:
                    return reason
