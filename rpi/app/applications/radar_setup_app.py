# applications/radar_setup_app.py
# RADAR EINRICHTEN (Radar-Spec §5): leer messen, am Zielwert und dahinter, Schwellen rechnen,
# schreiben und pruefen. Die Tasten liest der Pi im Radar-Modus selbst am Expander, wie bei RADAR.
import logging
import time

from app.applications.radar_records import TARGETS_M, RadarRecords
from app.applications.radar_tuning import M_N, apply, compute, figures, figures_summary
from app.driver.uart.ld2410s import LD2410S, LD2410SError
from app.ui.app_host import StopApp
from app.ui.buttons import BT2, BT4, BT5, BT6, ExpanderButtons, ExpanderError

log = logging.getLogger(__name__)

# Zeiten in Sekunden (Spec §11)
LEAVE_S = 15
POSITION_S = 10
EMPTY_S = 30
TARGET_S = 20
BEHIND_S = 20
RELEASE_WAIT_S = 20
TEST_EMPTY_S = 30
TEST_TARGET_S = 15
TEST_END_S = 2  # am Ziel bestanden, wenn in den letzten 2 s nur "jemand" kommt
TEST_BEHIND_S = 20
NOCHMAL_S = 3
WAIT_KEY_S = 5 * 60
TOTAL_S = 50 * 60  # unter den 60 min, nach denen der ESP den Radar-Modus selbst beendet
POLL_S = 0.1

ATTEMPTS = 3
MIN_FRAMES = 10
BEHIND_M = 0.7
TEST_DELAY_S = 10
FINAL_DELAY_S = 30  # R5
MARGIN_STEP_DB = 1.0  # nach einem verpatzten Leer-Test (Spec §6.9)

BACK = "BT4 ZURUECK"


class _Abort(Exception):
    """BT4, BT2, keine Taste oder Zeit um: alte Werte zurueck, ohne Ergebnisseite."""


class _Stopped(Exception):
    pass


class _Retry(Exception):
    def __init__(self, result: str, text: str, margin_up: bool = False) -> None:
        super().__init__(result)
        self.result = result
        self.text = text
        self.margin_up = margin_up


class _Mismatch(Exception):
    pass


def _m(metres: float) -> str:
    return "%.1f M" % metres


class RadarSetupApp:
    name = "RADAR EINRICHTEN"

    def __init__(self, switch_factory, radar_factory=LD2410S, buttons_factory=ExpanderButtons,
                 records_factory=RadarRecords, clock=time.monotonic) -> None:
        self._switch_factory = switch_factory
        self._radar_factory = radar_factory
        self._buttons_factory = buttons_factory
        self._records_factory = records_factory
        self._clock = clock

    def run(self, ctx) -> None:
        with ctx.activity.busy():
            with self._switch_factory() as uart:
                session = _Session(self, ctx, uart)
                lines = session.run()
        # Zurueckgeschaltet: ab hier kommen die Tasten wieder ueber den ESP.
        if session.stopped:
            raise StopApp(ctx.stop_event.reason or "shutdown")
        if lines is None:
            raise StopApp("back")
        ctx.display.show_lines(lines)
        ctx.wait_button()


class _Session:
    def __init__(self, app: RadarSetupApp, ctx, uart) -> None:
        self._ctx = ctx
        self._clock = app._clock
        self._radar = app._radar_factory(uart)
        self._buttons = app._buttons_factory()
        self._records = app._records_factory(ctx.config_dir)
        self._started = self._clock()
        self._backup = None
        self._written = False
        self._clean = True  # False, solange eine alte Sicherung halb zurueckgeschrieben ist
        self._report = None
        self.stopped = False

    # --- Rahmen ---

    def run(self):
        """Ergebnisseite, oder None nach einem Abbruch."""
        try:
            self._buttons.start()
            return self._main()
        except _Abort as abort:
            log.info("Radar-Einrichtung abgebrochen: %s", abort)
            self._end("abbruch")
            return None
        except _Stopped:
            self.stopped = True
            self._end("gestoppt")
            return None
        except _Mismatch:
            log.error("Radar-Einrichtung: Radar behaelt die Werte nicht")
            restored = self._end("fehler_speichern")
            return ["FEHLER - ALTE WERTE" if restored else "FEHLER RADAR",
                    "RADAR SPEICHERT NICHT", BACK]
        except LD2410SError as error:
            log.error("Radar-Einrichtung: %s", error)
            restored = self._end("fehler_radar")
            return ["FEHLER RADAR", "ALTE WERTE ZURUECK" if restored else "WERTE UNKLAR", BACK]
        except ExpanderError as error:
            log.error("Radar-Einrichtung: Tasten nicht lesbar: %s", error)
            restored = self._end("fehler_tasten")
            return ["FEHLER TASTEN", "ALTE WERTE ZURUECK" if restored else "WERTE UNKLAR", BACK]
        except Exception:
            log.exception("Radar-Einrichtung: unerwarteter Fehler")
            self._end("fehler")
            raise  # run_app zeigt das Fehlerbild

    def _end(self, result: str) -> bool:
        """Sicherung zurueck, falls schon geschrieben; Bericht. True, wenn die alten Werte gelten."""
        restored = self._restore()
        self._finish(result)
        return restored

    def _restore(self) -> bool:
        try:
            self._radar.minimal_mode()  # RADAR erwartet den Kurzmodus, wie auch immer es endete
        except Exception as error:
            log.error("Radar: Kurzmodus nicht zurueck: %s", error)
        if self._backup is None:
            return self._clean
        try:
            if not self._written:
                self._records.close_backup("unveraendert")
                return True
            self._radar.write_settings(self._backup)
            ok = self._radar.read_settings() == self._backup
            if ok:
                self._written = False
                self._records.close_backup("zurueck")
            return ok
        except Exception as error:
            # die Sicherung bleibt "laufend": der naechste Start schreibt sie
            log.error("Radar-Sicherung nicht zurueckgeschrieben: %s", error)
            return False

    def _finish(self, result: str) -> None:
        if self._report is None:
            return
        self._report["ergebnis"] = result
        try:
            self._records.write_report(self._report)
        except OSError:
            log.exception("Radar-Bericht nicht geschrieben")

    # --- Warten, Tasten, Anzeige ---

    def _show(self, *lines: str) -> None:
        self._ctx.display.show_lines(list(lines))

    def _wait(self, seconds: float) -> None:
        """Wartet hoechstens seconds auf eine Taste; BT4/BT2, Stopp und Zeit um werfen."""
        if self._ctx.stop_event.is_set():
            raise _Stopped()
        if self._clock() - self._started >= TOTAL_S:
            raise _Abort("Zeit um")
        button = self._buttons.get(seconds)
        if button in (BT2, BT4):
            raise _Abort("BT%d" % button)
        return button

    def _pause(self, seconds: float) -> None:
        end = self._clock() + seconds
        while self._clock() < end:
            self._wait(min(POLL_S, end - self._clock()))

    def _key(self, lines, allow=(BT5,)) -> int:
        self._show(*lines)
        start = self._clock()
        while True:
            button = self._wait(POLL_S)
            if button in allow:
                self._ctx.activity.touch()
                return button
            if self._clock() - start >= WAIT_KEY_S:
                raise _Abort("keine Taste")

    def _countdown(self, title: str, seconds: int) -> None:
        for remaining in range(seconds, 0, -1):
            self._show(title, "IN %d S" % remaining)
            self._pause(1.0)

    # --- Ablauf ---

    def _main(self):
        self._show("RADAR EINRICHTEN", "LESE ALTE WERTE")
        self._radar.minimal_mode()
        pending = self._records.pending_backup()
        if pending is not None:
            log.info("Radar-Einrichtung: unterbrochene Einrichtung, alte Werte zurueck")
            self._show("RADAR EINRICHTEN", "STELLE ALTE WERTE HER")
            self._clean = False
            self._radar.write_settings(pending)
            if self._radar.read_settings() != pending:
                raise _Mismatch()
            self._clean = True
            self._records.close_backup("zurueck")
        self._backup = self._radar.read_settings()
        self._records.save_backup(self._backup)
        target = self._choose_target(self._records.last_target_m())
        self._records.save_target_m(target)
        self._report = {"zielwert_m": target, "alte_werte": self._backup.to_dict(),
                        "anlaeufe": [], "fernstes_tor": None, "neue_werte": None,
                        "tests": None}
        margin = M_N
        for attempt in range(1, ATTEMPTS + 1):
            info = {"abstand_db": margin}
            self._report["anlaeufe"].append(info)
            try:
                tuning, tests = self._attempt(target, margin, info)
            except _Retry as retry:
                info["ergebnis"] = retry.result
                if retry.margin_up:
                    margin += MARGIN_STEP_DB
                if attempt < ATTEMPTS:
                    self._show("NOCHMAL", retry.text, "ANLAUF %d VON %d" % (attempt + 1, ATTEMPTS))
                    self._pause(NOCHMAL_S)
                continue
            info["ergebnis"] = "fertig"
            final = apply(self._backup, tuning, FINAL_DELAY_S)
            self._show("SPEICHERE")
            self._write_checked(final)
            self._records.close_backup("fertig")
            self._written = False
            self._report.update(fernstes_tor=tuning.farthest, neue_werte=final.to_dict(),
                                tests=tests)
            self._finish("fertig")
            log.info("Radar eingerichtet: Zielwert %.1f m, fernstes Tor %d", target,
                     tuning.farthest)
            hint = "HINWEIS GRENZE UNSCHARF" if tests["dahinter"] is False else ""
            return ["FERTIG", "BIS ETWA " + _m(target), hint, BACK]
        log.warning("Radar-Einrichtung: %d Anlaeufe ohne Erfolg", ATTEMPTS)
        restored = self._end("fehler")
        return ["FEHLER - ALTE WERTE" if restored else "FEHLER RADAR",
                "%d ANLAEUFE OHNE ERFOLG" % ATTEMPTS, BACK]

    def _choose_target(self, default: float) -> float:
        index = TARGETS_M.index(default)
        while True:
            key = self._key(["ZIELWERT " + _m(TARGETS_M[index]), "BT6 WEITER", "BT5 OK"],
                            allow=(BT5, BT6))
            if key == BT5:
                return TARGETS_M[index]
            index = (index + 1) % len(TARGETS_M)

    def _measure(self, title: str, note: str, seconds: int) -> list:
        self._countdown(title, POSITION_S if title != "MESSE LEER" else LEAVE_S)
        self._show(title, note)
        frames = self._radar.measure(seconds, self._wait)
        if len(frames) < MIN_FRAMES:
            raise LD2410SError("%s: nur %d Meldungen" % (title, len(frames)))
        return frames

    def _attempt(self, target: float, margin: float, info: dict):
        behind_m = round(target + BEHIND_M, 1)
        here, there = _m(target), _m(behind_m)
        self._key(["RAUM VERLASSEN", "DANN BT5"])
        empty = self._measure("MESSE LEER", "BITTE WARTEN", EMPTY_S)
        self._key(["STELL DICH AUF " + here, "DANN BT5"])
        at_target = self._measure("MESSE AUF " + here, "RUHIG STEHEN", TARGET_S)
        behind = None
        if self._key(["STELL DICH AUF " + there, "BT5 OK", "BT6 UEBERSPRINGEN"],
                     allow=(BT5, BT6)) == BT5:
            behind = self._measure("MESSE AUF " + there, "RUHIG STEHEN", BEHIND_S)
        self._show("BERECHNE")
        fig = figures(empty, at_target, behind)
        info["messung"] = figures_summary(fig)
        tuning = compute(fig, margin)
        if tuning is None:
            raise _Retry("nochmal", "NICHT UNTERSCHEIDBAR")
        info["fernstes_tor"] = tuning.farthest
        self._show("SPEICHERE")
        self._write_checked(apply(self._backup, tuning, TEST_DELAY_S))

        self._key(["TEST LEER", "RAUM VERLASSEN", "DANN BT5"])
        self._countdown("TEST LEER", LEAVE_S)
        self._show("TEST LEER", "BITTE WARTEN")
        if not self._test_empty():
            raise _Retry("leer_erkannt", "LEER NICHT RUHIG", margin_up=True)
        self._key(["TEST AUF " + here, "STELL DICH HIN", "DANN BT5"])
        self._countdown("TEST AUF " + here, POSITION_S)
        self._show("TEST AUF " + here, "RUHIG STEHEN")
        seen = self._watch(TEST_TARGET_S)
        end = [present for t, present in seen if t >= TEST_TARGET_S - TEST_END_S]
        if not (end and all(end)):
            raise _Retry("ziel_nicht_erkannt", "AM ZIEL NICHT ERKANNT")
        behind_ok = None
        if behind is not None:
            self._key(["TEST AUF " + there, "STELL DICH HIN", "DANN BT5"])
            self._countdown("TEST AUF " + there, POSITION_S)
            self._show("TEST AUF " + there, "RUHIG STEHEN")
            # Wer BT5 drueckt, steht an der Wand: erst die Meldung vom Weggehen ablaufen lassen.
            # Gibt das Radar nicht frei, haelt es die Person dahinter fest.
            behind_ok = self._released() and not any(
                present for _, present in self._watch(TEST_BEHIND_S))
        return tuning, {"leer": True, "ziel": True, "dahinter": behind_ok}

    def _watch(self, seconds: float) -> list:
        seen = self._radar.watch(seconds, self._wait)
        if not seen:
            raise LD2410SError("keine Kurzmodus-Meldungen")
        return seen

    def _released(self) -> bool:
        """Wartet hoechstens RELEASE_WAIT_S, bis das Radar niemanden mehr meldet."""
        start = self._clock()
        while self._watch(1.0)[-1][1]:
            if self._clock() - start >= RELEASE_WAIT_S:
                return False
        return True

    def _test_empty(self) -> bool:
        """Erst die Freigabe abwarten (Nachlaufzeit), dann darf niemand gemeldet werden (R10)."""
        return self._released() and not any(
            present for _, present in self._watch(TEST_EMPTY_S))

    def _write_checked(self, settings) -> None:
        """Schreiben und zuruecklesen; stimmt es nicht, einmal neu (Spec §8)."""
        for _ in range(2):
            self._written = True  # auch ein halber Schreibvorgang wird zurueckgenommen
            self._radar.write_settings(settings)
            if self._radar.read_settings() == settings:
                return
            log.warning("Radar: zurueckgelesene Werte weichen ab")
        raise _Mismatch()
