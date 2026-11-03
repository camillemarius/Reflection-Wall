"""Tests fuer die Berechnung der Radar-Einrichtung mit den Messungen vom 2026-11-03 (Spec §6)."""
import itertools
import json
import pathlib
import unittest

from app.applications.radar_tuning import Tuning, apply, compute, figures, figures_summary
from app.driver.uart.ld2410s import RadarSettings

DATA = pathlib.Path(__file__).parent / "radar_messungen"
WERK = RadarSettings({"farthest": 2, "nearest": 0, "delay_s": 10, "status_hz10": 80,
                      "distance_hz10": 5, "speed": 10},
                     [48, 42, 36, 34, 32] + [31] * 11, [45, 42, 33, 32] + [28] * 12)


def load(name):
    # Die Aufnahmen enthalten noch die Meldungen direkt nach dem Umschalten; der Treiber
    # verwirft die ersten 2 s, das sind hier die ersten 3 Meldungen.
    return json.loads((DATA / f"{name}.json").read_text())[3:]


EMPTY, SPOILED = load("leer"), load("leer_verdorben")
AT_1M, AT_2M, AT_2M5 = load("person_1m0"), load("person_2m0"), load("person_2m5")


class ComputeTest(unittest.TestCase):
    def test_target_2m_behind_2m5(self):
        tuning = compute(figures(EMPTY, AT_2M, AT_2M5))
        self.assertEqual(tuning.farthest, 3)
        self.assertEqual(tuning.trigger[3], 34)
        self.assertEqual(tuning.hold[3], 32)
        self.assertGreaterEqual(tuning.trigger[0], 48)
        self.assertGreaterEqual(tuning.trigger[1], 42)
        self.assertGreaterEqual(tuning.hold[0], 45)
        self.assertGreaterEqual(tuning.hold[1], 42)
        self.assertEqual(len(tuning.trigger), 4)
        self.assertEqual(len(tuning.hold), 4)

    def test_target_2m_without_behind(self):
        self.assertEqual(compute(figures(EMPTY, AT_2M)).farthest, 4)

    def test_target_1m_with_2m_as_behind(self):
        tuning = compute(figures(EMPTY, AT_1M, AT_2M))
        self.assertEqual(tuning.farthest, 2)
        self.assertEqual(tuning.trigger[2], 35)

    def test_target_2m5_without_behind_falls_back_to_reachable_gate(self):
        # Tor 4: Schwelle 34 laege ueber dem Median 33,7, also nicht sichtbar; bleibt Tor 3
        tuning = compute(figures(EMPTY, AT_2M5))
        self.assertEqual(tuning.farthest, 3)
        self.assertEqual(tuning.trigger[3], 33)

    def test_spoiled_empty_gives_none(self):
        self.assertIsNone(compute(figures(SPOILED, AT_2M, AT_2M5)))

    def test_larger_margin_can_give_none(self):
        self.assertIsNone(compute(figures(EMPTY, AT_2M, AT_2M5), margin_db=5))

    def test_target_not_apart_from_behind_gives_none(self):
        self.assertIsNone(compute(figures(EMPTY, AT_2M, AT_2M)))

    def test_hold_never_above_trigger(self):
        for target, behind in itertools.product([AT_1M, AT_2M, AT_2M5],
                                                [None, AT_1M, AT_2M, AT_2M5]):
            tuning = compute(figures(EMPTY, target, behind))
            if tuning is None:
                continue
            for t, h in zip(tuning.trigger, tuning.hold):
                self.assertLessEqual(h, t)

    def test_zero_frames_are_ignored(self):
        with_zeros = EMPTY + [[0] * 16] * 5
        self.assertEqual(figures(with_zeros, AT_2M).noise_p95, figures(EMPTY, AT_2M).noise_p95)

    def test_summary_is_rounded_and_json(self):
        summary = figures_summary(figures(EMPTY, AT_2M, AT_2M5))
        self.assertEqual(summary["ziel_median"][3], 35.0)
        self.assertIsNone(figures_summary(figures(EMPTY, AT_2M))["dahinter_median"])
        json.dumps(summary)


class ApplyTest(unittest.TestCase):
    def test_apply_keeps_far_gates_and_sets_general(self):
        tuning = Tuning(farthest=3, trigger=[48, 42, 35, 34], hold=[45, 42, 34, 32])
        new = apply(WERK, tuning, delay_s=10)
        self.assertEqual(new.general, {"farthest": 3, "nearest": 0, "delay_s": 10,
                                       "status_hz10": 80, "distance_hz10": 40, "speed": 5})
        self.assertEqual(new.trigger, [48, 42, 35, 34] + WERK.trigger[4:])
        self.assertEqual(new.hold, [45, 42, 34, 32] + WERK.hold[4:])
        self.assertEqual(WERK.general["farthest"], 2)  # die alten Werte bleiben unberuehrt


if __name__ == "__main__":
    unittest.main()
