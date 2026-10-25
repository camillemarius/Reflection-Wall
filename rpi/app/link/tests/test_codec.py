import unittest

from app.link.codec import (
    DecodeError,
    EncodeError,
    Message,
    deadline_ms,
    decode,
    encode,
    role_of,
)
from app.tests.vectors import load_vectors

VECTORS = load_vectors("protocol_vectors.json")


def _of_kind(*kinds):
    return [v for v in VECTORS if v["kind"] in kinds]


def _line(v):
    return v["line"].encode("latin-1")


class CodecVectorTest(unittest.TestCase):
    def test_both(self):
        cases = _of_kind("both")
        self.assertTrue(cases)
        for v in cases:
            with self.subTest(name=v["name"]):
                msg = Message(v["seq"], v["command"], v["data"])
                self.assertEqual(encode(msg), _line(v))
                self.assertEqual(decode(_line(v)), msg)

    def test_decode(self):
        cases = _of_kind("decode")
        self.assertTrue(cases)
        for v in cases:
            with self.subTest(name=v["name"]):
                self.assertEqual(decode(_line(v)), Message(v["seq"], v["command"], v["data"]))

    def test_error(self):
        cases = _of_kind("error")
        self.assertTrue(cases)
        for v in cases:
            with self.subTest(name=v["name"]):
                with self.assertRaises(DecodeError) as cm:
                    decode(_line(v))
                self.assertEqual(cm.exception.code, v["error"])

    def test_encode_error(self):
        cases = _of_kind("encode_error")
        self.assertTrue(cases)
        for v in cases:
            with self.subTest(name=v["name"]):
                with self.assertRaises(EncodeError) as cm:
                    encode(Message(v["seq"], v["command"], v["data"]))
                self.assertEqual(cm.exception.code, v["error"])

    def test_command(self):
        cases = _of_kind("command")
        self.assertTrue(cases)
        for v in cases:
            with self.subTest(name=v["name"]):
                self.assertEqual(role_of(v["command"]), v["role"])
                if "deadline_ms" in v:
                    self.assertEqual(deadline_ms(v["command"]), v["deadline_ms"])


class CodecTypeTest(unittest.TestCase):
    def test_decode_takes_bytes(self):
        with self.assertRaises(TypeError):
            decode("$00:PING*2A")

    def test_seq_out_of_range(self):
        for seq in (-1, 256):
            with self.subTest(seq=seq):
                with self.assertRaises(EncodeError) as cm:
                    encode(Message(seq, "PING"))
                self.assertEqual(cm.exception.code, "BAD_FORMAT")


if __name__ == "__main__":
    unittest.main()
