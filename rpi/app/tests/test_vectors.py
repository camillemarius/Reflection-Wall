import unittest

from app.tests.vectors import load_vectors


class VectorFileTest(unittest.TestCase):
    def test_protocol_vectors_have_the_shared_form(self):
        vectors = load_vectors("protocol_vectors.json")
        self.assertGreaterEqual(len(vectors), 52)

    def test_display_vectors_have_the_shared_form(self):
        vectors = load_vectors("display_vectors.json")
        self.assertGreaterEqual(len(vectors), 60)
        self.assertEqual({v["kind"] for v in vectors}, {"wrap", "glyph"})


if __name__ == "__main__":
    unittest.main()
