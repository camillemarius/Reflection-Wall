# applications/stickman_app.py
# Strichmaennchen auf der Wand: die handgezeichneten Bilder laufen in einer Schleife bis BT4.
# Die Bilddateien werden nur gelesen (ast), nie ausgefuehrt.
import ast
import logging
import math
import time
from pathlib import Path

log = logging.getLogger(__name__)

COLUMNS = 24
ROWS = 4
DEFAULT_FRAME_TIME = 0.4
FRAMES_DIR = Path(__file__).resolve().parent / "Animations" / "videoframes"


def _assigned_values(path: Path) -> dict:
    values = {}
    for node in ast.parse(path.read_text(encoding="utf-8-sig")).body:
        if isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name) and target.id in ("VIDEO_FRAMES", "FRAME_TIME"):
                    values[target.id] = ast.literal_eval(node.value)
    return values


def _patterns(frame: dict) -> list:
    patterns = [0] * (COLUMNS * ROWS)
    if not isinstance(frame, dict):
        raise ValueError("Bild ist kein dict")
    for (column, row), pattern in frame.items():
        if not all(isinstance(v, int) for v in (column, row, pattern)):
            raise ValueError("Zelle ist nicht ganzzahlig")
        if 0 <= column < COLUMNS and 0 <= row < ROWS:
            patterns[row * COLUMNS + column] = pattern
    return patterns


def load_frames(directory) -> list:
    """Alle Bilder des Ordners: Liste von (96 Muster, Dauer in s)."""
    folder = Path(directory)
    frames = []
    if not folder.is_dir():
        return frames
    for path in sorted(folder.glob("*.py")):
        try:
            values = _assigned_values(path)
            duration = float(values.get("FRAME_TIME", DEFAULT_FRAME_TIME))
            if not (math.isfinite(duration) and duration > 0):
                duration = DEFAULT_FRAME_TIME
            file_frames = [(_patterns(frame), duration)
                           for frame in values.get("VIDEO_FRAMES", [])]
        except Exception as error:
            log.warning("Bilddatei %s uebersprungen: %s", path.name, error)
            continue
        frames.extend(file_frames)
    return frames


class StickmanApp:
    name = "STRICHMAENNCHEN"

    def __init__(self, frames_dir=FRAMES_DIR, frames=None, clock=time.monotonic) -> None:
        self._clock = clock
        self._frames_dir = frames_dir
        self._frames = frames

    def run(self, ctx) -> None:
        frames = self._frames if self._frames is not None else load_frames(self._frames_dir)
        if not frames:
            ctx.display.show_lines(["KEINE BILDER", "BT4 ZURUECK"])
            while True:
                ctx.wait_button()
        while True:
            for patterns, duration in frames:
                ctx.display.show_cells(patterns)
                deadline = self._clock() + duration
                while True:
                    remaining = deadline - self._clock()
                    if remaining <= 0:
                        break
                    ctx.wait_button(timeout=remaining)
