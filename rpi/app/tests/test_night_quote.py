import tempfile
import unittest
from pathlib import Path
from unittest import mock

from app import night_quote, topics
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


SYSTEM = ("Entwickle daraus den nächsten Gedanken. Höchstens 96 Zeichen, auf keinen Fall länger. "
          "Nur Buchstaben, Ziffern, Leerzeichen und Punkt, keine Umlaute.")
GOOD = "Mut ist leise"
TOO_LONG = "x" * 97


class FakeAsk:
    """Gibt feste Antworten der Reihe nach zurueck; eine Exception wird geworfen."""

    def __init__(self, *answers):
        self.answers = list(answers)
        self.calls = []

    def __call__(self, messages):
        self.calls.append(messages)
        answer = self.answers.pop(0)
        if isinstance(answer, Exception):
            raise answer
        return answer


class MakeNightQuoteTest(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.dir = Path(self._tmp.name)

    def write(self, name, text):
        (self.dir / name).write_text(text, encoding="utf-8")

    def test_messages_with_and_without_yesterday(self):
        with_y = night_quote.build_night_messages("Mut", "Gestern war ruhig")
        self.assertEqual(with_y[0], {"role": "system", "content": SYSTEM})
        self.assertEqual(len(with_y), 2)
        self.assertEqual(with_y[1]["role"], "user")
        self.assertEqual(with_y[1]["content"], "Thema: Mut\nGedanke von gestern: Gestern war ruhig")
        without = night_quote.build_night_messages("Mut", "")
        self.assertEqual(without[1]["content"], "Thema: Mut")

    def test_new_topic_drops_yesterday(self):
        self.write("thema.txt", "Mut\n")
        topics.save_last_daily(self.dir, "Angst")
        ask = FakeAsk(GOOD)
        night_quote.make_night_quote("Gestern war ruhig", ask, self.dir)
        self.assertEqual(ask.calls[0][1]["content"], "Thema: Mut")

    def test_same_topic_keeps_yesterday(self):
        self.write("thema.txt", "Mut\n")
        topics.save_last_daily(self.dir, "Mut")
        ask = FakeAsk(GOOD)
        night_quote.make_night_quote("Gestern war ruhig", ask, self.dir)
        self.assertIn("Gedanke von gestern: Gestern war ruhig", ask.calls[0][1]["content"])

    def test_empty_last_topic_counts_as_new(self):
        self.write("thema.txt", "Mut\n")
        ask = FakeAsk(GOOD)
        night_quote.make_night_quote("Gestern war ruhig", ask, self.dir)
        self.assertEqual(ask.calls[0][1]["content"], "Thema: Mut")

    def test_first_fitting_answer_wins_and_topic_is_remembered(self):
        self.write("thema.txt", "Mut\n")
        ask = FakeAsk(TOO_LONG, GOOD, "Nicht gebraucht")
        result = night_quote.make_night_quote("", ask, self.dir)
        self.assertEqual(result, ("QUOTE", GOOD))
        self.assertEqual(len(ask.calls), 2)
        self.assertEqual(topics.read_last_daily(self.dir), "Mut")

    def test_cleaning_makes_answer_fit(self):
        ask = FakeAsk("  Mut über  alles!  ")
        result = night_quote.make_night_quote("", ask, self.dir)
        self.assertEqual(result, ("QUOTE", "Mut ueber alles"))

    def test_three_bad_answers_is_zu_lang(self):
        ask = FakeAsk(TOO_LONG, TOO_LONG, TOO_LONG, GOOD)
        result = night_quote.make_night_quote("", ask, self.dir)
        self.assertEqual(result, ("ERROR", "ZU_LANG"))
        self.assertEqual(len(ask.calls), 3)

    def test_ai_error_string_is_ki(self):
        ask = FakeAsk("Fehler: Zeitueberschreitung", GOOD)
        self.assertEqual(night_quote.make_night_quote("", ask, self.dir), ("ERROR", "KI"))
        self.assertEqual(len(ask.calls), 1)  # nach einem Fehler der KI keine zweite Frage

    def test_ai_exception_is_ki(self):
        ask = FakeAsk(RuntimeError("kein Netz"), GOOD)
        self.assertEqual(night_quote.make_night_quote("", ask, self.dir), ("ERROR", "KI"))
        self.assertEqual(len(ask.calls), 1)

    def test_empty_answer_fallback_is_ki(self):
        # write_to_ai gibt "Leere Antwort" zurueck, wenn auch der Rueckfall nichts liefert. Das
        # ist kein Zitat: ERROR|KI, keine zweite Frage, und .thema_zuletzt bleibt ungeschrieben.
        for raw in ("Leere Antwort", "  Leere Antwort\n"):
            with self.subTest(raw=raw):
                ask = FakeAsk(raw, GOOD)
                self.assertEqual(night_quote.make_night_quote("", ask, self.dir), ("ERROR", "KI"))
                self.assertEqual(len(ask.calls), 1)
                self.assertFalse((self.dir / topics.LAST_DAILY_FILE).exists())

    def test_failed_topic_write_still_returns_quote(self):
        # M5: eine nur lesbare SD-Karte darf die Nacht nicht scheitern lassen
        self.write("thema.txt", "Mut\n")
        with mock.patch.object(night_quote.topics, "save_last_daily",
                               side_effect=OSError("Read-only file system")) as save, \
                self.assertLogs("app.night_quote", "ERROR") as logs:
            result = night_quote.make_night_quote("", FakeAsk(GOOD), self.dir)
        self.assertEqual(result, ("QUOTE", GOOD))
        save.assert_called_once_with(self.dir, "Mut")
        self.assertIn(topics.LAST_DAILY_FILE, "\n".join(logs.output))

    def test_failed_night_keeps_last_topic(self):
        self.write("thema.txt", "Mut\n")
        topics.save_last_daily(self.dir, "Angst")
        night_quote.make_night_quote("", FakeAsk("Fehler: x"), self.dir)
        night_quote.make_night_quote("", FakeAsk(TOO_LONG, TOO_LONG, TOO_LONG), self.dir)
        self.assertEqual(topics.read_last_daily(self.dir), "Angst")

    def test_missing_topic_file_uses_default(self):
        ask = FakeAsk(GOOD)
        night_quote.make_night_quote("", ask, self.dir)
        self.assertEqual(ask.calls[0][1]["content"], "Thema: " + topics.DEFAULT_TOPIC)
        self.assertEqual(topics.read_last_daily(self.dir), topics.DEFAULT_TOPIC)


if __name__ == "__main__":
    unittest.main()
