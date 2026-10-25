import unittest

from app.ui.short_answer import SHORT_RULE, ask_short


class AskShortTest(unittest.TestCase):
    def _asker(self, answers):
        calls = []

        def ask():
            calls.append(1)
            return answers[len(calls) - 1]

        return ask, calls

    def test_ask_short_retries_until_fit(self):
        ask, calls = self._asker(["X" * 200, "KURZ"])
        self.assertEqual(ask_short(ask), "KURZ")
        self.assertEqual(len(calls), 2)

    def test_ask_short_gives_up_after_three(self):
        answers = ["X" * 200, "Y" * 200, "Z" * 200, "W" * 200]
        ask, calls = self._asker(answers)
        self.assertEqual(ask_short(ask), "Z" * 200)
        self.assertEqual(len(calls), 3)

    def test_fitting_answer_is_asked_once(self):
        ask, calls = self._asker(["Hallo Welt"])
        self.assertEqual(ask_short(ask), "Hallo Welt")
        self.assertEqual(len(calls), 1)

    def test_rule_names_the_limit(self):
        self.assertIn("96", SHORT_RULE)


if __name__ == "__main__":
    unittest.main()
