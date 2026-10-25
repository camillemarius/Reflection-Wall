import concurrent.futures
import queue
import sys
import threading
import time
import types
import unittest
from unittest import mock

from app import main as app_main
from app.link.codec import Message
from app.ui.activity import Activity
from app.ui.app_host import AppContext, StopSignal, run_app
from app.ui.buttons import QueueButtons


class FakeDisplay:
    def __init__(self):
        self.shown = []

    def show_lines(self, lines, dots_own_cell=False):
        self.shown.append(list(lines))

    def start(self):
        pass


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


class RunWallTest(unittest.TestCase):
    def patched(self, apps):
        return mock.patch.object(app_main, "build_apps", return_value=(apps, []))

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
