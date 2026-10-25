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
from app.link.codec import Message, decode, encode, role_of
from app.link.pi_link import LinkBusy
from app.link.tests.fakes import FakePort
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
        self.delay = 0.0  # > 0: wie Regel B mit haengendem INT_GPIO_EXP, vor jeder Uebertragung

    def start(self):
        self.events.append(("guard", "start"))

    def stop(self):
        self.events.append(("guard", "stop"))

    def radar_high(self):
        return False

    @contextlib.contextmanager
    def _transfer(self):
        if self.delay:
            time.sleep(self.delay)
        yield

    def __call__(self):
        return self._transfer()


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


def frame(seq, command, data=""):
    return encode(Message(seq, command, data)) + b"\n"


class LinePort(FakePort):
    """Port fuer den echten PiLink: der Test spielt den ESP und liest mit, was der Pi sendet."""

    def __init__(self, events):
        super().__init__()
        self.events = events
        self._sent = b""

    def close(self):
        self.events.append(("port", "close"))

    def sent(self):
        """Alles, was der Pi bisher gesendet hat, als Nachrichten."""
        self._sent += self.take_tx()
        return [decode(line) for line in self._sent.split(b"\n") if line]


class WallRun:
    """main() im Wand-Modus in einem eigenen Thread. Bus, Port, PiLink, BusGuard und power_off
    sind Fakes; was sie sehen, steht der Reihe nach in events.

    Mit real_link=True laeuft der echte PiLink auf einem LinePort: put() schreibt dann Zeilen
    wie der ESP, und port.sent() zeigt, was der Pi geantwortet hat.

    Nach der Sitzung bedient main() weiter, bis der Prozess endet (I-1). Das Warten darauf ist
    hier ein Event: serving ist gesetzt, sobald main() wartet; end_process() beendet es, wie
    systemd beim Herunterfahren."""

    def __init__(self, test, apps=None, run_wall=None, real_link=False):
        self.events = []
        self.bus = FakeBus(self.events)
        self.guard = FakeGuard(self.events)
        self.power_off = mock.Mock(side_effect=lambda: self.events.append(("power_off",)))
        self.serving = threading.Event()
        self.process_end = threading.Event()
        self._seq = 0
        self._stack = contextlib.ExitStack()
        test.addCleanup(self._stack.close)
        smbus2 = types.SimpleNamespace(SMBus=mock.Mock(side_effect=self._open_bus))
        self.smbus = smbus2.SMBus
        self._stack.enter_context(mock.patch.dict(sys.modules, {"smbus2": smbus2}))
        self.patch("load_dotenv")
        self.patch("idle_minutes_from_env", return_value=0)
        self.patch("open_esp_port", side_effect=self._open_port)
        if real_link:
            self.link = None
            self.port = LinePort(self.events)
        else:
            self.link = WallLink(self.events)
            self.port = mock.Mock()
            self.port.close.side_effect = lambda: self.events.append(("port", "close"))
            self.pilink = self.patch("PiLink", return_value=self.link)
        self.patch("_wait_for_process_end", side_effect=self._wait_for_end)
        self.can_power_off = self.patch("can_power_off", return_value=True)  # nie echtes sudo
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

    def _wait_for_end(self):
        self.serving.set()
        self.process_end.wait(10)

    def _end(self):
        if self.thread.is_alive():
            if not self.serving.is_set():
                self.put("SHUTDOWN")  # die Sitzung laeuft noch
            self.process_end.set()
            self.thread.join(3)

    def start(self):
        """Startet main(); True, sobald READY gesendet (mit echtem PiLink: und beantwortet) ist."""
        self.thread.start()
        if self.link is not None:
            return wait_for(lambda: ("request", "READY") in self.events)
        if not wait_for(lambda: self.sent("READY")):
            return False
        self.port.feed(frame(self.sent("READY")[-1].seq, "OK"))
        return True

    def put(self, command, data=""):
        """Eine Anfrage des ESP; der Zeitpunkt steht als ("put", command, data) in events.
        Gibt die Nummer zurueck."""
        self._seq += 1
        self.events.append(("put", command, data))
        if self.link is not None:
            self.link.incoming.put(Message(self._seq, command, data))
        else:
            self.port.feed(frame(self._seq, command, data))
        return self._seq

    def sent(self, command):
        """Mit echtem PiLink: was der Pi mit diesem Befehl gesendet hat."""
        return [m for m in self.port.sent() if m.command == command]

    def answers(self):
        """Mit echtem PiLink: die Antworten des Pi als (Nummer, Befehl)."""
        return [(m.seq, m.command) for m in self.port.sent() if role_of(m.command) == "response"]

    def replies(self, command):
        """Mit WallLink: die Antworten des Pi auf diesen Befehl, der Reihe nach."""
        return [e[2] for e in list(self.events) if e[0] == "reply" and e[1] == command]

    def wait_serving(self):
        """True, sobald main() nach der Sitzung nur noch bedient und auf das Prozessende wartet."""
        return wait_for(self.serving.is_set)

    def end_process(self, timeout=1.5):
        """Wie systemd beim Herunterfahren: das Warten endet, main() raeumt auf und kehrt zurueck."""
        self.process_end.set()
        return self.join(timeout)

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
        self.assertTrue(wall.wait_serving())
        self.assertTrue(wall.end_process())
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
        self.assertTrue(wall.wait_serving())
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
        self.assertTrue(wall.wait_serving())

    def test_nacht_keeps_display_dark_until_shutdown(self):
        wall = WallRun(self)
        self.assertTrue(wall.start())
        wall.put("SESSION", "NACHT")
        self.assertTrue(wait_for(lambda: ("reply", "SESSION", "OK") in wall.events))
        time.sleep(0.2)
        self.assertTrue(wall.thread.is_alive())  # wartet auf SHUTDOWN
        self.assertFalse(wall.serving.is_set())
        wall.put("SHUTDOWN")
        self.assertTrue(wall.wait_serving())
        self.assertIn(("reply", "SHUTDOWN", "OK"), wall.events)
        wall.power_off.assert_called_once_with()
        self.assertEqual(wall.display_writes(), [])
        self.assertEqual(wall.requests(), ["READY"])

    def test_shutdown_before_session_powers_off_without_display(self):
        # R9: BT2 waehrend EINSCHALTEN, der ESP schickt SHUTDOWN gleich nach READY
        wall = WallRun(self)
        self.assertTrue(wall.start())
        wall.put("SHUTDOWN")
        self.assertTrue(wall.wait_serving())
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
        self.assertTrue(wall.wait_serving())
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
        self.assertTrue(wall.wait_serving())
        self.assertIn(["ENDE"], wall.shown())
        self.assertLess(max(wall.display_writes()), wall.position(("reply", "SHUTDOWN", "OK")))

    def test_ok_to_shutdown_waits_for_a_slow_display_write(self):
        # Review Focus 4 mit Review Focus 5: haengt INT_GPIO_EXP, wartet der Guard vor jeder
        # Uebertragung, und ein ganzes Bild dauert lange. Das OK auf SHUTDOWN kommt erst nach
        # dem Schreiben. Der Dispatcher hier hat nur 0,05 s als eigene Frist; besteht der Test,
        # dann gibt main() die eigene, laengere Frist mit.
        running = threading.Event()
        full_screen = ["X" * 24] * 4

        def busy(ctx):
            try:
                ctx.display.show_lines(["A"])
                running.set()
                while True:
                    ctx.wait_button()
            finally:
                ctx.display.show_lines(full_screen)  # alle 12 Module, je mit Wartezeit
                wall.events.append(("left",))

        def short_default(*args, release_wait_s=0.05, **kwargs):
            return LinkDispatcher(*args, release_wait_s=release_wait_s, **kwargs)

        wall = WallRun(self, apps=[FakeApp("A", run=busy)])
        wall.patch("LinkDispatcher", short_default)
        self.assertTrue(wall.start())
        wall.put("SESSION", "HAND")
        self.assertTrue(wait_for(lambda: wall.shown()))
        wall.put("BUTTON", "5")
        self.assertTrue(running.wait(2))
        wall.guard.delay = 0.03  # ab jetzt: 12 Module brauchen zusammen etwa 0,36 s
        wall.put("SHUTDOWN")
        self.assertTrue(wall.wait_serving())
        ok = wall.position(("reply", "SHUTDOWN", "OK"))
        self.assertIn(full_screen, wall.shown())
        self.assertLess(max(wall.display_writes()), ok)
        self.assertLess(wall.position(("left",)), ok)
        # Die Frist deckt ein ganzes Bild mit haengender Leitung (12 x 1 s) und bleibt unter
        # T_shutdown (60 s), der Frist des ESP fuer SHUTDOWN.
        self.assertGreater(app_main.RELEASE_WAIT_S, 12.0)
        self.assertLess(app_main.RELEASE_WAIT_S, 60.0)

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
        self.assertTrue(wall.wait_serving())
        wall.power_off.assert_called_once_with()
        self.assertEqual(wall.display_writes(), [])

    def _session_ends_with(self, result):
        wall = WallRun(self, run_wall=mock.Mock(return_value=result))
        wall.patch("SHUTDOWN_WAIT_S", 0.05)  # nach DONE gilt die lange Frist
        self.assertTrue(wall.start())
        wall.put("SESSION", "HAND")
        self.assertTrue(wait_for(lambda: "DONE" in wall.requests()))
        time.sleep(0.2)
        self.assertFalse(wall.serving.is_set())  # wartet auf SHUTDOWN
        wall.put("SHUTDOWN")
        self.assertTrue(wall.wait_serving())
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
            self.assertTrue(wall.wait_serving())
            self.assertTrue(wall.end_process())
        wall.link.stop.assert_called_once_with()
        self.assertIn(("port", "close"), wall.events)
        self.assertIn(("guard", "stop"), wall.events)

    # --- I-1: nach dem OK auf SHUTDOWN weiter bedienen, bis der Prozess endet ---------------

    def test_second_shutdown_after_ok_gets_ok_and_powers_off_once(self):
        # Ein Reset des ESP in HERUNTERFAHREN sendet SHUTDOWN noch einmal, mit neuer Nummer
        # (R8). Der Pi hat schon geantwortet und power_off gerufen; er bleibt an der Leitung.
        wall = WallRun(self)
        self.assertTrue(wall.start())
        wall.put("SESSION", "HAND")
        self.assertTrue(wait_for(lambda: wall.shown()))
        wall.put("SHUTDOWN")
        self.assertTrue(wall.wait_serving())
        wall.put("SHUTDOWN")
        self.assertTrue(wait_for(lambda: wall.replies("SHUTDOWN") == ["OK", "OK"]))
        wall.power_off.assert_called_once_with()
        self.assertTrue(wall.thread.is_alive())
        self.assertNotIn(("link", "stop"), wall.events)
        self.assertTrue(wall.end_process())
        for event in (("link", "stop"), ("port", "close"), ("guard", "stop")):
            self.assertIn(event, wall.events)

    def test_second_shutdown_while_the_first_waits_gets_ok_real_link(self):
        # Mit dem echten PiLink: das zweite SHUTDOWN kommt, waehrend das erste noch auf die
        # Anzeige wartet. PiLink kennt dann nur noch die neue Nummer, das OK auf das erste
        # geht nicht mehr raus (pi_link.py reply). Das neue SHUTDOWN bekommt sein OK.
        entered, leaving, finish = threading.Event(), threading.Event(), threading.Event()

        def slow_leave(ctx):
            entered.set()
            try:
                while True:
                    ctx.wait_button()
            finally:
                leaving.set()
                finish.wait(2)  # wie leave() der Radar-Umschaltung: die Anzeige ist noch belegt

        wall = WallRun(self, apps=[FakeApp("A", run=slow_leave)], real_link=True)
        self.assertTrue(wall.start())
        session = wall.put("SESSION", "HAND")
        self.assertTrue(wait_for(lambda: wall.shown()))
        self.assertIn((session, "OK"), wall.answers())
        wall.put("BUTTON", "5")
        self.assertTrue(entered.wait(2))
        first = wall.put("SHUTDOWN")
        self.assertTrue(leaving.wait(2))  # das erste SHUTDOWN wartet jetzt auf die Anzeige
        second = wall.put("SHUTDOWN")     # der ESP sendet nach einem Reset neu
        self.assertTrue(wait_for(lambda: wall.port.unread() == 0))
        time.sleep(0.05)                  # PiLink hat die Zeile gelesen und gemeldet
        finish.set()
        self.assertTrue(wait_for(lambda: (second, "OK") in wall.answers()))
        self.assertNotIn((first, "OK"), wall.answers())
        self.assertTrue(wall.wait_serving())
        wall.power_off.assert_called_once_with()
        third = wall.put("SHUTDOWN")      # noch ein Reset
        self.assertTrue(wait_for(lambda: (third, "OK") in wall.answers()))
        wall.power_off.assert_called_once_with()
        self.assertTrue(wall.end_process())

    def test_shutdown_before_ok_to_ready_serves_on(self):
        # T9-a: kommt SHUTDOWN, bevor READY sein OK hat, gibt announce_ready False. Auch dann
        # bleibt der Pi an der Leitung und beantwortet jedes weitere SHUTDOWN.
        wall = WallRun(self)
        wall.patch("announce_ready", side_effect=lambda link, stop: not stop.wait(2))
        wall.thread.start()
        wall.put("SHUTDOWN")
        self.assertTrue(wall.wait_serving())
        wall.put("SHUTDOWN")
        self.assertTrue(wait_for(lambda: wall.replies("SHUTDOWN") == ["OK", "OK"]))
        wall.power_off.assert_called_once_with()
        self.assertEqual(wall.display_writes(), [])
        self.assertTrue(wall.end_process())

    def test_ctrl_c_while_serving_ends_main_and_cleans_up(self):
        wall = WallRun(self)
        wall.patch("_wait_for_process_end", side_effect=KeyboardInterrupt)
        self.assertTrue(wall.start())
        wall.put("SHUTDOWN")
        self.assertTrue(wall.join())
        for event in (("link", "stop"), ("port", "close"), ("guard", "stop")):
            self.assertIn(event, wall.events)

    # --- M-4: Sitzung ohne SHUTDOWN zu Ende, sudoers-Regel -------------------------------

    def test_done_without_shutdown_powers_off_and_serves_on(self):
        # DONE ist bestaetigt, aber kein SHUTDOWN kommt. Der Pi wollte aus und faehrt selbst
        # herunter; ein spaetes SHUTDOWN bekommt trotzdem sein OK, power_off laeuft einmal.
        wall = WallRun(self, run_wall=mock.Mock(return_value="idle"))
        wall.patch("DONE_WAIT_S", 0.05)
        self.assertTrue(wall.start())
        with self.assertLogs("app.main", "WARNING"):
            wall.put("SESSION", "HAND")
            self.assertTrue(wall.wait_serving())
        self.assertEqual(wall.requests(), ["READY", "DONE"])
        wall.power_off.assert_called_once_with()
        wall.put("SHUTDOWN")
        self.assertTrue(wait_for(lambda: wall.replies("SHUTDOWN") == ["OK"]))
        wall.power_off.assert_called_once_with()

    def test_unconfirmed_done_without_shutdown_does_not_power_off(self):
        wall = WallRun(self, run_wall=mock.Mock(return_value="idle"))
        wall.patch("DONE_WAIT_S", 0.05)
        with mock.patch.object(LinkDispatcher, "send_done", return_value=False):
            self.assertTrue(wall.start())
            wall.put("SESSION", "HAND")
            self.assertTrue(wall.wait_serving())
        wall.power_off.assert_not_called()

    def test_missing_sudoers_rule_is_logged_as_error(self):
        wall = WallRun(self)
        wall.can_power_off.return_value = False
        with self.assertLogs("app.main", "ERROR") as logs:
            self.assertTrue(wall.start())
        self.assertIn("sudoers", "\n".join(logs.output))
        wall.can_power_off.assert_called_once_with()
        wall.put("SESSION", "HAND")  # sonst aendert sich nichts
        self.assertTrue(wait_for(lambda: wall.shown()))

    def test_sudoers_rule_is_checked_at_start(self):
        wall = WallRun(self)
        with self.assertNoLogs("app.main", "ERROR"):
            self.assertTrue(wall.start())
        wall.can_power_off.assert_called_once_with()

    # --- M-3: READY noch einmal, solange SESSION fehlt -------------------------------------

    def _repeating_wall(self):
        wall = WallRun(self)
        wall.patch("READY_REPEAT_S", 0.05)
        wall.patch("SESSION_POLL_S", 0.01)
        return wall

    def test_ready_repeats_until_session_comes(self):
        # Hat der ESP das OK auf READY gegeben und vor dem Sichern einen Reset gehabt, steht er
        # noch in EINSCHALTEN und sendet kein SESSION. Ein neues READY holt ihn zurueck (L3).
        self.assertEqual(app_main.READY_REPEAT_S, 10.0)
        wall = self._repeating_wall()
        self.assertTrue(wall.start())
        self.assertTrue(wait_for(lambda: wall.requests().count("READY") >= 3))
        wall.put("SESSION", "HAND")
        self.assertTrue(wait_for(lambda: wall.shown()))
        count = wall.requests().count("READY")
        time.sleep(0.2)
        self.assertEqual(wall.requests().count("READY"), count)

    def test_ready_repeat_ends_with_shutdown_before_session(self):
        wall = self._repeating_wall()
        self.assertTrue(wall.start())
        self.assertTrue(wait_for(lambda: wall.requests().count("READY") >= 2))
        wall.put("SHUTDOWN")
        self.assertTrue(wall.wait_serving())
        count = wall.requests().count("READY")
        time.sleep(0.2)
        self.assertEqual(wall.requests().count("READY"), count)
        wall.power_off.assert_called_once_with()

    def test_ready_repeat_skips_a_busy_link(self):
        wall = self._repeating_wall()
        original, calls = wall.link.request, []

        def request(command, data=""):
            calls.append(command)
            if len(calls) > 1:
                raise LinkBusy("Anfrage offen")
            return original(command, data)

        wall.link.request = request
        self.assertTrue(wall.start())
        self.assertTrue(wait_for(lambda: len(calls) >= 3))
        wall.put("SESSION", "HAND")
        self.assertTrue(wait_for(lambda: wall.shown()))

    def test_wait_for_process_end_sleeps_until_interrupted(self):
        sleeps = []

        def sleep(s):
            sleeps.append(s)
            if len(sleeps) == 3:
                raise KeyboardInterrupt

        with self.assertRaises(KeyboardInterrupt):
            app_main._wait_for_process_end(sleep=sleep)
        self.assertEqual(sleeps, [app_main.SERVE_POLL_S] * 3)


if __name__ == "__main__":
    unittest.main()
