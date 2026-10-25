import unittest

from app.driver.display.ascii_map import ASCII_16SEG
from app.driver.display.cells import lines_to_cells
from app.driver.display.text_layout import wrap
from app.ui.pages import paginate

POINTER_MASK = ASCII_16SEG[">"]


class PaginateTest(unittest.TestCase):
    def test_pointer_in_the_last_cell_even_with_dots_in_row_4(self):
        # Ein Punkt teilt die Stelle mit dem Zeichen davor: der Zeiger muss trotzdem in Stelle 96.
        pages = paginate("SO. ENDE. MEHR TEXT. " * 12)
        self.assertGreater(len(pages), 1)
        self.assertTrue(any("." in page[3] for page in pages[:-1]))
        for page in pages[:-1]:
            cells = lines_to_cells(page)
            self.assertEqual(cells[95], POINTER_MASK, page)
            self.assertNotIn(POINTER_MASK, cells[72:95], page)
        self.assertNotIn(POINTER_MASK, lines_to_cells(pages[-1]))

    def test_short_text_one_page(self):
        self.assertEqual(paginate("HALLO WELT"), [wrap("HALLO WELT")[0]])

    def test_empty_text_one_blank_page(self):
        self.assertEqual(paginate(""), [wrap("")[0]])

    def test_exactly_fitting_text_is_one_page_without_pointer(self):
        text = "X" * 96
        self.assertEqual(paginate(text), [wrap(text)[0]])

    def test_long_text_pages_with_pointer(self):
        p = paginate(" ".join(["WORT"] * 60))
        self.assertGreater(len(p), 1)
        for page in p[:-1]:
            self.assertEqual(page[3][23], ">")
            self.assertNotEqual(page[3][22], ">")
        self.assertNotIn(">", "".join(p[-1]))
        for page in p:
            self.assertEqual(len(page), 4)
            self.assertTrue(all(len(r) == 24 for r in page))

    def test_no_words_lost_or_split(self):
        words = ["WORT%d" % i for i in range(80)]
        p = paginate(" ".join(words))
        got = []
        for page in p:
            for i, row in enumerate(page):
                if i == 3 and page is not p[-1]:
                    row = row[:23]
                got.extend(row.split())
        self.assertEqual(got, words)

    def test_long_word_is_hard_split_across_pages(self):
        p = paginate("A" * 300)
        self.assertGreater(len(p), 2)
        joined = "".join(r for page in p for r in page)
        self.assertEqual(joined.replace(">", "").replace(" ", ""), "A" * 300)


if __name__ == "__main__":
    unittest.main()
