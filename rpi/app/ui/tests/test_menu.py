import unittest

from app.ui.menu import Menu


class MenuTest(unittest.TestCase):
    def test_menu_scrolls_and_wraps(self):
        m = Menu(["A", "B", "C", "D", "E", "F"])
        for _ in range(4):
            m.down()
        self.assertEqual(m.lines()[3], "> E")
        self.assertEqual(m.lines()[0], "  B")
        m.down()
        m.down()
        self.assertEqual(m.lines()[0], "> A")
        self.assertEqual(m.selected, 0)

    def test_short_menu_is_padded_to_four_lines(self):
        m = Menu(["A", "B"])
        self.assertEqual(m.lines(), ["> A", "  B", "", ""])

    def test_select_sets_pointer(self):
        m = Menu(["A", "B", "C", "D", "E"])
        m.select(4)
        self.assertEqual(m.selected, 4)
        self.assertEqual(m.lines()[3], "> E")
