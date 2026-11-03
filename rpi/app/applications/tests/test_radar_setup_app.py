"""Tests fuer RADAR EINRICHTEN (Radar-Spec §5) mit nachgebildetem Radar, Tasten und Uhr."""
import json
import tempfile
import unittest
from pathlib import Path

from app.applications.radar_records import RadarRecords
from app.applications.radar_setup_app import RadarSetupApp
from app.applications.tests.test_radar_tuning import AT_2M, AT_2M5, EMPTY, SPOILED, WERK
from app.driver.uart.ld2410s import LD2410SError, RadarSettings
from app.ui.activity import Activity
from app.ui.app_host import AppContext, StopSignal, run_app
from app.ui.buttons import BT2, BT4, BT5, BT6, ExpanderError, QueueButtons


class Clock:
    def __init__(self):
        self.now = 0.0

    def __call__(self):
        return self.now


class FakeDisplay:
    def __init__(self):
        self.shown = []  # jede gezeigte Seite als Liste von Zeilen
        self.attempts = 0  # wie oft der erste Schritt eines Anlaufs kam

    def show_lines(self, lines, dots_own_cell=False):
        self.shown.append(list(lines))
        if list(lines)[:2] == ["RAUM VERLASSEN", "DANN BT5"]:
            self.attempts += 1

    def clear(self):
        self.shown.append([])

    @property
    def text(self):
        return "|".join(self.shown[-1]) if self.shown else ""

    @property
    def title(self):
        return self.shown[-1][0] if self.shown and self.shown[-1] else ""


class FakeButtons:
    """Drueckt BT5, sobald eine Seite BT5 verlangt; script: Textteil -> Taste (None = nie),
    oder eine Funktion, die einmal aufgerufen wird."""

    def __init__(self, clock, display, script=None, error_on=None):
        self.clock = clock
        self.display = display
        self.script = dict(script or {})
        self.error_on = error_on
        self._answered = None

    def start(self):
        pass

    def get(self, timeout):
        self.clock.now += timeout or 0
        text = self.display.text
        if self.error_on and self.error_on in text:
            raise ExpanderError("Expander 0x20 nicht lesbar")
        if self._answered == len(self.display.shown):
            return None
        for part, key in self.script.items():
            if part in text:
                self._answered = len(self.display.shown)
                return key() if callable(key) else key
        if "BT5" in text:
            self._answered = len(self.display.shown)
            return BT5
        return None


class FakeRadar:
    """Radar nach Titel der Anzeige: Messungen je Titel, Anwesenheit je Titel; je Anlauf ein
    eigener Wert, sonst gilt der letzte."""

    def __init__(self, clock, display, measurements=None, presence=None):
        self.clock = clock
        self.display = display
        self.settings = RadarSettings.from_dict(WERK.to_dict())
        self.measurements = {"MESSE LEER": [EMPTY], "MESSE AUF 2.0 M": [AT_2M],
                             "MESSE AUF 2.7 M": [AT_2M5]}
        self.measurements.update(measurements or {})
        self.presence = {"TEST LEER": [False], "TEST AUF 2.0 M": [True], "TEST AUF 2.7 M": [False]}
        self.presence.update(presence or {})
        self.mode = "minimal"
        self.writes = []
        self.fail_write = None  # Nummer des Schreibvorgangs, der scheitert
        self.read_back = None  # was read_settings statt der Werte liefert

    def _pick(self, table):
        options = table.get(self.display.title)
        if options is None:
            raise AssertionError("unerwarteter Titel %r" % self.display.title)
        return options[min(self.display.attempts, len(options)) - 1]

    def minimal_mode(self):
        self.mode = "minimal"

    def read_settings(self):
        return self.read_back if self.read_back is not None else self.settings

    def write_settings(self, settings):
        self.writes.append(settings)
        if self.fail_write == len(self.writes):
            raise LD2410SError("Befehl 0x0070: keine Antwort")
        self.settings = settings

    def _run(self, seconds, wait):
        start = self.clock.now
        while self.clock.now - start < seconds:
            wait(0.1)

    def measure(self, seconds, wait, settle_s=2.0):
        frames = self._pick(self.measurements)
        self.mode = "standard"
        try:
            self._run(seconds, wait)
        finally:
            self.mode = "minimal"
        return frames

    def watch(self, seconds, wait):
        present = self._pick(self.presence)
        start = self.clock.now
        self._run(seconds, wait)
        return [(t / 8.0, present) for t in range(1, int((self.clock.now - start) * 8) + 1)]


class FakeSwitch:
    def __init__(self, log):
        self.log = log

    def __enter__(self):
        self.log.append("enter")
        return "uart"

    def __exit__(self, *exc):
        self.log.append("leave")
        return False


class SetupTest(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.config = Path(self._tmp.name)
        self.clock = Clock()
        self.display = FakeDisplay()
        self.radar = FakeRadar(self.clock, self.display)
        self.switch_log = []
        self.script = {}
        self.error_on = None
        self.stop = StopSignal()
        self.wall_buttons = QueueButtons()
        self.wall_buttons.put(BT5)  # schliesst die Ergebnisseite nach dem Zurueckschalten

    def tearDown(self):
        self._tmp.cleanup()

    def run_setup(self):
        app = RadarSetupApp(
            switch_factory=lambda: FakeSwitch(self.switch_log),
            radar_factory=lambda uart: self.radar,
            buttons_factory=lambda: FakeButtons(self.clock, self.display, self.script,
                                                self.error_on),
            clock=self.clock)
        ctx = AppContext(self.display, self.wall_buttons, Activity(clock=self.clock), self.stop,
                         config_dir=self.config)
        return run_app(app, ctx)

    def report(self):
        reports = sorted((self.config / "radar").glob("einrichtung-*.json"))
        self.assertEqual(len(reports), 1)
        return json.loads(reports[0].read_text(encoding="utf-8"))

    def backup_status(self):
        return json.loads((self.config / "radar" / "sicherung.json").read_text())["status"]

    def all_text(self):
        return [line for page in self.display.shown for line in page]

    def test_full_run_writes_tuning_and_final_delay(self):
        self.assertEqual(self.run_setup(), "back")
        final = self.radar.writes[-1]
        self.assertEqual(final.general["farthest"], 3)
        self.assertEqual(final.general["delay_s"], 30)
        self.assertEqual(final.general["speed"], 5)
        self.assertEqual(final.trigger[3], 34)
        self.assertEqual(final.hold[3], 32)
        self.assertEqual(self.radar.writes[0].general["delay_s"], 10)  # waehrend der Tests
        report = self.report()
        self.assertEqual(report["ergebnis"], "fertig")
        self.assertEqual(report["zielwert_m"], 2.0)
        self.assertEqual(report["fernstes_tor"], 3)
        self.assertEqual(report["alte_werte"], WERK.to_dict())
        self.assertTrue(report["tests"]["dahinter"])
        self.assertEqual(self.backup_status(), "fertig")
        self.assertEqual(RadarRecords(self.config).last_target_m(), 2.0)
        self.assertEqual(self.switch_log, ["enter", "leave"])
        self.assertIn(["FERTIG", "BIS ETWA 2.0 M", "", "BT4 ZURUECK"], self.display.shown)

    def test_bt6_cycles_target_and_skips_behind(self):
        self.script = {"ZIELWERT 2.0 M": BT6, "ZIELWERT 2.5 M": BT6, "ZIELWERT 3.0 M": BT5,
                       "STELL DICH AUF 3.7 M": BT6}
        self.radar.measurements["MESSE AUF 3.0 M"] = [AT_2M]
        self.radar.presence["TEST AUF 3.0 M"] = [True]
        self.assertEqual(self.run_setup(), "back")
        report = self.report()
        self.assertEqual(report["zielwert_m"], 3.0)
        self.assertIsNone(report["anlaeufe"][-1]["messung"]["dahinter_median"])
        self.assertIsNone(report["tests"]["dahinter"])
        self.assertEqual(self.radar.writes[-1].general["farthest"], 4)
        self.assertNotIn("MESSE AUF 3.7 M", [p[0] for p in self.display.shown if p])

    def test_nochmal_then_success_counts_attempts(self):
        self.radar.measurements["MESSE LEER"] = [SPOILED, EMPTY]
        self.assertEqual(self.run_setup(), "back")
        report = self.report()
        self.assertEqual(report["ergebnis"], "fertig")
        self.assertEqual([a["ergebnis"] for a in report["anlaeufe"]], ["nochmal", "fertig"])
        self.assertIn("NOCHMAL", [p[0] for p in self.display.shown if p])

    def test_empty_test_fails_three_times_restores_backup(self):
        self.radar.presence["TEST LEER"] = [True]
        self.assertEqual(self.run_setup(), "back")
        self.assertEqual(self.radar.writes[-1], WERK)
        report = self.report()
        self.assertEqual(report["ergebnis"], "fehler")
        self.assertEqual([a["abstand_db"] for a in report["anlaeufe"]], [1.5, 2.5, 3.5])
        self.assertEqual(self.backup_status(), "zurueck")
        self.assertIn("FEHLER - ALTE WERTE", self.all_text())

    def test_target_not_detected_retries(self):
        self.radar.presence["TEST AUF 2.0 M"] = [False, True]
        self.assertEqual(self.run_setup(), "back")
        self.assertEqual([a["ergebnis"] for a in self.report()["anlaeufe"]],
                         ["ziel_nicht_erkannt", "fertig"])

    def test_behind_detected_is_only_a_hint(self):
        self.radar.presence["TEST AUF 2.7 M"] = [True]
        self.assertEqual(self.run_setup(), "back")
        self.assertEqual(self.report()["ergebnis"], "fertig")
        self.assertIs(self.report()["tests"]["dahinter"], False)
        self.assertIn("HINWEIS GRENZE UNSCHARF", self.all_text())

    def test_bt4_before_write_writes_nothing(self):
        self.script = {"STELL DICH AUF 2.0 M": BT4}
        self.assertEqual(self.run_setup(), "back")
        self.assertEqual(self.radar.writes, [])
        self.assertEqual(self.report()["ergebnis"], "abbruch")
        self.assertEqual(self.backup_status(), "unveraendert")
        self.assertEqual(self.switch_log, ["enter", "leave"])

    def test_bt4_during_measurement_restores_and_minimal_mode(self):
        self.script = {"TEST LEER|BITTE WARTEN": BT4}
        self.assertEqual(self.run_setup(), "back")
        self.assertEqual(self.radar.writes[-1], WERK)
        self.assertEqual(self.radar.mode, "minimal")
        self.assertEqual(self.backup_status(), "zurueck")

    def test_bt4_during_standard_mode_measurement(self):
        self.script = {"MESSE LEER|BITTE WARTEN": BT4}
        self.assertEqual(self.run_setup(), "back")
        self.assertEqual(self.radar.mode, "minimal")
        self.assertEqual(self.radar.writes, [])

    def test_bt2_aborts_like_bt4(self):
        pressed = []

        def bt2():
            pressed.append(self.clock.now)
            return BT2

        self.script = {"TEST AUF 2.0 M|STELL DICH HIN": bt2}
        self.assertEqual(self.run_setup(), "back")
        self.assertEqual(self.radar.writes[-1], WERK)
        self.assertLess(self.clock.now - pressed[0], 1.0)  # sofort, nicht erst nach 5 min

    def test_no_key_for_5_minutes_aborts(self):
        self.script = {"RAUM VERLASSEN|DANN BT5": None}
        self.assertEqual(self.run_setup(), "back")
        self.assertGreaterEqual(self.clock.now, 300)
        self.assertLess(self.clock.now, 320)
        self.assertEqual(self.report()["ergebnis"], "abbruch")

    def test_pending_backup_is_restored_first(self):
        older = RadarSettings.from_dict(WERK.to_dict())
        older.trigger[5] = 40
        RadarRecords(self.config).save_backup(older)
        self.script = {"ZIELWERT": BT4}
        self.assertEqual(self.run_setup(), "back")
        self.assertEqual(self.radar.writes, [older])
        self.assertIn(["RADAR EINRICHTEN", "STELLE ALTE WERTE HER"], self.display.shown)

    def test_radar_error_after_write_tries_restore(self):
        self.radar.fail_write = 2  # der zweite Schreibvorgang (die Endwerte) scheitert
        self.assertEqual(self.run_setup(), "back")
        self.assertEqual(self.radar.writes[-1], WERK)
        self.assertIn("FEHLER RADAR", self.all_text())
        self.assertEqual(self.report()["ergebnis"], "fehler_radar")

    def test_read_back_mismatch_restores(self):
        wrong = RadarSettings.from_dict(WERK.to_dict())
        wrong.general["farthest"] = 9

        def mismatch(settings, original=self.radar.write_settings):
            original(settings)
            self.radar.read_back = None if settings == WERK else wrong

        self.radar.write_settings = mismatch
        self.assertEqual(self.run_setup(), "back")
        self.assertIn("FEHLER - ALTE WERTE", self.all_text())
        self.assertEqual(len(self.radar.writes), 3)  # schreiben, nochmal, Sicherung
        self.assertEqual(self.radar.writes[-1], WERK)

    def test_too_few_frames_is_radar_error(self):
        self.radar.measurements["MESSE LEER"] = [EMPTY[:5]]
        self.assertEqual(self.run_setup(), "back")
        self.assertIn("FEHLER RADAR", self.all_text())
        self.assertEqual(self.radar.writes, [])

    def test_stop_signal_restores_and_stops(self):
        self.script = {"TEST AUF 2.0 M|STELL DICH HIN": lambda: self.stop.set("shutdown")}
        self.assertEqual(self.run_setup(), "shutdown")
        self.assertEqual(self.radar.writes[-1], WERK)
        self.assertEqual(self.switch_log, ["enter", "leave"])

    def test_expander_error_restores_and_shows_fehler_tasten(self):
        self.error_on = "TEST LEER|BITTE WARTEN"
        self.assertEqual(self.run_setup(), "back")
        self.assertEqual(self.radar.writes[-1], WERK)
        self.assertIn("FEHLER TASTEN", self.all_text())

    def test_all_lines_fit_24_chars(self):
        self.script = {"ZIELWERT 2.0 M": BT6, "ZIELWERT 2.5 M": BT6, "ZIELWERT 3.0 M": BT6,
                       "ZIELWERT 3.5 M": BT5}
        self.radar.measurements["MESSE AUF 3.5 M"] = [AT_2M]
        self.radar.measurements["MESSE AUF 4.2 M"] = [AT_2M5]
        self.radar.presence["TEST AUF 3.5 M"] = [True]
        self.radar.presence["TEST AUF 4.2 M"] = [True]
        self.run_setup()
        self.assertIn("HINWEIS GRENZE UNSCHARF", self.all_text())
        for line in self.all_text():
            self.assertLessEqual(len(line.replace(".", "")), 24, line)


if __name__ == "__main__":
    unittest.main()
