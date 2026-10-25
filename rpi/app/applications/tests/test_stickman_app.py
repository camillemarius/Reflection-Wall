import tempfile
import unittest
from pathlib import Path

from app.applications.stickman_app import FRAMES_DIR, StickmanApp, load_frames
from app.ui.activity import Activity
from app.ui.app_host import AppContext, StopApp, StopSignal
from app.ui.buttons import BT4, BT5


class FakeDisplay:
    def __init__(self):
        self.cells = []
        self.lines = []

    def show_cells(self, cells):
        self.cells.append(list(cells))

    def show_lines(self, lines, dots_own_cell=False):
        self.lines.append(list(lines))


class Buttons:
    """Liefert nach `after` leeren Abfragen die Taste `button`."""

    def __init__(self, button=BT4, after=0, extra=None):
        self.button, self.after, self.polls = button, after, 0
        self.extra = list(extra or [])

    def get(self, timeout):
        self.polls += 1
        if self.extra:
            return self.extra.pop(0)
        if self.polls > self.after:
            return self.button
        return None

    def drain(self):
        pass


def ctx_for(display, buttons):
    return AppContext(display, buttons, Activity(), StopSignal())


class LoadFramesTest(unittest.TestCase):
    def test_reads_the_nine_files_as_nine_frames(self):
        frames = load_frames(FRAMES_DIR)
        self.assertEqual(len(frames), 9)
        for patterns, duration in frames:
            self.assertEqual(len(patterns), 96)
            self.assertEqual(duration, 0.2)

    def test_cell_lands_at_row_times_24_plus_column(self):
        patterns, _ = load_frames(FRAMES_DIR)[0]
        self.assertEqual(patterns[1 * 24 + 2], 0xA7EB)
        self.assertEqual(patterns[0], 0)

    def test_default_time_multiple_frames_and_outside_cells(self):
        with tempfile.TemporaryDirectory() as tmp:
            Path(tmp, "b.py").write_text(
                "VIDEO_FRAMES = [{(0, 0): 1}, {(23, 3): 2, (24, 0): 9, (0, 4): 9}]\n")
            Path(tmp, "a.py").write_text("VIDEO_FRAMES = [{(1, 0): 5}]\nFRAME_TIME = 0.1\n")
            frames = load_frames(tmp)
        self.assertEqual([d for _, d in frames], [0.1, 0.4, 0.4])
        self.assertEqual(frames[0][0][1], 5)
        self.assertEqual(frames[1][0][0], 1)
        self.assertEqual(frames[2][0][95], 2)
        self.assertEqual(sum(1 for p in frames[2][0] if p), 1)

    def test_does_not_execute_the_files(self):
        with tempfile.TemporaryDirectory() as tmp:
            Path(tmp, "x.py").write_text(
                "raise RuntimeError('exec')\nVIDEO_FRAMES = [{(0, 0): 3}]\n")
            frames = load_frames(tmp)
        self.assertEqual(frames[0][0][0], 3)

    def test_missing_folder_gives_no_frames(self):
        self.assertEqual(load_frames(Path(tempfile.gettempdir()) / "gibt-es-nicht-xyz"), [])


class StickmanAppTest(unittest.TestCase):
    def test_name(self):
        self.assertEqual(StickmanApp().name, "STRICHMAENNCHEN")

    def test_shows_frames_in_turn_and_ends_on_bt4(self):
        frames = [([1] * 96, 0.001), ([2] * 96, 0.001)]
        display = FakeDisplay()
        buttons = Buttons(BT4, after=5)
        with self.assertRaises(StopApp):
            StickmanApp(frames=frames).run(ctx_for(display, buttons))
        shown = [c[0] for c in display.cells]
        self.assertGreaterEqual(len(shown), 3)
        self.assertEqual(shown[:3], [1, 2, 1])

    def test_other_buttons_are_ignored(self):
        display = FakeDisplay()
        buttons = Buttons(BT4, after=3, extra=[BT5, BT5])
        with self.assertRaises(StopApp):
            StickmanApp(frames=[([7] * 96, 0.001)]).run(ctx_for(display, buttons))
        self.assertGreaterEqual(len(display.cells), 2)

    def test_no_frames_shows_message_and_waits_for_bt4(self):
        display = FakeDisplay()
        with self.assertRaises(StopApp):
            StickmanApp(frames=[]).run(ctx_for(display, Buttons(BT4)))
        self.assertEqual(display.lines[-1], ["KEINE BILDER", "BT4 ZURUECK"])
        self.assertEqual(display.cells, [])


if __name__ == "__main__":
    unittest.main()
