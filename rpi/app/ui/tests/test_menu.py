import unittest

from app.ui.menu import Menu


class MenuTest(unittest.TestCase):
    def test_pointer_stays_in_second_line_and_list_moves_up(self):
        m = Menu(["A", "B", "C", "D", "E", "F"])
        self.assertEqual(m.lines(), ["", "> A", "  B", "  C"])
        m.down()
        self.assertEqual(m.lines(), ["  A", "> B", "  C", "  D"])
        m.down()
        self.assertEqual(m.lines(), ["  B", "> C", "  D", "  E"])

    def test_one_empty_line_marks_where_the_list_starts_again(self):
        m = Menu(["A", "B", "C", "D", "E", "F"])
        m.select(4)
        self.assertEqual(m.lines(), ["  D", "> E", "  F", ""])
        m.down()
        self.assertEqual(m.lines(), ["  E", "> F", "", "  A"])
        m.down()
        self.assertEqual(m.selected, 0)
        self.assertEqual(m.lines(), ["", "> A", "  B", "  C"])

    def test_four_items(self):
        m = Menu(["A", "B", "C", "D"])
        self.assertEqual(m.lines(), ["", "> A", "  B", "  C"])
        m.select(3)
        self.assertEqual(m.lines(), ["  C", "> D", "", "  A"])

    def test_short_menu_shows_every_item_once(self):
        three = Menu(["A", "B", "C"])
        self.assertEqual(three.lines(), ["", "> A", "  B", "  C"])
        three.select(2)
        self.assertEqual(three.lines(), ["  B", "> C", "", "  A"])
        two = Menu(["A", "B"])
        self.assertEqual(two.lines(), ["", "> A", "  B", ""])
        two.down()
        self.assertEqual(two.lines(), ["  A", "> B", "", ""])
        self.assertEqual(Menu(["A"]).lines(), ["", "> A", "", ""])

    def test_select_sets_pointer(self):
        m = Menu(["A", "B", "C", "D", "E"])
        m.select(4)
        self.assertEqual(m.selected, 4)
        self.assertEqual(m.lines()[1], "> E")


if __name__ == "__main__":
    unittest.main()
