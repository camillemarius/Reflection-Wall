import threading
import time
import unittest

from app.ui.activity import Activity
from app.ui.app_host import StopSignal
from app.ui.buttons import QueueButtons
from app.ui.shell import Shell


class FakeDisplay:
    def __init__(self):
        self.calls = []

    def show_lines(self, lines, dots_own_cell=False):
        self.calls.append(list(lines))

    @property
    def last(self):
        return self.calls[-1] if self.calls else None


class FakeApp:
    def __init__(self, name):
        self.name = name
        self.started = 0

    def run(self, ctx):
        self.started += 1
        ctx.wait_button(None)  # BT4 beendet


class BoomApp:
    name = "BOOM"

    def run(self, ctx):
        raise RuntimeError("x")


def script(display, buttons, steps, stop, final):
    """Je Schritt: warten, bis die Anzeige den Text zeigt, dann Taste druecken.
    Am Ende auf das Schlussbild warten und die Bildschirmfolge stoppen."""
    def wait_for(text):
        deadline = time.monotonic() + 3
        while not (display.last and text in display.last):
            if time.monotonic() > deadline:
                return False
            time.sleep(0.005)
        return True

    def work():
        for expected, button in steps:
            if not wait_for(expected):
                break
            buttons.put(button)
        else:
            wait_for(final)
        stop.set("shutdown")
    threading.Thread(target=work, daemon=True).start()


def make(apps, settings):
    display, buttons, stop = FakeDisplay(), QueueButtons(), StopSignal()
    shell = Shell(display, buttons, apps, settings, Activity(), stop)
    return shell, display, buttons, stop


class ShellTest(unittest.TestCase):
    def test_main_menu_has_apps_then_einstellungen(self):
        shell, display, _, stop = make([FakeApp("CHAT"), FakeApp("QUIZ")], [FakeApp("S1")])
        stop.set("shutdown")
        self.assertEqual(shell.run(), "shutdown")
        self.assertEqual(display.calls[0], ["> CHAT", "  QUIZ", "  EINSTELLUNGEN", ""])

    def test_shell_returns_to_selected_app(self):
        quiz = FakeApp("QUIZ")
        shell, display, buttons, stop = make([FakeApp("CHAT"), quiz], [])
        def drive():
            for text, button in [("> CHAT", 6), ("> QUIZ", 5)]:
                deadline = time.monotonic() + 3
                while not (display.last and text in display.last) and time.monotonic() < deadline:
                    time.sleep(0.005)
                buttons.put(button)
            deadline = time.monotonic() + 3
            while not quiz.started and time.monotonic() < deadline:
                time.sleep(0.005)
            time.sleep(0.05)
            shown = len(display.calls)
            buttons.put(4)
            while len(display.calls) == shown and time.monotonic() < deadline:
                time.sleep(0.005)
            stop.set("shutdown")
        threading.Thread(target=drive, daemon=True).start()
        self.assertEqual(shell.run(), "shutdown")
        self.assertEqual(quiz.started, 1)
        self.assertEqual(display.last[:2], ["  CHAT", "> QUIZ"])

    def test_settings_submenu_and_back(self):
        settings = [FakeApp("THEMA AENDERN"), FakeApp("RADAR EINRICHTEN")]
        shell, display, buttons, stop = make([FakeApp("CHAT")], settings)
        script(display, buttons,
               [("> CHAT", 6), ("> EINSTELLUNGEN", 5), ("> THEMA AENDERN", 4)],
               stop, final="> EINSTELLUNGEN")
        self.assertEqual(shell.run(), "shutdown")
        self.assertIn(["> THEMA AENDERN", "  RADAR EINRICHTEN", "", ""], display.calls)
        self.assertEqual(display.last, ["  CHAT", "> EINSTELLUNGEN", "", ""])

    def test_settings_app_starts_and_returns_to_submenu(self):
        thema = FakeApp("THEMA AENDERN")
        shell, display, buttons, stop = make([FakeApp("CHAT")], [thema])

        def drive():
            for text, button in [("> CHAT", 6), ("> EINSTELLUNGEN", 5), ("> THEMA AENDERN", 5)]:
                deadline = time.monotonic() + 3
                while not (display.last and text in display.last) and time.monotonic() < deadline:
                    time.sleep(0.005)
                buttons.put(button)
            deadline = time.monotonic() + 3
            while not thema.started and time.monotonic() < deadline:
                time.sleep(0.005)
            time.sleep(0.05)
            buttons.put(4)
            time.sleep(0.1)
            stop.set("shutdown")
        threading.Thread(target=drive, daemon=True).start()
        self.assertEqual(shell.run(), "shutdown")
        self.assertEqual(thema.started, 1)
        self.assertEqual(display.last[0], "> THEMA AENDERN")

    def test_buttons_before_start_are_drained(self):
        app = FakeApp("CHAT")
        shell, display, buttons, stop = make([app], [])
        buttons.put(5)

        def stopper():
            deadline = time.monotonic() + 3
            while not app.started and time.monotonic() < deadline:
                time.sleep(0.005)
            buttons.put(4)
            time.sleep(0.1)
            stop.set("shutdown")
        threading.Thread(target=stopper, daemon=True).start()
        self.assertEqual(shell.run(), "shutdown")
        self.assertEqual(app.started, 1)

    def test_idle_from_app_ends_shell(self):
        class IdleApp:
            name = "X"

            def run(self, ctx):
                ctx.stop_event.set("idle")
                ctx.wait_button(0.1)
        shell, _, buttons, _ = make([IdleApp()], [])
        buttons.put(5)
        self.assertEqual(shell.run(), "idle")
        self.assertTrue(shell.display_released.is_set())

    def test_error_app_returns_to_menu(self):
        shell, display, buttons, stop = make([BoomApp()], [])
        script(display, buttons, [("> BOOM", 5), ("BT4 ZURUECK", 4)], stop, final="> BOOM")
        with self.assertLogs("app.ui.app_host", level="ERROR"):
            self.assertEqual(shell.run(), "shutdown")
        self.assertTrue(any("FEHLER IN BOOM" in c for c in display.calls))

    def test_display_released_set_on_exception(self):
        shell, display, _, _ = make([FakeApp("A")], [])

        def bad(*args, **kwargs):
            raise OSError("anzeige")
        display.show_lines = bad
        with self.assertRaises(OSError):
            shell.run()
        self.assertTrue(shell.display_released.is_set())

    def test_display_released_set_on_stop(self):
        shell, _, _, stop = make([FakeApp("A")], [])
        self.assertFalse(shell.display_released.is_set())
        stop.set("shutdown")
        shell.run()
        self.assertTrue(shell.display_released.is_set())
