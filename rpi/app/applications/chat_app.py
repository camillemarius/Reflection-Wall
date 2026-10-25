# applications/chat_app.py
# Chat auf der Wand: BT5 nimmt auf, BT5 beendet, die Wand zeigt die Antwort, der Lautsprecher sagt sie.
# Die Antwort wird erst ganz angezeigt (Seiten mit BT5) und danach einmal gesprochen.
import logging

from app.ui.app_host import StopApp
from app.ui.buttons import BT5
from app.ui.short_answer import SHORT_RULE, ask_short

log = logging.getLogger(__name__)


def _default_recorder():
    from app.driver.speechRecognition.fasterWhisper import fasterWhsiper
    return fasterWhsiper()


def _default_speaker():
    from app.driver.speech.speaker import SpeechAssistant
    return SpeechAssistant()


class ChatApp:
    name = "CHAT"

    def __init__(self, recorder_factory=_default_recorder, ask=None, speaker=None) -> None:
        self._recorder_factory = recorder_factory
        self._ask = ask
        self._speaker = speaker

    def _ask_ai(self, text: str) -> str:
        ask = self._ask
        if ask is None:
            from app.driver.chatbot.groqAPI import write_to_ai
            ask = write_to_ai
        messages = [{"role": "system", "content": SHORT_RULE},
                    {"role": "user", "content": text}]
        answer = ask_short(lambda: ask(messages))
        if answer.startswith("Fehler"):
            raise RuntimeError(answer)
        return answer

    def _speak(self, text: str) -> None:
        if self._speaker is None:
            self._speaker = _default_speaker()
        self._speaker.speak(text)

    @staticmethod
    def _wait_for(ctx, button: int) -> None:
        while ctx.wait_button() != button:
            pass

    def run(self, ctx) -> None:
        recorder = self._recorder_factory()
        if not recorder.mic_available:
            ctx.display.show_lines(["KEIN MIKROFON", "BT4 ZURUECK"])
            while True:
                ctx.wait_button()

        while True:
            ctx.display.show_lines(["BT5 UND SPRECHEN"])
            self._wait_for(ctx, BT5)
            text = self._record(ctx, recorder)
            if not text.strip():
                ctx.display.show_lines(["NICHTS VERSTANDEN", "BT5 UND SPRECHEN"])
                self._wait_for(ctx, BT5)
                continue
            answer = self._answer(ctx, text)
            ctx.show_pages(answer)
            try:
                ctx.run_blocking(self._speak, answer)
            except StopApp:
                raise
            except Exception:
                log.exception("Sprechen fehlgeschlagen")

    def _record(self, ctx, recorder) -> str:
        recorder.start_recording()
        recording = True
        try:
            ctx.display.show_lines(["AUFNAHME", "BT5 ENDE"])
            self._wait_for(ctx, BT5)
            ctx.display.show_lines(["DENKE NACH"])
            recording = False
            return ctx.run_blocking(recorder.stop_recording) or ""
        finally:
            if recording:
                try:
                    recorder.stop_recording()
                except Exception:
                    log.exception("Aufnahme liess sich nicht beenden")

    def _answer(self, ctx, text: str) -> str:
        while True:
            ctx.display.show_lines(["DENKE NACH"])
            try:
                return ctx.run_blocking(self._ask_ai, text)
            except StopApp:
                raise
            except Exception:
                log.exception("KI-Anfrage fehlgeschlagen")
            ctx.display.show_lines(["KI NICHT ERREICHBAR", "BT5 NOCH EINMAL"])
            self._wait_for(ctx, BT5)
