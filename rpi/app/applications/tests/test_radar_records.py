"""Tests fuer Sicherung, Zielwert und Bericht der Radar-Einrichtung (Spec §7)."""
import datetime
import json
import tempfile
import unittest
from pathlib import Path

from app.applications.radar_records import RadarRecords
from app.driver.uart.ld2410s import RadarSettings

SETTINGS = RadarSettings({"farthest": 2, "nearest": 0, "delay_s": 10, "status_hz10": 80,
                          "distance_hz10": 5, "speed": 10},
                         [48, 42, 36, 34] + [31] * 12, [45, 42, 33, 32] + [28] * 12)


class RecordsTest(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.config = Path(self._tmp.name)
        self.records = RadarRecords(self.config,
                                    now=lambda: datetime.datetime(2026, 11, 3, 14, 5, 9))

    def tearDown(self):
        self._tmp.cleanup()

    def test_no_backup_means_none(self):
        self.assertIsNone(self.records.pending_backup())

    def test_backup_roundtrip_and_close(self):
        self.records.save_backup(SETTINGS)
        self.assertEqual(self.records.pending_backup(), SETTINGS)
        self.records.close_backup("fertig")
        self.assertIsNone(self.records.pending_backup())
        saved = json.loads((self.config / "radar" / "sicherung.json").read_text())
        self.assertEqual(saved["status"], "fertig")
        self.assertEqual(saved["werte"], SETTINGS.to_dict())

    def test_target_default_and_saved(self):
        self.assertEqual(self.records.last_target_m(), 2.0)
        self.records.save_target_m(3.5)
        self.assertEqual(RadarRecords(self.config).last_target_m(), 3.5)

    def test_report_name_from_clock(self):
        path = self.records.write_report({"ergebnis": "fertig"})
        self.assertEqual(path.name, "einrichtung-20261103-140509.json")
        self.assertEqual(json.loads(path.read_text()), {"ergebnis": "fertig"})
        self.assertEqual(sorted(p.name for p in path.parent.iterdir()), [path.name])

    def test_corrupt_files_count_as_absent(self):
        folder = self.config / "radar"
        folder.mkdir()
        for text in ("{halb", json.dumps({"status": "laufend", "werte": {"general": {}}}),
                     json.dumps(["laufend"])):
            (folder / "sicherung.json").write_text(text)
            self.assertIsNone(self.records.pending_backup())
        for text in ("7.3", "zwei", ""):
            (folder / "zielwert.txt").write_text(text)
            self.assertEqual(self.records.last_target_m(), 2.0)


if __name__ == "__main__":
    unittest.main()
