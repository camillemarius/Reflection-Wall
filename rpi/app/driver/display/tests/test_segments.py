import unittest

from app.driver.display import segments as s
from app.driver.display.ascii_map import ASCII_16SEG


class BitsTest(unittest.TestCase):
    def test_bits_match_the_font(self):
        # Ziffer 0 = der ganze Rahmen
        self.assertEqual(s.A | s.B | s.C | s.D1 | s.D2 | s.E | s.F, ASCII_16SEG["0"])
        self.assertEqual(s.G1 | s.G2, ASCII_16SEG["-"])
        self.assertEqual(s.DPB, ASCII_16SEG["."])

    def test_mirror_swaps_left_and_right(self):
        self.assertEqual(s.mirror(s.B | s.H | s.K | s.G1 | s.D1), s.F | s.J | s.M | s.G2 | s.D2)
        self.assertEqual(s.mirror(s.A | s.I | s.L | s.DPB), s.A | s.I | s.L | s.DPB)
        self.assertEqual(s.mirror(s.mirror(0xFFFF)), 0xFFFF)


class BufferTest(unittest.TestCase):
    def test_new_buffer_is_96_empty_cells(self):
        self.assertEqual(s.new_buffer(), [0] * 96)

    def test_set_cell_ors_inside_and_ignores_outside(self):
        buf = s.new_buffer()
        s.set_cell(buf, 1, 2, s.A)
        s.set_cell(buf, 1, 2, s.B)
        s.set_cell(buf, 4, 0, s.A)
        s.set_cell(buf, 0, 24, s.A)
        s.set_cell(buf, -1, 0, s.A)
        self.assertEqual(buf[1 * 24 + 2], s.A | s.B)
        self.assertEqual(sum(1 for m in buf if m), 1)

    def test_put_line_sets_glyphs_and_hangs_dots_on_the_char_before(self):
        buf = s.new_buffer()
        s.put_line(buf, 2, "Ab.", col=20)
        self.assertEqual(buf[2 * 24 + 20], ASCII_16SEG["A"])
        self.assertEqual(buf[2 * 24 + 21], ASCII_16SEG["B"] | s.DPB)
        self.assertEqual(buf[2 * 24 + 22], 0)

    def test_put_line_stops_at_the_edge(self):
        buf = s.new_buffer()
        s.put_line(buf, 0, "XYZ", col=22)
        self.assertEqual(buf[22:24], [ASCII_16SEG["X"], ASCII_16SEG["Y"]])
        self.assertEqual(buf[24], 0)

    def test_center_pads_to_the_middle(self):
        self.assertEqual(s.center("BRAVO"), " " * 9 + "BRAVO")


class LevelsTest(unittest.TestCase):
    def test_hbar_uses_top_middle_bottom_of_a_row(self):
        buf = s.new_buffer()
        s.hbar(buf, 3, 0)
        s.hbar(buf, 3, 4)
        s.hbar(buf, 3, 11)
        s.hbar(buf, 3, 12)
        self.assertEqual(buf[3], s.A)
        self.assertEqual(buf[24 + 3], s.G1 | s.G2)
        self.assertEqual(buf[72 + 3], s.D1 | s.D2)

    def test_vrun_skips_the_gap_between_rows(self):
        buf = s.new_buffer()
        s.vrun(buf, 0, 2, 0, 4)  # rechte Spur von Ebene 0 bis 4
        self.assertEqual(buf[0], s.B | s.C)
        self.assertEqual(buf[24], s.B)


if __name__ == "__main__":
    unittest.main()
