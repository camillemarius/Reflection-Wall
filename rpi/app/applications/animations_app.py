# applications/animations_app.py
# Die elf Animationen aus festen Segmentmustern (Vorlage: docs/werkstatt/wand-werkstatt.html,
# Zeilen 618-716 und Bildschirm 'anim'); alle 10 s die naechste, BT6 sofort die naechste.
import math
import random
import time
from types import SimpleNamespace

from app.driver.display.ascii_map import ASCII_16SEG
from app.driver.display.segments import (
    A, B, C, COLS, D1, D2, DPB, E, F, G1, G2, H, I, J, K, L, M, VD, VU,
    hbar, mirror, new_buffer, put_line, vrun,
)
from app.driver.display.text_layout import ROWS
from app.ui.buttons import BT6

ANIMS = ["equalizer", "regen", "welle", "tunnel", "feuerwerk", "pacman",
         "laufschrift", "schlange", "pong", "matrix", "lauflicht"]
ANIM_IV = {"equalizer": 0.1, "regen": 0.08, "welle": 0.08, "tunnel": 0.12, "feuerwerk": 0.12,
           "pacman": 0.16, "laufschrift": 0.08, "schlange": 0.06, "pong": 0.11,
           "matrix": 0.15, "lauflicht": 0.05}
SWITCH_S = 10.0
MAX_STEPS = 5

PAC_O = A | F | E | D1 | D2 | J | M
PAC_C = A | F | E | D1 | D2 | B | C | G2
GHOST = A | F | B | E | C | K | L | M
GHOST_SCARED = A | F | B | E | C | H | J
POWER = G1 | G2 | D1 | D2 | E | C

MCH = "ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789"
LAUF_TEXT = "   REFLECTION WALL   *   WER NACH INNEN SCHAUT ERWACHT   *"


def _round(x: float) -> int:
    """Math.round der Vorlage: halbe Werte nach oben."""
    return math.floor(x + 0.5)


def _sign(x: float) -> int:
    return (x > 0) - (x < 0)


def _set(buf, row, col, mask):
    if 0 <= row < ROWS and 0 <= col < COLS:
        buf[row * COLS + col] |= mask


def _snake_path() -> list:
    path = []
    for lv in range(12):
        row, k, right = lv // 3, lv % 3, lv % 2 == 0
        for i in range(COLS):
            c = i if right else COLS - 1 - i
            if k == 0:
                path.append((row, c, A))
            else:
                h = (G1, G2) if k == 1 else (D1, D2)
                first, second = (h[0], h[1]) if right else (h[1], h[0])
                path.append((row, c, first))
                path.append((row, c, second))
        if lv < 11 and k != 2:
            path.append((row, COLS - 1 if right else 0, (VU if k == 0 else VD)[2 if right else 0]))
    return path


SNAKE_PATH = _snake_path()


# ---------- Bilder ohne Zustand ----------

def _eq_frame(b, t):
    for c in range(COLS):
        v = (0.42 + 0.15 * (1 - c / 23) + 0.25 * math.sin(c * 0.55 + t * 2.7)
             + 0.2 * math.sin(t * 4.1 - c * 0.9) * math.sin(t * 0.9 + c * 0.2)
             + 0.1 * abs(math.sin(t * math.pi * 1.9)))
        h = max(1, min(12, _round(v * 12)))
        for lv in range(12 - h, 12):
            hbar(b, c, lv)


def _welle_frame(b, t):
    def lev(c):
        return max(0, min(11, _round(5.5 + 4.5 * math.sin(c * 0.42 - t * 2.4)
                                      + math.sin(c * 1.3 + t * 1.7))))
    for c in range(COLS):
        lo, nxt = lev(c), lev(c + 1)
        hbar(b, c, lo)
        if c < COLS - 1 and nxt != lo:
            vrun(b, c, 2, lo, nxt)


def _rect_at(b, k):
    top, bot, x0, x1 = k, 11 - k, 2 * k, COLS - 1 - 2 * k
    if top >= bot:
        return
    for c in range(x0, x1 + 1):
        hbar(b, c, top)
        hbar(b, c, bot)
    vrun(b, x0, 0, top, bot)
    vrun(b, x1, 2, top, bot)


def _tunnel_frame(b, t):
    ph = t * 2.4
    for j in range(3):
        _rect_at(b, 5 - math.floor((ph + j * 2) % 6))


def _lauf_frame(b, t):
    s, n = math.floor(t * 6), len(LAUF_TEXT)
    put_line(b, 1, "".join(LAUF_TEXT[(s + i) % n] for i in range(COLS)))
    for c in range(COLS):
        if (c + s) % 4 < 2:
            b[c] |= D1 | D2
            b[2 * COLS + c] |= A


def _snake_frame(b, t):
    n = len(SNAKE_PATH)
    head = math.floor(t * 16) % n
    for i in range(14):
        r, c, m = SNAKE_PATH[(head - i + n) % n]
        b[r * COLS + c] |= m


def _kitt_frame(b, t):
    u = (t * 0.8) % 2
    d = 1 if u < 1 else -1
    pos = _round((u if u < 1 else 2 - u) * (COLS - 1))
    masks = [A | G1 | G2 | D1 | D2, G1 | G2 | D1 | D2, G1 | G2, G2 if d > 0 else G1]
    for i, m in enumerate(masks):
        c = pos - d * i
        if 0 <= c < COLS:
            b[COLS + c] |= m
            b[2 * COLS + c] |= m


_STATELESS = {"equalizer": _eq_frame, "welle": _welle_frame, "tunnel": _tunnel_frame,
              "laufschrift": _lauf_frame, "schlange": _snake_frame, "lauflicht": _kitt_frame}


class AnimationsApp:
    name = "ANIMATIONEN"

    def __init__(self, clock=time.monotonic, rng=None) -> None:
        self._clock = clock
        self._rng = rng if rng is not None else random.Random()
        self._manual = 0
        self._anim = None
        self._last_step = -1
        self._last_name = ""
        self._reset()

    # ---------- Zufall und Zustand ----------

    def _floor_rand(self, n: int) -> int:
        return math.floor(self._rng.random() * n)

    def _new_drop(self, any_row: bool) -> dict:
        lane = self._floor_rand(COLS * 3)
        p = self._floor_rand(8) if any_row else -self._floor_rand(6)
        return {"lane": lane, "p": p, "splash": 0}

    def _rnd_ch(self) -> str:
        return MCH[self._floor_rand(len(MCH))]

    def _new_stream(self) -> dict:
        h = -self._rng.random() * 5
        v = 0.25 + self._rng.random() * 0.35
        return {"h": h, "v": v, "len": 2 + self._floor_rand(2)}

    def _pong_reset(self, direction=0) -> None:
        by = 3 + self._floor_rand(2)
        dx = direction or (-1 if self._rng.random() < 0.5 else 1)
        dy = -1 if self._rng.random() < 0.5 else 1
        self._anim.pong = {"bx": 12, "by": by, "dx": dx, "dy": dy, "lp": 3, "rp": 4, "wait": 4}

    def _matrix_reset(self) -> None:
        streams = []
        for _ in range(COLS):
            s = self._new_stream()
            s["ch"] = [self._rnd_ch() for _ in range(4)]
            streams.append(s)
        self._anim.matrix = streams

    def _reset(self) -> None:
        self._anim = SimpleNamespace(
            step=0, drops=[self._new_drop(True) for _ in range(22)], rockets=[], nextRocket=0,
            pac={"x": -1, "g": 0, "phase": "rechts", "t": 0, "k": 0}, pong=None, matrix=None)
        self._pong_reset()
        self._matrix_reset()
        self._last_step = -1
        self._last_name = ""

    # ---------- Schritte ----------

    def _regen_step(self) -> None:
        for d in self._anim.drops:
            if d["splash"]:
                d["splash"] -= 1
                if d["splash"] == 0:
                    d.update(self._new_drop(False))
                continue
            d["p"] += 1
            if d["p"] >= 8:
                d["splash"] = 2

    def _fw_step(self) -> None:
        a = self._anim
        if a.step >= a.nextRocket:
            c = 2 + self._floor_rand(COLS - 4)
            top = 2 + self._floor_rand(4)
            a.rockets.append({"c": c, "top": top, "p": 8, "up": True, "k": 0})
            a.nextRocket = a.step + 5 + self._floor_rand(7)
        for r in a.rockets:
            if r["up"]:
                r["p"] -= 1
                if r["p"] <= r["top"]:
                    r["up"] = False
            else:
                r["k"] += 1
        a.rockets = [r for r in a.rockets if r["up"] or r["k"] < 7]

    def _pac_step(self) -> None:
        P = self._anim.pac
        P["t"] += 1
        if P["phase"] == "rechts":
            P["x"] += 1
            if P["x"] >= 21:
                P["phase"] = "links"
                P["g"] = P["x"] - 3
        elif P["phase"] == "links":
            P["x"] -= 1
            if P["t"] % 2 == 0:
                P["g"] -= 1
            if P["x"] <= P["g"]:
                P["phase"] = "punkte"
                P["k"] = 0
        else:
            P["k"] += 1
            if P["k"] > 6:
                P.update(x=-1, phase="rechts", t=0)

    def _pong_step(self) -> None:
        P = self._anim.pong
        if P["wait"] > 0:
            P["wait"] -= 1
            return

        def follow(p, goal):
            return max(1, min(6, p + _sign(goal - p) * (1 if self._rng.random() < 0.8 else 0)))

        if P["dx"] < 0:
            P["lp"] = follow(P["lp"], P["by"])
        else:
            P["rp"] = follow(P["rp"], P["by"])
        P["bx"] += P["dx"]
        P["by"] += P["dy"]
        if P["by"] <= 0 or P["by"] >= 7:
            P["dy"] = -P["dy"]
            P["by"] = max(0, min(7, P["by"]))
        if P["bx"] <= 1 and P["dx"] < 0:
            if abs(P["by"] - P["lp"]) <= 1 and P["bx"] >= 1:
                P["dx"] = 1
            elif P["bx"] < 0:
                self._pong_reset(1)
        elif P["bx"] >= COLS - 2 and P["dx"] > 0:
            if abs(P["by"] - P["rp"]) <= 1 and P["bx"] <= COLS - 2:
                P["dx"] = -1
            elif P["bx"] > COLS - 1:
                self._pong_reset(-1)

    def _matrix_step(self) -> None:
        for s in self._anim.matrix:
            s["h"] += s["v"]
            index = self._floor_rand(4)
            s["ch"][index] = self._rnd_ch()
            if s["h"] - s["len"] > 3:
                s.update(self._new_stream())

    def _advance(self, name: str) -> None:
        """Ein Schritt: Zaehler hoch, dann die Schrittfunktion der Animation (falls es eine gibt)."""
        self._anim.step += 1
        step = {"regen": self._regen_step, "feuerwerk": self._fw_step, "pacman": self._pac_step,
                "pong": self._pong_step, "matrix": self._matrix_step}.get(name)
        if step:
            step()

    # ---------- Bilder mit Zustand ----------

    def _regen_frame(self, b) -> None:
        for d in self._anim.drops:
            c, x = d["lane"] // 3, d["lane"] % 3
            if d["splash"]:
                b[3 * COLS + c] |= (K | M) if d["splash"] == 2 else (D1 | D2)
                continue
            for p in (d["p"], d["p"] - 1):
                if p < 0 or p > 7:
                    continue
                b[(p >> 1) * COLS + c] |= (VD if p & 1 else VU)[x]

    def _fw_frame(self, b) -> None:
        for R in self._anim.rockets:
            if R["up"]:
                for p in (R["p"], R["p"] + 1):
                    if 0 <= p <= 7:
                        _set(b, p >> 1, R["c"], L if p & 1 else I)
                continue
            rb, cb, k = R["p"] >> 1, R["c"], R["k"]
            if k == 0:
                _set(b, rb, cb, H | J | K | M | I | L | G1 | G2)
            elif k == 1:
                _set(b, rb, cb, DPB)
                _set(b, rb, cb - 1, G1 | G2)
                _set(b, rb, cb + 1, G1 | G2)
                _set(b, rb - 1, cb, I | L)
                _set(b, rb + 1, cb, I | L)
                _set(b, rb - 1, cb - 1, H | M)
                _set(b, rb - 1, cb + 1, J | K)
                _set(b, rb + 1, cb - 1, J | K)
                _set(b, rb + 1, cb + 1, H | M)
            elif k == 2:
                for s in (-1, 1):
                    _set(b, rb, cb + 2 * s, G1 | G2)
                    _set(b, rb - 1, cb + s, H if s < 0 else J)
                    _set(b, rb + 1, cb + s, K if s < 0 else M)
                    _set(b, rb - 1, cb + 2 * s, H if s < 0 else J)
                    _set(b, rb + 1, cb + 2 * s, K if s < 0 else M)
            else:
                fall = k - 2
                for dc in (-2, -1, 1, 2):
                    _set(b, rb - 1 + fall + (dc & 1), cb + dc, DPB)

    def _pac_frame(self, b) -> None:
        P = self._anim.pac
        row = 1

        def put(c, m):
            if 0 <= c < COLS:
                b[row * COLS + c] |= m

        for c in range(COLS):
            b[c] |= D1 | D2
            b[2 * COLS + c] |= A
        open_ = P["t"] % 2 == 0
        if P["phase"] == "rechts":
            for c in range(max(0, P["x"] + 1), COLS):
                put(c, POWER if c == 22 else DPB)
            put(P["x"], PAC_O if open_ else PAC_C)
            put(P["x"] - 4, GHOST)
        elif P["phase"] == "links":
            put(P["x"], mirror(PAC_O) if open_ else mirror(PAC_C))
            put(P["g"], GHOST_SCARED if P["t"] % 4 < 2 else GHOST)
        else:
            put_line(b, row, "200", max(0, P["x"] - 1))

    def _pong_frame(self, b) -> None:
        P = self._anim.pong
        for c, x, p in ((0, 0, P["lp"]), (COLS - 1, 2, P["rp"])):
            for h in range(p - 1, p + 2):
                if 0 <= h <= 7:
                    b[(h >> 1) * COLS + c] |= (VD if h & 1 else VU)[x]
        for r in range(ROWS):
            b[r * COLS + 11] |= B
        if 0 <= P["bx"] < COLS:
            b[(P["by"] >> 1) * COLS + P["bx"]] |= (
                (G1 | G2 | E | C | D1 | D2) if P["by"] & 1 else (A | F | B | G1 | G2))

    def _matrix_frame(self, b) -> None:
        for c, s in enumerate(self._anim.matrix):
            hd = math.floor(s["h"])
            for r in range(max(0, hd - s["len"] + 1), min(ROWS - 1, hd) + 1):
                b[r * COLS + c] = ASCII_16SEG[s["ch"][r]]

    def _build(self, name: str, t: float) -> list:
        b = new_buffer()
        if name in _STATELESS:
            _STATELESS[name](b, t)
        else:
            {"regen": self._regen_frame, "feuerwerk": self._fw_frame, "pacman": self._pac_frame,
             "pong": self._pong_frame, "matrix": self._matrix_frame}[name](b)
        return b

    # ---------- Zeitsteuerung ----------

    def _current(self, t: float) -> str:
        return ANIMS[(math.floor(t / SWITCH_S) + self._manual) % len(ANIMS)]

    def _update(self, t: float):
        """Neues Bild fuer die Zeit t oder None, wenn sich nichts geaendert hat."""
        name = self._current(t)
        st = math.floor(t / ANIM_IV[name])
        if name == self._last_name and st == self._last_step:
            return None
        n = min(MAX_STEPS, st - self._last_step) if name == self._last_name else 1
        self._last_step, self._last_name = st, name
        for _ in range(n):
            self._advance(name)
        return self._build(name, t)

    def _timeout(self, t: float) -> float:
        """Bis zur naechsten Schrittgrenze oder zum naechsten 10-s-Wechsel."""
        name = self._current(t)
        step_end = (math.floor(t / ANIM_IV[name]) + 1) * ANIM_IV[name]
        switch_end = (math.floor(t / SWITCH_S) + 1) * SWITCH_S
        return max(0.001, min(step_end, switch_end) - t + 0.0005)

    def run(self, ctx) -> None:
        start = self._clock()
        self._manual = 0
        self._reset()
        while True:
            t = self._clock() - start
            buf = self._update(t)
            if buf is not None:
                ctx.display.show_cells(buf)
            if ctx.wait_button(timeout=self._timeout(t)) == BT6:
                self._manual += 1
