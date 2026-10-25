import types
import unittest

from app.applications.radar_app import RadarApp
from app.link.radar_switch import RadarSwitchError
from app.ui.app_host import AppContext, StopApp, StopSignal, run_app
from app.ui.buttons import BT1, BT2, BT4, BT5, BT6, ExpanderError, QueueButtons

NO_RADAR = ["RADAR ANTWORTET NICHT", "BT4 ZURUECK"]
RADAR_LIMIT_S = 55 * 60  # R15


class Clock:
    def __init__(self):
        self.now = 0.0

    def __call__(self):
        return self.now


class FakeDisplay:
    WIDTH = 24
    HEIGHT = 4

    def __init__(self, events):
        self.events = events
        self._x = None

    def clear(self):
        self.events.append("clear")

    def clear_canvas(self):
        self.events.append("clear_canvas")

    def set_segments(self, x, y, mask):
        self._x = x

    def refresh(self):
        self.events.append(("draw", self._x))

    def show_lines(self, lines, dots_own_cell=False):
        self.events.append(("lines", list(lines)))


class FakeSwitch:
    def __init__(self, events, error=None):
        self.events = events
        self.error = error
        self.uart = object()

    def __enter__(self):
        self.events.append("enter")
        if self.error is not None:
            raise self.error
        return self.uart

    def __exit__(self, *exc):
        self.events.append("leave")
        return False


class FakeSensor:
    """Je update() ein Eintrag: None = kein Frame, sonst Entfernung in cm (0 = niemand)."""

    def __init__(self, readings):
        self.readings = list(readings)
        self.data = types.SimpleNamespace(timestamp=0.0)
        self.present = False
        self.distance = 0
        self.uart = None

    def update(self):
        reading = self.readings.pop(0) if self.readings else None
        if reading is None:
            return
        self.data.timestamp += 1.0
        self.present = reading > 0
        self.distance = reading


class FakeExpander:
    """Je get() ein Eintrag (Taste, None oder Ausnahme); die Wartezeit laeuft auf der Uhr ab."""

    def __init__(self, events, clock, presses, start_error=None, on_get=None):
        self.events = events
        self.clock = clock
        self.presses = list(presses)
        self.start_error = start_error
        self.on_get = on_get
        self.gets = 0

    def start(self):
        self.events.append("buttons.start")
        if self.start_error is not None:
            raise self.start_error

    def get(self, timeout):
        self.gets += 1
        if self.on_get is not None:
            self.on_get(self.gets)
        self.clock.now += timeout
        press = self.presses.pop(0) if self.presses else None
        if isinstance(press, Exception):
            raise press
        return press

    def drain(self):
        pass


class CountingActivity:
    def __init__(self):
        self.touches = 0

    def touch(self):
        self.touches += 1


class RadarAppTest(unittest.TestCase):
    def setUp(self):
        self.events = []
        self.clock = Clock()
        self.display = FakeDisplay(self.events)
        self.link_buttons = QueueButtons()
        self.activity = CountingActivity()
        self.stop = StopSignal()
        self.ctx = AppContext(self.display, self.link_buttons, self.activity, self.stop)
        self.switch = FakeSwitch(self.events)
        self.sensor = FakeSensor([])
        self.expander = None

    def app(self, presses=(), **kw):
        self.expander = FakeExpander(self.events, self.clock, presses, **kw)

        def sensor_factory(uart):
            self.sensor.uart = uart
            return self.sensor
        return RadarApp(lambda: self.switch, sensor_factory=sensor_factory,
                        buttons_factory=lambda: self.expander, clock=self.clock)

    def display_events(self):
        return [e for e in self.events if e not in ("enter", "leave", "buttons.start")]

    def test_name(self):
        self.assertEqual(RadarApp(lambda: self.switch).name, "RADAR")

    def test_radar_app_bt4(self):
        self.sensor = FakeSensor([100] * 80)  # 8 s lang Daten: kein Abbruch wegen Stille
        app = self.app([None] * 79 + [BT4])
        self.assertEqual(run_app(app, self.ctx), "back")
        self.assertEqual(self.events[:3], ["enter", "buttons.start", "clear"])
        self.assertEqual(self.events[-1], "leave")
        self.assertIs(self.sensor.uart, self.switch.uart)
        self.assertNotIn(("lines", NO_RADAR), self.events)
        self.assertEqual(self.activity.touches, 1)

    def test_bt2_also_switches_back_to_the_menu(self):
        self.assertEqual(run_app(self.app([None, BT2]), self.ctx), "back")
        self.assertEqual(self.events[-1], "leave")
        self.assertEqual(self.expander.gets, 2)

    def test_every_expander_press_counts_as_activity(self):
        self.assertEqual(run_app(self.app([BT5, BT6, BT1, BT4]), self.ctx), "back")
        self.assertEqual(self.activity.touches, 4)

    def test_stickman_follows_the_distance(self):
        self.sensor = FakeSensor([70, 70, 200, 0])
        run_app(self.app([None, None, None, None, BT4]), self.ctx)
        self.assertEqual(self.display_events(),
                         ["clear", "clear_canvas", ("draw", 2), "clear_canvas", ("draw", 21),
                          "clear"])

    def test_no_data_for_5_s_switches_back_and_shows_message(self):
        self.sensor = FakeSensor([100])
        self.link_buttons.put(BT4)
        with self.assertLogs("app.applications.radar_app", "WARNING"):
            self.assertEqual(run_app(self.app(), self.ctx), "back")
        self.assertGreater(self.clock.now, 5.0)
        self.assertLess(self.clock.now, 5.3)
        self.assertEqual(self.events[-2:], ["leave", ("lines", NO_RADAR)])

    def test_stop_signal_leaves_and_ends_with_its_reason(self):
        def idle_after_three(gets):
            if gets == 3:
                self.stop.set("idle")
        app = self.app(on_get=idle_after_three)
        self.assertEqual(run_app(app, self.ctx), "idle")
        self.assertEqual(self.events[-1], "leave")
        self.assertEqual(self.expander.gets, 3)

    def test_expander_error_logs_and_returns_to_the_menu(self):
        app = self.app([None, ExpanderError("Expander 0x20 nicht lesbar")])
        with self.assertLogs("app.applications.radar_app", "ERROR"):
            self.assertEqual(run_app(app, self.ctx), "back")
        self.assertEqual(self.events[-1], "leave")

    def test_expander_error_at_start_logs_and_returns_to_the_menu(self):
        app = self.app(start_error=ExpanderError("Expander 0x20 nicht lesbar"))
        with self.assertLogs("app.applications.radar_app", "ERROR"):
            self.assertEqual(run_app(app, self.ctx), "back")
        self.assertEqual(self.events, ["enter", "buttons.start", "leave"])

    def app_jumping_to(self, now, presses):
        """Der erste Frame endet auf der Uhr der Anwendung bei now; Radar-Daten kommen laufend."""
        def jump(gets):
            if gets == 1:
                self.clock.now = now
        self.sensor = FakeSensor([100] * 5)
        app = self.app(presses, on_get=jump)
        self.expander.clock = Clock()  # nur der Sprung bestimmt die Zeit
        return app

    def test_after_55_min_switches_back_clears_and_ends_idle(self):
        # R15: nach 55 min Radar endet die Anwendung selbst, damit der Pi ums Ausschalten bittet
        app = self.app_jumping_to(RADAR_LIMIT_S, [None, BT4])
        with self.assertRaises(StopApp) as stopped:
            app.run(self.ctx)
        self.assertEqual(stopped.exception.reason, "idle")
        self.assertEqual(self.events[-2:], ["leave", "clear"])
        self.assertEqual(self.expander.gets, 1)

    def test_just_under_55_min_keeps_running(self):
        app = self.app_jumping_to(RADAR_LIMIT_S - 0.1, [None, BT4])
        self.assertEqual(run_app(app, self.ctx), "back")
        self.assertEqual(self.expander.gets, 2)
        self.assertEqual(self.events[-1], "leave")

    def test_failed_switch_shows_the_error_screen_without_reading_buttons(self):
        self.switch = FakeSwitch(self.events, error=RadarSwitchError("kein OK auf MODE|RADAR"))
        self.link_buttons.put(BT4)
        with self.assertLogs("app.ui.app_host", "ERROR"):
            self.assertEqual(run_app(self.app(), self.ctx), "error")
        self.assertEqual(self.events, ["enter", ("lines", ["FEHLER IN RADAR", "BT4 ZURUECK"])])


if __name__ == "__main__":
    unittest.main()
