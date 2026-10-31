# Teil 3b: Mitternacht – Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Um Mitternacht schaltet der ESP den Pi selbst ein, holt mit `GET|QUOTE` ein neues Zitat von der KI, prüft es, schaltet den Pi wieder aus und schreibt das Zitat vorne in die Liste im FRAM. Dafür schläft der ESP mit Timer (höchstens 3 h), führt eine Uhr (UTC, Ortszeit Zürich mit Sommerzeit) und gleicht sie per WLAN und NTP ab.

**Architecture:** Auf dem ESP kommen drei reine Bausteine in `esp/lib/core` dazu, alle mit nativen Tests:
- `CivilTime` rechnet UTC in Ortszeit Zürich um.
- `Clock` und `WakePlan` führen die Uhr und entscheiden bei jedem Wecken: schlafen (wie lange, mit oder ohne Funk), abgleichen oder den Nacht-Auftrag starten.
- `QuoteCheck` prüft ein Zitat.

`PiSession` lernt `GET|QUOTE`, die Nacht-Regeln N2 und N3 und eine neue Aktion „Zitat ist da“. Die Arduino-Seite bekommt `TimeSync` (WLAN, NTP, Einrichtungsportal), neue Felder im RTC-Speicher und die Verdrahtung in `Application`. Auf dem Pi entsteht `night_quote` (Thema, Auftrag an die KI, Bereinigung, Prüfung). Der Dispatcher beantwortet `GET` in einem eigenen Thread, und `main` wechselt bei `SESSION|HAND` von der Nacht ins Menü.

**Tech Stack:** ESP8266, PlatformIO, C++14, Unity (native), WiFiManager; Python 3, `unittest`, Groq.

**Spec:** `docs/superpowers/specs/2026-10-19-esp-pi-steuerung-design.md`:
- §9 Mitternacht;
- §11 Gespeicherter Zustand;
- §12 Fristen;
- §13 Fehler;
- Entscheide M2-c, M3-a, M4-a, Z6, Z11, P1-a, T2-a und N1–N4.

Dazu kommen aus `docs/superpowers/specs/2026-10-23-menue-und-anwendungen-design.md` die Punkte F1 und §8 (Themen).

## Global Constraints

- Branch `feature/mitternacht` (von `main` bd8d8e0). Nicht pushen, nichts aufs Gerät laden.
- **Commits ohne Zuschreibung:** keine Zeile `Co-Authored-By`, kein „Generated with“. Betreff auf Deutsch, in ASCII. Nur geänderte Dateien beim Namen stagen; nie `git add -A` oder `git add .` (der Ordner `.superpowers/` ist nicht ignoriert).
- ESP-Tests: `cd esp && pio test -e native` (MinGW-GCC 6.3, nur C++14; **kein** `localtime_r`, `gmtime_r`, `timegm` unter MinGW, deshalb Kalenderrechnung selbst). ESP-Build: `cd esp && pio run`. Ist ein Pfad länger als 260 Zeichen, in `%TEMP%\fpb` bauen.
- Python-Tests: `cd rpi && "C:\Users\cross-INGCamilleChat\.venvs\reflection-wall-rpi\Scripts\python.exe" -m unittest discover -s app -t .`. Die Ausgabe enthält keine Tracebacks. `test_imports` bleibt grün. Kein Test ruft die echte KI auf.
- Wer einen Testlauf startet, beendet nur diesen eigenen Lauf. Nie alle `python.exe` beenden.
- Logik des ESP in `esp/lib/core`, ohne Arduino-Typen; Zeit kommt als Parameter.
- Werte (Spec §9, §12, N1–N4; „Plan“ = Startwert dieses Plans):

  | Name | Wert | Herkunft |
  |---|---|---|
  | Längste Schlafstrecke | 10 800 s (3 h) | M3-a |
  | WLAN + NTP höchstens | 15 s | M3-a |
  | Einrichtungsportal | 180 s, nur Kaltstart ohne Zugangsdaten, AP `ReflectionWall` | M3-a, bestehender Code |
  | NTP-Server | `pool.ntp.org`, `time.nist.gov` | bestehender Code |
  | Zeitzone | Europa/Zürich: MEZ = UTC+1, MESZ = UTC+2 von letzter Sonntag März 01:00 UTC bis letzter Sonntag Oktober 01:00 UTC | §9 |
  | Termine der Nacht | 00:00, 01:00, 02:00 Ortszeit; Fenster bis 03:00 | M3-a, M4-a |
  | Abgleich gilt als frisch | 900 s (15 min) | Plan (R2) |
  | Frist `GET` | 120 000 ms (steht im Codec) | §12 |
  | Abgelehnte Zitate pro Versuch | 3 | Z6 |
  | KI-Anfragen pro `GET` (Pi) | 3 | M2-c |
  | Zitat | 1–96 Zeichen; Zeichen `A–Z a–z 0–9 - . / : + *` und Leerzeichen; passt in 4 × 24 nach der Umbruchregel | §9 |
  | Testschalter N4 | `Features::NIGHT_TEST = false`; Vorlauf 120 s | N4 |
  | Neue `MAGIC` | `0x52574C34` („RWL4“) | Plan |

- `GET` hat die Daten `QUOTE|<Text vom Vortag>` (leer = neue Kette). Antworten: `QUOTE|<Text>`, `ERROR|ZU_LANG` (drei KI-Antworten passten nicht), `ERROR|KI` (KI nicht erreichbar oder Fehler), `ERROR|BAD_GET` (Daten ohne `QUOTE|`).
- Sendereihenfolge auf dem ESP (eine eigene Anfrage zur Zeit): `SESSION`, `SHUTDOWN`, `BUTTON`, `GET`, `PING` (R8).
- In einer Sitzung `NACHT` gilt N2: §8 läuft weiter, BT1 und BT3–BT6 bleiben beim ESP. BT2 gilt N3.

## Was dieser Plan entscheidet (Rulings)

- **R1 Kalender selbst rechnen:** Die Uhr zählt UTC-Sekunden seit 1970 in `uint32_t` (reicht bis 2106). Ortszeit und Sommerzeit rechnet `CivilTime` ohne libc, weil MinGW die Funktionen nicht hat und die Tests sonst nicht laufen. Kostet: etwa 100 Zeilen und Tests über die Umstellungen.
- **R2 Der Versuch um 00:00 braucht einen frischen Abgleich:** Der ESP startet den ersten Versuch der Nacht nur, wenn er in den letzten 15 min per NTP abgeglichen hat (§9 Schritt 1). Fehlt der Abgleich, startet er neu mit Funk und gleicht zuerst ab. So stimmt das Datum des Zitats, auch wenn die Uhr nach N1 vorging. Die Versuche um 01:00 und 02:00 brauchen keinen neuen Abgleich; sie nehmen das Datum aus dem ersten Versuch.
- **R3 Neu starten mit Funk:** Braucht der ESP den Funk und hat ihn in diesem Durchlauf nicht, schläft er 1 ms mit `WAKE_RF_DEFAULT`. Die Anzeige behält dabei ihren Inhalt (HT16K33), eine laufende Sitzung übersteht es wie jeden Reset (R8 aus Teil 2). Kostet: in einer Sitzung von Hand um Mitternacht bis zu 15 s ohne Sitzungsschleife; der Pi wiederholt seine Anfragen so lange.
- **R4 Testschalter über alle Abgleiche:** Ist `NIGHT_TEST` an, legt der erste Abgleich nach einem Kaltstart einmal eine Verschiebung fest, sodass in 120 s Mitternacht ist. Jeder spätere Abgleich bis zum nächsten Kaltstart addiert dieselbe Verschiebung; sonst würde der Abgleich vor Mitternacht die Verschiebung wieder aufheben. Bei jedem Wecken steht `NIGHT_TEST AN` im Log.
- **R5 Ein Zitat, zwei gleiche Prüfungen:** ESP (`QuoteCheck`) und Pi (`quote_fits`) prüfen mit denselben Fällen aus `tests/quote_vectors.json`. `>` ist auf dem ESP darstellbar, gehört aber nicht zu den erlaubten Zeichen eines Zitats (§9).
- **R6 Text vom Vortag im RTC-Speicher:** Der ESP hält den neuesten Listeneintrag als `yesterday` im RTC-Speicher und erneuert ihn bei jedem Laden der Liste. Ein Kaltstart lädt die Liste einmal, solange der Pi aus ist. So liest der ESP das FRAM nie, während der Pi die Anzeige schreiben könnte (R14 aus Teil 2).
- **R7 Erfolg zählt beim Empfang:** Ist ein gültiges Zitat da, gilt die Nacht als erledigt (`doneDate`). Scheitert das Schreiben ins FRAM, bleibt das Zitat im RTC-Speicher (`pendingWrite`). Der ESP versucht es bei jedem späteren Wecken erneut, solange der Pi aus ist.
- **R8 Sendereihenfolge:** `GET` kommt nach `BUTTON`. So bleiben Tasten in einer Sitzung von Hand flink, und `GET` geht beim nächsten freien Takt.
- **R9 Fehler des Pi:**
  - `ERROR|KI`, wenn die KI ausfällt (`write_to_ai` liefert „Fehler…“ oder wirft).
  - `ERROR|ZU_LANG` nach drei unpassenden Antworten.
  - `.thema_zuletzt` schreibt der Pi erst nach einem gelungenen Zitat, damit ein Fehlversuch den Themenwechsel nicht verbraucht.
- **R10 `GET` im eigenen Thread:** Der Pi beantwortet `GET` in einem Arbeits-Thread, damit `BUTTON`, `SESSION` und `SHUTDOWN` weiterlaufen. Kommt `GET` noch einmal (neue Nummer nach einem Reset des ESP, R8), startet kein zweiter Thread; das Ergebnis geht an das neueste `GET`.
- **R11 `TimeSync` statt `WifiController`:** Der ungenutzte `WifiController` hat keine Fristen. Er wird durch `TimeSync` ersetzt. `OtaManager` bleibt, wie er ist.
- **R12 Weckgrund ohne Radar:** Mit `RADAR_INSTALLED = false` beachtet `WakeupReason` INT_HLK nicht mehr. Heute meldet er ein Timer-Wecken sonst als `INT_HLK`, weil der Pull-up die Leitung HIGH hält.
- **R13 Früh geweckt (N1):** Als „vor der Zeit“ gilt jedes Wecken ausser `TIMER` und `POWER_ON`. Die geplante Strecke zählt in jedem Fall ganz. Nur ein Wecken vor der Zeit macht die Uhr „ungenau“.
- **R14 Uhr unbekannt:** Nach einem Kaltstart ohne gelungenen Abgleich schläft der ESP Strecken von 3 h mit Funk und versucht bei jedem Wecken nach Zeitplan (nicht bei einem Tastendruck) abzugleichen (Entscheid B des Owners vom 2026-10-31). Bis dahin lässt er die Nacht aus (M3-a).
- **R15 Ergebnis der Nacht:** `NightResult` merkt sich `Ok` oder den Grund und kommt bei jedem Wecken ins Log (§9 „Fehler in der Nacht“). Die Gründe: `NoReady`, `NoAnswer`, `Error`, `Rejected`, `SessionEnded`, `NoClock`, `StoreFailed`.
- **R16 Abgleich scheitert um Mitternacht:** Dann läuft der Auftrag nach der eigenen Uhr (§13 „WLAN fehlt um Mitternacht“), ohne weiteren Abgleich in diesem Durchlauf. Kostet: Ging die Uhr nach N1 vor, kann der Auftrag vor dem echten Mitternacht laufen und das Zitat das Datum des nächsten Tages tragen.

## Review Focus

1. **Sommerzeit-Wechsel in der Nacht:**
   - Im Herbst gibt es 02:00 zweimal; es gilt das erste Mal.
   - Im Frühling gibt es 02:00 nicht; es gilt 03:00 MESZ, und die Nacht hat dann nur zwei Termine im Fenster.
   - Tests in Task 1 und Task 2.
2. **Viele Resets am Abend:** Die Uhr geht höchstens vor. Der Abgleich vor 00:00 korrigiert sie, und Mitternacht wird nie verschlafen (N1, R2). Test in Task 2.
3. **Kaltstart in der Nacht** (Strom kommt um 01:30 zurück): Abgleich, dann das Datum des neuesten Listeneintrags vergleichen und den Auftrag sofort starten, wenn das Zitat fehlt. Test in Task 2.
4. **Reset während `GET` offen ist:** `GET` geht noch einmal raus, ohne als Ablehnung zu zählen. Auf dem Pi läuft nur ein Thread, und die Antwort geht an das neueste `GET`. Tests in Task 4 und Task 8.
5. **BT2 in der Nacht, während `GET` läuft:** BT2 setzt den ESP zurück, das offene `GET` verfällt. `PI STARTET` erscheint sofort, `SESSION|HAND` geht zuerst, dann sendet der ESP das `GET` noch einmal mit neuer Nummer. Der Pi gibt es dem Arbeits-Thread, der noch rechnet, oder antwortet mit dem Zitat, das er schon hat. Das Zitat zählt, und der Pi wechselt ins Menü. Tests in Task 4 und Task 8, seit der Schlussprüfung in dieser Reihenfolge und auf dem echten `PiLink`.

---

### Task 1: `CivilTime` – UTC und Ortszeit Zürich

**Files:**
- Create: `esp/lib/core/src/CivilTime.h`, `esp/lib/core/src/CivilTime.cpp`
- Test: `esp/test/test_civil_time/test_main.cpp`

**Interfaces:**
- Produces:
  ```cpp
  namespace CivilTime {
      struct Local { int year; int month; int day; int hour; int minute; int second; bool summer; };
      Local toZurich(uint32_t utc);                              // UTC-Sekunden seit 1970 → Ortszeit Zürich
      bool isSummer(uint32_t utc);                               // EU-Regel (Global Constraints)
      // Erster Zeitpunkt (UTC) am Ortsdatum year-month-day, an dem die Ortszeit hour:00 ist.
      // Gibt es hour:00 an dem Tag nicht (Frühling 02:00), der erste gültige Zeitpunkt danach (03:00 MESZ).
      // Gibt es hour:00 zweimal (Herbst 02:00), das erste Mal.
      uint32_t atLocalHour(int year, int month, int day, int hour);
      uint32_t nextLocalHour(uint32_t utc, int hour);            // kleinster Zeitpunkt > utc mit Ortszeit hour:00 (Regeln wie oben)
      std::string date(const Local& t);                          // "JJJJ-MM-TT"
  }
  ```
- [ ] **Step 1: Tests**:

  | Test | Prüft |
  |---|---|
  | `test_winter_is_utc_plus_1` | 2026-01-15 12:00:00 UTC → 13:00:00, `summer` falsch |
  | `test_summer_is_utc_plus_2` | 2026-07-01 22:30:00 UTC → 2026-07-02 00:30:00 |
  | `test_spring_change` | 2026-03-29 00:59:59 UTC → 01:59:59 MEZ; 01:00:00 UTC → 03:00:00 MESZ |
  | `test_autumn_change` | 2026-10-25 00:59:59 UTC → 02:59:59 MESZ; 01:00:00 UTC → 02:00:00 MEZ |
  | `test_leap_day` | 2028-02-29 und 2028-03-01 richtig; 2100 ist kein Schaltjahr |
  | `test_at_local_hour_midnight` | `atLocalHour(2026,7,2,0)` = 2026-07-01 22:00 UTC |
  | `test_at_local_hour_spring_gap` | `atLocalHour(2026,3,29,2)` = 2026-03-29 01:00 UTC (= 03:00 MESZ) |
  | `test_at_local_hour_autumn_twice` | `atLocalHour(2026,10,25,2)` = 2026-10-25 00:00 UTC (erstes 02:00) |
  | `test_next_local_hour` | von 23:59:59 Ortszeit → 00:00 des nächsten Tages; von genau 00:00 → nächster Tag |
  | `test_date_string` | `"2026-03-09"` mit führenden Nullen |
- [ ] **Step 2:** `pio test -e native -f test_civil_time` → FAIL (Datei fehlt). **Step 3:** umsetzen. **Step 4:** grün, ganze Suite grün. **Step 5:** Commit `ESP: Ortszeit Zuerich aus UTC (CivilTime)`

### Task 2: `Clock` und `WakePlan`

**Files:**
- Create: `esp/lib/core/src/Clock.h/.cpp`, `esp/lib/core/src/NightData.h`, `esp/lib/core/src/WakePlan.h/.cpp`
- Test: `esp/test/test_wake_plan/test_main.cpp`

**Interfaces:**
- Consumes: `CivilTime` (Task 1).
- Produces:
  ```cpp
  // Clock.h – liegt im RTC-Speicher
  struct ClockData { uint32_t utc; uint32_t plannedS; uint32_t lastSyncUtc; int32_t testOffsetS;
                     uint16_t ms; uint8_t valid; uint8_t exact; uint8_t radio; uint8_t pad[3]; };   // static_assert(sizeof == 24)
  namespace Clock {
      void reset(ClockData&);                                   // unbekannt
      void onBoot(ClockData&, bool early);                      // N1: utc += plannedS; plannedS = 0; early → exact = 0
      void advance(ClockData&, unsigned long elapsedMs);        // wach verbrachte Zeit (ms-Rest in ms)
      void synced(ClockData&, uint32_t ntpUtc);                 // utc = ntpUtc + testOffsetS; valid = exact = 1; lastSyncUtc = utc
      void beforeSleep(ClockData&, uint32_t sleepS, bool radio); // plannedS = sleepS; radio = Funk beim nächsten Start
      bool freshSync(const ClockData&);                         // valid && exact && utc - lastSyncUtc <= 900
  }
  // NightData.h – liegt im RTC-Speicher
  enum class NightStatus : uint8_t { Idle = 0, Wanted = 1, Got = 2, Failed = 3 };
  enum class NightResult : uint8_t { None = 0, Ok = 1, NoReady = 2, NoAnswer = 3, Error = 4, Rejected = 5,
                                     SessionEnded = 6, NoClock = 7, StoreFailed = 8 };
  struct NightData {
      NightStatus status; uint8_t attempts; uint8_t rejects; NightResult result; uint8_t pendingWrite;
      char date[11]; char doneDate[11]; char yesterday[97]; char quote[97]; uint8_t pad[3];
  };                                                                        // static_assert(sizeof == 224)
  namespace NightJob { void reset(NightData&); bool valid(const NightData&); }   // Bereiche der enums, NUL in jedem Text
  // WakePlan.h
  enum class WakeKind { Sleep, SyncNow, RestartWithRadio, StartNight };
  struct WakeDecision { WakeKind kind; uint32_t sleepS; bool radio; };
  // radioOn: dieser Durchlauf hat Funk; syncFailed: ein Abgleich in diesem Durchlauf ist gescheitert
  namespace WakePlan { WakeDecision decide(const ClockData& clock, const NightData& night, bool radioOn, bool syncFailed); }
  ```
- `decide` (die Regeln dieser Tabelle sind verbindlich; „heute“ = Ortsdatum von `clock.utc`; der Versuch k einer Nacht hat den Termin 00:00, 01:00, 02:00 für k = 0, 1, 2; `night.attempts` gilt nur, wenn `night.date` = heute, sonst 0):

  | Lage | Entscheid |
  |---|---|
  | Uhr unbekannt | `radioOn`, nicht `syncFailed` und nicht `earlyWake` (Wecken vor der Zeit) → `SyncNow`; sonst `Sleep(10 800, radio)` (R14) |
  | 00:00 ≤ Ortszeit < 03:00, `doneDate` ≠ heute, Versuche < 3, Versuch 0 fällig, `freshSync` falsch | `syncFailed` → `StartNight` nach eigener Uhr (§13, R16); sonst `radioOn` → `SyncNow`; sonst `RestartWithRadio` (R2) |
  | gleiches Fenster, Termin des nächsten Versuchs erreicht (bei Versuch 0 mit `freshSync`) | `StartNight` |
  | gleiches Fenster, Termin noch nicht erreicht | `Sleep(bis zum Termin, radio = Versuch 0)` |
  | sonst (erledigt, drei Versuche oder ausserhalb des Fensters) | `Sleep(min(bis nächstes 00:00, 10 800), radio = Strecke endet um 00:00)` |
- [ ] **Step 1: Tests** (Zeiten über `CivilTime::atLocalHour` aufbauen):

  | Test | Prüft |
  |---|---|
  | `test_on_boot_adds_planned_leg` | `plannedS` 3600 → `utc` + 3600; Timer-Wecken lässt `exact` |
  | `test_early_wake_counts_full_leg_and_marks_inexact` | N1 |
  | `test_unknown_clock_never_becomes_known_by_boot` | `onBoot` macht `valid` nie 1 |
  | `test_advance_keeps_ms_remainder` | 3 × 400 ms → 1 s, Rest 200 ms |
  | `test_synced_applies_test_offset` | R4 |
  | `test_fresh_sync_window` | 899 s frisch, 901 s nicht |
  | `test_evening_sleeps_toward_midnight_with_radio_on_last_leg` | 18:00 → 3 h ohne Funk; 22:30 → 1,5 h mit Funk |
  | `test_unknown_clock_sleeps_3h_with_radio_and_syncs_when_radio_on` | R14 |
  | `test_midnight_without_fresh_sync_restarts_with_radio` | R2 |
  | `test_failed_sync_at_midnight_runs_by_own_clock` | R16; ohne Endlosschleife: `syncFailed` → nie wieder `SyncNow` im selben Durchlauf |
  | `test_midnight_with_fresh_sync_starts_night` | |
  | `test_sync_shows_before_midnight_sleeps_rest_with_radio` | 23:40 nach Abgleich → `Sleep(1200, radio)` |
  | `test_retries_at_1_and_2` | Versuch 1 → `StartNight` ab 01:00; davor `Sleep` bis 01:00 ohne Funk |
  | `test_three_attempts_then_next_night` | |
  | `test_done_tonight_sleeps_to_next_midnight` | |
  | `test_window_closes_at_3` | 03:00 ohne Erfolg → nächste Nacht |
  | `test_cold_boot_in_the_night_starts_at_once` | Review Focus 3: 01:30, `doneDate` ≠ heute, Versuche 0, frisch → `StartNight` |
  | `test_many_evening_resets_never_miss_midnight` | Review Focus 2: Folge von `onBoot(early)` mit `plannedS` bis 3 h; jede Entscheidung führt spätestens beim echten 00:00 (mit `synced`) zu `StartNight` |
  | `test_spring_night_has_no_2_oclock_term` | Review Focus 1: 2026-03-29 Versuch 2 fällt auf 03:00 MESZ = Fenster zu |
  | `test_autumn_night_uses_first_2_oclock` | Review Focus 1 |
  | `test_night_data_valid_rejects_bad_values` | `NightJob::valid` |
- [ ] **Step 2:** FAIL. **Step 3:** umsetzen. **Step 4:** grün, ganze Suite grün. **Step 5:** Commit `ESP: Uhr und Weckplan fuer die Nacht`

### Task 3: Zitat prüfen, gleich auf beiden Seiten

**Files:**
- Create: `tests/quote_vectors.json`, `esp/lib/core/src/QuoteCheck.h/.cpp`, `rpi/app/night_quote.py` (nur `clean_quote` und `quote_fits` in diesem Task)
- Modify: `esp/test/support/VectorFile.h` (Pfad `QUOTE_VECTORS`, Lader für die neue Datei, falls das bestehende Format nicht passt)
- Test: `esp/test/test_quote_check/test_main.cpp`, `rpi/app/tests/test_night_quote.py`

**Interfaces:**
- Produces:
  - ESP: `namespace QuoteCheck { bool acceptable(const std::string& text); }`. Die Bedingungen: 1–96 Zeichen; jedes Zeichen aus `A–Z a–z 0–9 - . / : + *` oder Leerzeichen; `TextLayout::wrap(text).fits`.
  - Pi:
    - `clean_quote(text: str) -> str` ersetzt `ä→ae ö→oe ü→ue Ä→Ae Ö→Oe Ü→Ue ß→ss` und entfernt alle anderen Zeichen ausserhalb der erlaubten. Leerraum wird zu einem Leerzeichen, vorne und hinten wird gekürzt.
    - `quote_fits(text: str) -> bool` prüft dieselben Bedingungen wie `acceptable`, mit `text_layout.wrap`.
  - `tests/quote_vectors.json`: `{"vectors": [{"name", "text", "acceptable": bool}, …]}` und `{"clean": [{"name", "raw", "cleaned"}]}`. Die Fälle sind mindestens:
    - genau 96 Zeichen, die passen;
    - 97 Zeichen;
    - leer;
    - `>`;
    - Komma;
    - Umlaut;
    - ein Wort, das nicht in 4 × 24 passt;
    - Kleinbuchstaben erlaubt;
    - `|`.
- [ ] **Step 1:** Vektoren schreiben, dann beide Testsuiten, die sie lesen. **Step 2:** FAIL. **Step 3:** umsetzen. **Step 4:** beide grün. **Step 5:** Commit `Zitat pruefen: gemeinsame Faelle fuer ESP und Pi`

### Task 4: `PiSession` lernt die Nacht

**Files:**
- Modify: `esp/lib/core/src/PiSession.h/.cpp`
- Modify: `esp/test/test_pi_session/test_main.cpp` (Konstruktor mit zwei Argumenten in allen Tests; neue Tests)

**Interfaces:**
- Consumes: `NightData`, `NightJob` (Task 2), `QuoteCheck` (Task 3).
- Produces:
  - `PiSession(SessionData& data, NightData& night)` ersetzt den Konstruktor mit einem Argument.
  - `Awaiting::Get = 5`. `PiSession::valid` lässt `Get` zu.
  - `SessionAction::Kind::QuoteReady`; der Text steht in `command`.
  - `bool requestQuote()` gilt in Starting und Running. Es setzt `night.status = Wanted`, sofern der Status nicht schon `Wanted` oder `Got` ist, und gibt zurück, ob ein neuer Auftrag begonnen hat. Datum und `yesterday` setzt vorher die Application.
  - `startNight(out)` bleibt wie heute; die Application ruft danach `requestQuote` auf (dann ist der Zustand Starting).
- Verhalten:
  - **Senden:**
    - In Running geht `GET` mit `QUOTE|` + `yesterday`, wenn `night.status == Wanted` (Reihenfolge R8).
    - `resume` setzt nach `awaiting == Get` nur `awaiting = None`; `GET` geht erneut, und das zählt nicht als Ablehnung.
  - **`QUOTE|text`:**
    - Ist der Text gültig: `night.quote = text`, `status = Got`, `doneDate = date`, `result = Ok`, `pendingWrite = 1`, Aktion `QuoteReady`. In NACHT folgt HERUNTERFAHREN (N2).
    - Ist er ungültig: `rejects++`. Bei weniger als 3 bleibt `Wanted`. Beim dritten `status = Failed` und `result = Rejected`; in NACHT folgt HERUNTERFAHREN.
  - **`ERROR|…` oder eine andere Antwort:** `Failed`, `Error`; in NACHT HERUNTERFAHREN.
  - **Abgelaufenes `GET`:** `Failed`, `NoAnswer`; in NACHT HERUNTERFAHREN.
  - **Ende der Sitzung, während `Wanted`:**
    - `status = Failed`.
    - `result` ist `NoReady` nach dem Ende ohne `READY`, `NoAnswer` nach drei `PING`-Aussetzern, sonst `SessionEnded`.
  - **Tasten in NACHT (N2, N3):**
    - BT2 in Starting: `reason = Hand`, `Show "PI STARTET"`. Nach `READY` geht `SESSION|HAND`.
    - BT2 in Running: `reason = Hand`, `Show "PI STARTET"`, `NeedSession`. Ist `GET` offen, wartet `SESSION`, weil nur eine eigene Anfrage zur Zeit offen sein darf.
    - BT2 in HERUNTERFAHREN und HALT-WARTEN: nichts.
    - BT1, BT3–BT6: nichts.
- [ ] **Step 1: Tests** (bestehende auf den neuen Konstruktor umstellen, dann neue):

  | Test | Prüft |
  |---|---|
  | `test_night_sends_get_after_session` | NACHT: `READY` → `SESSION\|NACHT` → `GET` mit `QUOTE\|<yesterday>` |
  | `test_get_waits_for_buttons` | Running HAND mit `Wanted` und Taste in der Schlange → erst `BUTTON`, dann `GET` (R8) |
  | `test_no_ping_while_get_open` | L2 |
  | `test_valid_quote_sets_got_emits_ready_and_shuts_down_at_night` | |
  | `test_valid_quote_in_hand_session_keeps_session` | M4-a |
  | `test_three_rejects_fail_and_shut_down` | Z6 |
  | `test_error_answer_fails` ; `test_get_expired_fails` | |
  | `test_reset_while_get_open_resends_without_counting` | Review Focus 4 |
  | `test_session_end_while_wanted_records_reason` | `NoReady`, `NoAnswer`, `SessionEnded` |
  | `test_bt2_at_night_running_becomes_hand_after_get` | N3 ohne Reset, innerhalb eines Durchlaufs: `Show PI STARTET` sofort, `SESSION\|HAND` nach der Antwort auf `GET`, Zitat zählt |
  | `test_bt2_at_night_with_get_open_after_reset_sends_hand_then_get_again` | Review Focus 5, wie auf dem Gerät: BT2 setzt den ESP zurück, `resume()` verwirft das offene `GET`; `SESSION\|HAND` zuerst, dann das `GET` noch einmal mit neuer Nummer; `QUOTE` → Got, Grund Hand, kein Herunterfahren (seit der Schlussprüfung) |
  | `test_bt2_at_night_starting_becomes_hand` | N3 |
  | `test_other_buttons_at_night_do_nothing` | N2 |
  | `test_request_quote_only_in_starting_or_running` | |
- [ ] **Step 2:** FAIL. **Step 3:** umsetzen. **Step 4:** grün, ganze Suite grün. **Step 5:** Commit `ESP: PiSession holt das Zitat der Nacht (GET, N2, N3)`

### Task 5: RTC-Speicher, Weckgrund, `TimeSync`, Testschalter

**Files:**
- Modify: `esp/lib/system/PersistentState.h/.cpp`, `esp/lib/system/wakeupReason.cpp`, `esp/lib/config/features.h`
- Create: `esp/lib/ota/TimeSync.h/.cpp`
- Delete: `esp/lib/ota/WifiController.h/.cpp` (R11)

**Interfaces:**
- Produces:
  - `PersistentState::Data` bekommt am Ende `ClockData clock; NightData night;`. Dazu `static_assert(sizeof(Data) == 300)` und `MAGIC = 0x52574C34`. `setDefaults` ruft `Clock::reset` und `NightJob::reset`.
  - `WakeupReason` beachtet INT_HLK nur, wenn `Features::RADAR_INSTALLED` (R12).
  - `features.h`: `constexpr bool NIGHT_TEST = false;` und `constexpr uint32_t NIGHT_TEST_LEAD_S = 120;` (N4, R4). Der Schalter `WAKE_RF_ENABLED` fällt weg; ob Funk an ist, entscheidet jetzt jede Schlafstrecke selbst.
  - `class TimeSync`:
    - `static bool hasCredentials()`: Zugangsdaten im SDK-Speicher vorhanden.
    - `static bool sync(unsigned long timeoutMs, uint32_t& utc)`: STA, `WiFi.begin()`, `configTime(0, 0, …)`, wartet auf eine Zeit nach 2024. Danach WLAN aus. Das Ganze dauert höchstens `timeoutMs`.
    - `static bool portal(unsigned long timeoutS)`: WiFiManager mit `setConfigPortalTimeout`; `WiFi.persistent(true)` nur während des Portals.
- [ ] **Step 1:** umsetzen. **Step 2:** `pio run` → SUCCESS ohne neue Warnungen; `pio test -e native` grün. **Step 3:** Commit `ESP: Uhr und Nacht im RTC-Speicher, Weckgrund ohne Radar, TimeSync`

### Task 6: `Application` – Uhr, Schlaf und Nacht

**Files:**
- Modify: `esp/lib/app/application.h/.cpp`, `esp/README.md`

**Interfaces:**
- Consumes: Tasks 1–5.
- Produces (Ablauf in `run()`):
  1. **Uhr:**
     - Nach `load`: `Clock::onBoot(_state.clock, early)`. `early` gilt bei jedem Weckgrund ausser `TIMER` und `POWER_ON` (R13).
     - Bei einem Kaltstart `Clock::reset` und `NightJob::reset`.
     - Ungültige `NightData` → `NightJob::reset` mit Log.
     - Im Log stehen `NightResult` und, wenn `NIGHT_TEST` an ist, `NIGHT_TEST AN`.
  2. **Funk:** Dieser Durchlauf hat Funk, wenn er ein Kaltstart ist oder die letzte Schlafstrecke mit Funk geplant war (`clock.radio`). Abgeglichen wird nur, wenn `decide` `SyncNow` sagt, nicht bei jedem Start mit Funk. So wartet ein Tastendruck kurz vor Mitternacht nicht auf das WLAN.
     - `SyncNow`: `TimeSync::sync(15 000)`. Nach einem Kaltstart ohne Zugangsdaten öffnet er zuerst das Portal (180 s). Danach entscheidet er sofort neu.
     - Gelingt der Abgleich: `Clock::synced`. Beim ersten Abgleich nach einem Kaltstart mit `NIGHT_TEST` legt er die Verschiebung fest (R4).
     - Scheitert er: `syncFailed` gilt für den Rest des Durchlaufs.
  3. **Kaltstart:** Die Liste wird einmal geladen (der Pi ist aus). Danach gilt `night.yesterday` = neuester Text und `night.doneDate` = Datum des neuesten Eintrags (R6, Review Focus 3).
  4. **Zitat nachtragen:** Ist `pendingWrite` gesetzt und keine Sitzung aktiv, lädt der ESP die Liste, setzt das Zitat mit `addNewest(night.date, night.quote)` vorne an und speichert (P1-a).
     - Gelingt das: `pendingWrite = 0`, `yesterday` = Zitat.
     - Sonst: `result = StoreFailed` (Log); das Zitat bleibt im RTC-Speicher (R7).
  5. **Entscheiden:** `WakePlan::decide(clock, night, radioOn)` am Ende jedes Durchlaufs, ebenso jede Sekunde in `runWallLoop` und in `runSession`. Die Ergebnisse:
     - `StartNight`, ohne Sitzung: `night.date` = heute, `rejects = 0`, `startNight`, dann `requestQuote()`; liefert es true, `attempts++`. Danach die Sitzungsschleife.
     - `StartNight`, in einer laufenden Sitzung: `night.date` = heute, `rejects = 0`, nur `requestQuote()`; `attempts++` nur, wenn es true liefert (M4-a). In einer Nacht-Sitzung liefert es false, solange `GET` läuft oder das Zitat da ist.
     - `RestartWithRadio`: `Clock::beforeSleep(…, 0, true)`, sichern, `ESP.deepSleep(1000, WAKE_RF_DEFAULT)` (R3).
     - `SyncNow`: siehe Schritt 2.
     - `Sleep` (nur am Ende eines Durchlaufs; in den Schleifen bedeutet es „weiter“): `Clock::beforeSleep(…, sleepS, radio)`, sichern, dann `ESP.deepSleep(sleepS × 10⁶, radio ? WAKE_RF_DEFAULT : WAKE_RF_DISABLED)`, höchstens `ESP.deepSleepMax()`.
  6. **Uhr nachführen:** `Clock::advance` vor jedem `saveState()`, mit den ms seit dem letzten Nachführen. So geht bei einem Reset im Wachsein nur die Zeit seit dem letzten Sichern verloren.
  7. **Nacht-Sitzung (N2):**
     - In `runSession` laufen bei `reason == Night` die Wand-Regeln mit: Radar alle 200 ms, `wallShouldTurnOff` → `turnWallOff`.
     - Tasten beim Start einer Nacht-Sitzung: BT1 geht an die Wand-Regeln (`decideOnBoot`), BT2 an `onButton`, die anderen sind ohne Wirkung.
     - Wechselt der Grund auf HAND (N3), enden die Wand-Regeln, und die Anzeige gehört nach R14 aus Teil 2 dem Pi.
  8. **`QuoteReady`:** Ist die Anzeige an und der Grund NACHT, zeigt der ESP das Zitat sofort aus dem RTC-Speicher, mit `shownIndex = 0` und `shownDate = night.date` (Z11). In einer Sitzung von Hand zeigt er nichts.
  9. **Nach der Sitzung:** Schritt 4 (nachtragen), dann Schritt 5 (entscheiden).
  10. **README:** Nacht, Uhr, Testschalter `NIGHT_TEST`, Einrichtungsportal, neue `MAGIC` (vor dem ersten Flashen die Wand stromlos machen wie in Teil 2).
- [ ] **Step 1:** umsetzen. Die Logik steckt in Tasks 1–4; hier wird nur verdrahtet. **Step 2:** `pio run` → SUCCESS ohne neue Warnungen; `pio test -e native` grün. **Step 3:** Commit `ESP: Nacht-Auftrag, Uhr und Timer-Schlaf in der Application`

### Task 7: Pi – Zitat der Nacht von der KI

**Files:**
- Modify: `rpi/app/night_quote.py` (aus Task 3), `rpi/app/topics.py` (`.thema_zuletzt` lesen und schreiben)
- Test: `rpi/app/tests/test_night_quote.py`, `rpi/app/tests/test_topics.py`

**Interfaces:**
- Produces:
  - `build_night_messages(topic: str, yesterday: str) -> list[dict]`, Systemauftrag wörtlich nach §9 Schritt 3: „Entwickle daraus den nächsten Gedanken. Höchstens 96 Zeichen, auf keinen Fall länger. Nur Buchstaben, Ziffern, Leerzeichen und Punkt, keine Umlaute.“ Die Benutzernachricht ist `Thema: …`, dazu `Gedanke von gestern: …` nur, wenn `yesterday` nicht leer ist.
  - `make_night_quote(yesterday: str, ask, config_dir) -> tuple[str, str]`:
    - liest das Thema mit `read_daily` und vergleicht es mit `.thema_zuletzt`; ist das Thema neu, lässt es `yesterday` weg;
    - fragt höchstens 3-mal und bereinigt jede Antwort mit `clean_quote`;
    - beim ersten Text, der passt (`quote_fits`): `("QUOTE", text)`, und `.thema_zuletzt` = Thema;
    - nach 3 unpassenden Antworten: `("ERROR", "ZU_LANG")`;
    - wenn `ask` wirft oder einen Text liefert, der mit „Fehler“ beginnt: `("ERROR", "KI")` (R9).
  - `topics.read_last_daily(config_dir) -> str` und `topics.save_last_daily(config_dir, topic)`, beide atomar wie `save`.
- [ ] **Step 1: Tests** (feste Antworten statt KI):

  | Test | Prüft |
  |---|---|
  | `test_messages_with_and_without_yesterday` | |
  | `test_new_topic_drops_yesterday` | M2-c |
  | `test_first_fitting_answer_wins_and_topic_is_remembered` | |
  | `test_cleaning_makes_answer_fit` | |
  | `test_three_bad_answers_is_zu_lang` | |
  | `test_ai_error_string_is_ki` ; `test_ai_exception_is_ki` | |
  | `test_failed_night_keeps_last_topic` | R9 |
  | `test_missing_topic_file_uses_default` | |
- [ ] **Step 2:** FAIL. **Step 3:** umsetzen. **Step 4:** grün. **Step 5:** Commit `Pi: Zitat der Nacht von der KI`

### Task 8: Pi – `GET` im Dispatcher und Wechsel von der Nacht ins Menü

**Files:**
- Modify: `rpi/app/ui/link_dispatch.py`, `rpi/app/main.py`
- Test: `rpi/app/ui/tests/test_link_dispatch.py`, `rpi/app/tests/test_main.py` (`WallRun` patcht die KI und nimmt ein temporäres `config_dir`)

**Interfaces:**
- Consumes: `make_night_quote` (Task 7).
- Produces:
  - `LinkDispatcher(..., quote_maker: Callable[[str], tuple[str, str]] = None)`. `GET` mit Daten `QUOTE|<yesterday>`:
    - startet einen Arbeits-Thread mit `quote_maker(yesterday)`;
    - antwortet mit dem Ergebnis an das neueste `GET` (R10);
    - während der Thread läuft, startet ein weiteres `GET` keinen zweiten Thread;
    - Daten ohne `QUOTE|` → `ERROR|BAD_GET`; ohne `quote_maker` → `ERROR|KI`.
  - `SESSION|HAND` nach `NACHT`: `session_reason = "HAND"`, und das neue Event `hand_requested` wird gesetzt (N3). Für alle anderen zweiten `SESSION` gilt die bisherige Regel.
  - `main`:
    - `_night_session(dispatcher, stop, start_menu, released)` wartet auf `stop` oder `hand_requested`; bei `hand_requested` geht es weiter wie `_hand_session`.
    - `_serve_wall` gibt dem Dispatcher `quote_maker = lambda y: make_night_quote(y, write_to_ai, CONFIG_DIR)`, mit einem späten Import von `write_to_ai`.
- [ ] **Step 1: Tests:**

  | Test | Prüft |
  |---|---|
  | `test_get_answers_quote_from_worker` | |
  | `test_get_does_not_block_buttons` | `BUTTON` wird beantwortet, während `quote_maker` noch rechnet |
  | `test_repeated_get_one_worker_answer_to_newest` | Review Focus 4 |
  | `test_get_bad_data` ; `test_get_without_maker_is_ki_error` | |
  | `test_session_hand_after_nacht_sets_hand_requested` | |
  | `test_night_then_hand_starts_menu` (WallRun) | Review Focus 5: `NACHT`, `GET` läuft, `SESSION\|HAND` → Menü erscheint, `GET` wird beantwortet |
  | `test_night_get_and_shutdown` (WallRun) | `NACHT` → `GET` → `QUOTE` → `SHUTDOWN` → `power_off` einmal, Anzeige nie beschrieben |
- [ ] **Step 2:** FAIL. **Step 3:** umsetzen. **Step 4:** grün, ganze Suite grün. **Step 5:** Commit `Pi: GET beantworten, von der Nacht ins Menue`

### Task 9: Dokumente

**Files:**
- Modify: `rpi/README.md` (Nacht, Thema, `.thema_zuletzt`, Fehlercodes), Hauptentwurf §11 (die Felder so, wie sie gebaut sind: `ClockData`, `NightData`; `sessionSeconds` bleibt bei `sessionMs`)

- [ ] **Step 1:** schreiben. **Step 2:** Commit `Doku: Mitternacht in README und Hauptentwurf`

### Task 10: Abnahme am Gerät (offen bis Teil 0)

1. Kaltstart ohne Zugangsdaten → Portal `ReflectionWall` öffnet sich; WLAN eintragen; Abgleich im Log.
2. Build mit `NIGHT_TEST = true` → nach 2 min startet die Nacht: Pi ein, `SESSION|NACHT`, `GET`, `QUOTE`, Pi aus, Zitat vorne in der Liste (BT1 zeigt es), `NightResult Ok` im Log.
3. Dasselbe ohne Internet am Pi → `ERROR|KI`, Pi aus, neuer Versuch um „01:00“ der verschobenen Uhr.
4. Während der Test-Nacht vor der Wand stehen → Wand an; das neue Zitat erscheint sofort (N2, Z11).
5. BT2 während der Test-Nacht → `PI STARTET`, Menü; das Zitat steht danach in der Liste (N3).
6. Nach mehreren Tastendrücken am Abend (Build ohne Test): Abgleich vor Mitternacht im Log, Auftrag um 00:00 (N1).
7. Kaltstart in der Nacht (Review Focus 3) mit einem eigenen Testbuild: `NIGHT_TEST = true` und `NIGHT_TEST_LEAD_S = -5400`. Mit dem Vorlauf von 120 s ginge es nicht, denn ein Stromunterbruch ist ein Kaltstart, und der erste Abgleich danach stellt die Uhr wieder auf 23:58. Mit −5400 zeigt sie nach dem Abgleich 01:30, 90 min nach dem falschen Mitternacht → Auftrag sofort nach dem Start. Die Liste darf dabei keinen Eintrag mit dem falschen Datum einer früheren Testnacht haben; sonst gilt die Nacht als erledigt und läuft nicht.
8. Danach `NIGHT_TEST = false` und `NIGHT_TEST_LEAD_S = 120` flashen.

## Stand nach der Umsetzung (2026-10-31)

### Gebaut

| Task | Was | Commits |
|---|---|---|
| 1 | Ortszeit Zürich aus UTC (`CivilTime`) | 0750568 |
| 2 | Uhr und Weckplan (`Clock`, `WakePlan`); ein später Versuch zählt die verpassten Termine (`markAttempt`) | 694e535, a68df1d |
| 3 | Zitat prüfen, mit gemeinsamen Fällen für ESP und Pi | bdf6118 |
| 4 | `PiSession` holt das Zitat der Nacht (`GET`, N2, N3) | 00edbec |
| 5 | Uhr und Nacht im RTC-Speicher, Weckgrund ohne Radar, `TimeSync` | d5f3c78 |
| 6 | Nacht-Auftrag, Uhr und Timer-Schlaf in der `Application`; README; Nachbesserung nach der Prüfung | 09f3995, cfdfa28, b2cb44f |
| 7 | Zitat der Nacht von der KI (`make_night_quote`) | 0ddce50 |
| 8 | `GET` auf dem Pi; von der Nacht ins Menü | d1057b1 |
| 9 | README und Hauptentwurf | 9c42def |
| 10 | Abnahme am Gerät | offen bis Teil 0 |
| Abschluss | Korrekturen aus der Schlussprüfung: N3 in der Reihenfolge des Geräts getestet, auf beiden Seiten (I1); der Pi merkt das Zitat, bis es zugestellt ist (Fall C); „Leere Antwort“ ist ein Fehler der KI (I2); das Zitat gilt, auch wenn `.thema_zuletzt` nicht geschrieben werden kann (M5); `NIGHT_TEST_LEAD_S` mit Vorzeichen (M6); zwei Werte in §12 (M8); Entscheid B zu M4; kleinere Punkte aus Task 7 und 8 | 528536e, d29b173, 3d7274a und der Commit mit dieser Zeile |

### Entscheide während der Umsetzung

Jeder Entscheid sagt, was gilt, und was es kostet, wenn er falsch ist.

- **Reihenfolge der Tasks:** 1, 2, 3, 5, 4, 6, 7, 8, 9. Task 5 bringt `_state.night`; erst danach kann Task 4 den Konstruktor von `PiSession` ändern, ohne den Build für esp12e zu brechen. Kostet: nichts.
- **`WAKE_RF_ENABLED` bis Task 6:** Task 5 bringt die neuen Schalter, Task 6 entfernt den alten mit seiner letzten Verwendung. Kostet: eine veraltete Konstante für einen Task.
- **`markAttempt`:** Eine neue Nacht setzt Status, Versuche, Ablehnungen und Ergebnis zurück und setzt das Datum auf heute. Ein später Versuch verbraucht die Termine, die schon vorbei sind (§9). Kostet: ein Helfer und seine Tests.
- **`markAttempt` nur bei einem neuen Versuch:** Die `Application` ruft es auf `StartNight` nur, wenn das Datum neu ist oder der Status Idle oder Failed. Kostet: sonst ein falsch gezählter Versuch.
- **Zitat, das noch geschrieben werden muss:** Steht es noch aus, wenn die nächste Nacht beginnt, schreibt der ESP es zuerst. Scheitert das wieder, fällt der Versuch dieser Nacht aus (`StoreFailed`), damit das alte Zitat nicht überschrieben wird. Geschrieben wird mit dem Datum seiner eigenen Nacht (`doneDate`). In einer Sitzung von Hand wartet das bis zu ihrem Ende. Kostet: Ein kaputtes FRAM kostet Nächte, bis es repariert ist; eine Sitzung über 03:00 verliert dann die Nacht.
- **Abgleich höchstens 14 s:** So bleiben Verbinden, NTP und Ausschalten in den 15 s von M3-a. Kostet: eine Sekunde weniger für einen langsamen Router.
- **Text vom Vortag:** Nur ein Listeneintrag, der `QuoteCheck::acceptable` besteht, wird zu `yesterday`; sonst beginnt eine neue Kette. Kostet: eine abgebrochene Kette nach einem Eintrag von Hand mit Umlaut.
- **BT2 in der Nacht im Radar-Debug:** nichts. Der Zustand kommt in der Nacht nicht vor. Kostet: nichts.
- **Abgleich während einer Sitzung:** Nur, wenn die Uhr gültig ist und die Sitzung den Auftrag der Nacht jetzt annähme. Sonst wartet der Abgleich bis nach der Sitzung. Kostet: Der Versuch um 00:00 in einer Sitzung von Hand gleicht ein paar Sekunden später ab.
- **5 s Pause:** Der Pi bleibt mindestens 5 s aus, bevor der ESP ihn für einen Versuch wieder einschaltet (`PI_MIN_OFF_MS`, vorläufig). Kostet: 5 s späterer Start eines Versuchs gleich nach einer Sitzung.
- **Nachbesserung von Task 6:** Die Runde nahm fünf kleine Punkte der Prüfung mit, weil sie denselben Code betrafen. Kostet: nichts.
- **Task 9 auch für das README des Repos** (Owner, 2026-10-31). Kostet: eine Datei mehr im Commit.
- **I1, BT2 in der Nacht:** Jede Taste setzt den ESP zurück. Ein offenes `GET` verfällt, `SESSION|HAND` geht zuerst, dann das `GET` noch einmal mit neuer Nummer. Die Tests auf beiden Seiten folgen jetzt dieser Reihenfolge, auf dem Pi mit dem echten `PiLink`. Die angenommenen Kosten „kein `BUTTON` und kein `PING`, solange `GET` offen ist“ fallen auf dem Gerät nie an. Kostet: nichts, das sichtbare Verhalten bleibt.
- **I1, Fall C:** Der Pi merkt sich das Zitat mit seinem Text vom Vortag, bis es zugestellt ist. Nimmt `PiLink` die Antwort nicht an, weil schon eine neuere Anfrage da ist, bekommt das `GET`, das danach kommt, dieses Zitat, ohne zweite KI-Runde. Ist die Antwort zugestellt (der ESP lehnt das Zitat ab, oder ein Reset kam, während sie auf der Leitung war), rechnet ein späteres `GET` neu, wie vorher. Ein `ERROR` merkt er sich nie: ein späterer Versuch in derselben Sitzung fragt neu. Mit `SHUTDOWN` verfällt das Zitat ebenfalls. Kostet: ein gemerkter Text, bis er zugestellt ist.
- **I2:** „Leere Antwort“ von `write_to_ai` gilt wie „Fehler…“ als `ERROR|KI`. Die Chat-Anwendung behält diesen Text. Kostet: nichts.
- **I3:** nicht in dieser Runde, siehe „Technische Schuld“. Kostet: Ein Fehler in diesen Regeln fällt erst in Task 10 oder in der späteren Runde auf.
- **M5, M6, M8 und die kleinen Punkte aus Task 7 und 8:** in der Runde der Schlussprüfung. Jeder ist klein.
- **M1:** wartet auf die Abnahme am Gerät, denn die 5 s sind vorläufig. Startet der Pi nach einer kurzen Pause nicht, kommt die Zeit des letzten Ausschaltens in den RTC-Speicher. Kostet: ein verlorener Termin nach einem Reset durch BT2.
- **M2, M3, M7:** bleiben offen (unten).

### Entscheid B des Owners zu M4 (2026-10-31)

Kennt der ESP die Zeit nicht, gleicht er nur nach einem Kaltstart oder einem Timer-Wecken ab, nie nach einer Taste. So steht es schon in §9 des Hauptentwurfs („bei jedem Timer-Weckvorgang (höchstens alle 3 h)“); die Zeile M3-a sagt es jetzt auch. Nach einer Taste schläft der Durchlauf am Ende 3 h mit Funk, wie nach einem gescheiterten Abgleich, und das nächste Timer-Wecken gleicht ab. Die Regel steht in `WakePlan::decide` (`earlyWake`), mit nativem Test. Der Abgleich nach dem Kaltstart, das Portal und der frische Abgleich um Mitternacht (R2) bleiben, wie sie sind.

### Technische Schuld (I3)

Die Regeln der Nacht, die vor Datenverlust schützen, stehen in `application.cpp` ohne nativen Test:

- `syncWaitsForSession` mit dem probeweisen `markAttempt` und dem Zurücksetzen danach;
- `beginNightAttempt`: zuerst das ausstehende Schreiben, `StoreFailed` lässt die Nacht aus, Zurücksetzen, wenn die Sitzung den Auftrag nicht annimmt;
- nach einem Kaltstart das `doneDate` aus `list.at(0).date`;
- `writePendingQuote`: kein Eintrag doppelt, ein spätes Gelingen setzt `StoreFailed` auf `Ok` zurück;
- die Reihenfolge von `resume` und `handleInput` (I1).

Jeder Zweig ist heute richtig, das Risiko ist ein späterer Fehler. Geplant: ein reiner `NightRunner` in `lib/core`, mit Uhr, Daten der Nacht, einer Sicht auf die Sitzung und dem Ergebnis des Speichers als Eingang und Aktionen als Ausgang, und mit nativen Tests für die Fälle oben.

### Offen

**Aus der Schlussprüfung**

- M1: Die 5 s Pause gilt nur innerhalb eines Durchlaufs. Jede Taste setzt den ESP zurück, darum gilt sie für eine Sitzung mit BT2 nicht (anders als eine frühere Notiz zu Task 6 sagte). Auch der Lauf um 00:00 nach einer Sitzung kurz davor schaltet den Pi ohne Pause ein. Siehe den Entscheid oben.
- M2: Geht eine Antwort verloren (ein Reset, während sie auf der Leitung ist, die Frist von 120 s, ein Stromausfall vor dem Schreiben), ist `.thema_zuletzt` schon geschrieben. Ein späterer Versuch mit neuem Thema setzt dann die alte Kette fort. Fall C deckt der gemerkte Text jetzt ab.
- M3: BT2 in der Nacht, nachdem die Antwort da ist, tut 30–40 s lang nichts und zeigt nichts. Man muss nach dem Ausschalten noch einmal drücken.
- M7: Ist das Internet weg, das WLAN aber da, kann `ERROR|KI` nach der Frist von 120 s kommen. Die Nacht steht dann als `NoAnswer` im Log, als hinge der Pi.

**ESP**

- `CivilTime.cpp:117`: Der Zweig, der nie erreicht wird, gibt `utc` zurück; ein Assert oder ein Kommentar fehlt.
- Keine Tests für den Jahreswechsel um Mitternacht Ortszeit, für Jahre nahe 2100 und für ein Jahr, dessen letzter Tag im März oder Oktober ein Sonntag ist. Ein Literal in `test_main.cpp:242` liest sich schwer.
- Die Grenze von 900 s in `freshSync` ist nicht getestet. `MAX_ATTEMPTS` zählt zugleich die Termine einer Nacht. Die Bedingung von `markAttempt` (Uhr gültig) steht nirgends. Die Suite prüft keine absolute Zeit.
- Ein Text nur aus Leerzeichen besteht die Prüfung auf beiden Seiten und bliebe auf der Anzeige leer. Es fehlt ein Fall mit Leerzeichen am Ende. Zwei Fälle heissen unpassend oder doppelt (`only_space_ok_chars`, `sharp_s`).
- `TimeSync`: `sync()` überzieht um etwa 50 ms, `portal()` um bis zu 15 s. `persistent(false)` bleibt global gesetzt. `<string.h>` für `memset` fehlt.
- `PiSession`: kein `static_assert`, dass `date` und `doneDate` gleich gross sind; ein überdecktes `n` in `test_button_queue_holds_six_then_logs`; der Schritt `onQuote` in der Nacht ist nicht als frei von Anzeige-Aktionen geprüft; einige Prüfungen sind schwach; das harte Aus nach 10 min `BUSY` bei Wanted ist ungetestet.
- `RestartWithRadio` in einer Sitzung von Hand liest den Expander ohne Flanke an INT; Regel B warnt den Pi dann nicht, und eine abgeschnittene Übertragung wiederholt der Pi.
- BT1 in der Nacht zwischen `QuoteReady` und dem Schreiben zeigt Eintrag 1. Ein Absturz vor dem ersten Sichern zählt `plannedS` doppelt. Der Rückfall von 600 s wird nie erreicht. Pro Sitzung steht eine Zeile der Nacht zu viel im Log.
- Ein spätes Zurücksetzen von `StoreFailed` auf `Ok` kann im Log `Ok` mit dem Status Failed der neuen Nacht zeigen (nur im Log).

**Pi**

- Kein Test für eine Antwort der KI, die kein Text ist. `startswith("Fehler")` fängt auch ein echtes Zitat, das mit „Fehler“ beginnt.
- `night_quote.py`: Ein Docstring sagt „kuerzen“; die erlaubten Zeichen stehen zweimal da.
- `PiLink.reply` gibt nur `False` zurück. Das Log einer abgelehnten Antwort nennt darum alle drei möglichen Gründe, nicht den einen.

**Anleitung**

- `README.md:29` vereinfacht, wem der Bus in einer Sitzung von Hand gehört: Der ESP schreibt dort auch seine eigenen Texte (`esp/README.md:78`).

### Prüfen am Gerät (Task 10)

- Die Pause von 5 s (M1): Startet ein Pi 5 im Halt nach 5 s wieder, und nach einer Pause von wenigen Millisekunden?
- Ist der Funk nach einem Reset von aussen da, während der ESP wach ist (`clock.radio`)?
- Der Kaltstart um 01:30 mit dem Testbuild (`NIGHT_TEST_LEAD_S = -5400`, Schritt 7).
