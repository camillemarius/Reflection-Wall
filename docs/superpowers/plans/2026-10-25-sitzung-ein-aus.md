# Teil 2: Ein- und Ausschalten des Pi, mit der ESP-Seite von Teil 4 – Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Der ESP führt eine Sitzung mit dem Pi. BT2 schaltet ein, der Pi meldet `READY`, bekommt `SESSION|HAND` und zeigt das Menü. Die Tasten kommen als `BUTTON|n` an. BT2, `DONE` oder ein hängender Pi beenden die Sitzung, sauber oder hart. Der Pi läuft als Dienst, fährt sich auf Anfrage herunter und hält sich an Regel B für den I²C-Bus.

**Architecture:** Auf dem ESP kommt eine reine Zustandsmaschine `PiSession` dazu (C++ ohne Arduino, in `esp/lib/core`). Sie bekommt Tasten, Ereignisse der Verbindung und die verstrichene Zeit. Zurück gibt sie Aktionen: Speisung, Nachricht, Antwort, Anzeigetext. Ihr Zustand liegt im RTC-Speicher und übersteht jeden Reset. `Application` führt die Aktionen aus und bleibt wach, solange eine Sitzung läuft. Auf dem Pi bekommt `app.main` einen Dienst-Ablauf: `READY` senden bis `OK`, auf `SESSION` warten, dann das Menü zeigen (HAND) oder die Anzeige nicht anfassen (NACHT). `SHUTDOWN` fährt den Pi herunter. Ein `BusGuard` setzt Regel B um.

**Tech Stack:** ESP8266, PlatformIO, C++14, Unity (native); Python 3, `unittest`, lgpio, smbus2, systemd.

**Spec:** `docs/superpowers/specs/2026-10-19-esp-pi-steuerung-design.md` (§6 Protokoll, §7 Sitzung, §10 Tasten und Regel B, §11 Zustand, §12 Fristen, §13 Fehler; Entscheide L1–L4). Für die ESP-Seite von Teil 4 gilt zusätzlich `docs/superpowers/specs/2026-10-23-menue-und-anwendungen-design.md` (F1, F2, F3 mit Tabelle 5.2, V1, D18, §9.4, §10).

## Global Constraints

- Branch `feature/sitzung-ein-aus`. Nicht pushen, nichts aufs Gerät laden.
- **Commits ohne Zuschreibung:** keine Zeile `Co-Authored-By`, kein „Generated with“. Betreff auf Deutsch, in ASCII (`ae`, `oe`, `ue`). Geänderte Dateien beim Namen stagen. Nie `git add -A` oder `git add .`, denn der Ordner `.superpowers/` ist nicht ignoriert.
- ESP-Tests: `cd esp && pio test -e native` (MinGW-GCC 6.3, nur C++14). Ist ein Pfad länger als 260 Zeichen, in `%TEMP%\fpb` bauen. ESP-Build: `cd esp && pio run`.
- Python-Tests: `cd rpi && "C:\Users\cross-INGCamilleChat\.venvs\reflection-wall-rpi\Scripts\python.exe" -m unittest discover -s app -t .`. Die Ausgabe enthält keine Tracebacks. `test_imports` bleibt grün: Beim Import wird weder `smbus2` noch `lgpio` geladen.
- Wer einen Testlauf startet, beendet nur diesen eigenen Lauf. Nie alle `python.exe` beenden.
- Die Logik des ESP steht in `esp/lib/core`, ohne Arduino-Typen. Zeit, Port und Pin kommen als Parameter oder Schnittstelle.
- Neue Nachricht `SESSION` (ESP → Pi), Daten `HAND` oder `NACHT`, Antwort `OK`, Frist 3 s. Rolle „ESP-Anfrage“ auf beiden Seiten.
- Fristen und Startwerte (Spec §12). `T_halt` wird bei der Abnahme gemessen.

  | Name | Wert |
  |---|---|
  | `T_boot` (Einschalten bis `READY`) | 120 000 ms |
  | PING-Abstand im Betrieb | 10 000 ms |
  | PING-Aussetzer bis hart aus | 3 |
  | `T_shutdown` (Frist von `SHUTDOWN`) | 60 000 ms (steht schon im Codec) |
  | BUSY-Wiederholung | 30 000 ms |
  | BUSY höchstens (ab Eintritt in HERUNTERFAHREN) | 600 000 ms |
  | `T_halt` (nach `OK` bis Speisung aus) | 30 000 ms, Startwert |
  | Radar-Debug höchstens | 3 600 000 ms |
  | `PI ANTWORTET NICHT` sichtbar (D18) | 10 000 ms |
  | `T_bus_frei` (Pi nach INT_GPIO_EXP HIGH) | 5 ms |
  | Pi-Pause nach steigender INT_HLK-Flanke (R3) | 250 ms, Startwert |
  | Längstes Warten des Pi auf den Bus (R3) | 1 000 ms |

- Anzeigetexte des ESP: `PI STARTET`, `PI FAEHRT HERUNTER`, `PI ANTWORTET NICHT`. Sie gehen über `Display::show` und werden wie ein Zitat gesetzt (R11). Bei einer Sitzung `NACHT` fasst der ESP die Anzeige nicht an (V1).
- Tasten am ESP je Zustand (Teil-4-Spec, Tabelle 5.2):

  | Zustand | BT2 | BT1, BT3 | BT4–BT6 |
  |---|---|---|---|
  | AUS | Sitzung HAND starten | wie heute (§8, Verbindungstest) | nichts |
  | EINSCHALTEN | merken; nach `READY` sofort herunterfahren | nichts | nichts |
  | BETRIEB | `SHUTDOWN` | `BUTTON\|n` | `BUTTON\|n` |
  | RADAR-DEBUG | merken | nichts | nichts |
  | HERUNTERFAHREN, HALT-WARTEN | nichts | nichts | nichts |

- Anfragen des Pi je Zustand (aus Spec §6.2, §7 und R8, R12):

  | Anfrage | EINSCHALTEN | BETRIEB | RADAR-DEBUG | HERUNTERFAHREN, HALT-WARTEN |
  |---|---|---|---|---|
  | `READY` | `OK`; dann `SESSION` → BETRIEB, oder bei gemerktem BT2 → HERUNTERFAHREN (R9) | `OK`, `SESSION` noch einmal (L3) | `OK`, `SESSION` noch einmal → BETRIEB, oder bei gemerktem BT2 → HERUNTERFAHREN | `OK` |
  | `DONE` | `OK` | `OK` → HERUNTERFAHREN | `OK` → HERUNTERFAHREN | `OK` |
  | `MODE\|RADAR` | `ERROR\|STATE` | `OK` → RADAR-DEBUG | `OK` | `ERROR\|STATE` |
  | `MODE\|NORMAL` | `OK` | `OK` | `OK` → BETRIEB, oder bei gemerktem BT2 → HERUNTERFAHREN | `OK` |

## Was dieser Plan entscheidet (Rulings)

Jeder Eintrag sagt, was gilt, warum, und was es kostet, wenn er falsch ist.

- **R1 Zeit:** Die Sitzung misst Zeit als „seit dem Eintritt verstrichene ms“. `Application` führt diese Zeit bei jedem Takt aus `millis()` nach. Die Zeit eines Resets (etwa 0,1–0,3 s) geht verloren. Genauer ginge es nur mit einer Uhr, die es nicht gibt.
- **R2 Eine Anfrage zur Zeit:** Eine eigene Nachricht geht nur raus, wenn keine eigene Anfrage offen ist (Spec §6.2). Was warten muss, merkt sich die Sitzung: `SESSION` und `SHUTDOWN` als Flag, Tasten in einer Warteschlange für bis zu 6 Tasten. Gesendet wird nur in `onTick`, in dieser Reihenfolge: `SESSION`, `SHUTDOWN`, `BUTTON`, `PING`. Kostet: Eine Taste kann bis zu 3 s warten, wenn gerade ein `PING` läuft.
- **R3 Regel B nach einer Radar-Flanke:** Nach einer Radar-Flanke bleibt INT_GPIO_EXP HIGH, während der ESP neu startet und 60–100 ms später den Bus nimmt. Die Spec-Regel „warten, bis INT_GPIO_EXP HIGH ist“ hält den Pi dann nicht auf. Der Pi pausiert deshalb nach einer steigenden INT_HLK-Flanke 250 ms. Länger als 1 s wartet er nie, danach schreibt er mit einer Warnung im Log. Kostet: zwei Zahlen, die die Abnahme misst.
- **R4 D18 nur bei HAND:** `PI ANTWORTET NICHT` erscheint nur in einer Sitzung HAND, nach fehlendem `READY` oder nach drei `PING`-Aussetzern. Ein hartes Aus nach `T_shutdown` oder nach 10 min BUSY zeigt keinen Text. Die Anzeige geht dann nur aus, mit Eintrag im Log. In der Nacht bleibt die Wand dunkel (V1).
- **R5 Anzeige erst nach `SESSION|HAND`:** Der Pi startet die Anzeige (`WallDisplay.start()` schreibt schon) erst, wenn `SESSION|HAND` da ist. Vorher gehört sie dem ESP (`PI STARTET`).
- **R6 Herunterfahren:** Der Pi ruft `sudo -n /usr/bin/systemctl poweroff`. Die sudoers-Regel dafür richtet Teil 0 ein; die README nennt sie.
- **R7 Kein PING in EINSCHALTEN:** Die Zeichnung in Spec §7 zeigt dort „PING wiederholt“. Seit L1 wiederholt der Pi `READY` selbst, und `T_boot` fängt einen Pi ab, der nie meldet. Ein PING an einen Pi, der noch bootet, bringt nichts. Kostet nichts an Funktion; die Zeichnung wird beim Abschluss nachgeführt.
- **R8 Anfrage, die ein Reset abbricht:** Nach einem Reset ist eine eigene Anfrage weg (`PiLink` startet leer). Die Sitzung weiss aus `awaiting`, welche es war. `SESSION` und `SHUTDOWN` gehen noch einmal raus, mit neuer Nummer. Der Pi verarbeitet beide doppelt ohne Schaden. Ein abgebrochenes `PING` zählt nicht als Aussetzer. Ein abgebrochenes `BUTTON` wird nicht wiederholt, nur geloggt: Es hat den Pi fast immer schon erreicht, und eine Wiederholung würde doppelt drücken. Umgekehrt kennt `PiLink` nach einem Reset seine letzte Antwort nicht mehr. Wiederholt der Pi eine Anfrage, die der ESP vor dem Reset beantwortet hat, meldet `PiLink` sie deshalb noch einmal. Die Sitzung beantwortet jede Anfrage des Pi so, dass eine zweite nichts ändert (Tabelle oben). Kostet: In seltenen Fällen geht ein `BUTTON` verloren, wenn der Reset die Zeile abschnitt, bevor der Pi sie las.
- **R9 BT2 während EINSCHALTEN:** Nach `READY` schickt der ESP gleich `SHUTDOWN`, ohne `SESSION`. So blitzt das Menü nicht kurz auf. F1 sagt „in jedem Fall“ und meint damit beide Startgründe. Kostet: Der Pi muss `SHUTDOWN` auch vor `SESSION` verarbeiten (Test in Task 9).
- **R10 Nach der Sitzung:** Ist die Sitzung zu Ende, schläft der ESP sofort. Die Wand bleibt dunkel, bis die nächste Radar-Flanke oder BT1 §8 auslöst (V1: „danach dunkel“). Kostet: Wer nach dem Ausschalten vor der Wand stehen bleibt, sieht kein Zitat, bis er sich bewegt.
- **R11 Texte wie ein Zitat:** Die drei Anzeigetexte gehen über `Display::show` und werden wie ein Zitat gesetzt. Dafür braucht es keine neue Schnittstelle zur Anzeige. Kostet: Die Texte stehen oben links statt mittig.
- **R12 `MODE|RADAR` ausserhalb von BETRIEB:** Der ESP antwortet `ERROR|STATE`. Der Pi schaltet dann nicht um (Spec §6.2). Ein `OK` in HERUNTERFAHREN würde den Pi auf 115 200 Baud schicken, und das `SHUTDOWN` käme nie an.
- **R13 GPIO22 gehört dem `BusGuard`:** lgpio kann eine Leitung in einem Prozess nur einmal belegen. Der `BusGuard` belegt GPIO4 und GPIO22 und bietet `radar_high()` an. `Activity` liest die Anwesenheit dort statt über `RadarPresence`.
- **R14 Bus in der Sitzung:** Der ESP hält den I²C-Bus heute bis zum Deep Sleep (`enterDeepSleep` gibt ihn frei). In einer Sitzung gibt er ihn gleich nach dem Lesen des Expanders frei. Er nimmt ihn nur für seine eigenen Anzeige-Aktionen. Die kommen nur vor, wenn der Pi nicht schreibt: in EINSCHALTEN, nach `OK` auf `SHUTDOWN` und nach einem harten Aus.
- **R15 Radar endet nach 55 min** (während Task 3 entschieden, vom Owner bestätigt am 2026-10-25): Die Anwendung Radar des Pi endet nach 55 min von selbst. Der Pi schaltet zurück (`MODE|NORMAL`) und schickt `DONE`. Die 60 min des ESP bleiben als Rückfall für einen Pi, der im Radar-Debug hängt (Spec §13). Grund: V6 will nach 60 min Radar ein Herunterfahren. Im Radar-Modus gehört die UART aber dem Radar, ein `SHUTDOWN` des ESP käme nie an. Der Pi muss den Modus also selbst verlassen. Die 5 min Abstand decken eine Uhr des ESP, die nach Resets nachgeht (R1). Kostet: Eine Sitzung mit Radar endet nach 55 statt 60 min. Die Zahl kann der Owner ändern.

## Review Focus

1. **Reset mitten in der Sitzung** (Taste, Radar): Der ESP kommt im selben Zustand mit denselben Zählern und Nummern zurück. Er schaltet die Speisung nicht noch einmal und behandelt eine abgebrochene Anfrage nach R8. Tests in Task 2 und Task 3.
2. **Der Pi-Dienst startet neu** (wieder Nummer `00`): `READY` wird trotzdem verarbeitet, und der ESP schickt `SESSION` noch einmal (L3), auch aus RADAR-DEBUG. Tests in Task 2 und Task 3.
3. **`SHUTDOWN`, während eine eigene Anfrage offen ist** (ein `PING` läuft): `SHUTDOWN` geht raus, sobald die Leitung frei ist, und keine Frist läuft doppelt. Test in Task 3.
4. **Der Pi schreibt die Anzeige nie vor `SESSION|HAND` und nie nach seinem `OK` auf `SHUTDOWN`.** Er fährt auch herunter, wenn `SHUTDOWN` vor `SESSION` kommt (R9). Tests in Task 9.
5. **Regel B ohne Radar** (INT_HLK fest LOW) **und mit hängendem INT_GPIO_EXP** (bleibt LOW): Der Pi wartet höchstens 1 s und schreibt dann trotzdem, mit Eintrag im Log. Test in Task 8.

---

### Task 1: `SESSION` im Protokoll beider Seiten

**Files:**
- Modify: `tests/protocol_vectors.json`
- Modify: `esp/lib/core/src/LinkCodec.cpp:129-138` (`roleOf`)
- Modify: `rpi/app/link/codec.py:11` (`_ESP_REQUESTS`)
- Test: `esp/test/test_link_codec/test_main.cpp` und `rpi/app/link/tests/test_codec.py` lesen die Vektoren schon. Nur ändern, falls eine Suite die Anzahl der Vektoren fest prüft.

**Interfaces:**
- Produces: `roleOf("SESSION") == Role::EspRequest` und `deadlineMs("SESSION") == 3000`; in Python `role_of("SESSION") == "esp_request"`.

- [ ] **Step 1: Vektoren ergänzen**, an der passenden Stelle der Liste `vectors` (Datei mit LF):
  ```json
  {"name": "cmd_session", "kind": "command", "command": "SESSION", "role": "esp_request", "deadline_ms": 3000},
  {"name": "session_hand", "kind": "both", "line": "$00:SESSION|HAND*1B", "seq": 0, "command": "SESSION", "data": "HAND"},
  {"name": "session_nacht", "kind": "both", "line": "$01:SESSION|NACHT*49", "seq": 1, "command": "SESSION", "data": "NACHT"}
  ```
- [ ] **Step 2:** Beide Suiten laufen lassen. Erwartet: FAIL bei `cmd_session` (Rolle `unknown`).
- [ ] **Step 3:** `SESSION` auf beiden Seiten als ESP-Anfrage eintragen.
- [ ] **Step 4:** Beide Suiten grün.
- [ ] **Step 5:** Commit `Protokoll: neue Nachricht SESSION (ESP an Pi)`

### Task 2: `PiLink` auf dem ESP: `READY` nie als Wiederholung, und nach einem Reset neu melden

**Files:**
- Modify: `esp/lib/core/src/PiLink.cpp:63-67` (Erkennung doppelter Pi-Anfragen in `handleLine`)
- Test: `esp/test/test_pi_link/test_main.cpp`

**Interfaces:**
- Produces: Kommt eine Pi-Anfrage mit der zuletzt empfangenen Nummer, gilt:
  - Ist sie `READY`: wird sie als `Request` gemeldet wie eine neue (L3).
  - Ist sie gemeldet, aber noch nicht beantwortet: wird sie verworfen (wie heute).
  - Ist die letzte Antwort bekannt: wird diese noch einmal gesendet (wie heute).
  - Ist keine Antwort bekannt (nach `restore`): wird sie als `Request` gemeldet (R8).

- [ ] **Step 1: Tests schreiben**
  - `test_ready_with_same_number_is_reported_again`: `$00:READY` empfangen, mit `OK` beantworten, `$00:READY` noch einmal → beide Male `Kind::Request`, und jedes Mal genau eine `OK`-Zeile auf dem Port.
  - `test_done_with_same_number_is_still_a_duplicate`: `$01:DONE`, `reply("OK")`, `$01:DONE` noch einmal → das zweite Mal `Kind::None`, und die alte Antwortzeile steht noch einmal auf dem Port.
  - `test_repeat_after_restore_is_reported_again`: `restore({txSeq 5, rxSeq 1, rxValid true})`, dann `$01:DONE` → `Kind::Request`.
- [ ] **Step 2:** `pio test -e native -f test_pi_link`. Erwartet: FAIL beim ersten und dritten Test.
- [ ] **Step 3:** Umsetzen.
- [ ] **Step 4:** Die Suite ist grün, die ganze native Suite auch.
- [ ] **Step 5:** Commit `PiLink: READY nie als Wiederholung, nach Reset neu melden`

### Task 3: Zustandsmaschine `PiSession`

**Files:**
- Create: `esp/lib/core/src/PiSession.h`, `esp/lib/core/src/PiSession.cpp`
- Test: `esp/test/test_pi_session/test_main.cpp`

**Interfaces:**
- Consumes: `LinkEvent`, `LinkCodec::Message` aus `PiLink.h`.
- Produces:
  ```cpp
  enum class SessionState : uint8_t { Off = 0, Starting = 1, Running = 2, RadarDebug = 3, ShuttingDown = 4, Halting = 5 };
  enum class StartReason : uint8_t { Hand = 0, Night = 1 };
  enum class Awaiting : uint8_t { None = 0, Ping = 1, Session = 2, Shutdown = 3, Button = 4 };

  // Liegt im RTC-Speicher (Task 4): nur feste Typen, die Zahlenwerte der enums bleiben.
  struct SessionData {
      SessionState state;  StartReason reason;  Awaiting awaiting;  uint8_t flags;
      uint8_t missedPings;  uint8_t buttonCount;  uint8_t buttons[6];   // Warteschlange (R2)
      uint32_t inStateMs;    // T_boot, T_halt, 60 min Radar, 10 min BUSY, 10 s Text (D18)
      uint32_t sincePingMs;
      uint32_t sinceBusyMs;
      uint32_t sessionMs;    // nur fürs Log (Spec §11 sessionSeconds)
  };
  static_assert(sizeof(SessionData) == 28, "SessionData liegt im RTC-Speicher");
  namespace SessionFlag { constexpr uint8_t PendingShutdown = 1, NeedSession = 2, NeedShutdown = 4, ShowingNoAnswer = 8; }

  struct SessionAction {
      enum class Kind { PowerOn, PowerOff, Send, Reply, Show, DisplayOff, Log };
      Kind kind;
      std::string command;   // Send/Reply: Befehl; Show/Log: der Text
      std::string data;      // Send/Reply: Daten
  };

  namespace SessionTiming { /* die Werte aus den Global Constraints als constexpr unsigned long */ }

  class PiSession {
  public:
      explicit PiSession(SessionData& data);
      static void reset(SessionData& data);                  // Kaltstart: Off, alles 0
      bool active() const;                                   // nicht Off, oder PI ANTWORTET NICHT noch sichtbar
      void resume(std::vector<SessionAction>& out);          // einmal nach jedem Reset, wenn active() (R8)
      void startHand(std::vector<SessionAction>& out);       // BT2 im Zustand Off
      void startNight(std::vector<SessionAction>& out);      // für Teil 3b, hier nur getestet
      void onButton(int button, std::vector<SessionAction>& out);           // Tabelle 5.2, ausser Off
      void onLink(const LinkEvent& event, std::vector<SessionAction>& out); // Antworten sofort als Reply
      void onTick(unsigned long elapsedMs, bool linkBusy, std::vector<SessionAction>& out);  // nur hier Send
  };
  ```
- Verhalten (Spec §7, §6.2, F1–F3, V1, D18, L1–L3, R1, R2, R4, R7–R9, R12; die zwei Tabellen in den Global Constraints sind verbindlich):
  - **Starting:** Beim Eintritt `PowerOn`, bei HAND zusätzlich `Show "PI STARTET"`. Kein `PING` (R7). Auf `READY` siehe Tabelle. Nach `T_boot` ohne `READY` folgt ein hartes Aus mit Text.
  - **Running:** Ein `PING` geht raus, wenn `sincePingMs ≥ 10 000` und die Leitung frei ist; dabei wird `sincePingMs` auf 0 gesetzt. Jede Antwort auf `PING` setzt `missedPings` auf 0. Ein abgelaufenes `PING` zählt als Aussetzer; beim dritten folgt ein hartes Aus mit Text. Ist die Leitung belegt, wartet `PING` (L2). Ein abgelaufenes `SESSION` oder eine Antwort ausser `OK` darauf → ShuttingDown. Ein abgelaufenes `BUTTON` wird nur geloggt.
  - **RadarDebug:** Kein `PING`. Nach 60 min → ShuttingDown.
  - **ShuttingDown:** Beim Eintritt `NeedShutdown` setzen; die Warteschlange der Tasten leeren. Auf `OK` → Halting, bei HAND `Show "PI FAEHRT HERUNTER"`. Auf `BUSY` oder eine andere Antwort wird `SHUTDOWN` nach 30 s noch einmal gesendet. Läuft `SHUTDOWN` ab, oder sind seit dem Eintritt 10 min vergangen, folgt ein hartes Aus ohne Text.
  - **Halting:** Nach `T_halt` `PowerOff`, bei HAND auch `DisplayOff`, dann → Off.
  - **Hart aus:** `PowerOff` und `Log` mit Grund. Mit Text (nur HAND, R4): `Show "PI ANTWORTET NICHT"`, nach 10 s `DisplayOff`. Bis dahin ist `active()` wahr. Ohne Text: bei HAND gleich `DisplayOff`, bei NACHT nichts an der Anzeige.
  - **resume (R8):** `awaiting` Session → `NeedSession`, Shutdown → `NeedShutdown`, Ping → nichts, Button → `Log`. Danach `awaiting = None`.
  - **Tasten** nach Tabelle 5.2. In Running reihen BT1 und BT3–BT6 sich in die Warteschlange ein; ist sie voll, folgt `Log`.
  - **sessionMs** zählt über die ganze Sitzung. Beim Übergang nach Off kommt `Log` mit der Dauer.

- [ ] **Step 1: Tests schreiben.** Hilfen und zwei ausgeschriebene Tests legen das Muster fest:
  ```cpp
  static SessionData d;
  static std::vector<SessionAction> out;
  static LinkEvent ev(LinkEvent::Kind k, const char* cmd, const char* data = "") {
      LinkEvent e; e.kind = k; e.message.command = cmd; e.message.data = data; return e; }
  static bool has(SessionAction::Kind k, const std::string& c = "", const std::string& v = "") {
      for (const auto& a : out) if (a.kind == k && (c.empty() || a.command == c) && (v.empty() || a.data == v)) return true;
      return false; }
  void setUp() { PiSession::reset(d); out.clear(); }

  void test_ready_replies_ok_then_tick_sends_session_hand() {
      PiSession s(d); s.startHand(out);
      TEST_ASSERT_TRUE(has(SessionAction::Kind::PowerOn));
      TEST_ASSERT_TRUE(has(SessionAction::Kind::Show, "PI STARTET"));
      out.clear(); s.onLink(ev(LinkEvent::Kind::Request, "READY"), out);
      TEST_ASSERT_TRUE(has(SessionAction::Kind::Reply, "OK"));
      out.clear(); s.onTick(0, false, out);
      TEST_ASSERT_TRUE(has(SessionAction::Kind::Send, "SESSION", "HAND"));
      TEST_ASSERT_EQUAL(static_cast<int>(SessionState::Running), static_cast<int>(d.state));
  }

  void test_no_ready_within_t_boot_is_hard_off_with_message_for_10_s() {
      PiSession s(d); s.startHand(out); out.clear();
      s.onTick(119999, false, out); TEST_ASSERT_FALSE(has(SessionAction::Kind::PowerOff));
      s.onTick(1, false, out);
      TEST_ASSERT_TRUE(has(SessionAction::Kind::PowerOff));
      TEST_ASSERT_TRUE(has(SessionAction::Kind::Show, "PI ANTWORTET NICHT"));
      TEST_ASSERT_TRUE(s.active());
      out.clear(); s.onTick(10000, false, out);
      TEST_ASSERT_TRUE(has(SessionAction::Kind::DisplayOff));
      TEST_ASSERT_FALSE(s.active());
  }
  ```
  Die weiteren Tests, je Name und das, was er prüft:

  | Test | Prüft |
  |---|---|
  | `test_night_start_shows_nothing_and_sends_session_nacht` | kein `Show`; nach `READY` und Takt `Send SESSION\|NACHT` |
  | `test_no_ping_while_starting` | `onTick(60000, false)` in Starting: kein `Send PING` (R7) |
  | `test_bt2_while_starting_shuts_down_after_ready_without_session` | BT2, `READY` → `Reply OK`; Takt → `Send SHUTDOWN`, kein `SESSION` (R9) |
  | `test_ping_every_10_s` | Running: 9 999 ms kein `PING`, 1 ms mehr → `Send PING` |
  | `test_three_missed_pings_hard_off_with_message` | dreimal `Expired PING` → `PowerOff`, `Show PI ANTWORTET NICHT` |
  | `test_pong_resets_missed_pings` | zwei Aussetzer, `PONG`, drei Aussetzer → erst beim dritten neuen `PowerOff` |
  | `test_ping_waits_while_link_busy` | `onTick(20000, true)` → kein `Send`; dann `onTick(0, false)` → `Send PING` (L2) |
  | `test_ready_in_running_resends_session` | `Reply OK`, Takt → `Send SESSION\|HAND`; Zustand bleibt Running (L3) |
  | `test_ready_in_radar_debug_returns_to_running` | `Reply OK`, → Running, Takt → `Send SESSION` |
  | `test_done_starts_shutdown` | `Reply OK`, Takt → `Send SHUTDOWN` |
  | `test_bt2_in_running_starts_shutdown` | Takt → `Send SHUTDOWN` |
  | `test_shutdown_waits_for_free_link` | `PING` offen, BT2: `onTick(0, true)` kein `Send`; Antwort `PONG`, `onTick(0, false)` → `Send SHUTDOWN` (Review Focus 3) |
  | `test_busy_retries_after_30_s` | `BUSY` → 29 999 ms nichts, dann `Send SHUTDOWN` |
  | `test_busy_for_10_min_is_hard_off_without_message` | → `PowerOff`, `DisplayOff`, kein `Show PI ANTWORTET NICHT` |
  | `test_shutdown_expired_is_hard_off_without_message` | `Expired SHUTDOWN` → `PowerOff`, `DisplayOff`, kein Text |
  | `test_ok_to_shutdown_shows_text_then_power_off_after_t_halt` | `OK` → `Show PI FAEHRT HERUNTER`; 29 999 ms nichts, dann `PowerOff`, `DisplayOff`, `active()` falsch |
  | `test_night_halting_has_no_display_actions` | NACHT: weder `Show` noch `DisplayOff` |
  | `test_session_expired_starts_shutdown` | `Expired SESSION` → Takt `Send SHUTDOWN` |
  | `test_mode_radar_and_normal` | `MODE\|RADAR` → `Reply OK`, RadarDebug, kein `PING` nach 20 s; `MODE\|NORMAL` → `Reply OK`, Running |
  | `test_mode_radar_outside_running_is_error_state` | in ShuttingDown → `Reply ERROR\|STATE` (R12) |
  | `test_bt2_in_radar_debug_shuts_down_after_mode_normal` | BT2 merken; `MODE\|NORMAL` → Takt `Send SHUTDOWN` |
  | `test_radar_debug_ends_after_60_min` | 3 600 000 ms → Takt `Send SHUTDOWN` |
  | `test_buttons_in_running_send_button_n_in_order` | BT6, BT5 in einem Durchlauf → `Send BUTTON\|6`, nach der Antwort `Send BUTTON\|5` |
  | `test_buttons_ignored_outside_running` | Starting, RadarDebug, ShuttingDown, Halting: BT1, BT3–BT6 → keine Aktion |
  | `test_repeated_pi_requests_change_nothing` | `DONE` zweimal → einmal ShuttingDown, beide `Reply OK` (R8) |
  | `test_resume_after_reset` | neue `PiSession` auf demselben `SessionData`; `awaiting` Session → `Send SESSION`, Shutdown → `Send SHUTDOWN`, Ping → kein Aussetzer, Button → nur `Log` (Review Focus 1) |
  | `test_reset_gives_off_and_inactive` | nach `reset`: Off, `active()` falsch, alle Zähler 0 |

- [ ] **Step 2:** `pio test -e native -f test_pi_session`. Erwartet: FAIL (Datei fehlt).
- [ ] **Step 3:** Umsetzen.
- [ ] **Step 4:** Die Suite ist grün, die ganze native Suite auch.
- [ ] **Step 5:** Commit `ESP: Zustandsmaschine der Sitzung mit dem Pi`

### Task 4: Sitzung, Speisung und Nummern im RTC-Speicher

**Files:**
- Modify: `esp/lib/system/PersistentState.h`, `esp/lib/system/PersistentState.cpp`

**Interfaces:**
- Consumes: `SessionData`, `PiSession::reset` (Task 3).
- Produces: `PersistentState::Data` erhält am Ende `SessionData session; uint8_t piPowered; uint8_t txSeq; uint8_t rxSeq; uint8_t rxValid;`. Dazu `static_assert(sizeof(Data) % 4 == 0)`, `MAGIC = 0x52574C33` („RWL3“). `setDefaults` ruft `PiSession::reset(data.session)` und setzt `piPowered`, die Nummern und `rxValid` auf 0.

- [ ] **Step 1:** Umsetzen. Der Kommentar zu `MAGIC` nennt „RWL3“.
- [ ] **Step 2:** `pio run` → SUCCESS. `pio test -e native` grün. PersistentState ist Arduino-Code und hat keinen nativen Test.
- [ ] **Step 3:** Commit `ESP: Sitzung, Speisung und Nummern im RTC-Speicher`

### Task 5: `Application` führt die Sitzung

**Files:**
- Modify: `esp/lib/app/application.h`, `esp/lib/app/application.cpp` (`run()` Z. 85–248, `handleInput` Z. 451–490)
- Modify: `esp/README.md` (Tasten, Sitzung, Anzeigetexte, Hinweis zum ersten Flashen)

**Interfaces:**
- Consumes: `PiSession` (Task 3), `PersistentState` (Task 4), `PiLink::state/restore/poll/send/reply/busy`, `PiPower::restore/switchTo`, `Display::begin/show/setPower`, `I2CMasterControl::enable/disable`.
- Produces: Ablauf in `run()`:
  1. Nach `PersistentState::load`: `_piPower.restore(_state.piPowered)` und `_link.restore({txSeq, rxSeq, rxValid})`.
  2. BT4–BT6 auf `InputTrigger::ANY_EDGE`. Den Kommentar Z. 140–146 nachführen: Alle sechs Tasten laufen über Flipflops (Spec §4 F9).
  3. Ist die Sitzung nach dem Laden aktiv: zuerst `resume`. Dann geht jede neue Taste an `onButton`, BT2 eingeschlossen. Ist sie nicht aktiv: BT2 → `startHand`; BT1 und BT3 wie heute. Der Stand des Expanders wird in jedem Fall gesichert (F3).
  4. Ist die Sitzung jetzt aktiv: Die Wand-Regeln (§8, BT1-Minute, Radar) entfallen in diesem Durchlauf. Der Bus wird freigegeben (`I2CMasterControl::disable()`, R14). Dann läuft die Sitzungsschleife mit einem Takt von höchstens 20 ms, solange `active()`:
     - `_link.poll(now)` → `onLink`.
     - `onTick(now - letzterTakt, _link.busy())`.
     - Aktionen ausführen:
       - `PowerOn` / `PowerOff` → `switchTo(true/false)`, `piPowered` nachführen.
       - `Send` → `_link.send`; `awaiting` setzt die Sitzung selbst.
       - `Reply` → `_link.reply`.
       - `Show` → `enable`, `ensureDisplayReady`, `show`, `setPower(true)`, `disable`.
       - `DisplayOff` → `enable`, `ensureDisplayReady`, `setPower(false)`, `disable`; `displayState = Off`.
       - `Log` → `DebugSerial`.
     - Sitzung und `_link.state()` in `_state` übernehmen und sichern, sobald sich etwas geändert hat, sonst spätestens jede Sekunde.
     - `yield()`.
  5. Ist die Sitzung zu Ende: sichern und schlafen (R10).
  6. Der BT3-Verbindungstest bleibt ausserhalb einer Sitzung, wie er ist (Tabelle 5.2).
  7. README: Nach dem ersten Flashen dieser Firmware gilt die neue `MAGIC` als Kaltstart, und der ESP hält den Pi für aus. Läuft der Pi gerade, vorher die Wand kurz stromlos machen. Sonst schaltet der erste BT2 den Pi hart aus.

- [ ] **Step 1:** Umsetzen. Die Logik steckt in Task 3; hier geht es nur um die Verdrahtung.
- [ ] **Step 2:** `pio run` → SUCCESS, ohne neue Warnungen aus den geänderten Dateien. `pio test -e native` grün.
- [ ] **Step 3:** README nachführen.
- [ ] **Step 4:** Commit `ESP: Sitzung mit dem Pi in der Application, BT4-BT6 als Pegelwechsel`

### Task 6: `READY` und `SESSION` auf dem Pi

**Files:**
- Create: `rpi/app/link/ready.py`
- Modify: `rpi/app/ui/link_dispatch.py`
- Test: `rpi/app/link/tests/test_ready.py`, `rpi/app/ui/tests/test_link_dispatch.py`

**Interfaces:**
- Produces:
  - `announce_ready(link, stop, sleep=time.sleep) -> bool` in `app/link/ready.py` (L1):
    - `link.request("READY")` senden und auf die Antwort warten.
    - Antwort `OK` → True.
    - Antwort `None` (Frist) → Log, dann sofort ein neues `READY`; `request` vergibt die neue Nummer.
    - `LinkBusy` → 0,25 s warten.
    - Ist `stop` gesetzt → False.
  - `LinkDispatcher`:
    - `SESSION` mit `HAND` oder `NACHT` → `reply OK`. Beim ersten Mal `session_reason` (`"HAND"`/`"NACHT"`) setzen und `session_event: threading.Event` auslösen; danach nur `OK` und Log.
    - `SESSION` mit anderen Daten → `ERROR|BAD_SESSION`.
    - Neu `shutdown_done: threading.Event`. Es wird gesetzt, nachdem `_shutdown` geantwortet und `on_shutdown` aufgerufen hat.
- [ ] **Step 1: Tests**
  - `test_ready_returns_true_on_ok`
  - `test_ready_repeats_after_deadline_with_new_request`: zwei `request`-Aufrufe
  - `test_ready_waits_on_link_busy`
  - `test_ready_stops_on_stop_signal`
  - `test_session_hand_sets_reason_and_event`
  - `test_second_session_is_answered_and_ignored`
  - `test_session_bad_data_is_error`
  - `test_shutdown_sets_shutdown_done_after_reply`
- [ ] **Step 2:** FAIL.
- [ ] **Step 3:** Umsetzen.
- [ ] **Step 4:** Grün.
- [ ] **Step 5:** Commit `Pi: READY bis OK, SESSION im Dispatcher`

### Task 7: Herunterfahren auf dem Pi

**Files:**
- Create: `rpi/app/system/__init__.py`, `rpi/app/system/power.py`
- Test: `rpi/app/system/tests/__init__.py`, `rpi/app/system/tests/test_power.py`

**Interfaces:**
- Produces: `power_off(runner=subprocess.run) -> bool` ruft `runner(["sudo", "-n", "/usr/bin/systemctl", "poweroff"], check=False)` (R6). Ein Fehler oder ein Rückgabecode ≠ 0 führt zu einem Log-Eintrag und `False`; geworfen wird nichts.
- [ ] **Step 1: Tests** mit einem Fake-Runner:
  - `test_power_off_runs_systemctl_poweroff`: genau diese Liste.
  - `test_power_off_logs_nonzero_return`
  - `test_power_off_logs_missing_sudo`: Der Runner wirft `FileNotFoundError`.
- [ ] **Step 2:** FAIL.
- [ ] **Step 3:** Umsetzen.
- [ ] **Step 4:** Grün.
- [ ] **Step 5:** Commit `Pi: herunterfahren ueber systemctl poweroff`

### Task 8: Regel B auf dem Pi (`BusGuard`)

**Files:**
- Create: `rpi/app/driver/bus_rule.py`
- Test: `rpi/app/driver/tests/__init__.py`, `rpi/app/driver/tests/test_bus_rule.py`

**Interfaces:**
- Produces: `class BusGuard(lgpio_module=None, clock=time.monotonic, sleep=time.sleep, free_s=0.005, radar_pause_s=0.25, max_wait_s=1.0)`:
  - `start()` belegt auf gpiochip 0 zwei Eingänge mit Meldung beider Flanken (lgpio-Alerts): GPIO4 (INT_GPIO_EXP, Pull-up) und GPIO22 (INT_HLK, Pull-down). lgpio wird erst hier geladen. Fehlt lgpio (am PC), wartet der Guard nie.
  - `__call__()` gibt einen Kontextmanager für eine Übertragung zurück. Vor dem Start wartet er:
    - solange INT_GPIO_EXP LOW ist;
    - danach `free_s` ab dessen steigender Flanke;
    - nach einer steigenden INT_HLK-Flanke `radar_pause_s` (R3).
    - Eine laufende Übertragung unterbricht er nie.
    - Nach `max_wait_s` geht es trotzdem weiter, mit Warnung im Log (Review Focus 5).
  - `radar_high() -> bool` liest GPIO22 (R13). Ohne lgpio ist der Wert False.
  - `stop()` gibt die Leitungen frei.
  - `WallDisplay._transfer` und `ExpanderButtons._read` wiederholen eine abgeschnittene Übertragung schon einmal (Regel B, Rückfall). Daran ändert sich nichts.
- [ ] **Step 1: Tests** mit Fake-lgpio und eingespeister Uhr. Der Fake ruft die Alert-Callbacks von Hand auf:
  - `test_no_wait_when_line_high_and_no_edge`
  - `test_waits_while_expander_int_low`
  - `test_waits_free_s_after_rising_edge`
  - `test_waits_radar_pause_after_hlk_rising_edge`
  - `test_gives_up_after_max_wait_with_warning`
  - `test_without_lgpio_never_waits`
  - `test_radar_high_reads_gpio22`
- [ ] **Step 2:** FAIL.
- [ ] **Step 3:** Umsetzen.
- [ ] **Step 4:** Grün. `test_imports` bleibt grün.
- [ ] **Step 5:** Commit `Pi: Regel B fuer den I2C-Bus`

### Task 9: Dienst-Ablauf in `app.main`

**Files:**
- Modify: `rpi/app/main.py` (`run_wall` Z. 61–108, `main` Z. 111–153)
- Modify: `rpi/app/ui/shell.py` (Z. 17–26: optionales `display_released`)
- Test: `rpi/app/tests/test_main.py`, `rpi/app/ui/tests/test_shell.py`

**Interfaces:**
- Consumes:
  - `announce_ready` und `LinkDispatcher.session_event/session_reason/shutdown_done` (Task 6)
  - `power_off` (Task 7)
  - `BusGuard` (Task 8)
  - `WallDisplay(bus, bus_guard)`, `ExpanderButtons(bus, bus_guard)`
- Produces:
  - `Shell(..., display_released: threading.Event = None)`: Ein übergebenes Event wird benutzt, sonst entsteht ein eigenes wie heute.
  - `run_wall(..., dispatcher=None, display_released=None)`: Mit einem übergebenen `dispatcher` legt `run_wall` keinen eigenen an, startet und stoppt ihn nicht und nimmt ihn für `send_done`. Ohne ihn bleibt alles wie heute (PC-Modus, Tests aus 4a).
  - Wand-Modus von `main()`, in dieser Reihenfolge:
    1. `SMBus(1)`, `BusGuard.start()`, Port öffnen, `PiLink.start()`.
    2. `released = threading.Event()`, gesetzt, weil noch keine Bildschirmfolge läuft.
    3. `LinkDispatcher(..., display_released=released, on_shutdown=power_off)` erzeugen und starten.
    4. `announce_ready` (L1).
    5. Warten, bis `session_event` oder `stop` gesetzt ist.
    6. **HAND:** `released.clear()`. Erst jetzt `WallDisplay(bus=bus, bus_guard=guard).start()` (R5). Dann `run_wall(..., dispatcher=dispatcher, display_released=released)`. Die Anwesenheit kommt von `guard.radar_high` (R13). Die Radar-Tasten laufen über `ExpanderButtons(bus=_SmbusReader(bus), bus_guard=guard)`.
    7. **NACHT:** Die Anzeige nicht anfassen und auf `stop` warten (Teil 3b ergänzt `GET|QUOTE`).
    8. **`stop` vor `SESSION`** (R9): Die Anzeige nicht anfassen.
    9. Danach:
       - `run_wall` gibt `"shutdown"` zurück → auf `shutdown_done` warten, höchstens 10 s.
       - `"idle"` → `DONE` ist schon gesendet → auf `shutdown_done` warten, höchstens 120 s.
       - `"error"` → `dispatcher.send_done()`, dann wie bei `"idle"`.
    10. `finally`: Dispatcher, Link, Port und Guard stoppen.
- [ ] **Step 1: Tests.** Port, Bus und lgpio sind gepatcht, `power_off` ist ein Fake.
  - `test_no_display_write_before_session_hand` (Review Focus 4): Bis `SESSION` kommt, gibt es keinen Bus-Zugriff auf eine Anzeige-Adresse.
  - `test_hand_starts_menu`
  - `test_nacht_keeps_display_dark_until_shutdown`
  - `test_shutdown_before_session_powers_off_without_display` (R9)
  - `test_shutdown_calls_power_off_after_display_released`
  - `test_no_display_write_after_ok_to_shutdown` (Review Focus 4)
  - `test_shell_uses_given_display_released`
- [ ] **Step 2:** FAIL.
- [ ] **Step 3:** Umsetzen.
- [ ] **Step 4:** Grün, die ganze Suite auch.
- [ ] **Step 5:** Commit `Pi: Dienst-Ablauf mit READY, SESSION und Herunterfahren`

### Task 10: systemd-Dienst und README

**Files:**
- Create: `rpi/systemd/reflection-wall.service`
- Modify: `rpi/README.md`

**Interfaces:**
- Produces: Die Unit enthält:
  - `User=pi`, mit dem Vermerk „anpassen“;
  - `WorkingDirectory=/home/pi/Reflection-Wall/rpi` und `ExecStart=/home/pi/.venvs/reflection-wall-rpi/bin/python -m app.main`, beide als „anpassen“ markiert;
  - `Restart=on-failure`, `RestartSec=2`, `Environment=PYTHONUNBUFFERED=1`;
  - `AmbientCapabilities=CAP_NET_BIND_SERVICE`, für die Webseite auf Port 80;
  - `WantedBy=multi-user.target`.

  Die README beschreibt:
  - die Installation des Dienstes;
  - die sudoers-Regel `<benutzer> ALL=(root) NOPASSWD: /usr/bin/systemctl poweroff` (R6);
  - die Gruppen `dialout`, `i2c` und `gpio`;
  - den Ablauf `READY`, `SESSION`, `SHUTDOWN` und Regel B.

  Alles ist als „ungeprüft bis zur Abnahme“ markiert.
- [ ] **Step 1:** Datei und README schreiben. Es gibt keinen Test.
- [ ] **Step 2:** Commit `Pi: systemd-Dienst und Anleitung`

### Task 11: Abnahme am Gerät (offen bis Teil 0)

Diese Abnahme folgt erst, wenn der Pi eingerichtet ist (Teil 0) und der Owner flasht. Sie deckt Spec §14 „Am Gerät“ 1–4 und Teil-4-Spec §11 „Am Gerät“ 1, 4, 5, 7, 8 ab.

0. Vor dem ersten Flashen: Läuft der Pi, die Wand kurz stromlos machen (Task 5, Schritt 7).
1. Die Verbindung mit 74 880 Baud am Pi 5 prüfen.
2. BT2 → `PI STARTET` → Menü. BT2 → `PI FAEHRT HERUNTER` → der Pi fährt sauber herunter, die Wand wird dunkel.
3. `T_halt` messen, verdoppeln und eintragen.
4. Den Dienst stoppen → nach drei PING `PI ANTWORTET NICHT`, nach 10 s dunkel.
5. Den Dienst während der Sitzung neu starten → das Menü kommt wieder (L3).
6. Regel B: den Abstand von der INT_GPIO_EXP-Flanke bis zur ersten SCL-Flanke des ESP und die Reaktion des Pi messen. Dasselbe nach einer Radar-Flanke (R3).
7. RADAR im Menü, mit `MODE`. BT2 im Radar → herunterfahren nach der Rückkehr.
8. Den kürzesten sicheren Abstand für BT6 messen und in die Anleitung eintragen.
9. BT2 im Menü zweimal schnell hintereinander drücken → `PI FAEHRT HERUNTER`, der Pi fährt sauber herunter.
10. BT2 noch einmal drücken, während `PI FAEHRT HERUNTER` geschrieben wird → der Pi fährt trotzdem sauber herunter.
11. Den Dienst neu starten, während die Anwendung Radar läuft → die UART gehört wieder dem ESP, und das Menü kommt wieder.
12. Nach jeder Sitzung der Schritte 2–11 die Logs prüfen: Der Pi hat `poweroff` aufgerufen, und im Log des ESP steht kein „hart aus“. Ausnahme ist Schritt 4, dort ist das harte Aus gewollt.

---

## Stand nach der Umsetzung (2026-10-25)

### Gebaut

| Task | Was | Commits |
|---|---|---|
| 1 | `SESSION` im Protokoll beider Seiten | 494a98d |
| 2 | `PiLink` auf dem ESP: `READY` nie als Wiederholung, nach Reset neu melden | 5cc3b84 |
| 3 | Zustandsmaschine `PiSession` | 47314bf |
| 4 | Sitzung, Speisung und Nummern im RTC-Speicher; Prüfung der Daten | 79b8d60, c085f5e |
| 5 | `Application` führt die Sitzung; Sitzungszeit in jedem Takt gesichert | b07b54b, 7563124 |
| 6 | `READY` und `SESSION` auf dem Pi | 8da8f32 |
| 7 | Herunterfahren auf dem Pi | b49a131 |
| 8 | Regel B auf dem Pi (`BusGuard`) | 3287a51 |
| 9 | Dienst-Ablauf in `app.main`; Radar endet nach 55 min (R15); `OK` auf `SHUTDOWN` erst nach freier Anzeige | c4a9631, 086b2b2, e0a96cf |
| 10 | systemd-Dienst und README | 7a9a78c, e0df19e |
| 11 | Abnahme am Gerät | offen bis Teil 0 |
| Abschluss | Korrekturen aus der Schlussprüfung: der Pi bedient nach dem `OK` auf `SHUTDOWN` weiter (I-1); `READY` noch einmal ohne `SESSION` (M-3); nach `DONE` ohne `SHUTDOWN` selbst aus, sudoers-Regel beim Start geprüft (M-4); Warnung von Regel B höchstens alle 10 s; `StartLimitIntervalSec=0`; der ESP sichert vor den Aktionen und nach jedem Senden, ein nicht gesendetes Send gilt als Frist (I-1, M-1, M-2); Spezifikationen nachgeführt (M-7, M-8) | 01e74d1, eb60844, 1cf05df, fcedbb6, fc05086, 9e1c2f6, 71dfbac, 5a86f97 |
| Nachtrag | Doppeldruck auf BT2 nach Option A: `ExecStop=/bin/sleep 3`; geht das `OK` auf ein `SHUTDOWN` nicht raus, fährt das neuere `SHUTDOWN` nach seinem `OK` herunter, sonst ein Rückfall nach 3 s; README zum neuen Verhalten des Dienstes | 4320601 und der Commit mit dieser Zeile |

### Entscheide während der Umsetzung

Jeder Entscheid sagt, was gilt, und was es kostet, wenn er falsch ist.

- **Task 4 und 5 zusammen:** Ein Auftrag und eine Prüfung für beide. Task 4 hat keinen eigenen Test und dient nur Task 5. Kostet: Die Prüfung sieht einen grösseren Diff auf einmal.
- **Offene Punkte in Task 3:**
  - `startHand` und `startNight` gelten nur aus AUS. Ein Start von Hand beendet `PI ANTWORTET NICHT` früher.
  - Jede Antwort auf `PING` setzt die Aussetzer auf null.
  - Eine Antwort ohne offene eigene Anfrage wird nur geloggt.
  - Zurück in BETRIEB beginnt der PING-Abstand neu.

  Kostet: kleine Änderungen am Verhalten von Task 3, die die Prüfung oder die Abnahme findet.
- **Daten im RTC-Speicher prüfen:** `PiSession::valid` prüft die enums und `buttonCount <= 6`, mit nativem Test. Die `Application` setzt eine ungültige Sitzung nach dem Laden zurück. Die Zeitzähler bleiben beim grössten Wert stehen, statt überzulaufen. Grund: Daten mit gültiger CRC, aber falschen Werten schrieben sonst neben die Warteschlange oder schliefen nie ein. Kostet: ein paar Zeilen in `PiSession`.
- **R15:** siehe die Liste der Rulings oben. Kostet: Eine Sitzung mit Radar endet nach 55 statt 60 min.
- **Offene Punkte in Task 6:**
  - `announce_ready` wartet auf jede Antwort nur begrenzt und versucht es bei jeder Antwort ausser `OK` neu.
  - `session_reason` bleibt `None` bis zum ersten gültigen `SESSION`.
  - `shutdown_done` wird nach dem `OK` und nach `on_shutdown` gesetzt, auch wenn `on_shutdown` wirft, nie bei `BUSY`. Seit der Schlussprüfung läuft `on_shutdown` höchstens einmal. `shutdown_done` kommt auch auf dem Weg von M-4 (bestätigtes `DONE`, 120 s kein `SHUTDOWN`). Geht das `OK` nicht raus, weil ein neueres `SHUTDOWN` es ersetzt hat, kommt `shutdown_done` nach dem `OK` auf das neuere, sonst nach dem Rückfall von 3 s.

  Kostet: kleine Änderungen am Verhalten des Pi; Task 9 baut darauf.
- **Offene Punkte in Task 8:**
  - Der Guard wartet, indem er mit der eingespeisten Uhr und `sleep` nachschaut.
  - `free_s` zählt ab der letzten steigenden Flanke an GPIO4, die Radar-Pause ab der letzten an GPIO22. Beides muss erfüllt sein.
  - `max_wait_s` begrenzt ein Warten. Seit der Schlussprüfung kommt die Warnung dazu höchstens alle 10 s, mit der Zahl der ausgelassenen.
  - Fehlt lgpio oder scheitert `start()`, wartet der Guard nie, mit einem Eintrag im Log.
  - `stop()` darf mehrmals laufen.

  Kostet: Zeiten, die die Abnahme ohnehin misst.
- **Wer `DONE` schickt:** Mit dem Dispatcher von `main()` schickt `run_wall` kein `DONE`. `main()` schickt es genau einmal, bei „idle“ und „error“. R15 bringt einen zweiten Grund für „idle“, und zwei Stellen hätten `DONE` doppelt geschickt. Kostet: ein `DONE` mehr auf der Leitung, ohne Schaden.
- **Task 9, 45 s für die Anzeige:** Im Wand-Modus wartet der Dispatcher bis zu 45 s (`RELEASE_WAIT_S`) auf die freie Anzeige, bevor er `SHUTDOWN` mit `OK` beantwortet, statt 2 s. Das bleibt unter den 60 s des ESP und deckt ein ganzes Bild bei hängendem INT_GPIO_EXP (12 × 1 s). Die stärkere Lösung (`BUSY` bei Ablauf) hätte Task 6 geändert. Kostet: Im Fehlerfall antwortet der Pi bis zu 45 s später. Ist die Anzeige nach 45 s noch nicht frei, bleibt das alte Risiko.
- **Eine Runde für alle Korrekturen der Schlussprüfung:** I-1 auf beiden Seiten, M-1 bis M-4, M-7, M-8, die Warnung von Regel B, `StartLimitIntervalSec=0`, die zusätzlichen Schritte in Task 11 und dieser Abschnitt. Die Prüfung wollte I-1, M-1 und M-7 vor dem Merge, den Rest vor der Abnahme. Alles ist klein, eine Runde ist billiger als eine spätere. Kostet: ein grösserer Diff für die nächste Prüfung.
- **Rest von I-1, Option A des Owners (2026-10-25):** Ohne Schonfrist endet der Dienst gleich nach `poweroff`. systemd stoppt ihn, und SIGTERM beendet Python sofort. Ein neu gesendetes `SHUTDOWN` braucht 0,1 s oder mehr und fände meist keinen Dienst mehr, der antwortet. Kam es, während das erste noch auf die Anzeige wartete, lief `power_off` sogar vor seinem `OK`. Der Owner hat am 2026-10-25 Option A gewählt, und sie ist gebaut:
  - `ExecStop=/bin/sleep 3`: Beim Herunterfahren bedient der Dienst noch 3 s weiter, erst dann kommt SIGTERM.
  - Geht das `OK` auf ein `SHUTDOWN` nicht raus, weil ein neueres es ersetzt hat, ruft der Pi `power_off` nicht gleich. Das neuere `SHUTDOWN` bekommt sein `OK` und fährt dann herunter. Tut es das nicht innerhalb von 3 s, fährt ein Rückfall herunter.

  Ein abgelaufenes, neu gesendetes `SHUTDOWN` endet weiter mit einem harten Aus. Task 11 prüft den Doppeldruck auf BT2 (Schritte 9, 10 und 12). Kostet: Jedes Stoppen des Dienstes dauert 3 s länger. Kommt ein neues `SHUTDOWN` erst nach diesen 3 s, schaltet der ESP nach `T_shutdown` hart aus.
- **M-5 und M-6 bleiben:** M-5 ist fast unmöglich, M-6 nur kosmetisch (siehe unten). Kostet: wie dort beschrieben.

### R15 vom Owner bestätigt

Der Owner hat R15 am 2026-10-25 bestätigt: „55 min passt“.

### Doppeldruck auf BT2: Option A vom Owner gewählt

Der Owner hat am 2026-10-25 Option A gewählt: 3 s Schonfrist mit `ExecStop`, und `power_off` überlässt der Pi dem neueren `SHUTDOWN` (siehe „Rest von I-1“ oben).

### Offen

**Protokoll und `PiLink` (ESP)**

- `test_link_codec` prüft die Zahl der Befehlsvektoren (14) fest. Jede neue Nachricht muss sie ändern.
- Die Bedingungen in `roleOf` und in `PiLink::handleLine` sind lang. Ein benannter Zwischenwert läse sich besser.
- Task 1: Die Zahl der Fälle (130 rot, 129 grün) ist nicht erklärt. Es fehlt kein Test.
- Kein Test für `READY`, das noch einmal kommt, während das vorige gemeldet, aber noch nicht beantwortet ist.
- `test_repeat_after_restore_is_reported_again` zeigt nicht, dass die Antwort danach gespeichert ist.

**`PiSession` und `Application` (ESP)**

- Kein Test für die untere Grenze der 10 s von `PI ANTWORTET NICHT` (`onTick(9999)`).
- Kein Test prüft, dass `PowerOff` vor `Show PI ANTWORTET NICHT` kommt (R14).
- `linkBusy` ist nur zusammen mit einem offenen `PING` getestet.
- Das Rücksetzen der Aussetzer beim Eintritt in BETRIEB ist ungetestet.
- Ein abgewiesenes `startNight` während `PI ANTWORTET NICHT` bleibt still. Teil 3b soll das im Header festhalten.
- Der Inhalt des Logs (Dauer der Sitzung) ist nicht geprüft. Einige Tests verketten mehrere Abläufe. `PING_MISSES` ist eine Zahl, steht aber als `unsigned long` bei den Zeiten.
- Unterbricht ein Reset das Schreiben eines Sitzungstexts, zeigt `resume` ihn nicht neu. Die Anzeige bleibt für diesen Zustand dunkel oder halb geschrieben.
- Ein Zustandswechsel am Anfang des Durchlaufs (durch `resume` oder eine Taste, vor der Sitzungsschleife) wird nicht als `[SESSION] A -> B` geloggt. Ein Kommentar in `PiSession.h` ist nicht ausgerichtet.
- M-5: Eine Sitzung mit gültiger CRC, aber unbrauchbaren Werten wird zurückgesetzt, `piPowered` bleibt. Der Pi kann dann noch an sein, während der ESP wieder Zitate zeigt.
- Zwischen dem Sichern des Zustands AUS und dem Sichern von `piPowered = 0` vor dem Puls liegen einige µs. Ein Reset genau dort lässt die Speisung an und `piPowered` auf 1. Die nächste Sitzung pulst dann nicht und endet nach `T_boot` mit einem harten Aus. Doppelt gepulst wird nie.
- Die Sicherung vor den Aktionen und nach jedem Senden (I-1, M-1) und das nicht gesendete Send (M-2) haben keinen automatischen Test, denn `Application` hat keinen nativen Prüfstand. Task 11 prüft sie am Gerät (Schritte 9 und 10).
- R14 ging davon aus, dass der ESP den Bus heute bis zum Deep Sleep hält. Das stimmte nicht: `I2CMasterControl::begin()` gibt den Bus schon beim Start ab, und jeder Zugriff gibt ihn danach wieder frei. Das schadet nicht.

**Pi-Dienst**

- Der Zweig `TimeoutError` in `ready.py` ist ungetestet.
- `test_ready_repeats_after_deadline_with_new_request` prüft keine Nummer. `self.sleeps` in einem Test von `test_ready.py` ist unbenutzt. Ein Kommentar, dass `session_reason` erst nach `session_event` gilt, fehlt.
- `power_off` gibt dem Runner keine Frist. Die Tests der Fehlerfälle prüfen den Text der Meldung nicht.
- `BusGuard`: Zwischen dem Lesen des Pegels und dem Rückruf der Flanke liegt ein Wettlauf im µs-Bereich. Die Wiederholung einer abgeschnittenen Übertragung fängt ihn auf.
- `BusGuard.stop()` setzt die Zeitstempel der Flanken nicht zurück. `self._handle = None` steht doppelt.
- Tests des `BusGuard`: Der Test ohne lgpio trifft einen `AttributeError` statt `ImportError` und prüft die Warnung nicht. Es fehlen ein Test für 5 ms und 250 ms zusammen und Prüfungen für `stop()`. Einige Vergleiche liegen genau auf der Grenze.
- Wirft `start_menu` eine Ausnahme, schickt der Pi kein `DONE`. Der ESP schaltet dann mit `PI ANTWORTET NICHT` hart aus. Das betrifft nur Programmierfehler.
- `DONE` kann nach einem schon beantworteten `SHUTDOWN` kommen, wenn das automatische Aus oder R15 mit einem gemerkten BT2 zusammenfällt. Das schadet nicht. Ein gesetztes `shutdown_done` könnte das `DONE` auslassen.
- `test_main.py` liest das private `RadarApp._buttons_factory`.
- Die ganze Python-Suite braucht 16–24 s statt 13 s. Das ist kein Fehler.
- M-6: BT2 in der Anwendung Radar zeigt kurz das Hauptmenü (etwa 0,2 s), bevor `PI FAEHRT HERUNTER` kommt.
- Rest von I-1: siehe die Entscheide oben.

**Anleitung**

- README: Für den Dienst gelten neue Gruppen nach einem Neustart des Dienstes. „Neu anmelden“ braucht es nur für die eigene Shell.
- README: einmal sagen, ob Teil 0 oder die Befehle von Hand gemeint sind; „man“ und „du“ vereinheitlichen.
- README, Regel B: „schreibt eine Warnung ins Log“ sagt nicht, dass die Warnung höchstens alle 10 s kommt.
