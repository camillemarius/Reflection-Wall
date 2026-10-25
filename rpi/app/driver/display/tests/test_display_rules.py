import unittest

from app.driver.display.ascii_map import ASCII_16SEG
from app.driver.display.text_layout import displayable, wrap
from app.tests.vectors import load_vectors


def _of_kind(kind):
    return [v for v in load_vectors("display_vectors.json") if v["kind"] == kind]


class DisplayRulesTest(unittest.TestCase):
    def test_wrap_vectors(self):
        vectors = _of_kind("wrap")
        self.assertGreaterEqual(len(vectors), 14)
        for v in vectors:
            with self.subTest(v["name"]):
                rows = [v["row1"], v["row2"], v["row3"], v["row4"]]
                self.assertEqual(wrap(v["text"]), (rows, v["fits"] == 1))

    def test_font_matches_glyphs(self):
        vectors = _of_kind("glyph")
        self.assertGreaterEqual(len(vectors), 45)
        for v in vectors:
            with self.subTest(v["name"]):
                self.assertEqual(ASCII_16SEG.get(v["char"].upper(), 0), int(v["segments"], 16))

    def test_displayable(self):
        for v in _of_kind("glyph"):
            with self.subTest(v["name"]):
                self.assertEqual(displayable(v["char"]), v["displayable"] == 1)


if __name__ == "__main__":
    unittest.main()
