"""Tests fuer Regel B auf dem Pi (BusGuard) mit Fake-lgpio und Fake-Uhr."""
import unittest

from app.driver import bus_rule
from app.driver.bus_rule import BusGuard


class FakeClock:
    def __init__(self):
        self.now = 100.0
        self.sleeps = 0

    def __call__(self):
        return self.now

    def sleep(self, s):
        self.sleeps += 1
        self.now += s


class FakeCb:
    def __init__(self):
        self.cancelled = False

    def cancel(self):
        self.cancelled = True


class FakeLgpio:
    BOTH_EDGES = 3
    SET_PULL_UP = 32
    SET_PULL_DOWN = 64

    def __init__(self):
        self.levels = {4: 1, 22: 0}
        self.funcs = {}
        self.freed = []
        self.closed = False

    def gpiochip_open(self, chip):
        return 7

    def gpio_claim_alert(self, handle, gpio, edge, flags):
        pass

    def callback(self, handle, gpio, edge, func):
        self.funcs[gpio] = func
        return FakeCb()

    def gpio_read(self, handle, gpio):
        return self.levels[gpio]

    def gpio_free(self, handle, gpio):
        self.freed.append(gpio)

    def gpiochip_close(self, handle):
        self.closed = True

    def edge(self, gpio, level):
        self.levels[gpio] = level
        self.funcs[gpio](0, gpio, level, 0)


class BusGuardTest(unittest.TestCase):
    def setUp(self):
        self.lg = FakeLgpio()
        self.clk = FakeClock()
        self.guard = BusGuard(lgpio_module=self.lg, clock=self.clk,
                              sleep=self.clk.sleep)
        self.guard.start()

    def _enter(self):
        t0 = self.clk.now
        with self.guard():
            pass
        return self.clk.now - t0

    def test_no_wait_when_line_high_and_no_edge(self):
        self.assertEqual(self._enter(), 0)
        self.assertEqual(self.clk.sleeps, 0)

    def test_waits_while_expander_int_low(self):
        self.lg.edge(4, 0)
        calls = []
        orig = self.clk.sleep

        def sleep(s):
            orig(s)
            if self.clk.now >= 100.2 and not calls:
                calls.append(1)
                self.lg.edge(4, 1)
        self.guard._sleep = sleep
        waited = self._enter()
        self.assertGreaterEqual(waited, 0.2)
        self.assertLess(waited, 0.3)

    def test_waits_free_s_after_rising_edge(self):
        self.lg.edge(4, 0)
        self.lg.edge(4, 1)
        waited = self._enter()
        self.assertGreaterEqual(waited, 0.005)
        self.assertLess(waited, 0.05)

    def test_waits_radar_pause_after_hlk_rising_edge(self):
        self.lg.edge(22, 1)
        waited = self._enter()
        self.assertGreaterEqual(waited, 0.25)
        self.assertLess(waited, 0.3)

    def test_gives_up_after_max_wait_with_warning(self):
        self.lg.edge(4, 0)
        with self.assertLogs(bus_rule.log, level="WARNING"):
            waited = self._enter()
        self.assertGreaterEqual(waited, 1.0)
        self.assertLess(waited, 1.1)

    def test_warning_at_most_every_10_s_with_count_of_skipped(self):
        # T8: haengt INT_GPIO_EXP, wartet jede Uebertragung 1 s. Ohne Grenze stuende jede im
        # Log; ein ganzes Bild sind 12 Uebertragungen.
        self.assertEqual(bus_rule.WARN_EVERY_S, 10.0)
        self.lg.edge(4, 0)
        with self.assertLogs(bus_rule.log, level="WARNING") as logs:
            for _ in range(12):
                self._enter()        # endet je etwa 1 s spaeter
                self.clk.now += 0.5  # bis zur naechsten Uebertragung
        # Warnung bei 101 s, die naechste erst bei 111,5 s (Uebertragung 8), dazwischen 6
        self.assertEqual(len(logs.output), 2)
        self.assertNotIn("weitere", logs.output[0])
        self.assertIn("6 weitere", logs.output[1])

    def test_without_lgpio_never_waits(self):
        guard = BusGuard(lgpio_module=None, clock=self.clk,
                         sleep=self.clk.sleep)
        guard._load = lambda: None  # kein lgpio am PC
        guard.start()
        t0 = self.clk.now
        with guard():
            pass
        self.assertEqual(self.clk.now, t0)
        self.assertFalse(guard.radar_high())
        guard.stop()

    def test_radar_high_reads_gpio22(self):
        self.assertFalse(self.guard.radar_high())
        self.lg.levels[22] = 1
        self.assertTrue(self.guard.radar_high())
        self.guard.stop()
        self.guard.stop()
        self.assertTrue(self.lg.closed)


if __name__ == "__main__":
    unittest.main()
