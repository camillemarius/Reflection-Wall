import unittest

from app import night_quote
from app.tests.vectors import load_vectors


class QuoteVectorTest(unittest.TestCase):
    def test_quote_fits_follows_the_shared_cases(self):
        cases = [v for v in load_vectors("quote_vectors.json") if v["kind"] == "check"]
        self.assertGreaterEqual(len(cases), 15)
        for v in cases:
            with self.subTest(v["name"]):
                self.assertEqual(night_quote.quote_fits(v["text"]), v["acceptable"] == 1)

    def test_clean_quote_follows_the_shared_cases(self):
        cases = [v for v in load_vectors("quote_vectors.json") if v["kind"] == "clean"]
        self.assertGreaterEqual(len(cases), 15)
        for v in cases:
            with self.subTest(v["name"]):
                self.assertEqual(night_quote.clean_quote(v["raw"]), v["cleaned"])


if __name__ == "__main__":
    unittest.main()
