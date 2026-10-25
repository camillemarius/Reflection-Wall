import unittest

from app.driver.display.ascii_map import ASCII_16SEG
from app.driver.display.cells import line_to_cells, lines_to_cells, normalize


class CellsTest(unittest.TestCase):
    def test_dot_merges_into_previous(self):
        c = line_to_cells("ZIEL.")
        self.assertEqual(c[3], ASCII_16SEG["L"] | 0x0004)
        self.assertEqual(c[4], 0)

    def test_dot_at_line_start_stays_empty(self):
        c = line_to_cells(".A")
        self.assertEqual(c[0], 0)
        self.assertEqual(c[1], ASCII_16SEG["A"])

    def test_dot_own_cell(self):
        c = line_to_cells("WALL.LOCAL", dots_own_cell=True)
        self.assertEqual(c[4], 0x0004)
        self.assertEqual(c[5], ASCII_16SEG["L"])

    def test_dots_never_overflow(self):
        self.assertEqual(len(line_to_cells("A." * 30)), 24)
        self.assertEqual(len(line_to_cells("A." * 30, dots_own_cell=True)), 24)

    def test_unknown_character_is_blank(self):
        self.assertEqual(line_to_cells("A~B")[1], 0)

    def test_lines_to_cells_pads_missing_rows(self):
        c = lines_to_cells(["A"])
        self.assertEqual(len(c), 96)
        self.assertEqual(c[0], ASCII_16SEG["A"])
        self.assertEqual(c[24:], [0] * 72)

    def test_normalize(self):
        self.assertEqual(normalize("Grüße\nÄrger"), "GRUESSE AERGER")
        self.assertEqual(normalize("a\r\nb Öl Ü"), "A  B OEL UE")


if __name__ == "__main__":
    unittest.main()
