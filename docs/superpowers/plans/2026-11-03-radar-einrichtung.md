# RADAR EINRICHTEN – Bauplan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Die Anwendung `RADAR EINRICHTEN` misst leer, am Zielwert und dahinter, rechnet fernstes Tor und Schwellen aus, schreibt sie ins LD2410S, prüft sie und hält alles in Sicherung und Bericht fest.

**Architecture:** Vier neue Dateien mit je einer Aufgabe: Treiber (Bytes am Draht), Berechnung (reine Funktionen), Ablage (Sicherung, Zielwert, Bericht), Anwendung (Ablauf mit Tasten und Anzeige). `main.py` hängt die Anwendung im Wand-Modus mit derselben `RadarSwitch` und denselben `ExpanderButtons` ein wie RADAR; am PC bleibt der Platzhalter.

**Tech Stack:** Python 3.13, nur Standardbibliothek, `unittest`.

**Spec:** `docs/superpowers/specs/2026-10-22-radar-einrichtung-design.md`

## Global Constraints

- Kommentare und Docstrings deutsch, im Code ohne Umlaute (ae, oe, ue); Kopfzeile `# <ordner>/<datei>.py` + eine Zeile Zweck.
- Anzeige: höchstens 4 Zeilen zu 24 Zeichen; Dezimalzeichen ist der Punkt (`2.0 M`, er belegt keine eigene Stelle).
- Zielwerte 1.0 1.5 2.0 2.5 3.0 3.5 m; dahinter = Zielwert + 0.7 m.
- Rechenwerte: `M_N = 1.5 dB`, `M_O = 1.0 dB`, Halte-Abstand 3 dB, Halte-Rauschzuschlag 1 dB; Tor 0/1 mindestens Auslöse 48/42, Halte 45/42.
- Radarwerte am Ende: nächstes Tor 0, Nachlaufzeit 30 s (in den Tests 10 s), Ansprechen 5, Meldetakt Zustand 80, Entfernung 40 (in 0,1 Hz).
- Höchstens 3 Anläufe; 5 min ohne Taste in einem Warteschritt = Abbruch wie BT4.
- Commits: Dateien einzeln mit `git add <datei>`, deutsche Nachricht, keine `Co-Authored-By`-Zeile.
- Tests am PC: `cd rpi && python -m unittest discover -s app/applications -t .` und `python -m unittest discover -s app/driver -t .`; `app/tests/test_main.py` braucht `dotenv` und läuft nur auf dem Pi.

## Review Focus

1. **Abbruch mitten in einer Messung** (BT4 während der Treiber im Messmodus ist): das Radar muss danach im Kurzmodus sein und die Sicherung zurückhaben → Test in Task 4 `test_bt4_during_measurement_restores_and_minimal_mode`.
2. **Radar antwortet während des Schreibens nicht mehr**: kein Absturzbild, `FEHLER RADAR`, Versuch die Sicherung zurückzuschreiben → Task 4 `test_radar_error_after_write_tries_restore`.
3. **Zu wenige Meldungen** (Radar sendet im Messmodus kaum): nicht mit leeren Listen rechnen → Task 4 `test_too_few_frames_is_radar_error`.
4. **Kaputte oder fremde Dateien im Ordner `radar`** (halb geschriebene Sicherung nach Stromausfall): gilt als nicht vorhanden, nichts stürzt ab → Task 3 `test_corrupt_files_count_as_absent`.
5. **Stoppsignal** (Sitzung endet) während der Einrichtung: Sicherung zurück, dann `StopApp` mit dem Grund → Task 4 `test_stop_signal_restores_and_stops`.

---

### Task 1: Treiber LD2410S

**Files:**
- Create: `rpi/app/driver/uart/ld2410s.py`
- Test: `rpi/app/driver/tests/test_ld2410s.py`

**Interfaces:**
- Produces:
  - `GENERAL_IDS: dict[str, int]` = `{"farthest": 0x05, "nearest": 0x0A, "delay_s": 0x06, "status_hz10": 0x02, "distance_hz10": 0x0C, "speed": 0x0B}` (Reihenfolge fest)
  - `@dataclass RadarSettings(general: dict[str, int], trigger: list[int], hold: list[int])` mit `to_dict() -> dict` und `RadarSettings.from_dict(d) -> RadarSettings` (wirft `ValueError` bei falscher Form)
  - `class LD2410SError(RuntimeError)`
  - `command_frame(cmd: int, value: bytes = b"") -> bytes`
  - `parse_acks(data: bytes) -> dict[int, bytes]` (Schlüssel = Befehl | 0x0100, Wert = Status + Daten)
  - `parse_energies(data: bytes) -> list[list[int]]` (je Messmodus-Meldung 16 Werte)
  - `parse_states(data: bytes) -> list[bool]` (je Kurzmodus-Meldung: jemand da)
  - `class LD2410S(uart, clock=time.monotonic, sleep=time.sleep, ack_timeout_s=1.0)` mit
    `read_settings() -> RadarSettings`, `write_settings(s: RadarSettings) -> None`,
    `minimal_mode() -> None`,
    `measure(seconds: float, wait: Callable[[float], None], settle_s: float = 2.0) -> list[list[int]]`,
    `watch(seconds: float, wait: Callable[[float], None]) -> list[tuple[float, bool]]`
  - `uart` braucht nur `write(bytes)` und `read_all() -> bytes` (wie `RadarUart`).

- [ ] **Step 1: Failing tests** mit einem `FakeRadar` im Test (nimmt geschriebene Befehle auseinander, hält allgemeine Werte und Schwellen, antwortet mit ACK, liefert je nach Ausgabe Kurz- oder Messmodus-Meldungen nach einer Fake-Uhr):
  - `test_command_frame_enable`: `command_frame(0x00FF, b"\x01\x00") == bytes.fromhex("fdfcfbfa0400ff00010004030201")`
  - `test_parse_acks_reads_to_tail_despite_wrong_length`: ein ACK `ff01 0000 0300 8000` mit falschem Längenfeld wird trotzdem gefunden.
  - `test_parse_energies_and_states`: je eine gebaute Meldung nach Spec §12 → 16 Energien / `[False, True]` für Zustand 1 und 2.
  - `test_read_settings_factory_values`: Fake mit den Werkswerten (farthest 2, nearest 0, delay 10, status 80, distance 5, speed 10; trigger 48 42 36 34 32 31…; hold 45 42 33 32 28…) → genau diese.
  - `test_write_then_read_back_equal`; `test_write_sends_one_config_session` (Reihenfolge der Befehle `FF 70 72 76 FE`).
  - `test_nonzero_status_raises`; `test_missing_ack_raises_after_timeout` (Fake-Uhr, kein Warten).
  - `test_measure_drops_settle_and_zero_frames`: Meldungen in den ersten 2 s und Null-Meldungen fehlen im Ergebnis; danach ist die Ausgabe wieder Kurzmodus.
  - `test_measure_restores_minimal_mode_when_wait_raises`.
  - `test_watch_returns_times_and_states`.
- [ ] **Step 2:** `python -m unittest app.driver.tests.test_ld2410s` → FAIL (Modul fehlt).
- [ ] **Step 3: Implement.** Jeder Befehl: `read_all()` verwerfen, Rahmen schreiben, lesen bis die passende ACK da ist (`ack_timeout_s`, mit `sleep(0.02)`), Status ≠ 0 → `LD2410SError`. `read_settings`/`write_settings`/`minimal_mode` je in einem Einstellvorgang `FF … FE`. `measure`: Messmodus ein, `wait(0.1)` in Schleife bis `seconds`, Bytes mit Zeitstempel ihrer Ankunft sammeln, im `finally` Kurzmodus; Rückgabe ohne Meldungen vor `settle_s` und ohne Null-Meldungen. `watch`: im Kurzmodus lesen, je Meldung (Sekunden seit Start, jemand da).
- [ ] **Step 4:** Test → PASS.
- [ ] **Step 5:** Commit `Radar-Einrichtung: Treiber fuer den LD2410S`.

### Task 2: Berechnung

**Files:**
- Create: `rpi/app/applications/radar_tuning.py`
- Test: `rpi/app/applications/tests/test_radar_tuning.py` (liest `tests/radar_messungen/*.json`; ein Helfer lässt die ersten 3 Meldungen weg, so wie der Treiber die ersten 2 s)

**Interfaces:**
- Consumes: `RadarSettings`, `GENERAL_IDS` aus Task 1.
- Produces:
  - `@dataclass Figures(noise_max: list[float], noise_p95: list[float], target: list[float], behind: list[float] | None)`; `figures(empty, target, behind=None) -> Figures` (Energielisten rein; Null-Meldungen werden verworfen; p95 = Rang `ceil(0.95·n)`)
  - `@dataclass Tuning(farthest: int, trigger: list[int], hold: list[int])` (Listen mit F+1 Werten)
  - `compute(fig: Figures, margin_db: float = M_N) -> Tuning | None` (`None` = NOCHMAL)
  - `apply(old: RadarSettings, tuning: Tuning, delay_s: int) -> RadarSettings`
  - `figures_summary(fig) -> dict` (auf 0,1 dB gerundet, für den Bericht)

- [ ] **Step 1: Failing tests:**
  - `test_target_2m_behind_2m5`: F = 3, `trigger[3] == 34`, `hold[3] == 32`, `trigger[0] >= 48`, `trigger[1] >= 42`, `hold[0] >= 45`, `hold[1] >= 42`.
  - `test_target_2m_without_behind`: F = 4.
  - `test_target_1m_with_2m_as_behind`: F = 2, `trigger[2] == 35`.
  - `test_spoiled_empty_gives_none`: `leer_verdorben` als leer → `None`.
  - `test_larger_margin_can_give_none`: `margin_db=5` → `None`.
  - `test_hold_never_above_trigger` über alle Kombinationen oben.
  - `test_apply_keeps_far_gates_and_sets_general`: Tore > F unverändert, `general == {"farthest": F, "nearest": 0, "delay_s": 10, "status_hz10": 80, "distance_hz10": 40, "speed": 5}` bei `delay_s=10`.
- [ ] **Step 2:** FAIL.
- [ ] **Step 3: Implement** nach Spec §6. Aufrunden mit Toleranz `ceil(x - 1e-9)`, runden `floor(x + 0.5)`.
- [ ] **Step 4:** PASS.
- [ ] **Step 5:** Commit `Radar-Einrichtung: Berechnung aus den Messungen` (mit den Testdaten `tests/radar_messungen/`).

### Task 3: Ablage

**Files:**
- Create: `rpi/app/applications/radar_records.py`
- Test: `rpi/app/applications/tests/test_radar_records.py`

**Interfaces:**
- Consumes: `RadarSettings` aus Task 1.
- Produces: `class RadarRecords(config_dir, now=datetime.now)`, Ordner `config_dir/radar`:
  `save_backup(s: RadarSettings) -> None` (Status `laufend`), `pending_backup() -> RadarSettings | None`,
  `close_backup(status: str) -> None` (`fertig` / `zurueck`), `last_target_m() -> float` (Vorgabe 2.0, nur Werte aus der Zielwert-Liste),
  `save_target_m(m: float) -> None`, `write_report(report: dict) -> Path` (`einrichtung-JJJJMMTT-hhmmss.json`).
  Alles über `.tmp` + `replace`.

- [ ] **Step 1: Failing tests:** `test_backup_roundtrip_and_close`, `test_no_backup_means_none`, `test_target_default_and_saved`, `test_report_name_from_clock`, `test_corrupt_files_count_as_absent` (kaputtes JSON, falsche Form, Zielwert `7.3`).
- [ ] **Step 2:** FAIL. **Step 3:** Implement. **Step 4:** PASS.
- [ ] **Step 5:** Commit `Radar-Einrichtung: Sicherung, Zielwert und Bericht`.

### Task 4: Anwendung

**Files:**
- Create: `rpi/app/applications/radar_setup_app.py`
- Test: `rpi/app/applications/tests/test_radar_setup_app.py`

**Interfaces:**
- Consumes: Tasks 1–3; `StopApp` aus `app.ui.app_host`; `BT2, BT4, BT5, BT6, ExpanderButtons, ExpanderError` aus `app.ui.buttons`.
- Produces: `class RadarSetupApp(switch_factory, radar_factory=LD2410S, buttons_factory=ExpanderButtons, records_factory=RadarRecords, clock=time.monotonic)`, `name = "RADAR EINRICHTEN"`, `run(ctx)`.

Zeiten (Entscheid Claude, Spec §11): Hinausgehen 15 s, Hinstellen 10 s, Messen leer 30 s, am Ziel 20 s, dahinter 20 s, Test leer 30 s nach höchstens 20 s Warten auf Freigabe, Test am Ziel 15 s (bestanden, wenn in den letzten 2 s nur „jemand“ kommt), Weggehen vor dem Test dahinter 15 s, Test dahinter 20 s (bestanden, wenn nie „jemand“), Gesamtdauer höchstens 50 min, mindestens 10 Meldungen je Messung.

Ablauf nach Spec §5.2. Tasten im Radar-Modus aus `ExpanderButtons`; BT4/BT2 jederzeit Abbruch. Das Ergebnis zeigt die Anwendung erst nach dem Zurückschalten (dann über `ctx.wait_button`, BT4 zurück, BT5 beendet ebenfalls). Die ganze Einrichtung läuft in `ctx.activity.busy()`.

- [ ] **Step 1: Failing tests** mit Fake-Schalter, `FakeRadar` (skriptbar: Energien je Messung, Zustände je Test, Fehler beim n-ten Befehl), Fake-Tasten (Taste zu einer Fake-Zeit) und Fake-Uhr:
  - `test_full_run_writes_tuning_and_final_delay`: Zielwert 2.0 mit Daten von 2 m / 2,5 m → zuletzt geschrieben farthest 3, delay 30, trigger[3] 34; Bericht `ergebnis == "fertig"`; Sicherung `fertig`; Zielwert gespeichert.
  - `test_bt6_cycles_target_and_skips_behind`: zweimal BT6 → 3.0 M; BT6 im Schritt dahinter → kein Test dahinter, Bericht `dahinter == None`.
  - `test_nochmal_then_success_counts_attempts`.
  - `test_empty_test_fails_three_times_restores_backup`: letzter Schreibvorgang = Sicherung, Anzeige `FEHLER - ALTE WERTE`, Abstand je Anlauf +1 dB (im Bericht).
  - `test_bt4_before_write_writes_nothing`.
  - `test_bt4_during_measurement_restores_and_minimal_mode`.
  - `test_bt2_aborts_like_bt4`.
  - `test_no_key_for_5_minutes_aborts`.
  - `test_pending_backup_is_restored_first`.
  - `test_radar_error_after_write_tries_restore`: Anzeige `FEHLER RADAR`, kein Absturzbild.
  - `test_too_few_frames_is_radar_error`.
  - `test_stop_signal_restores_and_stops`: `StopApp` mit dem Grund des Signals.
  - `test_expander_error_restores_and_shows_fehler_tasten`.
  - `test_all_lines_fit_24_chars`: jede gezeigte Zeile ≤ 24 Zeichen (Punkte nach einer Ziffer zählen nicht).
- [ ] **Step 2:** FAIL. **Step 3:** Implement. **Step 4:** PASS, dazu `discover -s app/applications`.
- [ ] **Step 5:** Commit `Radar-Einrichtung: Anwendung RADAR EINRICHTEN`.

### Task 5: Einhängen

**Files:**
- Modify: `rpi/app/main.py` (`build_apps`, `run_wall`, Wand-Modus bei `radar_factory`)
- Modify: `rpi/app/applications/settings_apps.py` (Kopfzeile: Platzhalter nur noch am PC)
- Test: `rpi/app/tests/test_main.py`

**Interfaces:**
- `build_apps(config_dir, radar_app=None, radar_setup_app=None)`: Einstellungen = `[ThemaApp(...), radar_setup_app or RadarSetupPlaceholder()]`.
- `run_wall(..., radar_factory=None, radar_setup_factory=None, ...)`.
- Wand-Modus: `RadarSetupApp(switch_factory=lambda: RadarSwitch(link, port), buttons_factory=lambda: ExpanderButtons(bus=_SmbusReader(bus), bus_guard=guard))`.

- [ ] **Step 1: Failing tests:** `test_radar_setup_app_is_taken_from_argument`, `test_wall_mode_builds_radar_setup_with_expander_buttons` (wie der bestehende Test für `radar_factory`).
- [ ] **Step 2–4:** auf dem Pi ausführen (`dotenv`): `~/.venvs/reflection-wall-rpi/bin/python -m unittest app.tests.test_main`.
- [ ] **Step 5:** Commit `Radar-Einrichtung: im Einstellungsmenue eingehaengt`.

### Task 6: Am Gerät

- [ ] Auf den Pi bringen (Pi-Stand `abnahme-pi` + diese Commits), Dienst neu starten.
- [ ] Mit dem Owner: Spec §10 „Am Gerät“ 1–3.
