# applications/dance_app.py
# Tanz-Show der Werkstatt auf der Wand: neun Szenen aus festen Segmentmustern, in einer Schleife.
# Vorlage: docs/werkstatt/wand-werkstatt.html (Modus 'show'); BT5 startet die Show neu.
import math
import time

from app.driver.display.segments import (
    A, B, C, COLS, D1, D2, E, F, G1, G2, H, I, J, K, L, M,
    center, mirror, new_buffer, put_line,
)
from app.driver.display.text_layout import ROWS
from app.ui.buttons import BT5

BPM = 116

O_ = A | B | C | D1 | D2 | E | F

# [Zeile relativ zum Rumpf, Spalte relativ zur Mitte, Muster], linker Arm; der rechte wird gespiegelt
ARM = {
    "none": [], "down": [(0, -1, B | C)], "out": [(0, -1, A)], "upout": [(-1, -1, H | M)],
    "up": [(-1, -1, B | C)], "downout": [(0, -1, J | K)], "hip": [(0, -1, J | M)],
    "wave": [(0, -1, A), (-1, -1, E | F)],
}
# Seitenansicht nach rechts
ARM_S = {
    "none": [], "fwd": [(0, 0, G2), (0, 1, G1 | G2)], "up": [(-1, 1, E | F)],
    "upfwd": [(-1, 1, J | K)], "swf": [(0, 0, M)], "swb": [(0, 0, K)],
}
# [Zeile relativ zur Huefte, Spalte, Muster]
LEGS = {
    "stand": [(0, 0, I | K | M), (1, 0, F | E | B | C)],
    "wide": [(0, 0, I | K | M), (1, -1, J | K), (1, 1, H | M)],
    "kneeL": [(0, 0, I | M | G1 | E), (1, 0, B | C)],
    "kneeR": [(0, 0, I | K | G2 | C), (1, 0, F | E)],
    "kickR": [(0, 0, I | K | G2), (0, 1, G1 | G2), (1, 0, F | E)],
    "kickL": [(0, 0, I | M | G1), (0, -1, G1 | G2), (1, 0, B | C)],
    "squat": [(0, 0, I | K | M)],
    "pass": [(0, 0, I | L), (1, 0, I | L)],
}
HEAD = {"F": O_ | G1 | G2 | H | J, "B": O_, "SR": O_ | G2, "SL": O_ | G1}


def Pz(v, la, ra, lg, sh=0):
    """Pose: Ansicht, linker Arm, rechter Arm, Beine, Absenkung."""
    return (v, la, ra, lg, sh)


def put_fig(buf, col, p) -> None:
    """Figur (3 Spalten, 4 Zeilen) mit Kopf in Spalte col."""
    v, la, ra, lg, sh = p
    tr, hr = 1 + sh, 2 + sh
    side = v in ("SR", "SL")
    flip = v == "SL"

    def put(r, c, m):
        if 0 <= r < ROWS and 0 <= c < COLS:
            buf[r * COLS + c] |= m

    put(sh, col, HEAD[v])
    put(tr, col, I | L if side else A | I | L)
    if side:
        for dr, dc, m in ARM_S[la]:
            put(tr + dr, col + (-dc if flip else dc), mirror(m) if flip else m)
    else:
        for dr, dc, m in ARM[la]:
            put(tr + dr, col + dc, m)
        for dr, dc, m in ARM[ra]:
            put(tr + dr, col - dc, mirror(m))
    for dr, dc, m in LEGS[lg]:
        put(hr + dr, col + (-dc if flip else dc), mirror(m) if flip else m)


def _rep4(a, b):
    return [a, b, a, b, a, b, a, b]


CHOREO = [
    [Pz("F", "out", "out", "stand"), Pz("F", "up", "up", "wide"), Pz("F", "out", "out", "stand"),
     Pz("F", "down", "down", "wide"), Pz("F", "upout", "upout", "stand"),
     Pz("F", "wave", "wave", "wide"), Pz("F", "out", "out", "stand"),
     Pz("F", "down", "down", "stand")],
    [Pz("F", "hip", "upout", "wide"), Pz("F", "hip", "downout", "wide"),
     Pz("F", "hip", "upout", "wide"), Pz("F", "hip", "downout", "wide"),
     Pz("F", "upout", "hip", "wide"), Pz("F", "downout", "hip", "wide"),
     Pz("F", "upout", "hip", "wide"), Pz("F", "downout", "hip", "wide")],
    [Pz("F", "out", "out", "stand"), Pz("SR", "fwd", "fwd", "stand"),
     Pz("B", "out", "out", "stand"), Pz("SL", "fwd", "fwd", "stand"),
     Pz("F", "up", "up", "wide"), Pz("SR", "upfwd", "upfwd", "kneeR"),
     Pz("B", "up", "up", "wide"), Pz("SL", "upfwd", "upfwd", "kneeR")],
    _rep4(Pz("F", "down", "upout", "kneeL"), Pz("F", "upout", "down", "kneeR")),
    _rep4(Pz("F", "upout", "upout", "wide"), Pz("F", "down", "down", "squat", 1)),
    [Pz("F", "out", "out", "kickR"), Pz("F", "out", "out", "stand"),
     Pz("F", "out", "out", "kickL"), Pz("F", "out", "out", "stand"),
     Pz("F", "wave", "wave", "kickR"), Pz("F", "wave", "wave", "stand"),
     Pz("F", "wave", "wave", "kickL"), Pz("F", "up", "up", "wide")],
]

T_IDLE = I | G1 | G2 | K | M  # kleine Figur in einer Anzeige: Arme seitlich
T_UP = I | H | J | K | M      # Arme hoch
D3 = [4, 12, 20]
D6 = [2, 6, 10, 14, 18, 22]


def _imul(a: int, b: int) -> int:
    """Math.imul: Produkt modulo 2^32 als vorzeichenbehaftete 32-Bit-Zahl."""
    r = (a * b) & 0xFFFFFFFF
    return r - 0x100000000 if r & 0x80000000 else r


def _hash(a: int, b: int) -> float:
    x = _imul(a, 73856093) ^ _imul(b, 19349663)
    x = _imul(x ^ ((x & 0xFFFFFFFF) >> 13), 1274126177)
    return ((x ^ ((x & 0xFFFFFFFF) >> 16)) & 0xFFFFFFFF) / 4294967296


def _blitz():
    return [0xFFFF] * (COLS * ROWS)


def _crowd(b, rows, up) -> None:
    for r in rows:
        for c in range(COLS):
            b[r * COLS + c] = T_UP if up(r, c) else T_IDLE


def _auftritt(k, b):
    if k <= 14:
        put_fig(b, -2 + k, Pz("SR", "swf" if k % 2 else "swb", "none", "wide" if k % 2 else "pass"))
    elif k == 15:
        put_fig(b, 12, Pz("F", "down", "down", "stand"))
    elif k < 20:
        put_fig(b, 12, Pz("F", "down", "wave" if k % 2 else "upout", "stand"))
    else:
        put_fig(b, 12, Pz("F", "out", "out", "stand"))


def _solo(k, b):
    beat = k >> 1
    put_fig(b, 12, (CHOREO[1] if beat < 8 else CHOREO[5])[beat % 8])


def _klone(k, b):
    if k == 0 or k == 9:
        return _blitz()
    arme = CHOREO[0]
    rest = Pz("F", "out", "out", "stand")
    if k <= 4:
        for c in (12 - 2 * k, 12, 12 + 2 * k):
            put_fig(b, c, rest)
    elif k < 9:
        for c in D3:
            put_fig(b, c, arme[(k - 5) >> 1])
    elif k <= 11:
        d = k - 9
        for c in D3:
            put_fig(b, c - d, rest)
            put_fig(b, c + d, rest)
    else:
        for c in D6:
            put_fig(b, c, arme[(2 + ((k - 12) >> 1)) % 8])
    return None


def _welle(k, b):
    n, p = k // 8, k % 8 - 1
    for j, c in enumerate(D6):
        d = abs((5 - j if n == 2 else j) - p)
        if d == 0:
            put_fig(b, c, Pz("F", "up", "up", "wide"))
        elif d == 1:
            put_fig(b, c, Pz("F", "upout", "upout", "stand"))
        else:
            put_fig(b, c, Pz("F", "down", "down", "stand"))


def _spiegel(k, b):
    beat = k >> 1
    for j, c in enumerate(D6):
        v = "SR" if j < 3 else "SL"
        if beat < 6:
            p = Pz(v, "fwd", "", "stand") if beat % 2 else Pz(v, "upfwd", "", "kneeR")
        elif beat == 6:
            p = Pz("B", "up", "up", "wide")
        else:
            p = Pz("F", "upout", "upout", "wide")
        put_fig(b, c, p)


def _drehung(k, b):
    views = ["F", "SR", "B", "SL"]
    for j, c in enumerate(D6):
        i = k - j
        v = "F" if i < 0 else views[i % 4]
        put_fig(b, c, Pz(v, "fwd", "", "stand") if v in ("SR", "SL")
                else Pz(v, "out", "out", "stand"))


def _stadion(k, b):
    if k == 0:
        return _blitz()
    if k <= 24:
        w = ((k - 1) % 12) / 11 * (COLS + 8) - 4
        _crowd(b, [0, 1, 2, 3], lambda r, c: abs(c - (w - r * 1.5)) < 1.3)
    else:
        _crowd(b, [0, 1, 2, 3], lambda r, c: _hash(k, r * COLS + c) < 0.5)
    return None


def _bravo(k, b):
    put_line(b, 1, center("* BRAVO *" if k % 2 else "  BRAVO  "))
    _crowd(b, [2, 3], lambda r, c: _hash(k + 100, r * COLS + c) < 0.5)


def _abgang(k, b):
    if k < 2:
        put_fig(b, 12, Pz("F", "up", "up", "wide"))
    elif k < 4:
        put_fig(b, 12, Pz("F", "down", "down", "squat", 1))
    elif k < 18:
        put_fig(b, 12 - (k - 4), Pz("SR", "none", "", "stand" if k % 2 else "pass"))


# (Name, Laenge in Halbtakten, Funktion); eine Szene darf ein eigenes Bild zurueckgeben
SHOW = [
    ("Auftritt", 22, _auftritt), ("Solo", 32, _solo), ("Klone", 18, _klone),
    ("Welle", 24, _welle), ("Spiegel", 16, _spiegel), ("Drehung", 16, _drehung),
    ("Stadion", 33, _stadion), ("Bravo", 8, _bravo), ("Abgang", 20, _abgang),
]
SHOW_LEN = sum(length for _, length, _ in SHOW)


def show_frame(h: int) -> list:
    """Bild (96 Muster) zum Halbtakt h; die Show laeuft in einer Schleife."""
    k = h % SHOW_LEN
    for _, length, f in SHOW:
        if k < length:
            b = new_buffer()
            r = f(k, b)
            return r if r is not None else b
        k -= length
    raise AssertionError("unerreichbar")


class DanceApp:
    name = "TANZ 3D"

    def __init__(self, clock=time.monotonic) -> None:
        self._clock = clock

    def run(self, ctx) -> None:
        start = self._clock()
        off = 0.0
        last = None
        while True:
            t = self._clock() - start
            h = math.floor((t - off) * BPM / 30)
            if h != last:
                last = h
                ctx.display.show_cells(show_frame(h))
            wait = max((h + 1) * 30 / BPM + off - t, 0.0) + 1e-6  # knapp ueber den Takt
            if ctx.wait_button(timeout=wait) == BT5:
                off = self._clock() - start
                last = None
