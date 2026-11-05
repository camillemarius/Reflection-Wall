# applications/dance_app.py
# Tanz-Show auf der Wand: neun Szenen aus festen Segmentmustern, in einer Schleife; BT5 startet
# sie neu. Auftritt, Solo, Welle, Spiegel, Drehung und Abgang stammen aus der Werkstatt
# (docs/werkstatt/wand-werkstatt.html, Modus 'show'). Neu fuer die Wand: im Einmarsch laufen die
# Taenzer einzeln herein, im Karussell drehen sie sich im Kreis (hinten klein und dunkel), beim
# Bravo jubelt das Publikum in den unteren zwei Reihen. Die ganze Wand leuchtet nie.
import math
import time

from app.driver.display.segments import (
    A, B, C, COLS, D1, D2, E, F, G1, G2, H, I, J, K, L, M,
    center, mirror, new_buffer, put_line,
)
from app.driver.display.text_layout import ROWS
from app.ui.buttons import BT5

BPM = 116
SUB = 4            # Bildschritte je Halbtakt: Karussell und La Ola bewegen sich auch dazwischen
FULL = (15,) * 12  # volle Helligkeit aller zwoelf Module

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
D6 = [2, 6, 10, 14, 18, 22]


def _imul(a: int, b: int) -> int:
    """Math.imul: Produkt modulo 2^32 als vorzeichenbehaftete 32-Bit-Zahl."""
    r = (a * b) & 0xFFFFFFFF
    return r - 0x100000000 if r & 0x80000000 else r


def _hash(a: int, b: int) -> float:
    x = _imul(a, 73856093) ^ _imul(b, 19349663)
    x = _imul(x ^ ((x & 0xFFFFFFFF) >> 13), 1274126177)
    return ((x ^ ((x & 0xFFFFFFFF) >> 16)) & 0xFFFFFFFF) / 4294967296


def _crowd(b, rows, up) -> None:
    for r in rows:
        for c in range(COLS):
            b[r * COLS + c] = T_UP if up(r, c) else T_IDLE


def _put(b, r, c, m) -> None:
    if 0 <= r < ROWS and 0 <= c < COLS:
        b[r * COLS + c] |= m


def _walk(b, col, step, right) -> None:
    """Grosse Figur in Seitenansicht mitten im Schritt."""
    put_fig(b, col, Pz("SR" if right else "SL", "swf" if step % 2 else "swb", "none",
                       "wide" if step % 2 else "pass"))


def _mittel(b, col, step) -> None:
    """Figur in zwei Zeilen (Zeile 1 und 2): weiter weg."""
    _put(b, 1, col, A | B | F | G1 | G2 | L | K | M)
    _put(b, 2, col, I | (K | M if step % 2 else L))


def _klein(b, col, step) -> None:
    """Figur in einer Zelle (Zeile 1): ganz hinten."""
    _put(b, 1, col, I | G1 | G2 | (K | M if step % 2 else L))


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


# Einmarsch: (Platz, kommt von links, Start-Halbtakt). Innen zuerst, abwechselnd links und rechts,
# damit niemand an einem Stehenden vorbeilaeuft; der Solist macht zuvor zwei Schritte auf Platz 10.
EINMARSCH = [(14, False, 1), (6, True, 4), (18, False, 7), (2, True, 10), (22, False, 13)]
EIN_TANZ = 19  # ab diesem Halbtakt tanzen alle sechs


def _greet(b, col, since, k) -> None:
    """Angekommen: nach vorne drehen, jubeln, dann im Takt warten."""
    if since == 0:
        p = Pz("F", "out", "out", "stand")
    elif since < 3:
        p = Pz("F", "up", "up", "wide")
    else:
        p = Pz("F", "down", "down", "stand") if k % 2 else Pz("F", "out", "out", "stand")
    put_fig(b, col, p)


def _einmarsch(k, b):
    if k >= EIN_TANZ:
        for c in D6:
            put_fig(b, c, CHOREO[0][((k - EIN_TANZ) >> 1) % 8])
        return
    if k < 2:
        _walk(b, 11 - k, k, right=False)
    else:
        _greet(b, 10, k - 2, k)
    for goal, left, start in EINMARSCH:
        if k < start:
            continue
        x0 = -2 if left else COLS + 1
        arrive = start + abs(goal - x0)
        if k < arrive:
            _walk(b, x0 + (k - start) * (1 if left else -1), k, left)
        else:
            _greet(b, goal, k - arrive, k)


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


# Karussell: die sechs schwenken aus der Reihe in einen Kreis (Mitte Spalte 12, Radius 10), drehen
# eine Runde und kommen in die Reihe zurueck; dann gehen fuenf ab, der auf Platz 10 geht in die
# Mitte. k laeuft hier in Viertel-Halbtakten (SUB), damit sich der Kreis fluessig dreht.
K_AUF, K_RUNDE, K_ZURUECK = 4, 24, 4
K_AB = K_AUF + K_RUNDE + K_ZURUECK
_IN_REIHE = [math.asin((c - 12) / 10) for c in D6]          # Winkel, unter denen die Reihe liegt
_IM_KREIS = [math.radians(-150 + 60 * j) for j in range(6)]  # gleichmaessig im Kreis
GROSS, MITTEL = 0.55, -0.4               # Tiefe (1 vorne, -1 hinten), ab der eine Figur so gross ist
LV_GROSS, LV_MITTEL, LV_KLEIN = 15, 8, 3
# Abgang aus der Reihe: (Platz, Richtung, Start-Halbtakt nach K_AB)
AUSMARSCH = [(2, -1, 1), (22, 1, 1), (6, -1, 2), (18, 1, 2), (14, 1, 3)]


def _smooth(u):
    u = min(max(u, 0.0), 1.0)
    return u * u * (3 - 2 * u)


def _ring(k):
    """(Spalte, Tiefe) der sechs Taenzer; in der Reihe gelten alle als vorne."""
    if k < K_AUF:
        s, phi = _smooth(k / K_AUF), 0.0
    elif k < K_AUF + K_RUNDE:
        s, phi = 1.0, 2 * math.pi * _smooth((k - K_AUF) / K_RUNDE)
    else:
        s, phi = 1.0 - _smooth((k - K_AUF - K_RUNDE) / K_ZURUECK), 0.0
    out = []
    for a0, a1 in zip(_IN_REIHE, _IM_KREIS):
        a = a0 + (a1 - a0) * s + phi
        out.append((12 + 10 * math.sin(a), 1 - s * (1 - math.cos(a))))
    return out


def _ring_bild(k):
    """Bild und Helligkeit je Modul: hinten zuerst gezeichnet, vorne deckt hinten zu."""
    pos, later = _ring(k), _ring(k + 0.05)
    step = int(k)
    cells, owner = new_buffer(), [0] * (COLS * ROWS)
    for j in sorted(range(6), key=lambda j: pos[j][1]):
        x, z = pos[j]
        col = int(round(x))
        fig = new_buffer()
        if z > GROSS:
            dx = later[j][0] - x
            if abs(dx) < 0.01:
                put_fig(fig, col, Pz("F", "out", "out", "stand"))
            else:
                _walk(fig, col, step + j, dx > 0)
            lv = LV_GROSS
        elif z > MITTEL:
            _mittel(fig, col, step + j)
            lv = LV_MITTEL
        else:
            _klein(fig, col, step + j)
            lv = LV_KLEIN
        for i, m in enumerate(fig):
            if m:
                cells[i], owner[i] = m, lv
    levels = [0] * 12
    for i, lv in enumerate(owner):
        module = (i // COLS) * 3 + (i % COLS) // 8
        levels[module] = max(levels[module], lv)
    return cells, tuple(lv or 15 for lv in levels)


def _ausmarsch(kk, b):
    for c, d, start in AUSMARSCH:
        if kk < start:
            put_fig(b, c, Pz("F", "down", "down", "stand"))
            continue
        x = c + d * (kk - start + 1)
        if -2 < x < COLS + 1:
            _walk(b, x, kk, d > 0)
    if kk < 5:
        put_fig(b, 10, Pz("F", "down", "down", "stand"))
    elif kk < 7:
        _walk(b, 6 + kk, kk, True)
    else:
        put_fig(b, 12, Pz("F", "down", "wave" if kk % 2 else "upout", "stand"))


def _karussell(k, b):
    if k >= K_AB:
        _ausmarsch(int(k) - K_AB, b)
        return
    b[:] = _ring_bild(k)[0]


def _karussell_levels(k):
    return FULL if k >= K_AB else _ring_bild(k)[1]


OLA = 8  # Halbtakte fuer eine La Ola von links nach rechts
BRAVO_LV = (15,) * 6 + (7,) * 3 + (15,) * 3  # hintere Publikumsreihe (Zeile 2) dunkler


def _bravo(k, b):
    h = int(k)
    put_line(b, 1, center("* BRAVO *" if h % 2 else "  BRAVO  "))
    if k < OLA:
        w = k / OLA * (COLS + 6) - 3
        _crowd(b, [2, 3], lambda r, c: abs(c - (w - (3 - r))) < 1.5)
    else:
        _crowd(b, [2, 3], lambda r, c: _hash(h + 100, r * COLS + c) < 0.5)


def _abgang(k, b):
    if k < 2:
        put_fig(b, 12, Pz("F", "up", "up", "wide"))
    elif k < 4:
        put_fig(b, 12, Pz("F", "down", "down", "squat", 1))
    elif k < 18:
        put_fig(b, 12 - (k - 4), Pz("SR", "none", "", "stand" if k % 2 else "pass"))


# (Name, Laenge in Halbtakten, Funktion)
SHOW = [
    ("Auftritt", 22, _auftritt), ("Solo", 32, _solo), ("Einmarsch", 30, _einmarsch),
    ("Welle", 24, _welle), ("Spiegel", 16, _spiegel), ("Drehung", 16, _drehung),
    ("Karussell", 46, _karussell), ("Bravo", 16, _bravo), ("Abgang", 20, _abgang),
]
SHOW_LEN = sum(length for _, length, _ in SHOW)
FINE = (_karussell, _bravo)  # bekommen k mit Bruchteil und bewegen sich zwischen den Halbtakten
LEVELS = {_karussell: _karussell_levels, _bravo: lambda k: BRAVO_LV}


def _at(h: int, q: int):
    k = h % SHOW_LEN
    for _, length, f in SHOW:
        if k < length:
            return f, (k + q / SUB if f in FINE else k)
        k -= length
    raise AssertionError("unerreichbar")


def show_frame(h: int, q: int = 0) -> list:
    """Bild (96 Muster) zum Halbtakt h, Viertel q; die Show laeuft in einer Schleife."""
    f, k = _at(h, q)
    b = new_buffer()
    f(k, b)
    return b


def show_levels(h: int, q: int = 0) -> tuple:
    """Helligkeit der zwoelf Module (0..15) zum Halbtakt h, Viertel q."""
    f, k = _at(h, q)
    levels = LEVELS.get(f)
    return levels(k) if levels else FULL


class DanceApp:
    name = "TANZ 3D"

    def __init__(self, clock=time.monotonic) -> None:
        self._clock = clock

    def run(self, ctx) -> None:
        # Anzeigen ohne Helligkeit je Modul (Terminal) zeigen die Show einfach gleich hell
        set_levels = getattr(ctx.display, "set_levels", None)
        start = self._clock()
        off = 0.0
        last_tick, last_cells, last_levels = None, None, FULL
        try:
            while True:
                t = self._clock() - start
                tick = math.floor((t - off) * BPM * SUB / 30)
                if tick != last_tick:
                    last_tick = tick
                    h, q = divmod(tick, SUB)
                    levels = show_levels(h, q)
                    if set_levels and levels != last_levels:
                        set_levels(levels)
                        last_levels = levels
                    cells = show_frame(h, q)
                    if q == 0 or cells != last_cells:  # auf jeden Halbtakt ein Bild, dazwischen nur Neues
                        ctx.display.show_cells(cells)
                        last_cells = cells
                wait = max((tick + 1) * 30 / (BPM * SUB) + off - t, 0.0) + 1e-6  # knapp danach
                if ctx.wait_button(timeout=wait) == BT5:
                    off = self._clock() - start
                    last_tick = None
        finally:
            if set_levels and last_levels != FULL:
                set_levels(FULL)
