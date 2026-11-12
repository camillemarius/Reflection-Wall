# applications/radar_tuning.py
# Radar-Einrichtung (Spec §6): aus den Energien leer, am Zielwert und dahinter das fernste Tor
# und die Schwellen je Tor. Reine Funktionen; Schwellen sind dB der Energien.
import math
import statistics
from dataclasses import dataclass
from typing import Optional

from app.driver.uart.ld2410s import RadarSettings

M_N = 1.5  # Abstand zum hoechsten Rauschwert
M_O = 1.0  # Abstand der Person am Ziel zur Person dahinter
HOLD_NOISE_DB = 1.0
HOLD_GAP_DB = 3
# Tor 0 und 1: nie empfindlicher als ab Werk (Stoerungen der Wand selbst, etwa die Luefter)
NEAR_TRIGGER_FLOOR = (48, 42)
NEAR_HOLD_FLOOR = (45, 42)
THRESHOLD_MAX = 100
# Am Ende geschrieben (Spec §6.7): naechstes Tor, Meldetakte in 0,1 Hz. Die Geschwindigkeit
# bleibt, wie gemessen wurde: mit "normal" statt "schnell" hielt das Radar am Geraet niemanden
# mehr, obwohl die Energie ueber der Halteschwelle lag (2026-11-03).
NEAREST = 0
STATUS_HZ10 = 80
DISTANCE_HZ10 = 40


@dataclass
class Figures:
    noise_max: list
    noise_p95: list
    target: list
    behind: Optional[list]


@dataclass
class Tuning:
    farthest: int
    trigger: list
    hold: list


def _db(frames) -> list:
    return [[10 * math.log10(max(e, 1)) for e in f] for f in frames if any(f)]


def _p95(values) -> float:
    ordered = sorted(values)
    return ordered[math.ceil(0.95 * len(ordered)) - 1]


def _medians(frames) -> list:
    return [statistics.median(column) for column in zip(*frames)]


def _up(x: float) -> int:
    return math.ceil(x - 1e-9)


def _half_up(x: float) -> int:
    return math.floor(x + 0.5)


def figures(empty, target, behind=None) -> Figures:
    """Energien je Meldung -> Kennzahlen je Tor in dB; leere Meldungen zaehlen nicht."""
    noise = _db(empty)
    return Figures(noise_max=[max(c) for c in zip(*noise)],
                   noise_p95=[_p95(c) for c in zip(*noise)],
                   target=_medians(_db(target)),
                   behind=_medians(_db(behind)) if behind is not None else None)


def compute(fig: Figures, margin_db: float = M_N) -> Optional[Tuning]:
    """Fernstes Tor und Schwellen; None, wenn Ziel und Rauschen oder dahinter nicht trennbar."""
    gates = range(len(fig.target))
    # Sichtbar: die ganzzahlige Schwelle ueber dem Rauschen erreicht die Person noch
    candidates = [g for g in gates
                  if _up(fig.noise_max[g] + margin_db) <= fig.target[g]
                  and (fig.behind is None or fig.target[g] >= fig.behind[g] + M_O)]
    for farthest in sorted(candidates, reverse=True):
        tuning = _thresholds(fig, farthest, margin_db)
        if tuning.trigger[farthest] <= fig.target[farthest]:
            return tuning
    return None


def _thresholds(fig: Figures, farthest: int, margin_db: float) -> Tuning:
    trigger, hold = [], []
    for g in range(farthest + 1):
        t = _up(fig.noise_max[g] + margin_db)
        if g == farthest and fig.behind is not None:
            t = max(t, _half_up((fig.target[g] + fig.behind[g]) / 2))
        if g < len(NEAR_TRIGGER_FLOOR):
            t = max(t, NEAR_TRIGGER_FLOOR[g])
        t = min(t, THRESHOLD_MAX)
        h = max(_up(fig.noise_p95[g] + HOLD_NOISE_DB), t - HOLD_GAP_DB)
        if g < len(NEAR_HOLD_FLOOR):
            h = max(h, NEAR_HOLD_FLOOR[g])
        trigger.append(t)
        hold.append(min(h, t))
    return Tuning(farthest, trigger, hold)


def apply(old: RadarSettings, tuning: Tuning, delay_s: int) -> RadarSettings:
    """Neue Einstellungen: Tore bis zum fernsten aus tuning, die uebrigen wie in old."""
    n = tuning.farthest + 1
    general = {"farthest": tuning.farthest, "nearest": NEAREST, "delay_s": delay_s,
               "status_hz10": STATUS_HZ10, "distance_hz10": DISTANCE_HZ10,
               "speed": old.general["speed"]}
    return RadarSettings(general, list(tuning.trigger) + list(old.trigger[n:]),
                         list(tuning.hold) + list(old.hold[n:]))


def figures_summary(fig: Figures) -> dict:
    """Fuer den Bericht: Kennzahlen je Tor auf 0,1 dB."""
    def r(values):
        return None if values is None else [round(v, 1) for v in values]
    return {"leer_max": r(fig.noise_max), "leer_p95": r(fig.noise_p95),
            "ziel_median": r(fig.target), "dahinter_median": r(fig.behind)}
