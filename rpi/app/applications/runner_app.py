# applications/runner_app.py
# Spiel "Laeufer" auf der Wand: Kakteen ueberspringen, unter Voegeln ducken (Vorlage: Werkstatt).
# Alles aus festen Segmentmustern. Der Rekord steht in config/spiel_rekord.txt.
import logging
import os
import random
import tempfile
import time
from pathlib import Path

from app.driver.display.segments import (
    A, B, COLS, D1, D2, F, G1, G2, H, I, J, K, L, M, center, new_buffer, put_line)
from app.ui.buttons import BT5, BT6

log = logging.getLogger(__name__)

RECORD_FILE = "spiel_rekord.txt"
RUN_TOP = (A | I | G2 | K | L, A | I | G1 | M | L)
RUN_LEGS = (I | K | M, I | L)
DUCK = A | I | G1 | G2 | K | M
CACTUS = (I | L | G1 | F | G2 | B, I | L | G2 | B)
BIRD = (H | J | G1 | G2, K | M | G1 | G2)
RC = 3  # Spalte des Laeufers
START_INTERVAL = 170  # ms je Schritt am Anfang
MIN_INTERVAL = 85
MAX_WAIT = 0.05  # laengstes Warten am Stueck, damit Tasten sofort wirken
MIN_WAIT = 0.005


class RunnerApp:
    name = "SPIEL"

    def __init__(self, clock=time.monotonic, rng=None, config_dir=None) -> None:
        self._clock = clock
        self._rng = rng if rng is not None else random.Random()
        self._config_dir = config_dir
        self._best = 0
        self._g = {}

    def run(self, ctx) -> None:
        if self._config_dir is None:
            self._config_dir = ctx.config_dir
        self._best = self._load_best()
        self._init_ready()
        shown = None
        last = self._clock()
        while True:
            frame = self._frame()
            if frame != shown:
                ctx.display.show_cells(frame)
                shown = frame
            g = self._g
            wait = MAX_WAIT
            if g["state"] == "lauf":
                wait = min(MAX_WAIT, max(MIN_WAIT, (g["interval"] - g["acc"]) / 1000))
            button = ctx.wait_button(timeout=wait)
            now = self._clock()
            if g["state"] == "lauf":
                g["acc"] += max(0.0, now - last) * 1000
                while g["acc"] >= g["interval"] and g["state"] == "lauf":
                    g["acc"] -= g["interval"]
                    self._step()
            last = now
            if button is not None:
                self._key(button)

    # --- Rekord ---

    def _record_path(self) -> Path:
        return Path(self._config_dir) / RECORD_FILE

    def _load_best(self) -> int:
        try:
            value = int(self._record_path().read_text(encoding="utf-8").strip())
        except (OSError, ValueError):
            return 0
        return max(0, value)

    def _save_best(self) -> None:
        try:
            directory = Path(self._config_dir)
            directory.mkdir(parents=True, exist_ok=True)
            fd, tmp = tempfile.mkstemp(dir=directory, prefix=RECORD_FILE + ".", suffix=".tmp")
            try:
                with os.fdopen(fd, "w", encoding="utf-8") as handle:
                    handle.write(f"{self._best}\n")
                os.replace(tmp, directory / RECORD_FILE)
            except BaseException:
                try:
                    os.unlink(tmp)
                except OSError:
                    pass
                raise
        except OSError as error:
            log.warning("Rekord nicht gespeichert: %s", error)

    # --- Spiel ---

    def _init_ready(self) -> None:
        self._g = {"state": "bereit", "acc": 0, "interval": START_INTERVAL, "obs": [],
                   "jump": 0, "duck": 0, "score": 0, "ground": 0, "anim": 0, "next": 6}

    def _reset(self) -> None:
        self._g = {"state": "lauf", "acc": 0, "interval": START_INTERVAL, "obs": [],
                   "jump": 0, "duck": 0, "score": 0, "ground": 0, "anim": 0, "next": 6}

    def _key(self, button) -> None:
        g = self._g
        if button == BT5:
            if g["state"] != "lauf":
                self._reset()
            elif g["jump"] == 0 and g["duck"] == 0:
                g["jump"] = 5
        elif button == BT6:
            if g["state"] == "lauf" and g["jump"] == 0:
                g["duck"] = 3

    def _step(self) -> None:
        g = self._g
        g["ground"] += 1
        g["anim"] ^= 1
        if g["jump"] > 0:
            g["jump"] -= 1
        if g["duck"] > 0:
            g["duck"] -= 1
        for o in g["obs"]:
            o["x"] -= 1
            if not o.get("passed") and o["x"] < RC:
                o["passed"] = True
                g["score"] += 1
        g["obs"] = [o for o in g["obs"] if o["x"] >= 0]
        g["next"] -= 1
        if g["next"] <= 0:
            kind = "vogel" if (g["score"] > 2 and self._rng.random() < 0.3) else "kaktus"
            v = 0 if self._rng.random() < 0.5 else 1
            g["obs"].append({"x": COLS - 1, "kind": kind, "v": v})
            g["next"] = 5 + int(self._rng.random() * max(3, 8 - g["score"] / 4))
        g["interval"] = max(MIN_INTERVAL, START_INTERVAL - g["score"] * 4)
        rows = (1, 2) if g["jump"] > 0 else (3,) if g["duck"] > 0 else (2, 3)
        for o in g["obs"]:
            if o["x"] == RC and (3 if o["kind"] == "kaktus" else 2) in rows:
                g["state"] = "aus"
                if g["score"] > self._best:
                    self._best = g["score"]
                    self._save_best()

    def _frame(self) -> list:
        g = self._g
        b = new_buffer()
        put_line(b, 0, "PUNKTE %03d" % g["score"])
        put_line(b, 0, "REKORD %03d" % self._best, COLS - 10)
        if g["state"] == "bereit":
            put_line(b, 1, "BT5 SPRINGEN BT6 DUCKEN")
        if g["state"] == "aus":
            put_line(b, 1, center("VORBEI - BT5 NOCHMAL"))
        for c in range(COLS):
            b[3 * COLS + c] = D1 if (c + g["ground"]) % 9 == 0 else (D1 | D2)
        for o in g["obs"]:
            if o["kind"] == "kaktus":
                b[3 * COLS + o["x"]] |= CACTUS[o["v"]]
            else:
                b[2 * COLS + o["x"]] = BIRD[g["anim"]]
        an = g["anim"] if g["state"] == "lauf" else 0
        if g["duck"] > 0:
            b[3 * COLS + RC] |= DUCK
        elif g["jump"] > 0:
            b[1 * COLS + RC] = RUN_TOP[0]
            b[2 * COLS + RC] = RUN_LEGS[0]
        else:
            b[2 * COLS + RC] = RUN_TOP[an]
            b[3 * COLS + RC] |= RUN_LEGS[an]
        return b
