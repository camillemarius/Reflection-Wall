import threading
import time
import unittest

from app.applications import chat_app
from app.applications.chat_app import ChatApp
from app.ui.activity import Activity
from app.ui.app_host import AppContext, StopApp, StopSignal
from app.ui.buttons import BT4, QueueButtons
from app.ui.short_answer import SHORT_RULE

STUCK_S = 5.0


class ScriptStuck(BaseException):
    """Das Skript kommt nicht weiter: der Test bricht ab, statt zu haengen."""


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
    def __init__(self, error=None):
        self.spoken = []
        self.error = error

    def speak(self, text):
        self.spoken.append(text)
        if self.error is not None:
            raise self.error


class ScriptedButtons:
    """Gibt eine Taste erst frei, wenn die Anzeige den erwarteten Text zeigt.

    Andere Tasten als BT4 kommen nur, wenn die Anwendung auf eine Taste wartet (get mit
    Wartezeit); get(0) leert nur die Warteschlange, eine Taste ginge dort verloren. BT4 darf
    jederzeit kommen. Eine Taste kann eine Funktion sein, die beim Freigeben die Taste liefert.
    """

    def __init__(self, display, script):
        self.display, self.script = display, list(script)
        self._progress = time.monotonic()

    def get(self, timeout):
        if time.monotonic() - self._progress > STUCK_S:
            raise ScriptStuck("Skript %r, Anzeige %r" % (self.script[:1], self.display.texts()[-1:]))
        if self.script:
            screen, button = self.script[0]
            texts = self.display.texts()
            waiting = timeout is None or timeout > 0
            if texts and screen in texts[-1] and (waiting or button == BT4):
                self.script.pop(0)
                self._progress = time.monotonic()
                return button() if callable(button) else button
        time.sleep(min(timeout or 0, 0.005))
        return None

    def drain(self):
        pass


PREP, READY, REC, THINK = "MIKROFON WIRD VORBEREITET", "BT5 UND SPRECHEN", "BT5 ENDE", "DENKE NACH"
ANSWER = "ES IST ZEIT"


def context(display, script, activity=None, stop=None):
    return AppContext(display, ScriptedButtons(display, script), activity or Activity(),
                      stop or StopSignal())


def make(script, recorder=None, ask=None, speaker=None, factory=None, activity=None, stop=None,
         **options):
    display = FakeDisplay()
    ctx = context(display, script, activity, stop)
    recorder = recorder or FakeRecorder()
    speaker = speaker or FakeSpeaker()
    made = []

    def default_factory():
        made.append(1)
        return recorder

    app = ChatApp(factory or default_factory, ask=ask or (lambda m: ANSWER), speaker=speaker,
                  **options)
    return app, ctx, display, recorder, speaker, made


def run(app, ctx):
    try:
        app.run(ctx)
    except StopApp as stop:
        return stop.reason


def screens(display):
    """Bildschirme in ihrer Reihenfolge, gleiche aufeinanderfolgende zusammengefasst."""
    out = []
    for text in display.texts():
        if not out or out[-1] != text:
            out.append(text)
    return out


def wait_for(cond, timeout=3.0):
    end = time.monotonic() + timeout
    while time.monotonic() < end:
        if cond():
            return True
        time.sleep(0.005)
    return False


def in_thread(app, ctx):
    result = []
    worker = threading.Thread(target=lambda: result.append(run(app, ctx)), daemon=True)
    worker.start()
    return worker, result


class ChatAppTest(unittest.TestCase):
    def test_name(self):
        self.assertEqual(ChatApp(lambda: None).name, "CHAT")

    def test_chat_flow(self):
        seen = []

        def ask(messages):
            seen.append(messages)
            return ANSWER

        app, ctx, display, rec, speaker, _ = make([(READY, 5), (REC, 5), (ANSWER, 5), (READY, 4)],
                                                  ask=ask)
        self.assertEqual(run(app, ctx), "back")
        self.assertEqual(rec.events, ["start", "stop"])
        self.assertEqual(screens(display),
                         [PREP, READY, "AUFNAHME BT5 ENDE", THINK, ANSWER, READY])
        self.assertEqual(speaker.spoken, [ANSWER])
        self.assertEqual(seen[0][0], {"role": "system", "content": SHORT_RULE})
        self.assertEqual(seen[0][-1], {"role": "user", "content": "WIE SPAET IST ES"})

    def test_answer_stays_until_bt5_when_speaking_fails(self):
        speaker = FakeSpeaker(error=FileNotFoundError("piper"))
        app, ctx, display, *_ = make([(READY, 5), (REC, 5), (ANSWER, 5), (READY, 4)],
                                     speaker=speaker)
        with self.assertLogs("app.applications.chat_app", level="ERROR"):
            self.assertEqual(run(app, ctx), "back")
        self.assertEqual(screens(display)[-2:], [ANSWER, READY])
        self.assertEqual(speaker.spoken, [ANSWER])

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

    def test_recorder_created_once_over_rounds_and_entries(self):
        app, ctx, display, rec, _, made = make(
            [(READY, 5), (REC, 5), (ANSWER, 5), (READY, 5), (REC, 5), (ANSWER, 5), (READY, 4)])
        self.assertEqual(run(app, ctx), "back")
        again = context(display, [(READY, 5), (REC, 5), (ANSWER, 5), (READY, 4)])
        self.assertEqual(run(app, again), "back")
        self.assertEqual(made, [1])
        self.assertEqual(rec.events, ["start", "stop"] * 3)
        self.assertEqual(display.texts().count(PREP), 1)

    def test_bt4_while_recorder_loads_returns_at_once_and_keeps_the_load(self):
        release, loaded = threading.Event(), threading.Event()
        self.addCleanup(release.set)
        made = []

        def slow_factory():
            made.append(1)
            release.wait(5)
            loaded.set()
            return FakeRecorder()

        app, _, display, *_ = make([], factory=slow_factory)
        buttons = QueueButtons()
        worker, result = in_thread(app, AppContext(display, buttons, Activity(), StopSignal()))
        self.assertTrue(wait_for(lambda: made))  # das Laden laeuft
        buttons.put(BT4)
        worker.join(1)
        self.assertFalse(worker.is_alive())
        self.assertEqual(result, ["back"])
        self.assertEqual(display.texts(), [PREP])
        release.set()
        self.assertTrue(loaded.wait(2))
        self.assertEqual(run(app, context(display, [(READY, 4)])), "back")
        self.assertEqual(made, [1])

    def test_stop_while_recorder_loads_writes_nothing_more(self):
        release, loaded = threading.Event(), threading.Event()
        self.addCleanup(release.set)
        made = []

        def slow_factory():
            made.append(1)
            release.wait(5)
            loaded.set()
            return FakeRecorder()

        stop = StopSignal()
        app, ctx, display, *_ = make([], factory=slow_factory, stop=stop)
        worker, result = in_thread(app, ctx)
        self.assertTrue(wait_for(lambda: made))
        stop.set("shutdown")
        worker.join(1)
        self.assertFalse(worker.is_alive())
        self.assertEqual(result, ["shutdown"])
        release.set()
        self.assertTrue(loaded.wait(2))
        time.sleep(0.05)
        self.assertEqual(display.texts(), [PREP])

    def test_empty_transcript(self):
        app, ctx, display, rec, speaker, _ = make([(READY, 5), (REC, 5), ('NICHTS VERSTANDEN', 4)], recorder=FakeRecorder(transcript="  "))
        run(app, ctx)
        self.assertTrue(any("NICHTS VERSTANDEN" in t for t in display.texts()))
        self.assertEqual(speaker.spoken, [])

    def test_ai_error_string_then_retry(self):
        answers = ["Fehler: Netz", "GUT"]
        app, ctx, display, rec, speaker, _ = make([(READY, 5), (REC, 5), ('NOCH EINMAL', 5), ("GUT", 5), (READY, 4)], ask=lambda m: answers.pop(0))
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
        app, ctx, display, rec, speaker, _ = make([(READY, 5), (REC, 5), ('NOCH EINMAL', 5), ("GUT", 5), (READY, 4)], ask=lambda m: answers.pop(0))
        with self.assertLogs("app.applications.chat_app", level="ERROR"):
            run(app, ctx)
        self.assertTrue(any("KI NICHT ERREICHBAR" in t for t in display.texts()))
        self.assertEqual(speaker.spoken, ["GUT"])

    def test_bt4_while_recording_stops_recorder(self):
        app, ctx, _, rec, *_ = make([(READY, 5), (REC, 4)])
        self.assertEqual(run(app, ctx), "back")
        self.assertTrue(wait_for(lambda: rec.events == ["start", "stop"], timeout=2))
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

    def _slow_stop_recorder(self):
        release = threading.Event()
        self.addCleanup(release.set)
        rec = FakeRecorder()

        def slow_stop():
            rec.events.append("stop-begin")
            release.wait(5)
            rec.events.append("stop-end")
            return "ALT"

        rec.stop_recording = slow_stop
        return rec, release

    def _assert_next_recording_waits(self, first_script):
        rec, release = self._slow_stop_recorder()
        app, ctx, display, *_ = make(first_script, recorder=rec)
        self.assertEqual(run(app, ctx), "back")
        self.assertTrue(wait_for(lambda: "stop-begin" in rec.events))
        worker, result = in_thread(app, context(display, [(READY, 5), (REC, 4)]))
        self.assertTrue(wait_for(lambda: display.texts()[-1] == PREP))
        time.sleep(0.1)
        self.assertEqual(rec.events, ["start", "stop-begin"])
        release.set()
        worker.join(2)
        self.assertEqual(result, ["back"])
        self.assertEqual(rec.events[:4], ["start", "stop-begin", "stop-end", "start"])

    def test_new_recording_waits_for_the_discarded_one(self):
        self._assert_next_recording_waits([(READY, 5), (REC, 4)])

    def test_new_recording_waits_for_a_transcription_left_with_bt4(self):
        self._assert_next_recording_waits([(READY, 5), (REC, 5), (THINK, 4)])

    def test_previous_recording_that_does_not_end_is_an_error(self):
        rec, _ = self._slow_stop_recorder()
        app, ctx, display, *_ = make([(READY, 5), (REC, 4)], recorder=rec, stop_wait_s=0.05)
        self.assertEqual(run(app, ctx), "back")
        with self.assertRaises(RuntimeError):
            app.run(context(display, [(READY, 5)]))
        self.assertEqual(rec.events.count("start"), 1)

    def test_recording_ends_by_itself_after_60_s(self):
        self.assertEqual(chat_app.MAX_RECORDING_S, 60.0)
        now = [0.0]

        def sixty_seconds_later():
            now[0] = 60.0
            return None  # keine Taste

        app, ctx, display, rec, speaker, _ = make(
            [(READY, 5), (REC, sixty_seconds_later), (ANSWER, 5), (READY, 4)],
            clock=lambda: now[0])
        self.assertEqual(run(app, ctx), "back")
        self.assertEqual(rec.events, ["start", "stop"])
        self.assertEqual(speaker.spoken, [ANSWER])
        self.assertEqual(screens(display),
                         [PREP, READY, "AUFNAHME BT5 ENDE", THINK, ANSWER, READY])

    def test_recording_counts_as_activity(self):
        now = [0.0]
        activity = Activity(clock=lambda: now[0], idle_minutes=1)
        seen = []

        def probe():
            now[0] = 1000.0  # weit ueber der Frist
            seen.append(activity.expired())
            return 5

        app, ctx, *_ = make([(READY, 5), (REC, probe), (ANSWER, 5), (READY, 4)],
                            activity=activity)
        self.assertEqual(run(app, ctx), "back")
        self.assertEqual(seen, [False])

    def test_long_answer_is_shortened_by_asking_again(self):
        answers = ["X" * 200, "KURZ"]
        app, ctx, _, _, speaker, _ = make([(READY, 5), (REC, 5), ("KURZ", 5), (READY, 4)], ask=lambda m: answers.pop(0))
        run(app, ctx)
        self.assertEqual(speaker.spoken, ["KURZ"])


if __name__ == "__main__":
    unittest.main()
