import unittest

from app.ui.menu import Menu


class MenuTest(unittest.TestCase):
    def test_pointer_stays_in_second_line_and_list_moves_up(self):
        m = Menu(["A", "B", "C", "D", "E", "F"])
        self.assertEqual(m.lines(), ["  F", "> A", "  B", "  C"])
        m.down()
        self.assertEqual(m.lines(), ["  A", "> B", "  C", "  D"])
        m.down()
        self.assertEqual(m.lines(), ["  B", "> C", "  D", "  E"])

    def test_list_wraps_round_after_the_last_item(self):
        m = Menu(["A", "B", "C", "D", "E", "F"])
        m.select(4)
        self.assertEqual(m.lines(), ["  D", "> E", "  F", "  A"])
        m.down()
        self.assertEqual(m.lines(), ["  E", "> F", "  A", "  B"])
        m.down()
        self.assertEqual(m.selected, 0)
        self.assertEqual(m.lines(), ["  F", "> A", "  B", "  C"])

    def test_four_items_fill_every_line(self):
        m = Menu(["A", "B", "C", "D"])
        self.assertEqual(m.lines(), ["  D", "> A", "  B", "  C"])

    def test_short_menu_shows_every_item_once(self):
        self.assertEqual(Menu(["A", "B", "C"]).lines(), ["  C", "> A", "  B", ""])
        two = Menu(["A", "B"])
        self.assertEqual(two.lines(), ["", "> A", "  B", ""])
        two.down()
        self.assertEqual(two.lines(), ["", "> B", "  A", ""])
        self.assertEqual(Menu(["A"]).lines(), ["", "> A", "", ""])

    def test_select_sets_pointer(self):
        m = Menu(["A", "B", "C", "D", "E"])
        m.select(4)
        self.assertEqual(m.selected, 4)
        self.assertEqual(m.lines()[1], "> E")


if __name__ == "__main__":
    unittest.main()
