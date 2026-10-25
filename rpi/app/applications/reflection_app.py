# applications/reflection_app.py
# Reflection von Hand: der erste Gedanke kommt nur vom Thema, jeder weitere baut auf dem vorherigen auf.
# Die Kette liegt nur in einer lokalen Variable von run: beim Verlassen ist alles vergessen.
# Nichts wird gespeichert (weder FRAM noch Tageskette noch Datenbank).
import logging

from app.topics import CONFIG_DIR, read_hand
from app.ui.app_host import StopApp
from app.ui.buttons import BT5
from app.ui.short_answer import SHORT_RULE, ask_short

log = logging.getLogger(__name__)


def build_reflection_messages(topic: str, previous):
    system = (SHORT_RULE + " Du hilfst beim Nachdenken: Gib genau einen kurzen Gedanken zum Thema, "
              "keine Frage und keine Aufzaehlung.")
    user = "Thema: " + topic
    if previous:
        user += "\nVorheriger Gedanke: " + previous + "\nGib den naechsten Gedanken, der darauf aufbaut."
    else:
        user += "\nGib den ersten Gedanken zu diesem Thema."
    return [{"role": "system", "content": system}, {"role": "user", "content": user}]


class ReflectionApp:
    name = "REFLECTION"

    def __init__(self, ask=None, config_dir=CONFIG_DIR) -> None:
        self._ask = ask
        self._config_dir = config_dir

    def _ask_ai(self, topic: str, previous) -> str:
        ask = self._ask
        if ask is None:
            from app.driver.chatbot.groqAPI import write_to_ai
            ask = write_to_ai
        messages = build_reflection_messages(topic, previous)
        answer = ask_short(lambda: ask(messages))
        if not answer.strip() or answer.startswith("Fehler"):
            raise RuntimeError(answer.strip() or "leere Antwort")
        return answer

    @staticmethod
    def _wait_for(ctx, button: int) -> None:
        while ctx.wait_button() != button:
            pass

    def run(self, ctx) -> None:
        topic = read_hand(self._config_dir)
        previous = None
        ctx.display.show_lines(["REFLECTION", "BT5 NEUER GEDANKE"])
        while True:
            self._wait_for(ctx, BT5)
            previous = self._think(ctx, topic, previous)
            ctx.show_pages(previous)

    def _think(self, ctx, topic: str, previous):
        while True:
            ctx.display.show_lines(["DENKE NACH"])
            try:
                return ctx.run_blocking(self._ask_ai, topic, previous)
            except StopApp:
                raise
            except Exception:
                log.exception("KI-Anfrage fehlgeschlagen")
            ctx.display.show_lines(["KI NICHT ERREICHBAR", "BT5 NOCH EINMAL"])
            self._wait_for(ctx, BT5)
