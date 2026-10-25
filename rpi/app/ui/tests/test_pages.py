import unittest

from app.driver.display.text_layout import wrap
from app.ui.pages import paginate


class PaginateTest(unittest.TestCase):
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
