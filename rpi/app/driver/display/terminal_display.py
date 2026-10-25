# display/terminal_display.py
# Anzeige im Terminal (PC-Modus), gleiche Schnittstelle wie WallDisplay.
from typing import Sequence

from app.driver.display.ascii_map import ASCII_16SEG
from app.driver.display.cells import DOT_BIT, lines_to_cells, normalize
from app.driver.display.text_layout import CHARS_PER_ROW, ROWS, wrap

# Umgekehrte Glyphentabelle; bei gleichem Muster (O/0) gewinnt der Grossbuchstabe
_REVERSE: dict = {}
for _ch, _mask in sorted(ASCII_16SEG.items(), key=lambda kv: not kv[0].isupper()):
    _REVERSE.setdefault(_mask, _ch)
_REVERSE[0] = " "


class TerminalDisplay:
    WIDTH = CHARS_PER_ROW
    HEIGHT = ROWS

    def __init__(self):
        self._canvas = [0] * (CHARS_PER_ROW * ROWS)

    def start(self) -> None:
        pass

    @staticmethod
    def _char(mask: int) -> str:
        if mask in _REVERSE:
            return _REVERSE[mask]
        if mask & DOT_BIT and (mask & ~DOT_BIT) in _REVERSE:
            return _REVERSE[mask & ~DOT_BIT]
        return "#"

    def show_cells(self, masks: Sequence[int]) -> None:
        print("+" + "-" * CHARS_PER_ROW + "+")
        for row in range(ROWS):
            cells = masks[row * CHARS_PER_ROW:(row + 1) * CHARS_PER_ROW]
            print("|" + "".join(self._char(m) for m in cells) + "|")
        print("+" + "-" * CHARS_PER_ROW + "+")

    def show_lines(self, lines: Sequence[str], dots_own_cell: bool = False) -> None:
        self.show_cells(lines_to_cells(lines, dots_own_cell))

    def show_text(self, text: str) -> bool:
        rows, fits = wrap(normalize(text))
        self.show_lines(rows)
        return fits

    def clear(self) -> None:
        self._canvas = [0] * (CHARS_PER_ROW * ROWS)
        self.show_cells(self._canvas)

    def clear_canvas(self) -> None:
        """Leert nur den Puffer der Zeichenflaeche; schreibt nichts (kein Flackern)."""
        self._canvas = [0] * (CHARS_PER_ROW * ROWS)

    def set_segments(self, x: int, y: int, mask: int) -> None:
        if 0 <= x < self.WIDTH and 0 <= y < self.HEIGHT:
            self._canvas[y * self.WIDTH + x] = mask

    def refresh(self) -> None:
        self.show_cells(self._canvas)
