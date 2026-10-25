# applications/quiz_app.py
# Quiz auf der Wand: Frage, dann mit BT5 Hinweis 1, Hinweis 2, Loesung, neue Frage.
# Die Datenbank des Quiz bleibt Sache des Generators.
import logging

from app.driver.display.cells import normalize
from app.driver.display.text_layout import wrap
from app.ui.app_host import StopApp
from app.ui.buttons import BT5

log = logging.getLogger(__name__)

MAX_GENERATIONS = 3
KEYS = ("frage", "hinweis1", "hinweis2", "lösung")
DEFAULTS = {"frage": "Keine Frage erhalten", "lösung": "Keine Lösung erhalten",
            "hinweis1": "Kein Hinweis 1", "hinweis2": "Kein Hinweis 2"}


def _default_generator():
    from app.applications.Quiz.AIQuizGenerator import AIQuizGenerator
    return AIQuizGenerator()


def _fits(quiz: dict) -> bool:
    return all(wrap(normalize(str(quiz.get(key, ""))))[1] for key in KEYS)


class QuizApp:
    name = "QUIZ"

    def __init__(self, generator_factory=_default_generator) -> None:
        self._factory = generator_factory
        self._generator = None

    @staticmethod
    def _wait_for(ctx, button: int) -> None:
        while ctx.wait_button() != button:
            pass

    def _generate(self) -> dict:
        if self._generator is None:
            self._generator = self._factory()
        quiz = {}
        for _ in range(MAX_GENERATIONS):
            quiz = self._generator.generate_quiz()
            if quiz.get("frage", DEFAULTS["frage"]) == DEFAULTS["frage"]:
                raise RuntimeError("keine Frage erhalten")
            if _fits(quiz):
                break
        return quiz

    def _new_quiz(self, ctx) -> dict:
        while True:
            ctx.display.show_lines(["FRAGE WIRD ERZEUGT"])
            try:
                return ctx.run_blocking(self._generate)
            except StopApp:
                raise
            except Exception:
                log.exception("Quiz-Erzeugung fehlgeschlagen")
            ctx.display.show_lines(["KI NICHT ERREICHBAR", "BT5 NOCH EINMAL"])
            self._wait_for(ctx, BT5)

    def run(self, ctx) -> None:
        while True:
            quiz = self._new_quiz(ctx)
            for key in KEYS:
                ctx.show_pages(str(quiz.get(key) or DEFAULTS[key]))
                self._wait_for(ctx, BT5)
