# applications/chat_app.py
# Chat auf der Wand: BT5 nimmt auf, BT5 beendet, die Wand zeigt die Antwort, der Lautsprecher sagt sie.
# Die Antwort wird erst ganz angezeigt (Seiten mit BT5) und danach einmal gesprochen. Sie bleibt
# stehen, bis BT5 wieder BT5 UND SPRECHEN zeigt.
import logging
import threading
import time
from typing import Callable

from app.ui.app_host import StopApp
from app.ui.buttons import BT5
from app.ui.short_answer import SHORT_RULE, ask_short

log = logging.getLogger(__name__)

PREPARING = ["MIKROFON WIRD", "VORBEREITET"]
MAX_RECORDING_S = 60.0  # danach endet eine Aufnahme von selbst, wie mit BT5
RECORDING_POLL_S = 0.5
STOP_WAIT_S = 120.0  # so lange wartet eine neue Aufnahme hoechstens auf das Ende der vorigen


def _default_recorder():
    from app.driver.speechRecognition.fasterWhisper import fasterWhsiper
    return fasterWhsiper()


def _default_speaker():
    from app.driver.speech.speaker import SpeechAssistant
    return SpeechAssistant()


class ChatApp:
    name = "CHAT"

    def __init__(self, recorder_factory=_default_recorder, ask=None, speaker=None,
                 clock: Callable[[], float] = time.monotonic,
                 stop_wait_s: float = STOP_WAIT_S) -> None:
        self._recorder_factory = recorder_factory
        self._ask = ask
        self._speaker = speaker
        self._clock = clock
        self._stop_wait_s = stop_wait_s
        # Der Recorder (Whisper-Modell) entsteht einmal und dient allen Runden und Eintritten.
        self._recorder = None
        self._load_lock = threading.Lock()
        # Thread, der zuletzt stop_recording aufgerufen hat, auch fuer eine verworfene Aufnahme
        self._stop_thread = None

    def _ask_ai(self, text: str) -> str:
        ask = self._ask
        if ask is None:
            from app.driver.chatbot.groqAPI import write_to_ai
            ask = write_to_ai
        messages = [{"role": "system", "content": SHORT_RULE},
                    {"role": "user", "content": text}]
        answer = ask_short(lambda: ask(messages))
        if not answer.strip() or answer.startswith("Fehler"):
            raise RuntimeError(answer.strip() or "leere Antwort")
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
        recorder = self._get_recorder(ctx)
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
            # Die Antwort bleibt stehen, auch wenn das Sprechen scheitert; BT5 fuehrt zurueck.
            self._wait_for(ctx, BT5)

    def _get_recorder(self, ctx):
        """Beim ersten Eintritt laedt das Modell im Hintergrund; BT4 und SHUTDOWN wirken dabei."""
        if self._recorder is None:
            ctx.display.show_lines(PREPARING)
            ctx.run_blocking(self._load_recorder)
        return self._recorder

    def _load_recorder(self):
        # Bricht BT4 das Warten ab, laedt dieser Thread trotzdem fertig; der naechste Eintritt
        # wartet am Lock und nimmt den fertigen Recorder.
        with self._load_lock:
            if self._recorder is None:
                self._recorder = self._recorder_factory()
            return self._recorder

    def _record(self, ctx, recorder) -> str:
        self._wait_for_previous_stop(ctx)
        recorder.start_recording()
        try:
            ctx.display.show_lines(["AUFNAHME", "BT5 ENDE"])
            with ctx.activity.busy():  # Aufnehmen zaehlt als Aktivitaet (F6)
                self._wait_recording_end(ctx)
            ctx.display.show_lines(["DENKE NACH"])
        except BaseException:
            # Nur das Mikrofon freigeben: im Hintergrund, das Ergebnis wird verworfen,
            # damit BT4 sofort ins Menue zurueckkehrt.
            self._begin_stop(recorder, discard=True)
            raise
        thread, outcome = self._begin_stop(recorder, discard=False)
        ctx.run_blocking(thread.join)
        if "error" in outcome:
            raise outcome["error"]
        return outcome.get("text") or ""

    def _wait_recording_end(self, ctx) -> None:
        """BT5 beendet die Aufnahme; nach MAX_RECORDING_S endet sie von selbst."""
        deadline = self._clock() + MAX_RECORDING_S
        while True:
            remaining = deadline - self._clock()
            if remaining <= 0:
                return
            if ctx.wait_button(timeout=min(remaining, RECORDING_POLL_S)) == BT5:
                return

    def _begin_stop(self, recorder, discard: bool):
        """stop_recording in einem eigenen Thread; die naechste Aufnahme wartet auf ihn."""
        outcome = {}

        def stop() -> None:
            try:
                outcome["text"] = recorder.stop_recording()
            except Exception as exc:
                outcome["error"] = exc
                if discard:
                    log.exception("Aufnahme liess sich nicht beenden")

        thread = threading.Thread(target=stop, name="chat-stop", daemon=True)
        self._stop_thread = thread
        thread.start()
        return thread, outcome

    def _wait_for_previous_stop(self, ctx) -> None:
        """Eine neue Aufnahme startet erst, wenn stop_recording der vorigen fertig ist."""
        thread = self._stop_thread
        if thread is None or not thread.is_alive():
            return
        ctx.display.show_lines(PREPARING)
        ctx.run_blocking(thread.join, self._stop_wait_s)
        if thread.is_alive():
            raise RuntimeError("die vorige Aufnahme endet nicht")

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
