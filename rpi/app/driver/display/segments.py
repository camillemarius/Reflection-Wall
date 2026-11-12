# display/segments.py
# Bausteine fuer Bilder aus festen Segmentmustern (Teil 5): Bits der 16 Segmente, Spiegeln,
# Zeichenflaeche zu 96 Stellen, Text an beliebiger Spalte und die 12 waagrechten Ebenen.
# Vorlage: docs/werkstatt/wand-werkstatt.html (dieselbe Kodierung wie ascii_map).
from app.driver.display.ascii_map import ASCII_16SEG
from app.driver.display.cells import DOT_BIT, normalize, used_cells
from app.driver.display.text_layout import CHARS_PER_ROW, ROWS

COLS = CHARS_PER_ROW
CELLS = COLS * ROWS

# Aussen: A oben, B/C rechts, D1/D2 unten, E/F links, G1/G2 Mitte. Innen: I/L senkrecht,
# H/J schraeg oben (links/rechts), K/M schraeg unten (links/rechts). DPB ist der Punkt.
A, B, C = 1 << 5, 1 << 1, 1 << 15
D1, D2, E, F = 1 << 10, 1 << 13, 1 << 9, 1 << 7
G1, G2 = 1 << 8, 1 << 0
H, I, J, K, L, M = 1 << 6, 1 << 4, 1 << 3, 1 << 11, 1 << 12, 1 << 14
DPB = DOT_BIT
ALL = 0xFFFF

_MIRROR_PAIRS = ((B, F), (C, E), (H, J), (K, M), (G1, G2), (D1, D2))

# Ebenen: je Zeile oben, Mitte, unten; Spuren: links, Mitte, rechts (obere/untere Haelfte)
HB = (A, G1 | G2, D1 | D2)
VU = (F, I, B)
VD = (E, L, C)


def mirror(mask: int) -> int:
    """Links und rechts getauscht; A, I, L und der Punkt bleiben."""
    result = mask & (A | I | L | DPB)
    for left, right in _MIRROR_PAIRS:
        if mask & left:
            result |= right
        if mask & right:
            result |= left
    return result


def new_buffer() -> list:
    return [0] * CELLS


def set_cell(buf: list, row: int, col: int, mask: int) -> None:
    """Segmente einer Stelle dazu (ODER); ausserhalb der Wand geschieht nichts."""
    if 0 <= row < ROWS and 0 <= col < COLS:
        buf[row * COLS + col] |= mask


def put_line(buf: list, row: int, text: str, col: int = 0) -> None:
    """Text ab col; ein Punkt kommt zur Stelle davor, am Rand ist Schluss."""
    c = col
    for ch in normalize(text):
        if ch == "." and c > col:
            buf[row * COLS + c - 1] |= DPB
            continue
        if c >= COLS:
            break
        if c >= 0:
            buf[row * COLS + c] = ASCII_16SEG.get(ch, 0)
        c += 1


def center(text: str) -> str:
    return " " * max(0, (COLS - used_cells(normalize(text))) // 2) + text


def hbar(buf: list, col: int, level: int) -> None:
    """Waagrechter Strich auf Ebene 0..11 (0 = ganz oben)."""
    if 0 <= col < COLS and 0 <= level <= 11:
        buf[(level // 3) * COLS + col] |= HB[level % 3]


def vrun(buf: list, col: int, lane: int, level1: int, level2: int) -> None:
    """Senkrechter Strich in Spur lane (0 links, 1 Mitte, 2 rechts) zwischen zwei Ebenen."""
    if not 0 <= col < COLS:
        return
    low, high = max(0, min(level1, level2)), min(11, max(level1, level2))
    for level in range(low, high):
        part = level % 3
        if part == 2:
            continue  # Luecke zwischen zwei Zeilen
        buf[(level // 3) * COLS + col] |= (VU if part == 0 else VD)[lane]
