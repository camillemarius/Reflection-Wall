import io
import unittest

from app.ui.buttons import (BT1, BT4, BT5, BT6, ExpanderButtons, ExpanderError,
                            KeyboardButtons, QueueButtons)


class FakeExpander:
    """Liefert nacheinander die Werte; der letzte bleibt stehen."""

    def __init__(self, values):
        self.values = list(values)
        self.reads = 0

    def read(self, addr, count):
        assert addr == 0x20 and count == 2
        self.reads += 1
        v = self.values.pop(0) if len(self.values) > 1 else self.values[0]
        if isinstance(v, Exception):
            raise v
        return bytes([v & 0xFF, v >> 8])


def make(values, **kw):
    bus = FakeExpander(values)
    b = ExpanderButtons(bus=bus, poll_s=0.001, **kw)
    b.start()
    return b, bus


class ExpanderButtonsTest(unittest.TestCase):
    def test_level_change_is_press(self):
        b, _ = make([0x0000, 1 << 9])
        self.assertEqual(b.get(0.2), 5)

    def test_toggle_back_is_second_press(self):
        b, _ = make([0x0000, 1 << 9, 0x0000])
        self.assertEqual(b.get(0.2), 5)
        self.assertEqual(b.get(0.2), 5)

    def test_two_changes_in_order(self):
        b, _ = make([0x0000, (1 << 10) | (1 << 8)])
        self.assertEqual(b.get(0.2), BT4)
        self.assertEqual(b.get(0.2), BT6)

    def test_bt1_bit3_and_no_press_without_change(self):
        b, _ = make([0x0000, 1 << 3])
        self.assertEqual(b.get(0.2), BT1)
        self.assertIsNone(b.get(0.01))

    def test_other_bits_ignored(self):
        b, _ = make([0x0000, 1 << 0 | 1 << 12])
        self.assertIsNone(b.get(0.01))

    def test_drain_discards_pending(self):
        b, _ = make([0x0000, (1 << 8) | (1 << 10)])
        self.assertEqual(b.get(0.2), BT4)
        b.drain()
        self.assertIsNone(b.get(0.01))

    def test_read_error_retried_once(self):
        b, _ = make([0x0000, OSError("x"), 1 << 9])
        self.assertEqual(b.get(0.2), BT5)

    def test_second_read_error_raises(self):
        b, _ = make([0x0000, OSError("x"), OSError("y"), OSError("z")])
        with self.assertRaises(ExpanderError):
            b.get(0.2)

    def test_bus_guard_used(self):
        calls = []

        import contextlib

        @contextlib.contextmanager
        def guard():
            calls.append(1)
            yield

        b, _ = make([0x0000, 0x0000], bus_guard=guard)
        b.get(0.01)
        self.assertGreaterEqual(len(calls), 2)


class QueueButtonsTest(unittest.TestCase):
    def test_put_get(self):
        q = QueueButtons()
        q.put(3)
        self.assertEqual(q.get(0), 3)

    def test_queue_drain(self):
        q = QueueButtons()
        q.put(5)
        q.drain()
        self.assertIsNone(q.get(0))

    def test_timeout_returns_none(self):
        self.assertIsNone(QueueButtons().get(0.01))


class KeyboardButtonsTest(unittest.TestCase):
    def test_digits_become_presses(self):
        k = KeyboardButtons(stream=io.StringIO("2\nx\n7\n 6 \n"))
        k.start()
        self.assertEqual(k.get(1), 2)
        self.assertEqual(k.get(1), 6)
        self.assertIsNone(k.get(0.05))

    def test_thread_is_daemon(self):
        k = KeyboardButtons(stream=io.StringIO(""))
        k.start()
        self.assertTrue(k._thread.daemon)


if __name__ == "__main__":
    unittest.main()
