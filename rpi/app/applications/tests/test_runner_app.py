import hashlib
import logging
import os
import tempfile
import unittest
from pathlib import Path

from app.applications.runner_app import RunnerApp
from app.driver.display.segments import center, new_buffer, put_line
from app.ui.app_host import StopApp
from app.ui.buttons import BT5, BT6

# Referenz: die Funktionen der Werkstatt (wand-werkstatt.html, Zeilen 722-748) unter Node,
# mit festem Zufall SEQ. Die Bilder eines Verlaufs sind als SHA-1 zusammengefasst.
SEQ = [0.62, 0.15, 0.88, 0.33, 0.05, 0.71, 0.47, 0.93, 0.26, 0.54, 0.12, 0.99, 0.38, 0.81, 0.2]
BEREIT = [931, 42626, 49858, 17288, 4144, 10145, 0, 42658, 42658, 42658, 0, 0,
          0, 0, 17315, 10145, 17288, 42658, 17315, 46130, 0, 42658, 42658, 42658,
          46131, 4144, 42401, 0, 42401, 931, 17315, 13360, 49858, 42657, 10145, 49858,
          0, 46131, 4144, 42913, 0, 46130, 42626, 9888, 17288, 10145, 49858, 0,
          0, 0, 0, 6193, 0, 0, 0, 0, 0, 0, 0, 0,
          0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0,
          1024, 9216, 9216, 27664, 9216, 9216, 9216, 9216, 9216, 1024, 9216, 9216,
          9216, 9216, 9216, 9216, 9216, 9216, 1024, 9216, 9216, 9216, 9216, 9216]
REF_NOKEYS = (26, "f03d67ae5f9b616d3a2265f385552358e9bff749", ("aus", 0, 170, 0))
REF_KEYS = (26, "301f68a92361ed4ec2f53443699c06d149526822", ("aus", 0, 170, 0))
REF_BOT = (300, "53553c609378bfb5d9dce5746b4679c3978597a7", ("lauf", 43, 85, 0))
REF_BOT_POINTS = {4: 154, 10: 130, 17: 102, 26: 85, 34: 85, 43: 85}  # Punkte -> interval
REF_BOTDIE = (103, "3db08c086680c9a1b1f0685750a384482e8b7bd5", ("aus", 10, 130, 10))


class FakeClock:
    def __init__(self):
        self.t = 0.0

    def __call__(self):
        return self.t


class SeqRng:
    """Liefert die Zahlen der Reihe nach, im Kreis (wie Math.random in der Referenz)."""

    def __init__(self, values):
        self.values, self.i = list(values), 0

    def random(self):
        value = self.values[self.i % len(self.values)]
        self.i += 1
        return value


class FakeCtx:
    """Anzeige und Tasten mit Fake-Uhr: Tasten kommen zur geplanten Zeit, bei stop_at endet es."""

    def __init__(self, clock, keys=(), stop_at=1.0, config_dir=None):
        self.clock, self.keys, self.stop_at = clock, sorted(keys), stop_at
        self.config_dir = config_dir
        self.shown = []
        self.timeouts = []
        self.display = self

    def show_cells(self, cells):
        self.shown.append(list(cells))

    def wait_button(self, timeout=None):
        self.timeouts.append(timeout)
        now = self.clock.t
        end = now + (timeout if timeout is not None else 1e9)
        if self.keys and self.keys[0][0] <= end:
            when, button = self.keys.pop(0)
            self.clock.t = max(now, when)
            return button
        if end > self.stop_at:
            self.clock.t = self.stop_at
            raise StopApp("back")
        self.clock.t = end
        return None


def digest(frames):
    parts = [hashlib.sha1(",".join(map(str, f)).encode()).hexdigest() for f in frames]
    return hashlib.sha1("".join(parts).encode()).hexdigest()


def line_frame(*items):
    buf = new_buffer()
    for row, text, col in items:
        put_line(buf, row, text, col)
    return buf


class TmpCase(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.dir = Path(self._tmp.name)

    def app(self, rng=None, config_dir=None):
        return RunnerApp(clock=FakeClock(), rng=rng or SeqRng(SEQ),
                         config_dir=config_dir if config_dir is not None else self.dir)

    def run_app(self, keys=(), stop_at=1.0, rng=None, config_dir=None):
        clock = FakeClock()
        app = RunnerApp(clock=clock, rng=rng or SeqRng([0.0]),
                        config_dir=config_dir if config_dir is not None else self.dir)
        ctx = FakeCtx(clock, keys, stop_at)
        with self.assertRaises(StopApp):
            app.run(ctx)
        return app, ctx


class FrameTest(TmpCase):
    def test_ready_frame_matches_the_reference(self):
        app, ctx = self.run_app(stop_at=0.3)
        self.assertEqual(ctx.shown, [BEREIT])
        self.assertEqual(app.name, "SPIEL")

    def test_ready_frame_text_and_ground(self):
        self.assertEqual(BEREIT[:48], line_frame((0, "PUNKTE 000", 0), (0, "REKORD 000", 14),
                                                 (1, "BT5 SPRINGEN BT6 DUCKEN", 0))[:48])

    def test_record_is_shown_in_the_first_line(self):
        (self.dir / "spiel_rekord.txt").write_text("7\n")
        app, ctx = self.run_app(stop_at=0.3)
        expected = list(BEREIT)
        expected[14:24] = line_frame((0, "REKORD 007", 14))[14:24]
        self.assertEqual(ctx.shown, [expected])

    def test_game_over_shows_the_message(self):
        app = self.app()
        app._reset()
        app._g["state"] = "aus"
        self.assertEqual(app._frame()[24:48], line_frame((1, center("VORBEI - BT5 NOCHMAL"), 0))[24:48])


class ReferenceTest(TmpCase):
    def play(self, keys=None, max_steps=400, bot_until=None, config_dir=None):
        app = self.app(config_dir=config_dir)
        app._reset()
        frames, points = [], {}
        for i in range(max_steps):
            if app._g["state"] != "lauf":
                break
            if keys and keys.get(i):
                app._key(BT5 if keys[i] == "J" else BT6)
            if bot_until is not None and i < bot_until:
                for o in list(app._g["obs"]):
                    if o["x"] == 5:
                        if o["kind"] == "kaktus":
                            app._key(BT5)
                        else:
                            app._key(BT6)
            app._step()
            frames.append(app._frame())
            points[app._g["score"]] = app._g["interval"]
        g = app._g
        return app, (len(frames), digest(frames), (g["state"], g["score"], g["interval"], app._best)), points

    def test_run_without_keys_dies_at_the_first_cactus(self):
        self.assertEqual(self.play()[1], REF_NOKEYS)

    def test_run_with_jumps_and_ducks(self):
        keys = {4: "J", 14: "J", 24: "D", 40: "J", 41: "D", 60: "J", 75: "D", 90: "J",
                105: "D", 120: "J"}
        self.assertEqual(self.play(keys)[1], REF_KEYS)

    def test_long_run_with_a_bot_speeds_up(self):
        app, result, points = self.play(max_steps=300, bot_until=10 ** 9)
        self.assertEqual(result, REF_BOT)
        for score, interval in REF_BOT_POINTS.items():
            self.assertEqual(points[score], interval)

    def test_bot_stops_and_crashes_with_a_record(self):
        app, result, _ = self.play(max_steps=2000, bot_until=100)
        self.assertEqual(result, REF_BOTDIE)
        self.assertEqual((self.dir / "spiel_rekord.txt").read_text().strip(), "10")


class ObstacleTest(TmpCase):
    def start(self, obs):
        app = self.app()
        app._reset()
        app._g["obs"] = obs
        app._g["next"] = 99
        return app

    def steps(self, app, n):
        for _ in range(n):
            if app._g["state"] == "lauf":
                app._step()

    def test_jump_over_a_cactus_scores_one_point(self):
        app = self.start([{"x": 5, "kind": "kaktus", "v": 0}])
        app._key(BT5)
        self.assertEqual(app._g["jump"], 5)
        self.steps(app, 3)
        self.assertEqual(app._g["state"], "lauf")
        self.assertEqual(app._g["score"], 1)

    def test_without_the_jump_the_cactus_hits(self):
        app = self.start([{"x": 5, "kind": "kaktus", "v": 0}])
        self.steps(app, 3)
        self.assertEqual(app._g["state"], "aus")

    def test_duck_under_a_bird(self):
        app = self.start([{"x": 5, "kind": "vogel", "v": 0}])
        app._key(BT6)
        self.assertEqual(app._g["duck"], 3)
        self.steps(app, 3)
        self.assertEqual(app._g["state"], "lauf")
        self.assertEqual(app._g["score"], 1)

    def test_a_bird_hits_when_running_or_jumping_into_it(self):
        app = self.start([{"x": 5, "kind": "vogel", "v": 0}])
        self.steps(app, 3)
        self.assertEqual(app._g["state"], "aus")
        app = self.start([{"x": 5, "kind": "vogel", "v": 0}])
        app._key(BT5)
        self.steps(app, 3)
        self.assertEqual(app._g["state"], "aus")

    def test_key_rules_during_the_run(self):
        app = self.start([])
        app._key(BT5)
        app._g["jump"] = 2
        app._key(BT5)
        self.assertEqual(app._g["jump"], 2)  # kein zweiter Sprung in der Luft
        app._key(BT6)
        self.assertEqual(app._g["duck"], 0)  # Ducken im Sprung geht nicht
        app._g["jump"] = 0
        app._key(BT6)
        self.assertEqual(app._g["duck"], 3)
        app._key(BT5)
        self.assertEqual(app._g["jump"], 0)  # Springen im Ducken geht nicht

    def test_duck_does_nothing_before_the_start(self):
        app = self.app()
        app._init_ready()
        app._key(BT6)
        self.assertEqual((app._g["duck"], app._g["state"]), (0, "bereit"))

    def test_speed_up_formula(self):
        app = self.start([])
        for score, interval in ((0, 170), (5, 150), (10, 130), (21, 86), (22, 85), (60, 85)):
            app._g["score"] = score
            app._step()
            self.assertEqual(app._g["interval"], interval)


class RunTest(TmpCase):
    def test_steps_follow_the_interval(self):
        app, ctx = self.run_app(keys=[(0.0, BT5)], stop_at=0.5)
        self.assertEqual(app._g["ground"], 2)  # Schritte bei 0.17 und 0.34
        self.assertEqual(len(ctx.shown), 1 + 1 + 2)
        self.assertTrue(all(t <= 0.05 + 1e-9 for t in ctx.timeouts))

    def test_catches_up_after_a_long_pause(self):
        clock = FakeClock()
        app = RunnerApp(clock=clock, rng=SeqRng([0.0]), config_dir=self.dir)

        class Slow(FakeCtx):
            def wait_button(self, timeout=None):
                self.timeouts.append(timeout)
                if not self.keys:
                    raise StopApp("back")
                self.keys.pop(0)
                if self.stage == 0:
                    self.stage = 1
                    return BT5
                self.clock.t += 0.6  # lange Pause ohne Taste
                return None

        ctx = Slow(clock, keys=[(0, 0), (0, 0)], stop_at=9)
        ctx.stage = 0
        with self.assertRaises(StopApp):
            app.run(ctx)
        self.assertEqual(app._g["ground"], 3)  # 600 ms = drei Schritte zu 170 ms

    def test_a_key_press_that_changes_nothing_shows_nothing(self):
        app, ctx = self.run_app(keys=[(0.1, BT6), (0.2, BT6)], stop_at=0.4)
        self.assertEqual(len(ctx.shown), 1)

    def test_jump_over_a_cactus_in_a_running_game(self):
        app, ctx = self.run_app(keys=[(0.0, BT5), (4.1, BT5)], stop_at=4.8)
        self.assertEqual(app._g["state"], "lauf")
        self.assertEqual(app._g["score"], 1)
        self.assertEqual(ctx.shown[-1][:10], line_frame((0, "PUNKTE 001", 0))[:10])

    def test_no_jump_ends_the_game_at_the_cactus(self):
        app, ctx = self.run_app(keys=[(0.0, BT5)], stop_at=5.0)
        self.assertEqual(app._g["state"], "aus")
        self.assertEqual(ctx.shown[-1][24:48], line_frame((1, center("VORBEI - BT5 NOCHMAL"), 0))[24:48])

    def test_bt5_after_game_over_starts_a_new_game(self):
        app, ctx = self.run_app(keys=[(0.0, BT5), (5.0, BT5)], stop_at=5.1)
        g = app._g
        self.assertEqual((g["state"], g["score"], g["obs"], g["ground"]), ("lauf", 0, [], 0))
        self.assertEqual(ctx.shown[-1][24:48], [0] * 24)
        self.assertEqual(g["interval"], 170)


class RecordTest(TmpCase):
    def load(self, text):
        (self.dir / "spiel_rekord.txt").write_text(text)
        return self.run_app(stop_at=0.1)[0]._best

    def test_missing_file_is_zero(self):
        self.assertEqual(self.run_app(stop_at=0.1)[0]._best, 0)

    def test_reads_a_number(self):
        self.assertEqual(self.load("42\n"), 42)

    def test_broken_file_is_zero(self):
        for text in ("abc", "", "4.5", "-3", "12 13", "\x00\x01"):
            self.assertEqual(self.load(text), 0, text)

    def test_binary_garbage_is_zero(self):
        (self.dir / "spiel_rekord.txt").write_bytes(b"\xff\xfe\x00\x80")
        self.assertEqual(self.run_app(stop_at=0.1)[0]._best, 0)

    def test_new_record_is_written_and_read_back(self):
        nested = self.dir / "a" / "b"
        app = self.app(config_dir=nested)
        app._reset()
        app._g["score"] = 9
        app._g["obs"] = [{"x": 4, "kind": "kaktus", "v": 0}]
        app._g["next"] = 99
        app._step()
        self.assertEqual(app._g["state"], "aus")
        self.assertEqual((nested / "spiel_rekord.txt").read_text().strip(), "9")
        self.assertEqual([p.name for p in nested.iterdir()], ["spiel_rekord.txt"])
        self.assertEqual(self.app(config_dir=nested)._load_best(), 9)

    def test_lower_score_keeps_the_record(self):
        (self.dir / "spiel_rekord.txt").write_text("20\n")
        app = self.app()
        app._best = app._load_best()
        app._reset()
        app._g["score"] = 5
        app._g["obs"] = [{"x": 4, "kind": "kaktus", "v": 0}]
        app._g["next"] = 99
        app._step()
        self.assertEqual(app._best, 20)
        self.assertEqual((self.dir / "spiel_rekord.txt").read_text().strip(), "20")

    def test_write_error_does_not_end_the_game(self):
        blocker = self.dir / "datei"
        blocker.write_text("x")  # ein Ordner kann hier nicht angelegt werden
        app = self.app(config_dir=blocker / "config")
        app._reset()
        app._g["score"] = 4
        app._g["obs"] = [{"x": 4, "kind": "kaktus", "v": 0}]
        app._g["next"] = 99
        with self.assertLogs("app.applications.runner_app", level=logging.WARNING):
            app._step()
        self.assertEqual(app._g["state"], "aus")
        self.assertEqual(app._best, 4)


if __name__ == "__main__":
    unittest.main()
