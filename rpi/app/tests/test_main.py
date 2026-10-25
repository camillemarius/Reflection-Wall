import concurrent.futures
import contextlib
import queue
import sys
import threading
import time
import types
import unittest
from unittest import mock

from app import main as app_main
from app.applications import settings_apps
from app.driver.display.wall_display import WallDisplay
from app.link.codec import Message
from app.ui.activity import Activity
from app.ui.app_host import AppContext, StopApp, StopSignal, run_app
from app.ui.buttons import BT4, QueueButtons, _SmbusReader
from app.ui.link_dispatch import LinkDispatcher

# Adressen der zwoelf Anzeige-Module (Review Focus 4)
DISPLAY_ADDRESSES = frozenset(range(0x70, 0x78)) | {0x79, 0x7B, 0x7D, 0x7F}


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


class FakeBus:
    """SMBus des Tests: jedes Schreiben landet mit seiner Adresse in events."""

    def __init__(self, events):
        self.events = events

    def write_byte(self, addr, value):
        self.events.append(("write", addr))

    def write_i2c_block_data(self, addr, register, data):
        self.events.append(("write", addr))


class RecordingWallDisplay(WallDisplay):
    """Echte Wandanzeige auf dem Test-Bus; merkt sich zusaetzlich die Zeilen."""

    def __init__(self, events, **kwargs):
        super().__init__(**kwargs)
        self._events = events

    def show_lines(self, lines, dots_own_cell=False):
        self._events.append(("show", list(lines)))
        super().show_lines(lines, dots_own_cell)


class FakeGuard:
    def __init__(self, events):
        self.events = events

    def start(self):
        self.events.append(("guard", "start"))

    def stop(self):
        self.events.append(("guard", "stop"))

    def radar_high(self):
        return False

    def __call__(self):
        return contextlib.nullcontext()


class WallLink:
    """PiLink des Tests: READY und DONE bekommen sofort OK; der ESP fragt ueber incoming."""

    def __init__(self, events):
        self.incoming = queue.Queue()
        self.events = events

    def start(self):
        self.events.append(("link", "start"))

    def stop(self):
        self.events.append(("link", "stop"))

    def reply(self, request, command, data=""):
        self.events.append(("reply", request.command, command))
        return True

    def request(self, command, data=""):
        self.events.append(("request", command))
        fut = concurrent.futures.Future()
        fut.set_result(Message(1, "OK", ""))
        return fut


class WallRun:
    """main() im Wand-Modus in einem eigenen Thread. Bus, Port, PiLink, BusGuard und power_off
    sind Fakes; was sie sehen, steht der Reihe nach in events."""

    def __init__(self, test, apps=None, run_wall=None):
        self.events = []
        self.bus = FakeBus(self.events)
        self.link = WallLink(self.events)
        self.guard = FakeGuard(self.events)
        self.port = mock.Mock()
        self.port.close.side_effect = lambda: self.events.append(("port", "close"))
        self.power_off = mock.Mock(side_effect=lambda: self.events.append(("power_off",)))
        self._seq = 0
        self._stack = contextlib.ExitStack()
        test.addCleanup(self._stack.close)
        smbus2 = types.SimpleNamespace(SMBus=mock.Mock(side_effect=self._open_bus))
        self.smbus = smbus2.SMBus
        self._stack.enter_context(mock.patch.dict(sys.modules, {"smbus2": smbus2}))
        self.patch("load_dotenv")
        self.patch("idle_minutes_from_env", return_value=0)
        self.patch("open_esp_port", side_effect=self._open_port)
        self.pilink = self.patch("PiLink", return_value=self.link)
        self.patch("BusGuard", return_value=self.guard)
        self.patch("power_off", self.power_off)
        self.wall_display = self.patch(
            "WallDisplay", side_effect=lambda **kw: RecordingWallDisplay(self.events, **kw))
        apps = [FakeApp("A"), FakeApp("B")] if apps is None else apps
        self.patch("build_apps", return_value=(apps, []))
        if run_wall is not None:
            self.patch("run_wall", run_wall)
        self.thread = threading.Thread(target=app_main.main, args=([],), daemon=True)
        test.addCleanup(self._end)  # laeuft vor dem Zuruecksetzen der Patches

    def patch(self, name, *args, **kwargs):
        return self._stack.enter_context(mock.patch.object(app_main, name, *args, **kwargs))

    def _open_bus(self, number):
        self.events.append(("smbus", number))
        return self.bus

    def _open_port(self):
        self.events.append(("port", "open"))
        return self.port

    def _end(self):
        if self.thread.is_alive():
            self.put("SHUTDOWN")
            self.thread.join(3)

    def start(self):
        """Startet main(); True, sobald READY gesendet wurde."""
        self.thread.start()
        return wait_for(lambda: ("request", "READY") in self.events)

    def put(self, command, data=""):
        """Eine Anfrage des ESP; der Zeitpunkt steht als ("put", command, data) in events."""
        self._seq += 1
        self.events.append(("put", command, data))
        self.link.incoming.put(Message(self._seq, command, data))

    def join(self, timeout=1.5):
        self.thread.join(timeout)
        return not self.thread.is_alive()

    def position(self, event):
        return self.events.index(event)

    def display_writes(self):
        """Positionen in events, an denen auf eine Anzeige-Adresse geschrieben wurde."""
        return [i for i, e in enumerate(list(self.events))
                if e[0] == "write" and e[1] in DISPLAY_ADDRESSES]

    def shown(self):
        return [e[1] for e in list(self.events) if e[0] == "show"]

    def requests(self):
        return [e[1] for e in list(self.events) if e[0] == "request"]


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

    def test_given_dispatcher_is_used_and_sends_no_done(self):
        # Wand-Modus: main() besitzt den Dispatcher und sendet DONE selbst, genau einmal
        now = [0.0]
        activity = Activity(clock=lambda: now[0], idle_minutes=1)
        link, display, buttons, stop = FakeLink(), FakeDisplay(), QueueButtons(), StopSignal()
        dispatcher, released = mock.Mock(), threading.Event()
        with self.patched([FakeApp("A")]), \
                mock.patch.object(app_main, "EXPIRY_POLL_S", 0.01), \
                mock.patch.object(app_main, "LinkDispatcher") as own:
            thread, result = start_wall(display, buttons, activity, stop, link=link,
                                        dispatcher=dispatcher, display_released=released)
            self.assertTrue(wait_for(lambda: display.shown))
            now[0] = 61.0
            thread.join(3)
        self.assertEqual(result, ["idle"])
        own.assert_not_called()
        self.assertEqual(dispatcher.method_calls, [])
        self.assertEqual(link.requests, [])
        self.assertTrue(released.is_set())

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
        run_wall = mock.Mock(return_value="shutdown")
        wall = WallRun(self, run_wall=run_wall)
        activity = wall.patch("Activity", wraps=Activity)
        expander = wall.patch("ExpanderButtons")
        self.assertTrue(wall.start())
        wall.put("SESSION", "HAND")
        self.assertTrue(wait_for(lambda: run_wall.called))
        wall.put("SHUTDOWN")
        self.assertTrue(wall.join())
        wall.smbus.assert_called_once_with(1)
        self.assertEqual([e for e in wall.events if e[0] in ("smbus", "guard", "port", "link")][:4],
                         [("smbus", 1), ("guard", "start"), ("port", "open"), ("link", "start")])
        wall.wall_display.assert_called_once_with(bus=wall.bus, bus_guard=wall.guard)
        wall.pilink.assert_called_once_with(wall.port)
        kwargs = run_wall.call_args.kwargs
        self.assertIs(kwargs["link"], wall.link)
        self.assertIsInstance(kwargs["dispatcher"], LinkDispatcher)
        self.assertIsInstance(kwargs["display_released"], threading.Event)
        # R13: die Anwesenheit kommt vom BusGuard; die Radar-Tasten teilen Bus und Guard
        self.assertEqual(activity.call_args.kwargs["person_present"], wall.guard.radar_high)
        kwargs["radar_factory"]()._buttons_factory()
        self.assertIsInstance(expander.call_args.kwargs["bus"], _SmbusReader)
        self.assertIs(expander.call_args.kwargs["bus_guard"], wall.guard)
        for event in (("link", "stop"), ("port", "close"), ("guard", "stop")):
            self.assertIn(event, wall.events)

    def test_no_display_write_before_session_hand(self):
        # Review Focus 4, R5: bis SESSION|HAND gehoert die Anzeige dem ESP (PI STARTET)
        wall = WallRun(self)
        self.assertTrue(wall.start())
        time.sleep(0.2)  # Zeit, in der main() nichts schreiben darf
        wall.put("SESSION", "HAND")
        self.assertTrue(wait_for(lambda: wall.shown()))
        self.assertTrue(wall.display_writes())
        self.assertGreater(min(wall.display_writes()), wall.position(("put", "SESSION", "HAND")))

    def test_hand_starts_menu(self):
        wall = WallRun(self)
        self.assertTrue(wall.start())
        wall.put("SESSION", "HAND")
        self.assertTrue(wait_for(lambda: wall.shown()))
        self.assertIn(("reply", "SESSION", "OK"), wall.events)
        self.assertEqual(wall.shown()[0][:2], ["> A", "  B"])
        wall.put("BUTTON", "6")
        self.assertTrue(wait_for(lambda: wall.shown()[-1][:2] == ["  A", "> B"]))
        wall.put("SHUTDOWN")
        self.assertTrue(wall.join())
        wall.power_off.assert_called_once_with()

    def test_auto_off_counts_from_the_menu_start(self):
        # Die Wartezeit auf READY und SESSION zaehlt nicht zur Frist des automatischen Aus
        now = [0.0]
        wall = WallRun(self)
        wall.patch("idle_minutes_from_env", return_value=1)
        wall.patch("Activity", side_effect=lambda **kw: Activity(clock=lambda: now[0], **kw))
        wall.patch("EXPIRY_POLL_S", 0.01)
        self.assertTrue(wall.start())
        now[0] = 61.0
        wall.put("SESSION", "HAND")
        self.assertTrue(wait_for(lambda: wall.shown()))
        time.sleep(0.1)
        self.assertNotIn("DONE", wall.requests())
        now[0] = 122.0
        self.assertTrue(wait_for(lambda: "DONE" in wall.requests()))
        wall.put("SHUTDOWN")
        self.assertTrue(wall.join())

    def test_nacht_keeps_display_dark_until_shutdown(self):
        wall = WallRun(self)
        self.assertTrue(wall.start())
        wall.put("SESSION", "NACHT")
        self.assertTrue(wait_for(lambda: ("reply", "SESSION", "OK") in wall.events))
        time.sleep(0.2)
        self.assertTrue(wall.thread.is_alive())  # wartet auf SHUTDOWN
        wall.put("SHUTDOWN")
        self.assertTrue(wall.join())
        self.assertIn(("reply", "SHUTDOWN", "OK"), wall.events)
        wall.power_off.assert_called_once_with()
        self.assertEqual(wall.display_writes(), [])
        self.assertEqual(wall.requests(), ["READY"])

    def test_shutdown_before_session_powers_off_without_display(self):
        # R9: BT2 waehrend EINSCHALTEN, der ESP schickt SHUTDOWN gleich nach READY
        wall = WallRun(self)
        self.assertTrue(wall.start())
        wall.put("SHUTDOWN")
        self.assertTrue(wall.join())
        self.assertIn(("reply", "SHUTDOWN", "OK"), wall.events)
        wall.power_off.assert_called_once_with()
        self.assertEqual(wall.display_writes(), [])
        self.assertEqual(wall.requests(), ["READY"])

    def test_shutdown_calls_power_off_after_display_released(self):
        entered = threading.Event()

        def slow_leave(ctx):
            entered.set()
            try:
                while True:
                    ctx.wait_button()
            finally:
                time.sleep(0.2)  # wie leave() der Radar-Umschaltung
                wall.events.append(("left",))

        wall = WallRun(self, apps=[FakeApp("A", run=slow_leave)])
        self.assertTrue(wall.start())
        wall.put("SESSION", "HAND")
        self.assertTrue(wait_for(lambda: wall.shown()))
        wall.put("BUTTON", "5")
        self.assertTrue(entered.wait(2))
        wall.put("SHUTDOWN")
        self.assertTrue(wall.join())
        ok = wall.position(("reply", "SHUTDOWN", "OK"))
        self.assertLess(wall.position(("left",)), ok)
        self.assertLess(ok, wall.position(("power_off",)))
        wall.power_off.assert_called_once_with()

    def test_no_display_write_after_ok_to_shutdown(self):
        # Review Focus 4: nach dem OK auf SHUTDOWN gehoert die Anzeige wieder dem ESP
        running = threading.Event()

        def busy(ctx):
            n = 0
            try:
                while True:
                    n += 1
                    ctx.display.show_lines([str(n)])
                    running.set()
                    ctx.wait_button(0.01)
            finally:
                time.sleep(0.1)
                ctx.display.show_lines(["ENDE"])  # Aufraeumen schreibt noch einmal

        wall = WallRun(self, apps=[FakeApp("A", run=busy)])
        self.assertTrue(wall.start())
        wall.put("SESSION", "HAND")
        self.assertTrue(wait_for(lambda: wall.shown()))
        wall.put("BUTTON", "5")
        self.assertTrue(running.wait(2))
        wall.put("SHUTDOWN")
        self.assertTrue(wall.join())
        self.assertIn(["ENDE"], wall.shown())
        self.assertLess(max(wall.display_writes()), wall.position(("reply", "SHUTDOWN", "OK")))

    def test_hand_after_ok_to_shutdown_leaves_display_alone(self):
        # Review Focus 4: SESSION|HAND und SHUTDOWN sind beantwortet, bevor main() die Sitzung
        # sieht. Nach dem OK auf SHUTDOWN darf das Menue nicht mehr starten.
        go = threading.Event()
        wall = WallRun(self)
        wall.patch("announce_ready", side_effect=lambda link, stop: go.wait(2))
        wall.thread.start()
        wall.put("SESSION", "HAND")
        wall.put("SHUTDOWN")
        self.assertTrue(wait_for(lambda: ("reply", "SHUTDOWN", "OK") in wall.events))
        go.set()
        self.assertTrue(wall.join())
        wall.power_off.assert_called_once_with()
        self.assertEqual(wall.display_writes(), [])

    def _session_ends_with(self, result):
        wall = WallRun(self, run_wall=mock.Mock(return_value=result))
        wall.patch("SHUTDOWN_WAIT_S", 0.05)  # nach DONE gilt die lange Frist
        self.assertTrue(wall.start())
        wall.put("SESSION", "HAND")
        self.assertTrue(wait_for(lambda: "DONE" in wall.requests()))
        time.sleep(0.2)
        self.assertTrue(wall.thread.is_alive())  # wartet auf SHUTDOWN
        wall.put("SHUTDOWN")
        self.assertTrue(wall.join())
        self.assertEqual(wall.requests(), ["READY", "DONE"])
        wall.power_off.assert_called_once_with()

    def test_idle_sends_done_once_and_waits_for_shutdown(self):
        self._session_ends_with("idle")

    def test_error_sends_done_once_and_waits_for_shutdown(self):
        self._session_ends_with("error")

    def test_cleanup_goes_on_when_one_part_fails_to_stop(self):
        wall = WallRun(self)
        wall.link.stop = mock.Mock(side_effect=OSError("Port weg"))
        self.assertTrue(wall.start())
        with self.assertLogs("app.main", "ERROR"):
            wall.put("SHUTDOWN")
            self.assertTrue(wall.join())
        wall.link.stop.assert_called_once_with()
        self.assertIn(("port", "close"), wall.events)
        self.assertIn(("guard", "stop"), wall.events)


if __name__ == "__main__":
    unittest.main()
