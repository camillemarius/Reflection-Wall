# settings_apps.py
# Einstellungen: THEMA AENDERN (Webseite auf dem Pi) und RADAR EINRICHTEN (vorerst Platzhalter).
import time
from typing import Callable, Tuple

from app.driver.display.cells import normalize
from app.topics import CONFIG_DIR
from app.ui.app_host import AppContext
from app.web.topic_server import TopicServer, wall_address

TIMEOUT_S = 15 * 60
POLL_S = 1.0


def default_server_factory(config_dir=CONFIG_DIR) -> Callable[[Callable[[], None]], TopicServer]:
    return lambda on_save: TopicServer(config_dir, on_save=on_save)


class ThemaApp:
    name = "THEMA AENDERN"

    def __init__(self, server_factory=None, clock: Callable[[], float] = time.monotonic,
                 address: Callable[[], Tuple[str, str]] = wall_address) -> None:
        self._factory = server_factory or default_server_factory()
        self._clock = clock
        self._address = address

    def run(self, ctx: AppContext) -> None:
        deadline = [self._clock() + TIMEOUT_S]

        def on_save() -> None:
            deadline[0] = self._clock() + TIMEOUT_S
            ctx.activity.touch()

        server = self._factory(on_save)
        try:
            try:
                server.start()
            except OSError:
                ctx.display.show_lines(["WEBSEITE GEHT NICHT", "BT4 ZURUECK"])
                while True:
                    ctx.wait_button()
            host, ip = self._address()
            ctx.display.show_lines(["WEBSEITE IM BROWSER", normalize(host),
                                    "ODER " + normalize(ip), "BT4 BEENDET SIE"],
                                   dots_own_cell=True)
            while self._clock() < deadline[0]:
                ctx.wait_button(timeout=POLL_S)
            ctx.display.show_lines(["WEBSEITE AUS"])
            ctx.wait_button(timeout=2.0)
        finally:
            server.stop()


class RadarSetupPlaceholder:
    name = "RADAR EINRICHTEN"

    def run(self, ctx: AppContext) -> None:
        ctx.display.show_lines(["RADAR EINRICHTEN", "KOMMT SPAETER", "BT4 ZURUECK"])
        while True:
            ctx.wait_button()
