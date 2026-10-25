import threading
import time
import unittest

from app.applications.chat_app import ChatApp
from app.ui.activity import Activity
from app.ui.app_host import AppContext, StopApp, StopSignal
from app.ui.buttons import QueueButtons
from app.ui.short_answer import SHORT_RULE


class FakeDisplay:
    def __init__(self):
        self.calls = []

    def show_lines(self, lines, dots_own_cell=False):
        self.calls.append(list(lines))

    def texts(self):
        return [" ".join(" ".join(c).split()) for c in self.calls]


class FakeRecorder:
    def __init__(self, transcript="WIE SPAET IST ES", mic=True):
        self.mic_available = mic
        self.transcript = transcript
        self.events = []

    def start_recording(self):
        self.events.append("start")

    def stop_recording(self):
        self.events.append("stop")
        return self.transcript


class FakeSpeaker:
    def __init__(self):
        self.spoken = []

    def speak(self, text):
        self.spoken.append(text)


class ScriptedButtons:
    """Gibt eine Taste erst frei, wenn die Anzeige den erwarteten Text zeigt."""

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


READY, REC, THINK = "BT5 UND SPRECHEN", "BT5 ENDE", "DENKE NACH"


def make(script, recorder=None, ask=None, speaker=None):
    display = FakeDisplay()
    buttons = ScriptedButtons(display, script)
    ctx = AppContext(display, buttons, Activity(), StopSignal())
    recorder = recorder or FakeRecorder()
    speaker = speaker or FakeSpeaker()
    made = []

    def factory():
        made.append(1)
        return recorder

    app = ChatApp(factory, ask=ask or (lambda m: "ES IST ZEIT"), speaker=speaker)
    return app, ctx, display, recorder, speaker, made


def run(app, ctx):
    try:
        app.run(ctx)
    except StopApp as stop:
        return stop.reason


class ChatAppTest(unittest.TestCase):
    def test_name(self):
        self.assertEqual(ChatApp(lambda: None).name, "CHAT")

    def test_chat_flow(self):
        seen = []

        def ask(messages):
            seen.append(messages)
            return "ES IST ZEIT"

        app, ctx, display, rec, speaker, _ = make([(READY, 5), (REC, 5), (READY, 4)], ask=ask)
        self.assertEqual(run(app, ctx), "back")
        self.assertEqual(rec.events, ["start", "stop"])
        texts = display.texts()
        self.assertTrue(any("BT5 UND SPRECHEN" in t for t in texts))
        self.assertTrue(any("DENKE NACH" in t for t in texts))
        self.assertTrue(any("ES IST ZEIT" in t for t in texts))
        self.assertEqual(speaker.spoken, ["ES IST ZEIT"])
        self.assertEqual(seen[0][0], {"role": "system", "content": SHORT_RULE})
        self.assertEqual(seen[0][-1], {"role": "user", "content": "WIE SPAET IST ES"})

    def test_chat_without_mic(self):
        app, ctx, display, rec, *_ = make([('KEIN MIKROFON', 4)], recorder=FakeRecorder(mic=False))
        self.assertEqual(run(app, ctx), "back")
        self.assertTrue(any("KEIN MIKROFON" in t for t in display.texts()))
        self.assertEqual(rec.events, [])

    def test_recorder_created_only_on_run(self):
        app, ctx, _, _, _, made = make([(READY, 4)])
        self.assertEqual(made, [])
        run(app, ctx)
        self.assertEqual(made, [1])

    def test_empty_transcript(self):
        app, ctx, display, rec, speaker, _ = make([(READY, 5), (REC, 5), ('NICHTS VERSTANDEN', 4)], recorder=FakeRecorder(transcript="  "))
        run(app, ctx)
        self.assertTrue(any("NICHTS VERSTANDEN" in t for t in display.texts()))
        self.assertEqual(speaker.spoken, [])

    def test_ai_error_string_then_retry(self):
        answers = ["Fehler: Netz", "GUT"]
        app, ctx, display, rec, speaker, _ = make([(READY, 5), (REC, 5), ('NOCH EINMAL', 5), (READY, 4)], ask=lambda m: answers.pop(0))
        with self.assertLogs("app.applications.chat_app", level="ERROR"):
            run(app, ctx)
        texts = display.texts()
        self.assertTrue(any("KI NICHT ERREICHBAR" in t for t in texts))
        self.assertEqual(speaker.spoken, ["GUT"])
        self.assertEqual(rec.events, ["start", "stop"])

    def test_ai_exception(self):
        def ask(messages):
            raise ValueError("GROQ_API_KEY fehlt")

        app, ctx, display, _, speaker, _ = make([(READY, 5), (REC, 5), ('NICHT ERREICHBAR', 4)], ask=ask)
        with self.assertLogs("app.applications.chat_app", level="ERROR"):
            self.assertEqual(run(app, ctx), "back")
        self.assertTrue(any("KI NICHT ERREICHBAR" in t for t in display.texts()))
        self.assertEqual(speaker.spoken, [])

    def test_empty_ai_answer_is_a_failure(self):
        answers = ["   ", "GUT"]
        app, ctx, display, rec, speaker, _ = make([(READY, 5), (REC, 5), ('NOCH EINMAL', 5), (READY, 4)], ask=lambda m: answers.pop(0))
        with self.assertLogs("app.applications.chat_app", level="ERROR"):
            run(app, ctx)
        self.assertTrue(any("KI NICHT ERREICHBAR" in t for t in display.texts()))
        self.assertEqual(speaker.spoken, ["GUT"])

    def test_bt4_while_recording_stops_recorder(self):
        app, ctx, _, rec, *_ = make([(READY, 5), (REC, 4)])
        self.assertEqual(run(app, ctx), "back")
        deadline = time.monotonic() + 2
        while rec.events != ["start", "stop"] and time.monotonic() < deadline:
            time.sleep(0.01)
        self.assertEqual(rec.events, ["start", "stop"])

    def test_bt4_while_recording_returns_without_waiting_for_transcription(self):
        release = threading.Event()
        rec = FakeRecorder()
        rec.stop_recording = lambda: (release.wait(5), "")[1]
        app, ctx, *_ = make([(READY, 5), (REC, 4)], recorder=rec)
        started = time.monotonic()
        self.assertEqual(run(app, ctx), "back")
        self.assertLess(time.monotonic() - started, 1)
        release.set()

    def test_long_answer_is_shortened_by_asking_again(self):
        answers = ["X" * 200, "KURZ"]
        app, ctx, _, _, speaker, _ = make([(READY, 5), (REC, 5), (READY, 4)], ask=lambda m: answers.pop(0))
        run(app, ctx)
        self.assertEqual(speaker.spoken, ["KURZ"])


if __name__ == "__main__":
    unittest.main()
