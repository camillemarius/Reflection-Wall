import tempfile
import time
import unittest
from pathlib import Path
from unittest import mock

from app.applications.reflection_app import ReflectionApp, build_reflection_messages
from app.ui.activity import Activity
from app.ui.app_host import AppContext, StopApp, StopSignal
from app.ui.short_answer import SHORT_RULE


class FakeDisplay:
    def __init__(self):
        self.calls = []

    def show_lines(self, lines, dots_own_cell=False):
        self.calls.append(list(lines))

    def texts(self):
        return [" ".join(" ".join(c).split()) for c in self.calls]


class ScriptedButtons:
    def __init__(self, display, script):
        self.display, self.script = display, list(script)

    def get(self, timeout):
        if self.script:
            screen, button = self.script[0]
            texts = self.display.texts()
            if texts and screen in texts[-1]:
                self.script.pop(0)
                return button
        time.sleep(min(timeout or 0, 0.005))
        return None

    def drain(self):
        pass


START = "BT5 NEUER GEDANKE"


class ReflectionAppTest(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.dir = Path(self._tmp.name)

    def make(self, script, ask):
        display = FakeDisplay()
        ctx = AppContext(display, ScriptedButtons(display, script), Activity(), StopSignal())
        return ReflectionApp(ask=ask, config_dir=self.dir), ctx, display

    @staticmethod
    def run_app(app, ctx):
        try:
            app.run(ctx)
        except StopApp as stop:
            return stop.reason

    def test_name(self):
        self.assertEqual(ReflectionApp(ask=lambda m: "").name, "REFLECTION")

    def test_messages(self):
        first = build_reflection_messages("Mut", None)
        self.assertEqual([m["role"] for m in first], ["system", "user"])
        self.assertTrue(first[0]["content"].startswith(SHORT_RULE))
        self.assertIn("Mut", first[1]["content"])
        second = build_reflection_messages("Mut", "ERSTER GEDANKE")
        self.assertIn("Mut", second[1]["content"])
        self.assertIn("ERSTER GEDANKE", second[1]["content"])
        self.assertNotIn("ERSTER", first[0]["content"] + first[1]["content"])

    def test_reflection_chain_in_memory(self):
        (self.dir / "thema_hand.txt").write_text("Mut", encoding="utf-8")
        seen = []
        answers = ["ERSTER", "ZWEITER", "NEUER"]

        def ask(messages):
            seen.append(messages)
            return answers.pop(0)

        app, ctx, display = self.make([(START, 5), ("ERSTER", 5), ("ZWEITER", 4)], ask)
        self.assertEqual(self.run_app(app, ctx), "back")
        self.assertTrue(any("DENKE NACH" in t for t in display.texts()))
        self.assertIn("Mut", seen[0][1]["content"])
        self.assertNotIn("ERSTER", seen[0][1]["content"])
        self.assertIn("ERSTER", seen[1][1]["content"])

        app2, ctx2, _ = self.make([(START, 5), ("NEUER", 4)], ask)
        self.assertEqual(self.run_app(app2, ctx2), "back")
        self.assertNotIn("ERSTER", seen[2][1]["content"])
        self.assertNotIn("ZWEITER", seen[2][1]["content"])

    def test_reflection_never_touches_db(self):
        with mock.patch("app.driver.database.mysql.get_previous_answers") as get, \
                mock.patch("app.driver.database.mysql.save_answer") as save, \
                mock.patch("app.driver.database.mysql.get_connection") as conn:
            app, ctx, _ = self.make([(START, 5), ("GEDANKE", 4)], lambda m: "GEDANKE")
            self.run_app(app, ctx)
        get.assert_not_called()
        save.assert_not_called()
        conn.assert_not_called()

    def test_ai_failure_then_retry(self):
        answers = ["Fehler: Netz", "GUT"]
        app, ctx, display = self.make(
            [(START, 5), ("NOCH EINMAL", 5), ("GUT", 4)], lambda m: answers.pop(0))
        with self.assertLogs("app.applications.reflection_app", level="ERROR"):
            self.assertEqual(self.run_app(app, ctx), "back")
        self.assertTrue(any("KI NICHT ERREICHBAR" in t for t in display.texts()))

    def test_ai_exception(self):
        def ask(messages):
            raise ValueError("kein Schluessel")

        app, ctx, display = self.make([(START, 5), ("NICHT ERREICHBAR", 4)], ask)
        with self.assertLogs("app.applications.reflection_app", level="ERROR"):
            self.assertEqual(self.run_app(app, ctx), "back")
        self.assertTrue(any("KI NICHT ERREICHBAR" in t for t in display.texts()))

    def test_long_thought_asks_again(self):
        answers = ["X" * 200, "KURZ"]
        app, ctx, display = self.make([(START, 5), ("KURZ", 4)], lambda m: answers.pop(0))
        self.run_app(app, ctx)
        self.assertEqual(answers, [])


if __name__ == "__main__":
    unittest.main()
