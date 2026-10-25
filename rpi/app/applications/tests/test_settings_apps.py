import unittest

from app.applications.settings_apps import RadarSetupPlaceholder, ThemaApp
from app.ui.activity import Activity
from app.ui.app_host import AppContext, StopApp, StopSignal
from app.ui.buttons import BT4


class FakeDisplay:
    def __init__(self):
        self.lines = []
        self.own_cell = []

    def show_lines(self, lines, dots_own_cell=False):
        self.lines.append(list(lines))
        self.own_cell.append(dots_own_cell)


class Buttons:
    def __init__(self, script=None):
        self.script = list(script or [])

    def get(self, timeout):
        return self.script.pop(0) if self.script else None

    def drain(self):
        pass


class FakeServer:
    def __init__(self, on_save, fail=False):
        self.on_save = on_save
        self.fail = fail
        self.started = self.stopped = 0

    def start(self):
        self.started += 1
        if self.fail:
            raise OSError("port 80")

    def stop(self):
        self.stopped += 1


class Clock:
    def __init__(self):
        self.now = 0.0

    def __call__(self):
        return self.now


def make(buttons, servers, fail=False, clock=None, stop=None, activity=None):
    display = FakeDisplay()
    ctx = AppContext(display, buttons, activity or Activity(), stop or StopSignal())

    def factory(on_save):
        server = FakeServer(on_save, fail)
        servers.append(server)
        return server

    app = ThemaApp(factory, clock=clock or Clock(),
                   address=lambda: ("wall.local", "192.168.1.50"))
    return app, ctx, display


class ThemaAppTest(unittest.TestCase):
    def test_name(self):
        self.assertEqual(ThemaApp(lambda on_save: None).name, "THEMA AENDERN")

    def test_shows_address_with_own_cell_dots(self):
        servers = []
        app, ctx, display = make(Buttons([BT4]), servers)
        with self.assertRaises(StopApp):
            app.run(ctx)
        self.assertEqual(display.lines[0], ["WEBSEITE IM BROWSER", "WALL.LOCAL",
                                            "ODER 192.168.1.50", "BT4 BEENDET SIE"])
        self.assertTrue(display.own_cell[0])

    def test_thema_app_stops_server_on_bt4(self):
        servers = []
        app, ctx, _ = make(Buttons([BT4]), servers)
        with self.assertRaises(StopApp):
            app.run(ctx)
        self.assertEqual((servers[0].started, servers[0].stopped), (1, 1))

    def test_stops_server_on_stop_signal(self):
        servers = []
        stop = StopSignal()
        stop.set("shutdown")
        app, ctx, _ = make(Buttons(), servers, stop=stop)
        with self.assertRaises(StopApp):
            app.run(ctx)
        self.assertEqual(servers[0].stopped, 1)

    def test_stops_server_on_error(self):
        servers = []

        class Boom(Buttons):
            def get(self, timeout):
                raise RuntimeError("x")

        app, ctx, _ = make(Boom(), servers)
        with self.assertRaises(RuntimeError):
            app.run(ctx)
        self.assertEqual(servers[0].stopped, 1)

    def test_thema_app_timeout(self):
        servers = []
        clock = Clock()

        class Ticking(Buttons):
            def get(self, timeout):
                clock.now += 400.0
                return None

        app, ctx, display = make(Ticking(), servers, clock=clock)
        app.run(ctx)  # kehrt zurueck, kein StopApp
        self.assertEqual(display.lines[-1][0], "WEBSEITE AUS")
        self.assertEqual(servers[0].stopped, 1)

    def test_save_restarts_the_timer_and_touches_activity(self):
        servers = []
        clock = Clock()
        activity = Activity(clock=clock)
        polls = {"n": 0}

        class Script(Buttons):
            def get(self, timeout):
                polls["n"] += 1
                clock.now += 400.0
                if polls["n"] == 2:  # 800 s: gespeichert
                    servers[0].on_save()
                if polls["n"] == 4:  # 1600 s, 800 s nach dem Speichern: noch offen
                    return BT4
                return None

        app, ctx, display = make(Script(), servers, clock=clock, activity=activity)
        with self.assertRaises(StopApp):
            app.run(ctx)
        self.assertNotEqual(display.lines[-1][0], "WEBSEITE AUS")
        self.assertEqual(activity._last, 1600.0)  # BT4 beim 4. Aufruf; Speichern bei 800 hat berührt

    def test_save_touches_activity_at_save_time(self):
        servers = []
        clock = Clock()
        activity = Activity(clock=clock)
        seen = {}

        class Script(Buttons):
            def get(self, timeout):
                clock.now += 10.0
                if not seen:
                    servers[0].on_save()
                    seen["touched"] = activity._last
                    return BT4
                return None

        app, ctx, _ = make(Script(), servers, clock=clock, activity=activity)
        with self.assertRaises(StopApp):
            app.run(ctx)
        self.assertEqual(seen["touched"], 10.0)

    def test_server_cannot_start(self):
        servers = []
        app, ctx, display = make(Buttons([BT4]), servers, fail=True)
        with self.assertRaises(StopApp):
            app.run(ctx)
        self.assertEqual(display.lines[-1][:2], ["WEBSEITE GEHT NICHT", "BT4 ZURUECK"])
        self.assertEqual(servers[0].stopped, 1)


class RadarSetupPlaceholderTest(unittest.TestCase):
    def test_shows_placeholder_until_bt4(self):
        display = FakeDisplay()
        ctx = AppContext(display, Buttons([BT4]), Activity(), StopSignal())
        app = RadarSetupPlaceholder()
        self.assertEqual(app.name, "RADAR EINRICHTEN")
        with self.assertRaises(StopApp):
            app.run(ctx)
        self.assertEqual(display.lines[0][:3], ["RADAR EINRICHTEN", "KOMMT SPAETER", "BT4 ZURUECK"])


if __name__ == "__main__":
    unittest.main()
