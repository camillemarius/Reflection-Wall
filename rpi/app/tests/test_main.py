import concurrent.futures
import queue
import sys
import threading
import time
import types
import unittest
from unittest import mock

from app import main as app_main
from app.applications import settings_apps
from app.link.codec import Message
from app.ui.activity import Activity
from app.ui.app_host import AppContext, StopApp, StopSignal, run_app
from app.ui.buttons import BT4, QueueButtons


class FakeDisplay:
    def __init__(self, events=None):
        self.shown = []
        self.events = events

    def show_lines(self, lines, dots_own_cell=False):
        self.shown.append(list(lines))
        if self.events is not None:
            self.events.append(("show", list(lines)))

    def start(self):
        pass


class EventLink:
    """Test-Leitung fuer den echten LinkDispatcher: Anfragen des ESP kommen ueber incoming."""

    def __init__(self, events):
        self.incoming = queue.Queue()
        self.events = events

    def reply(self, request, command, data=""):
        self.events.append(("reply", request.command, command))
        return True

    def request(self, command, data=""):
        self.events.append(("request", command))
        fut = concurrent.futures.Future()
        fut.set_result(Message(1, "OK", ""))
        return fut


class FakeLink:
    def __init__(self):
        self.incoming = queue.Queue()
        self.requests = []

    def reply(self, request, command, data=""):
        return True

    def request(self, command, data=""):
        self.requests.append(command)
        fut = concurrent.futures.Future()
        fut.set_result(Message(1, "OK", ""))
        return fut


class FakeApp:
    def __init__(self, name, run=None):
        self.name = name
        self._run = run

    def run(self, ctx):
        if self._run:
            self._run(ctx)
        else:
            while True:
                ctx.wait_button()


def wait_for(cond, timeout=3.0):
    end = time.monotonic() + timeout
    while time.monotonic() < end:
        if cond():
            return True
        time.sleep(0.01)
    return False


def start_wall(display, buttons, activity, stop, **kwargs):
    result = []
    thread = threading.Thread(
        target=lambda: result.append(app_main.run_wall(display, buttons, activity, stop, **kwargs)),
        daemon=True)
    thread.start()
    return thread, result


class BuildAppsTest(unittest.TestCase):
    def test_names_in_order(self):
        apps, settings = app_main.build_apps("cfg")
        self.assertEqual([a.name for a in apps],
                         ["CHAT", "QUIZ", "REFLECTION", "RADAR", "STRICHMAENNCHEN"])
        self.assertEqual([a.name for a in settings], ["THEMA AENDERN", "RADAR EINRICHTEN"])

    def test_radar_app_is_taken_from_argument(self):
        radar = FakeApp("RADAR")
        apps, _ = app_main.build_apps("cfg", radar_app=radar)
        self.assertIs(apps[3], radar)

    def test_pc_radar_placeholder_waits_for_bt4(self):
        placeholder = app_main.RadarPcPlaceholder()
        self.assertEqual(placeholder.name, "RADAR")
        display, buttons = FakeDisplay(), QueueButtons()
        ctx = AppContext(display, buttons, Activity(), StopSignal())
        buttons.put(4)
        self.assertEqual(run_app(placeholder, ctx), "back")
        self.assertEqual(display.shown[0][:2], ["RADAR NUR AN DER WAND", "BT4 ZURUECK"])

    def test_thema_app_writes_into_the_given_config_dir(self):
        _, settings = app_main.build_apps("eigener-ordner")
        thema = settings[0]
        buttons = QueueButtons()
        buttons.put(BT4)
        ctx = AppContext(FakeDisplay(), buttons, Activity(), StopSignal())
        with mock.patch.object(settings_apps, "TopicServer") as server:
            with self.assertRaises(StopApp):
                thema.run(ctx)
        server.assert_called_once()
        self.assertEqual(server.call_args[0][0], "eigener-ordner")


class RunWallTest(unittest.TestCase):
    def patched(self, apps):
        return mock.patch.object(app_main, "build_apps", return_value=(apps, []))

    def test_shell_crash_returns_error_and_is_logged(self):
        shell = mock.Mock()
        shell.return_value.run.side_effect = RuntimeError("kaputt")
        shell.return_value.display_released = threading.Event()
        with self.patched([FakeApp("A")]), mock.patch.object(app_main, "Shell", shell):
            with self.assertLogs("app.main", level="ERROR") as logs:
                result = app_main.run_wall(FakeDisplay(), QueueButtons(), Activity(), StopSignal())
        self.assertEqual(result, "error")
        self.assertIn("kaputt", "\n".join(logs.output))

    def _interrupt_in_app(self, leave_s):
        """run_wall bekommt Ctrl+C, waehrend eine Anwendung laeuft, deren Ende leave_s dauert."""
        display, buttons, stop = FakeDisplay(), QueueButtons(), StopSignal()
        self.addCleanup(stop.set, "shutdown")
        entered, left = threading.Event(), threading.Event()

        def radar(ctx):
            entered.set()
            try:
                while True:
                    ctx.wait_button()
            finally:
                time.sleep(leave_s)  # wie leave() der Radar-Umschaltung
                left.set()

        class Interrupting(Activity):
            def expired(self):
                if entered.is_set():
                    raise KeyboardInterrupt
                return False

        buttons.put(5)
        with self.patched([FakeApp("RADAR", run=radar)]), \
                mock.patch.object(app_main, "EXPIRY_POLL_S", 0.01):
            started = time.monotonic()
            with self.assertRaises(KeyboardInterrupt):
                app_main.run_wall(display, buttons, Interrupting(), stop)
        return stop, left, time.monotonic() - started

    def test_interrupt_stops_the_shell_and_waits_for_the_app_to_leave(self):
        stop, left, _ = self._interrupt_in_app(leave_s=0.2)
        self.assertTrue(left.is_set())
        self.assertEqual(stop.reason, "shutdown")

    def test_interrupt_waits_for_the_shell_only_up_to_the_limit(self):
        with mock.patch.object(app_main, "SHELL_STOP_WAIT_S", 0.1), \
                self.assertLogs("app.main", level="WARNING"):
            _, left, took = self._interrupt_in_app(leave_s=3.0)
        self.assertFalse(left.is_set())
        self.assertLess(took, 2.0)

    def test_end_to_end_with_link_dispatcher(self):
        # Echter LinkDispatcher mit Test-Leitung: BUTTON|n bewegt das Menue, SHUTDOWN bekommt
        # OK erst, wenn die Anwendung beendet und die Anzeige freigegeben ist.
        events = []
        display, link = FakeDisplay(events), EventLink(events)
        buttons, stop = QueueButtons(), StopSignal()
        entered = threading.Event()

        def slow_leave(ctx):
            entered.set()
            try:
                while True:
                    ctx.wait_button()
            finally:
                time.sleep(0.2)
                events.append(("left",))

        with self.patched([FakeApp("A"), FakeApp("B", run=slow_leave)]):
            thread, result = start_wall(display, buttons, Activity(), stop, link=link,
                                        on_shutdown=lambda: events.append(("on_shutdown",)))
            self.assertTrue(wait_for(lambda: display.shown))
            self.assertEqual(display.shown[-1][:2], ["> A", "  B"])
            link.incoming.put(Message(1, "BUTTON", "6"))
            self.assertTrue(wait_for(lambda: display.shown[-1][:2] == ["  A", "> B"]))
            link.incoming.put(Message(2, "BUTTON", "5"))
            self.assertTrue(entered.wait(3))
            link.incoming.put(Message(3, "SHUTDOWN", ""))
            thread.join(5)
            self.assertTrue(wait_for(lambda: ("on_shutdown",) in events))
        self.assertEqual(result, ["shutdown"])
        self.assertEqual([e for e in events if e[0] == "reply"],
                         [("reply", "BUTTON", "OK"), ("reply", "BUTTON", "OK"),
                          ("reply", "SHUTDOWN", "OK")])
        ok = events.index(("reply", "SHUTDOWN", "OK"))
        self.assertLess(events.index(("left",)), ok)
        self.assertLess(ok, events.index(("on_shutdown",)))
        self.assertFalse([e for e in events[ok:] if e[0] == "show"])

    def test_keys_6_5_4_do_not_end_and_show_menu_again(self):
        display, buttons, stop = FakeDisplay(), QueueButtons(), StopSignal()
        entered = threading.Event()
        apps = [FakeApp("A"), FakeApp("B", run=lambda ctx: (entered.set(), ctx.wait_button()))]
        with self.patched(apps):
            thread, result = start_wall(display, buttons, Activity(), stop)
            self.assertTrue(wait_for(lambda: display.shown))
            for key in (6, 5):
                buttons.put(key)
            self.assertTrue(entered.wait(3))
            shown_before = len(display.shown)
            buttons.put(4)
            self.assertTrue(wait_for(lambda: len(display.shown) > shown_before))
            self.assertTrue(thread.is_alive())
            self.assertEqual(result, [])
            stop.set("shutdown")
            thread.join(3)
        self.assertEqual(result, ["shutdown"])

    def test_sends_done_when_activity_expired(self):
        now = [0.0]
        activity = Activity(clock=lambda: now[0], idle_minutes=1)
        link, display, buttons, stop = FakeLink(), FakeDisplay(), QueueButtons(), StopSignal()
        with self.patched([FakeApp("A")]):
            thread, result = start_wall(display, buttons, activity, stop, link=link)
            self.assertTrue(wait_for(lambda: display.shown))
            now[0] = 61.0
            thread.join(5)
        self.assertFalse(thread.is_alive())
        self.assertEqual(link.requests, ["DONE"])
        self.assertEqual(result, ["idle"])

    def test_done_only_after_the_app_has_stopped(self):
        now = [0.0]
        activity = Activity(clock=lambda: now[0], idle_minutes=1)
        link, display, buttons, stop = FakeLink(), FakeDisplay(), QueueButtons(), StopSignal()
        order = []

        def slow_app(ctx):
            try:
                while True:
                    ctx.wait_button()
            finally:
                time.sleep(0.2)
                order.append("app_left")

        original = link.request

        def recording_request(command, data=""):
            order.append("done")
            return original(command, data)

        link.request = recording_request
        with self.patched([FakeApp("RADAR", run=slow_app)]):
            thread, result = start_wall(display, buttons, activity, stop, link=link)
            self.assertTrue(wait_for(lambda: display.shown))
            buttons.put(5)
            time.sleep(0.2)
            now[0] = 61.0
            thread.join(5)
        self.assertEqual(order, ["app_left", "done"])

    def test_no_done_without_expiry(self):
        link, display, buttons, stop = FakeLink(), FakeDisplay(), QueueButtons(), StopSignal()
        with self.patched([FakeApp("A")]):
            thread, result = start_wall(display, buttons, Activity(), stop, link=link)
            self.assertTrue(wait_for(lambda: display.shown))
            time.sleep(0.3)
            stop.set("shutdown")
            thread.join(3)
        self.assertEqual(link.requests, [])


class MainTest(unittest.TestCase):
    def test_pc_mode_uses_terminal_display_and_keyboard(self):
        shell = mock.Mock()
        shell.return_value.run.return_value = "shutdown"
        with mock.patch.object(app_main, "load_dotenv") as dotenv, \
                mock.patch.object(app_main, "Shell", shell), \
                mock.patch.object(app_main, "KeyboardButtons") as keyboard, \
                mock.patch.object(app_main, "open_esp_port") as port:
            app_main.main(["--pc"])
        dotenv.assert_called_once()
        keyboard.return_value.start.assert_called_once()
        port.assert_not_called()
        self.assertIsInstance(shell.call_args[0][0], app_main.TerminalDisplay)

    def test_wall_mode_shares_one_bus(self):
        fake_bus = object()
        smbus_module = types.SimpleNamespace(SMBus=mock.Mock(return_value=fake_bus))
        with mock.patch.dict(sys.modules, {"smbus2": smbus_module}), \
                mock.patch.object(app_main, "load_dotenv"), \
                mock.patch.object(app_main, "WallDisplay") as wall, \
                mock.patch.object(app_main, "open_esp_port") as port, \
                mock.patch.object(app_main, "PiLink") as pilink, \
                mock.patch.object(app_main, "run_wall", return_value="shutdown") as run_wall:
            app_main.main([])
        smbus_module.SMBus.assert_called_once_with(1)
        wall.assert_called_once_with(bus=fake_bus)
        pilink.assert_called_once_with(port.return_value)
        pilink.return_value.start.assert_called_once()
        kwargs = run_wall.call_args.kwargs
        self.assertIs(kwargs["link"], pilink.return_value)
        self.assertTrue(callable(kwargs["radar_factory"]))


if __name__ == "__main__":
    unittest.main()
