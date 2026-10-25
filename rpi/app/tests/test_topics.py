import os
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from app import topics


class TopicsTest(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.dir = Path(self._tmp.name)

    def write(self, name, text):
        (self.dir / name).write_text(text, encoding="utf-8")

    def test_default_topic(self):
        self.assertEqual(topics.DEFAULT_TOPIC, "Was ist der Sinn des Lebens")
        self.assertEqual(topics.read_daily(self.dir), topics.DEFAULT_TOPIC)
        self.assertEqual(topics.read_hand(self.dir), topics.DEFAULT_TOPIC)

    def test_config_dir(self):
        self.assertEqual(topics.CONFIG_DIR.name, "config")
        self.assertEqual(topics.CONFIG_DIR.parent.name, "app")

    def test_daily_read(self):
        self.write("thema.txt", "Mut\n")
        self.assertEqual(topics.read_daily(self.dir), "Mut")

    def test_hand_topic_falls_back(self):
        self.write("thema_hand.txt", "  \n")
        self.write("thema.txt", "Mut")
        self.assertEqual(topics.read_hand(self.dir), "Mut")

    def test_hand_topic_used(self):
        self.write("thema_hand.txt", "Zeit")
        self.write("thema.txt", "Mut")
        self.assertEqual(topics.read_hand(self.dir), "Zeit")

    def test_clean(self):
        cleaned = topics.clean("a\nb" + "x" * 200)
        self.assertNotIn("\n", cleaned)
        self.assertLessEqual(len(cleaned), 120)
        self.assertEqual(topics.clean("  a \t\n  b  "), "a b")

    def test_save_round_trip_and_creates_dir(self):
        target = self.dir / "neu" / "config"
        topics.save(target, "Mut\nund mehr", "Zeit")
        self.assertEqual(topics.read_daily(target), "Mut und mehr")
        self.assertEqual(topics.read_hand(target), "Zeit")
        self.assertEqual(sorted(os.listdir(target)), ["thema.txt", "thema_hand.txt"])

    def test_save_uses_replace(self):
        with mock.patch("app.topics.os.replace", wraps=os.replace) as rep:
            topics.save(self.dir, "A", "B")
        self.assertEqual(rep.call_count, 2)
        for call in rep.call_args_list:
            self.assertNotEqual(call.args[0], call.args[1])

    def test_save_empty_hand_falls_back(self):
        topics.save(self.dir, "Mut", "")
        self.assertEqual(topics.read_hand(self.dir), "Mut")


if __name__ == "__main__":
    unittest.main()
