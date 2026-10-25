import threading
import time
import unittest

from app.driver.display.cells import normalize
from app.ui.activity import Activity
from app.ui.app_host import AppContext, StopApp, StopSignal, run_app
from app.ui.buttons import QueueButtons
from app.ui.pages import paginate


class FakeDisplay:
    def __init__(self):
        self.calls = []

    def show_lines(self, lines, dots_own_cell=False):
        self.calls.append(list(lines))


def make_ctx():
    display, buttons, stop = FakeDisplay(), QueueButtons(), StopSignal()
    ctx = AppContext(display, buttons, Activity(), stop)
    return ctx, display, buttons, stop


class StopSignalTest(unittest.TestCase):
    def test_first_reason_wins(self):
        s = StopSignal()
        self.assertFalse(s.is_set())
        self.assertIsNone(s.reason)
        s.set("idle")
        s.set("shutdown")
        self.assertTrue(s.is_set())
        self.assertEqual(s.reason, "idle")
        self.assertTrue(s.wait(0))

    def test_wait_times_out(self):
        self.assertFalse(StopSignal().wait(0.01))


class WaitButtonTest(unittest.TestCase):
    def test_returns_button_and_touches_activity(self):
        ctx, _, buttons, _ = make_ctx()
        touched = []
        ctx.activity.touch = lambda: touched.append(1)
        buttons.put(5)
        self.assertEqual(ctx.wait_button(0.1), 5)
        self.assertTrue(touched)

    def test_timeout_returns_none(self):
        ctx, *_ = make_ctx()
        self.assertIsNone(ctx.wait_button(0.01))

    def test_bt4_raises_back(self):
        ctx, _, buttons, _ = make_ctx()
        buttons.put(4)
        with self.assertRaises(StopApp) as cm:
            ctx.wait_button(0.1)
        self.assertEqual(str(cm.exception), "back")

    def test_stop_signal_raises_reason(self):
        ctx, _, _, stop = make_ctx()
        stop.set("idle")
        with self.assertRaises(StopApp) as cm:
            ctx.wait_button(0.1)
        self.assertEqual(str(cm.exception), "idle")


class RunBlockingTest(unittest.TestCase):
    def test_run_blocking_stops_on_bt4(self):
        ctx, _, buttons, _ = make_ctx()
        buttons.put(4)
        t0 = time.monotonic()
        with self.assertRaises(StopApp):
            ctx.run_blocking(lambda: time.sleep(2) or "X")
        self.assertLess(time.monotonic() - t0, 0.5)

    def test_bt4_during_work_stops(self):
        ctx, _, buttons, _ = make_ctx()
        threading.Timer(0.05, buttons.put, (4,)).start()
        t0 = time.monotonic()
        with self.assertRaises(StopApp):
            ctx.run_blocking(time.sleep, 2)
        self.assertLess(time.monotonic() - t0, 0.5)

    def test_presses_during_busy_are_dropped(self):
        ctx, _, buttons, _ = make_ctx()
        buttons.put(5)
        buttons.put(6)
        self.assertEqual(ctx.run_blocking(lambda: "ok"), "ok")
        self.assertIsNone(buttons.get(0))

    def test_other_buttons_during_work_are_dropped(self):
        ctx, _, buttons, _ = make_ctx()
        threading.Timer(0.02, buttons.put, (5,)).start()
        self.assertEqual(ctx.run_blocking(lambda: time.sleep(0.15) or "ok"), "ok")
        self.assertIsNone(buttons.get(0))

    def test_press_at_the_end_of_the_work_does_not_carry_over(self):
        # Die Taste kommt genau, bevor fn zurueckkehrt (letztes Abfrageintervall).
        ctx, _, buttons, _ = make_ctx()

        def work():
            buttons.put(5)
            return "ok"
        self.assertEqual(ctx.run_blocking(work), "ok")
        self.assertIsNone(buttons.get(0))

    def test_bt4_at_the_end_of_the_work_discards_the_result(self):
        ctx, _, buttons, _ = make_ctx()

        def work():
            buttons.put(4)
            return "ok"
        with self.assertRaises(StopApp) as cm:
            ctx.run_blocking(work)
        self.assertEqual(cm.exception.reason, "back")

    def test_stop_at_the_end_of_the_work_discards_the_result(self):
        ctx, _, _, stop = make_ctx()

        def work():
            stop.set("shutdown")
            return "ok"
        with self.assertRaises(StopApp) as cm:
            ctx.run_blocking(work)
        self.assertEqual(cm.exception.reason, "shutdown")

    def test_press_at_the_end_of_a_failing_work_does_not_carry_over(self):
        ctx, _, buttons, _ = make_ctx()

        def boom():
            buttons.put(6)
            raise ValueError("kaputt")
        with self.assertRaises(ValueError):
            ctx.run_blocking(boom)
        self.assertIsNone(buttons.get(0))

    def test_exception_is_reraised(self):
        ctx, *_ = make_ctx()

        def boom():
            raise ValueError("kaputt")
        with self.assertRaises(ValueError):
            ctx.run_blocking(boom)

    def test_stop_signal_raises_reason(self):
        ctx, _, _, stop = make_ctx()
        threading.Timer(0.03, stop.set, ("shutdown",)).start()
        with self.assertRaises(StopApp) as cm:
            ctx.run_blocking(time.sleep, 2)
        self.assertEqual(str(cm.exception), "shutdown")

    def test_reports_busy_while_running(self):
        ctx, *_ = make_ctx()
        inside = []
        orig = ctx.activity.busy

        def spy():
            inside.append(1)
            return orig()
        ctx.activity.busy = spy
        ctx.run_blocking(lambda: None)
        self.assertEqual(inside, [1])


class ShowPagesTest(unittest.TestCase):
    LONG = "WORT " * 60

    def test_single_page_returns_immediately(self):
        ctx, display, *_ = make_ctx()
        ctx.show_pages("Hallo Welt")
        self.assertEqual(len(display.calls), 1)

    def test_bt5_turns_pages_other_buttons_ignored(self):
        ctx, display, buttons, _ = make_ctx()
        count = len(paginate(normalize(self.LONG)))
        self.assertGreater(count, 1)
        for _ in range(count - 1):
            buttons.put(6)
            buttons.put(5)
        ctx.show_pages(self.LONG)
        self.assertEqual(len(display.calls), count)

    def test_bt4_raises_back(self):
        ctx, _, buttons, _ = make_ctx()
        buttons.put(4)
        with self.assertRaises(StopApp):
            ctx.show_pages(self.LONG)


class FnApp:
    def __init__(self, name, fn):
        self.name = name
        self._fn = fn

    def run(self, ctx):
        self._fn(ctx)


class RunAppTest(unittest.TestCase):
    def test_error_screen(self):
        ctx, display, buttons, _ = make_ctx()

        def boom(_):
            raise RuntimeError("x")
        threading.Timer(0.1, buttons.put, (4,)).start()
        with self.assertLogs("app.ui.app_host", level="ERROR"):
            result = run_app(FnApp("Test", boom), ctx)
        self.assertEqual(result, "error")
        self.assertEqual(display.calls[-1][0], "FEHLER IN TEST")
        self.assertEqual(display.calls[-1][1], "BT4 ZURUECK")

    def test_long_error_title_is_wrapped_over_two_lines(self):
        for name, title in (("STRICHMAENNCHEN", ["FEHLER IN", "STRICHMAENNCHEN"]),
                            ("RADAR EINRICHTEN", ["FEHLER IN RADAR", "EINRICHTEN"])):
            with self.subTest(name=name):
                ctx, display, buttons, _ = make_ctx()

                def boom(_):
                    raise RuntimeError("x")
                buttons.put(4)
                with self.assertLogs("app.ui.app_host", level="ERROR"):
                    self.assertEqual(run_app(FnApp(name, boom), ctx), "error")
                self.assertEqual(display.calls[-1], title + ["BT4 ZURUECK"])

    def test_normal_return_is_back(self):
        ctx, *_ = make_ctx()
        self.assertEqual(run_app(FnApp("A", lambda c: None), ctx), "back")

    def test_stop_app_reason_is_returned(self):
        ctx, *_ = make_ctx()

        def stop(_):
            raise StopApp("idle")
        self.assertEqual(run_app(FnApp("A", stop), ctx), "idle")
