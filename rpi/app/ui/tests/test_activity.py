import threading
import unittest

from app.ui.activity import Activity, RadarPresence, idle_minutes_from_env


class Clock:
    def __init__(self):
        self.t = 0.0

    def __call__(self):
        return self.t


class ActivityTest(unittest.TestCase):
    def setUp(self):
        self.c = Clock()

    def test_off_by_default(self):
        a = Activity(clock=self.c)
        self.c.t = 10_000
        self.assertFalse(a.expired())

    def test_expires_after_idle(self):
        a = Activity(clock=self.c, idle_minutes=15)
        self.c.t = 15 * 60 - 1
        self.assertFalse(a.expired())
        self.c.t = 15 * 60 + 1
        self.assertTrue(a.expired())

    def test_touch_resets(self):
        a = Activity(clock=self.c, idle_minutes=15)
        self.c.t = 14 * 60
        a.touch()
        self.c.t = 28 * 60
        self.assertFalse(a.expired())
        self.c.t = 29 * 60 + 1
        self.assertTrue(a.expired())

    def test_busy_counts_as_activity(self):
        a = Activity(clock=self.c, idle_minutes=15)
        with a.busy():
            self.c.t = 100 * 60
            self.assertFalse(a.expired())
        self.assertFalse(a.expired())
        self.c.t = 100 * 60 + 15 * 60 - 1
        self.assertFalse(a.expired())
        self.c.t = 100 * 60 + 15 * 60 + 1
        self.assertTrue(a.expired())

    def test_nested_busy_counts(self):
        a = Activity(clock=self.c, idle_minutes=15)
        outer = a.busy()
        inner = a.busy()
        outer.__enter__()
        inner.__enter__()
        outer.__exit__(None, None, None)
        self.c.t = 50 * 60
        self.assertFalse(a.expired())
        inner.__exit__(None, None, None)
        self.assertFalse(a.expired())
        self.c.t = 66 * 60
        self.assertTrue(a.expired())

    def test_busy_released_on_exception(self):
        a = Activity(clock=self.c, idle_minutes=15)
        with self.assertRaises(ValueError):
            with a.busy():
                raise ValueError
        self.c.t = 16 * 60
        self.assertTrue(a.expired())

    def test_busy_from_worker_thread(self):
        a = Activity(clock=self.c, idle_minutes=15)
        entered, release = threading.Event(), threading.Event()

        def work():
            with a.busy():
                entered.set()
                release.wait(5)

        t = threading.Thread(target=work)
        t.start()
        entered.wait(5)
        self.c.t = 60 * 60
        self.assertFalse(a.expired())
        release.set()
        t.join()

    def test_person_present_counts(self):
        a = Activity(clock=self.c, idle_minutes=15, person_present=lambda: True)
        self.c.t = 10_000
        self.assertFalse(a.expired())

    def test_time_starts_when_person_leaves(self):
        present = [True]
        a = Activity(clock=self.c, idle_minutes=15, person_present=lambda: present[0])
        self.c.t = 100 * 60
        self.assertFalse(a.expired())
        present[0] = False
        self.c.t = 100 * 60 + 14 * 60
        self.assertFalse(a.expired())
        self.c.t = 100 * 60 + 15 * 60 + 1
        self.assertTrue(a.expired())

    def test_radar_not_read_when_off(self):
        calls = []
        a = Activity(clock=self.c, person_present=lambda: calls.append(1) or True)
        a.expired()
        self.assertEqual(calls, [])


class EnvTest(unittest.TestCase):
    def test_values(self):
        self.assertEqual(idle_minutes_from_env({}), 0)
        self.assertEqual(idle_minutes_from_env({"AUTO_AUS_MINUTEN": "15"}), 15)
        self.assertEqual(idle_minutes_from_env({"AUTO_AUS_MINUTEN": " 15 "}), 15)
        self.assertEqual(idle_minutes_from_env({"AUTO_AUS_MINUTEN": "abc"}), 0)
        self.assertEqual(idle_minutes_from_env({"AUTO_AUS_MINUTEN": "-5"}), 0)
        self.assertEqual(idle_minutes_from_env({"AUTO_AUS_MINUTEN": ""}), 0)


class FakeLgpio:
    SET_PULL_DOWN = 32

    def __init__(self, level=1):
        self.level = level
        self.calls = []

    def gpiochip_open(self, chip):
        self.calls.append(("open", chip))
        return 7

    def gpio_claim_input(self, h, gpio, flags=0):
        self.calls.append(("claim", h, gpio, flags))

    def gpiochip_close(self, h):
        self.calls.append(("close", h))

    def gpio_read(self, h, gpio):
        self.calls.append(("read", h, gpio))
        return self.level


class RadarPresenceTest(unittest.TestCase):
    def test_lazy_and_reads_gpio22(self):
        fake = FakeLgpio(1)
        r = RadarPresence(lgpio_module=fake)
        self.assertEqual(fake.calls, [])
        self.assertTrue(r.present())
        self.assertEqual(fake.calls[:2], [("open", 0), ("claim", 7, 22, 32)])
        fake.level = 0
        self.assertFalse(r.present())
        self.assertEqual(sum(1 for c in fake.calls if c[0] == "open"), 1)

    def test_claim_uses_pull_down(self):
        fake = FakeLgpio(0)
        RadarPresence(lgpio_module=fake).present()
        self.assertIn(("claim", 7, 22, fake.SET_PULL_DOWN), fake.calls)

    def test_claim_failure_closes_handle_and_keeps_nothing(self):
        class BusyPin(FakeLgpio):
            def gpio_claim_input(self, h, gpio, flags=0):
                raise OSError("GPIO busy")

        fake = BusyPin()
        r = RadarPresence(lgpio_module=fake)
        self.assertFalse(r.present())
        self.assertFalse(r.present())
        self.assertEqual(fake.calls.count(("close", 7)), 2)
        self.assertIsNone(r._handle)

    def test_failed_import_is_not_retried(self):
        import builtins
        real, tries = builtins.__import__, []

        def fake_import(name, *a, **k):
            if name == "lgpio":
                tries.append(1)
                raise ImportError(name)
            return real(name, *a, **k)

        builtins.__import__ = fake_import
        try:
            r = RadarPresence()
            self.assertFalse(r.present())
            self.assertFalse(r.present())
        finally:
            builtins.__import__ = real
        self.assertEqual(len(tries), 1)

    def test_error_means_absent(self):
        class Broken(FakeLgpio):
            def gpiochip_open(self, chip):
                raise OSError("kein GPIO")

        self.assertFalse(RadarPresence(lgpio_module=Broken()).present())


if __name__ == "__main__":
    unittest.main()
