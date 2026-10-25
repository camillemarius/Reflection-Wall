# display/cells.py
# Text zu Segmentmustern: 24 Stellen je Zeile, 4 Zeilen.
from typing import Sequence

from app.driver.display.ascii_map import ASCII_16SEG
from app.driver.display.text_layout import CHARS_PER_ROW, ROWS

DOT_BIT = 0x0004

_UMLAUTS = {"Ä": "AE", "Ö": "OE", "Ü": "UE", "ß": "SS"}


def normalize(text: str) -> str:
    """Grossbuchstaben, Umlaute umschrieben, Zeilenumbrueche als Leerzeichen."""
    for src, dst in _UMLAUTS.items():
        text = text.replace(src, dst).replace(src.lower(), dst)
    text = text.replace("\r", " ").replace("\n", " ")
    return text.upper()


def line_to_cells(line: str, dots_own_cell: bool = False) -> list[int]:
    """Genau 24 Muster. Ein Punkt gehoert zum Zeichen davor, ausser dots_own_cell;
    am Zeilenanfang bleibt seine Stelle leer."""
    cells: list[int] = []
    for ch in line:
        if ch == "." and not dots_own_cell:
            if cells:
                cells[-1] |= DOT_BIT
                continue
            # Punkt am Zeilenanfang: keine Stelle davor, die Stelle bleibt leer
            cells.append(0)
            continue
        if len(cells) >= CHARS_PER_ROW:
            break
        cells.append(DOT_BIT if ch == "." else ASCII_16SEG.get(ch, 0))
    return cells + [0] * (CHARS_PER_ROW - len(cells))


def used_cells(line: str) -> int:
    """Wie viele Stellen line belegt; Punkte zaehlen wie in line_to_cells (ohne dots_own_cell)."""
    count = 0
    for ch in line:
        if ch == "." and count:
            continue  # gehoert zum Zeichen davor
        count += 1
    return count


def lines_to_cells(lines: Sequence[str], dots_own_cell: bool = False) -> list[int]:
    """Genau 96 Muster, fehlende Zeilen bleiben leer."""
    cells: list[int] = []
    for row in range(ROWS):
        line = lines[row] if row < len(lines) else ""
        cells.extend(line_to_cells(line, dots_own_cell))
    return cells
