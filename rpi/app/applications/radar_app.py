# applications/radar_app.py
# Radar im Menue (Spec §7): das Strichmaennchen folgt der Entfernung der Person.
# Die Leitung schaltet RadarSwitch (F4); die Tasten liest der Pi solange selbst am Expander.
import logging
import time

from app.driver.display.animations.stickman import Stickman
from app.driver.uart.uart_hlk import UARTHLK
from app.ui.app_host import StopApp
from app.ui.buttons import BT2, BT4, ExpanderButtons, ExpanderError

log = logging.getLogger(__name__)

SENSOR_TIMEOUT_S = 5.0
FRAME_S = 0.1
NO_RADAR = ["RADAR ANTWORTET NICHT", "BT4 ZURUECK"]

_BACK = "back"
_STOPPED = "stopped"
_NO_DATA = "no_data"


class RadarApp:
    name = "RADAR"

    def __init__(self, switch_factory, sensor_factory=UARTHLK, buttons_factory=ExpanderButtons,
                 clock=time.monotonic) -> None:
        self._switch_factory = switch_factory
        self._sensor_factory = sensor_factory
        self._buttons_factory = buttons_factory
        self._clock = clock

    def run(self, ctx) -> None:
        with self._switch_factory() as uart:
            outcome = self._follow(ctx, uart)
        # Zurueckgeschaltet: ab hier kommen die Tasten wieder ueber den ESP.
        if outcome == _STOPPED:
            raise StopApp(ctx.stop_event.reason or "shutdown")
        if outcome == _NO_DATA:
            ctx.display.show_lines(NO_RADAR)
            while True:
                ctx.wait_button()

    def _follow(self, ctx, uart) -> str:
        buttons = self._buttons_factory()
        try:
            buttons.start()
            return self._loop(ctx, self._sensor_factory(uart), buttons)
        except ExpanderError as error:
            log.error("Radar beendet, Tasten nicht lesbar: %s", error)
            return _BACK

    def _loop(self, ctx, sensor, buttons) -> str:
        stickman = Stickman(ctx.display, min_distance=0.7, max_distance=2.0)
        ctx.display.clear()
        last_stamp = sensor.data.timestamp
        last_data = self._clock()
        present = False
        while True:
            if ctx.stop_event.is_set():
                return _STOPPED
            sensor.update()
            now = self._clock()
            if sensor.data.timestamp != last_stamp:
                last_stamp, last_data = sensor.data.timestamp, now
            elif now - last_data > SENSOR_TIMEOUT_S:
                log.warning("Radar: seit %.0f s keine Daten", SENSOR_TIMEOUT_S)
                return _NO_DATA
            if sensor.present:
                present = True
                stickman.show(sensor.distance / 100.0)
            elif present:
                present = False
                stickman.clear()
            button = buttons.get(FRAME_S)
            if button is not None:
                ctx.activity.touch()
                if button in (BT2, BT4):  # nach BT2 faehrt der ESP den Pi selbst herunter (§7)
                    return _BACK
