import contextlib
import io
import unittest
from types import SimpleNamespace

from app.driver.display.terminal_display import TerminalDisplay
from app.driver.display.wall_display import MODULE_ADDRESSES, WallDisplay


class FakeBus:
    def __init__(self):
        self.block_writes = []
        self.byte_writes = []
        self.fail_next_block = 0

    def write_i2c_block_data(self, addr, reg, data):
        if self.fail_next_block:
            self.fail_next_block -= 1
            raise OSError("bus")
        self.block_writes.append(SimpleNamespace(addr=addr, reg=reg, data=list(data)))

    def write_byte(self, addr, value):
        self.byte_writes.append((addr, value))

    def clear(self):
        self.block_writes.clear()
        self.byte_writes.clear()


class WallDisplayTest(unittest.TestCase):
    def setUp(self):
        self.bus = FakeBus()
        self.d = WallDisplay(bus=self.bus)

    def prime(self, d=None):
        (d or self.d).show_cells([0] * 96)
        self.bus.clear()

    def test_addresses_row_major(self):
        self.assertEqual(MODULE_ADDRESSES, (0x70, 0x71, 0x72, 0x73, 0x74, 0x75, 0x76, 0x77, 0x7F, 0x79, 0x7B, 0x7D))

    def test_start_initialises_every_module(self):
        self.d.start()
        for addr in MODULE_ADDRESSES:
            self.assertEqual([v for a, v in self.bus.byte_writes if a == addr], [0x21, 0x81, 0xEF])
        self.assertEqual(sorted(w.addr for w in self.bus.block_writes), sorted(MODULE_ADDRESSES))

    def test_only_changed_modules_written(self):
        self.d.show_cells([0] * 96)
        self.bus.clear()
        m = [0] * 96
        m[95] = 0x0840
        self.d.show_cells(m)
        self.assertEqual([c.addr for c in self.bus.block_writes], [0x7D])

    def test_cell_bytes(self):
        m = [0] * 96
        m[0] = 0xA6A2
        m[9] = 0x0102
        self.d.show_cells(m)
        w = self.bus.block_writes[0]
        self.assertEqual((w.addr, w.reg, len(w.data)), (0x70, 0x00, 16))
        self.assertEqual((w.data[0], w.data[1]), (0xA2, 0xA6))
        w2 = self.bus.block_writes[1]
        self.assertEqual(w2.addr, 0x71)
        self.assertEqual((w2.data[2], w2.data[3]), (0x02, 0x01))

    def test_module_mapping_is_row_major_in_threes(self):
        self.prime()
        m = [0] * 96
        m[24 * 2 + 8] = 1   # Zeile 2, Modul 1 -> Index 7 -> 0x77
        m[24 * 2 + 16] = 1  # Zeile 2, Modul 2 -> Index 8 -> 0x7F
        self.d.show_cells(m)
        self.assertEqual([c.addr for c in self.bus.block_writes], [0x77, 0x7F])

    def test_retry_once_on_oserror(self):
        self.prime()
        self.bus.fail_next_block = 1
        m = [0] * 96
        m[0] = 1
        self.d.show_cells(m)
        self.assertEqual([c.addr for c in self.bus.block_writes], [0x70])

    def test_second_failure_is_logged_not_raised(self):
        self.prime()
        self.bus.fail_next_block = 2
        m = [0] * 96
        m[0] = 1
        with self.assertLogs("app.driver.display.wall_display", level="WARNING"):
            self.d.show_cells(m)
        self.assertEqual(self.bus.block_writes, [])

    def test_failed_module_is_retried_on_next_show(self):
        self.prime()
        self.bus.fail_next_block = 2
        m = [0] * 96
        m[0] = 1
        with self.assertLogs("app.driver.display.wall_display", level="WARNING"):
            self.d.show_cells(m)
        self.d.show_cells(m)
        self.assertEqual([c.addr for c in self.bus.block_writes], [0x70])

    def test_bus_guard_wraps_every_transfer(self):
        events = []

        @contextlib.contextmanager
        def guard():
            events.append("in")
            yield
            events.append("out")

        d = WallDisplay(bus=self.bus, bus_guard=guard)
        self.prime(d)
        events.clear()
        m = [0] * 96
        m[0] = 1
        d.show_cells(m)
        self.assertEqual(events, ["in", "out"])

    def test_set_segments_refresh(self):
        self.d.set_segments(2, 3, 0x1111)
        self.assertEqual(self.bus.block_writes, [])
        self.d.refresh()
        w = [c for c in self.bus.block_writes if c.addr == 0x79]
        self.assertEqual(len(w), 1)
        self.assertEqual((w[0].data[2 * 2 + 0], w[0].data[2 * 2 + 1]), (0x11, 0x11))
        self.assertEqual((self.d.WIDTH, self.d.HEIGHT), (24, 4))

    def test_set_segments_out_of_range_ignored(self):
        self.prime()
        self.d.set_segments(24, 0, 1)
        self.d.set_segments(0, 4, 1)
        self.d.set_segments(-1, 0, 1)
        self.d.refresh()
        self.assertEqual(self.bus.block_writes, [])

    def test_canvas_clear_then_refresh_blanks(self):
        self.d.set_segments(0, 0, 0x1111)
        self.d.refresh()
        self.bus.clear()
        self.d.clear()
        self.assertEqual([c.addr for c in self.bus.block_writes], [0x70])
        self.assertEqual(self.bus.block_writes[0].data, [0] * 16)

    def test_show_lines_and_text(self):
        self.d.show_lines(["HALLO"])
        w = [c for c in self.bus.block_writes if c.addr == 0x70][0]
        self.assertNotEqual(w.data[:10], [0] * 10)
        self.bus.clear()
        self.assertTrue(self.d.show_text("hallo welt"))
        self.assertFalse(self.d.show_text("X" * 200))


class TerminalDisplayTest(unittest.TestCase):
    def test_prints_four_rows(self):
        d = TerminalDisplay()
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            d.show_text("hallo")
        lines = out.getvalue().splitlines()
        rows = [l for l in lines if "HALLO" in l]
        self.assertEqual(len(rows), 1)

    def test_unknown_pattern_is_hash(self):
        d = TerminalDisplay()
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            d.show_cells([0x7777] + [0] * 95)
        self.assertIn("#", out.getvalue())

    def test_canvas_api(self):
        d = TerminalDisplay()
        d.set_segments(0, 0, 0x0840)
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            d.refresh()
        self.assertIn(">", out.getvalue())
        self.assertEqual((d.WIDTH, d.HEIGHT), (24, 4))


if __name__ == "__main__":
    unittest.main()
