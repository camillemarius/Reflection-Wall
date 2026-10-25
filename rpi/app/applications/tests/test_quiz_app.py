import time
import unittest

from app.applications.quiz_app import QuizApp
from app.applications.Quiz.prompt import PROMPT_TEMPLATE
from app.ui.activity import Activity
from app.ui.app_host import AppContext, StopApp, StopSignal


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


def quiz(n=1, frage=None):
    return {"frage": frage or "FRAGE %d" % n, "lösung": "LOESUNG %d" % n,
            "hinweis1": "HINWEIS EINS %d" % n, "hinweis2": "HINWEIS ZWEI %d" % n,
            "hinweis3": "H3"}


class FakeGenerator:
    def __init__(self, results):
        self.results = list(results)
        self.calls = 0

    def generate_quiz(self):
        self.calls += 1
        result = self.results.pop(0)
        if isinstance(result, Exception):
            raise result
        return result


class QuizAppTest(unittest.TestCase):
    def make(self, script, results):
        display = FakeDisplay()
        ctx = AppContext(display, ScriptedButtons(display, script), Activity(), StopSignal())
        gen = FakeGenerator(results)
        made = []

        def factory():
            made.append(1)
            return gen

        return QuizApp(factory), ctx, display, gen, made

    @staticmethod
    def run_app(app, ctx):
        try:
            app.run(ctx)
        except StopApp as stop:
            return stop.reason

    def test_name(self):
        self.assertEqual(QuizApp(lambda: None).name, "QUIZ")

    def test_generator_created_only_on_run_and_once(self):
        app, ctx, display, gen, made = self.make([("FRAGE 1", 4)], [quiz()])
        self.assertEqual(made, [])
        self.run_app(app, ctx)
        self.assertEqual(made, [1])
        self.assertTrue(any("FRAGE WIRD ERZEUGT" in t for t in display.texts()))

    def test_quiz_steps(self):
        script = [("FRAGE 1", 5), ("HINWEIS EINS 1", 5), ("HINWEIS ZWEI 1", 5),
                  ("LOESUNG 1", 4)]
        app, ctx, display, gen, _ = self.make(script, [quiz()])
        self.assertEqual(self.run_app(app, ctx), "back")
        texts = display.texts()
        order = [next(i for i, t in enumerate(texts) if key in t)
                 for key in ("FRAGE WIRD", "FRAGE 1", "HINWEIS EINS 1", "HINWEIS ZWEI 1", "LOESUNG 1")]
        self.assertEqual(order, sorted(order))
        self.assertEqual(gen.calls, 1)

    def test_new_question_after_solution(self):
        script = [("FRAGE 1", 5), ("HINWEIS EINS 1", 5), ("HINWEIS ZWEI 1", 5),
                  ("LOESUNG 1", 5), ("FRAGE 2", 4)]
        app, ctx, display, gen, made = self.make(script, [quiz(1), quiz(2)])
        self.assertEqual(self.run_app(app, ctx), "back")
        self.assertEqual(gen.calls, 2)
        self.assertEqual(made, [1])

    def test_too_long_is_generated_again_at_most_three_times(self):
        results = [quiz(frage="X" * 200), quiz(frage="Y" * 200), quiz(frage="Z" * 200)]
        app, ctx, display, gen, _ = self.make([("ZZZZ", 4)], results)
        self.assertEqual(self.run_app(app, ctx), "back")
        self.assertEqual(gen.calls, 3)

    def test_long_hint_is_generated_again(self):
        bad = quiz(1)
        bad["hinweis2"] = "W" * 200
        app, ctx, _, gen, _ = self.make([("FRAGE 2", 4)], [bad, quiz(2)])
        self.run_app(app, ctx)
        self.assertEqual(gen.calls, 2)

    def test_generator_exception_then_retry(self):
        app, ctx, display, gen, _ = self.make(
            [("NOCH EINMAL", 5), ("FRAGE 1", 4)], [ValueError("kein Netz"), quiz()])
        with self.assertLogs("app.applications.quiz_app", level="ERROR"):
            self.assertEqual(self.run_app(app, ctx), "back")
        self.assertTrue(any("KI NICHT ERREICHBAR" in t for t in display.texts()))
        self.assertEqual(gen.calls, 2)

    def test_default_result_is_a_failure(self):
        default = {"frage": "Keine Frage erhalten", "lösung": "Keine Lösung erhalten",
                   "hinweis1": "Kein Hinweis 1", "hinweis2": "Kein Hinweis 2",
                   "hinweis3": "Kein Hinweis 3"}
        app, ctx, display, gen, _ = self.make(
            [("NOCH EINMAL", 5), ("FRAGE 1", 4)], [default, quiz()])
        with self.assertLogs("app.applications.quiz_app", level="ERROR"):
            self.run_app(app, ctx)
        self.assertTrue(any("KI NICHT ERREICHBAR" in t for t in display.texts()))
        self.assertEqual(gen.calls, 2)

    def test_prompt_limits_length_and_keeps_placeholder(self):
        self.assertIn("96", PROMPT_TEMPLATE)
        self.assertIn("{previous_text}", PROMPT_TEMPLATE)
        PROMPT_TEMPLATE.format(previous_text="x")


if __name__ == "__main__":
    unittest.main()
