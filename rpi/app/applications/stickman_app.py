# applications/stickman_app.py
# Strichmaennchen auf der Wand: die handgezeichneten Bilder laufen in einer Schleife bis BT4.
# Die Bilddateien werden nur gelesen (ast), nie ausgefuehrt.
import ast
from pathlib import Path

COLUMNS = 24
ROWS = 4
DEFAULT_FRAME_TIME = 0.4
FRAMES_DIR = Path(__file__).resolve().parent / "Animations" / "videoframes"


def _assigned_values(path: Path) -> dict:
    values = {}
    for node in ast.parse(path.read_text(encoding="utf-8")).body:
        if isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name) and target.id in ("VIDEO_FRAMES", "FRAME_TIME"):
                    values[target.id] = ast.literal_eval(node.value)
    return values


def _patterns(frame: dict) -> list:
    patterns = [0] * (COLUMNS * ROWS)
    for (column, row), pattern in frame.items():
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
        values = _assigned_values(path)
        duration = float(values.get("FRAME_TIME", DEFAULT_FRAME_TIME))
        for frame in values.get("VIDEO_FRAMES", []):
            frames.append((_patterns(frame), duration))
    return frames


class StickmanApp:
    name = "STRICHMAENNCHEN"

    def __init__(self, frames_dir=FRAMES_DIR, frames=None) -> None:
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
                ctx.wait_button(timeout=duration)
