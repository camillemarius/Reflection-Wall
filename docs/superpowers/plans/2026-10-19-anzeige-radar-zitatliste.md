# Teil 3a: Anzeige, Radar und Zitatliste – Umsetzungsplan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Die Wand ist dunkel, bis das Radar jemanden erkennt oder BT1 gedrückt wird; dann zeigt sie das neueste Zitat aus einer Liste im Flash, BT1 schaltet bei leuchtender Wand weiter, und der ESP schaltet die Anzeige aus, sobald niemand mehr da ist und die BT1-Minute vorbei ist.

**Architecture:** Die Entscheidungen (Liste lesen und schreiben, Umstieg vom alten Speicher, was beim Aufwachen passiert, wann ausgeschaltet wird) liegen in reinem C++ ohne Arduino in `esp/lib/core` und werden auf dem PC getestet. Die Firmware bindet sie mit dünnen Adaptern an LittleFS, den RTC-Speicher und die Anzeige. Die Pi-Sitzung (Teil 2) und Mitternacht (Teil 3b) sind nicht Teil dieses Plans.

**Tech Stack:** ESP8266 Arduino-Core über PlatformIO (`env:esp12e`), LittleFS, Unity-Tests in einer PlatformIO-`native`-Umgebung mit MinGW GCC 6.3 auf dem PC.

**Spec:** `docs/superpowers/specs/2026-10-19-esp-pi-steuerung-design.md` – Abschnitte 8 (Anzeige und Radar), 10 (Tasten), 11 (gespeicherter Zustand), 14 (Prüfen), 16 (Teil 3a).

## Global Constraints

- Code in `esp/lib/core/` bindet **keine** Arduino-Header ein und bleibt bei **C++14** – der PC-Compiler ist MinGW GCC 6.3 (kein `std::optional`, kein `std::string_view`).
- Liste: Datei `/quotes.txt`, eine Zeile pro Zitat `JJJJ-MM-TT|Text`, das neueste zuerst, höchstens **30** Einträge. Ein Eintrag ohne Datum (leerer Teil vor `|`) ist erlaubt.
- Atomar schreiben: ganze Liste nach `/quotes.new`, dann auf `/quotes.txt` umbenennen. Beim Laden ein übriggebliebenes `/quotes.new` löschen.
- Umstieg: nur wenn `/quotes.txt` fehlt und `/text.txt` existiert – erste Zeile von `/text.txt` wird der einzige Eintrag (Datum leer), danach `/text.txt` löschen.
- Leere Liste → die Wand zeigt `KEIN TEXT` (genau diese Zeichenfolge).
- BT1-Minute: **60 000 ms**. INT_HLK (`Pins::INT_HLK`, GPIO13) wird alle **200 ms** gelesen. HIGH = jemand erkannt.
- RTC-Layout ändert sich → `PersistentState::MAGIC` = `0x52574C32` („RWL2“).
- BT2 schaltet die Pi-Speisung weiter wie heute (Puls auf GPIO12); die Sitzungslogik kommt erst in Teil 2.
- Commit-Nachrichten auf Deutsch, letzte Zeile `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>`.
- Arbeitszweig: `feature/anzeige-radar-zitatliste`, abgezweigt von `design/esp-pi-steuerung`.
- Die PC-Tests laufen im Projektordner. Nicht in einen tieferen Ordner verschieben: MinGW GCC 6.3 kann keine Pfade über 260 Zeichen; dann findet es `unity.h` nicht (am 2026-10-19 so beobachtet).
- **BT1-Minute ohne Uhrzeit:** Jeder BT1-Druck setzt den ESP zurück (Flipflop → Expander-INT → RST). Die Minute zählt deshalb ab dem Start des Durchlaufs (`millis()`), und im RTC-Speicher steht nur, *dass* sie läuft (`button1Active`). Setzt das Radar den ESP während der Minute zurück, beginnt sie neu – die Wand bleibt dann höchstens etwas länger an.

## Review Focus

1. **Windows-Zeilenenden:** Git wandelt `data/quotes.txt` beim Auschecken in CRLF. Ein `\r` am Zeilenende darf nicht im angezeigten Text landen. → Test `test_parse_strips_carriage_return` in Task 1.
2. **Kaputte Zeilen:** Leere Zeilen, Zeilen ohne `|`, Zeilen mit leerem Text werden übersprungen statt als leeres Zitat gezeigt. → Test `test_parse_skips_invalid_lines` in Task 1.
3. **BT1 bei leerer Liste:** Die Wand zeigt `KEIN TEXT`; Weiterschalten darf nicht abstürzen (keine Division durch 0). → Test `test_next_index_on_empty_list_is_zero` in Task 1.
4. **Liste verschiebt sich:** Kommt vorne ein Eintrag dazu oder gibt es zwei gleiche Daten, muss die gespeicherte Position trotzdem auf ein vorhandenes Zitat zeigen. → Tests `test_resolve_index_*` in Task 1.
5. **Beide Dateien vorhanden:** Liegen `/quotes.txt` und `/text.txt` nebeneinander (zum Beispiel nach einem `uploadfs` mit beiden), gilt `/quotes.txt`, und `/text.txt` bleibt unberührt. → Test `test_load_prefers_quotes_over_legacy` in Task 2.

---

### Task 1: PC-Tests einrichten und Zitatliste

**Files:**
- Modify: `esp/platformio.ini`
- Create: `esp/lib/core/src/QuoteList.h`, `esp/lib/core/src/QuoteList.cpp`
- Test: `esp/test/test_quote_list/test_main.cpp`

**Interfaces:**
- Produces:
  ```cpp
  struct Quote { std::string date; std::string text; };

  class QuoteList {
  public:
      static constexpr std::size_t MAX_QUOTES = 30;
      static QuoteList parse(const std::string& content);
      std::string serialize() const;                 // "date|text\n" pro Eintrag
      void addNewest(const std::string& date, const std::string& text);
      std::size_t size() const;
      bool empty() const;
      const Quote& at(std::size_t index) const;
      std::size_t resolveIndex(std::size_t index, const std::string& date) const;
      std::size_t nextIndex(std::size_t index) const;
  };
  ```

- [ ] **Step 1: Zweig anlegen und `platformio.ini` erweitern**

```bash
git switch design/esp-pi-steuerung
git switch -c feature/anzeige-radar-zitatliste
```

In `esp/platformio.ini`: ganz oben `[platformio]` mit `default_envs = esp12e` (sonst baut `pio run` auch die PC-Umgebung). In `[env:esp12e]` die Zeile `test_ignore = *` (sonst lädt `pio test` Tests auf das Gerät). Neu:

```ini
[env:native]
platform = native
test_framework = unity
build_src_filter = -<*>
build_flags = -std=gnu++14
```

- [ ] **Step 2: Tests schreiben**

`esp/test/test_quote_list/test_main.cpp` mit Unity (`setUp`/`tearDown` leer, `main` ruft alle Tests auf):

```cpp
void test_parse_reads_entries_in_order() {
    QuoteList l = QuoteList::parse("2026-10-19|Neu\n2026-10-18|Alt\n");
    TEST_ASSERT_EQUAL(2, l.size());
    TEST_ASSERT_EQUAL_STRING("2026-10-19", l.at(0).date.c_str());
    TEST_ASSERT_EQUAL_STRING("Alt", l.at(1).text.c_str());
}
void test_parse_strips_carriage_return() {
    QuoteList l = QuoteList::parse("2026-10-19|Text mit CRLF\r\n");
    TEST_ASSERT_EQUAL_STRING("Text mit CRLF", l.at(0).text.c_str());
}
void test_parse_skips_invalid_lines() {
    QuoteList l = QuoteList::parse("\n   \nohne Trenner\n2026-10-19|\n2026-10-18|Gut\n");
    TEST_ASSERT_EQUAL(1, l.size());
    TEST_ASSERT_EQUAL_STRING("Gut", l.at(0).text.c_str());
}
void test_parse_accepts_entry_without_date() {
    QuoteList l = QuoteList::parse("|Alter Text\n");
    TEST_ASSERT_EQUAL_STRING("", l.at(0).date.c_str());
    TEST_ASSERT_EQUAL_STRING("Alter Text", l.at(0).text.c_str());
}
void test_parse_keeps_at_most_30() {
    std::string c;
    for (int i = 1; i <= 35; i++) c += "2026-01-" + std::to_string(i) + "|Text " + std::to_string(i) + "\n";
    QuoteList l = QuoteList::parse(c);
    TEST_ASSERT_EQUAL(30, l.size());
    TEST_ASSERT_EQUAL_STRING("Text 30", l.at(29).text.c_str());
}
void test_serialize_roundtrip() {
    const std::string c = "2026-10-19|A\n|B\n";
    TEST_ASSERT_EQUAL_STRING(c.c_str(), QuoteList::parse(c).serialize().c_str());
}
void test_add_newest_puts_entry_first() { /* addNewest("2026-10-20","X") → at(0) ist X */ }
void test_add_newest_drops_oldest_beyond_30() { /* 30 Einträge + addNewest → size 30, letzter alter fehlt */ }
void test_next_index_wraps_to_newest() { /* size 3: nextIndex(2) == 0, nextIndex(0) == 1 */ }
void test_next_index_on_empty_list_is_zero() { TEST_ASSERT_EQUAL(0, QuoteList().nextIndex(5)); }
void test_resolve_index_uses_index_when_date_matches() { /* index 1 mit passendem Datum → 1 */ }
void test_resolve_index_follows_date_after_insert() {
    // Position (0, "2026-10-19"), dann addNewest("2026-10-20", ...) → resolveIndex liefert 1
}
void test_resolve_index_with_duplicate_dates_keeps_index() {
    // "2026-10-19|A\n2026-10-19|B\n": resolveIndex(1, "2026-10-19") == 1
}
void test_resolve_index_unknown_date_is_zero() { /* Datum fehlt in der Liste → 0 */ }
```

Die Kommentarzeilen sind als echte Assertions auszuschreiben; die Werte stehen im Kommentar.

- [ ] **Step 3: Test laufen lassen, er muss scheitern**

Run: `cd esp && pio test -e native -f test_quote_list`
Expected: FAILED/ERRORED – `QuoteList.h` fehlt.

- [ ] **Step 4: `QuoteList` umsetzen** in `QuoteList.h/.cpp`

Falle: In C++14 braucht ein `static constexpr`-Mitglied, das per Referenz benutzt wird (zum Beispiel in `std::min`), zusätzlich eine Definition in der `.cpp` (`constexpr std::size_t QuoteList::MAX_QUOTES;`), sonst scheitert der Linker.

Regeln: `parse` trennt an `\n`, entfernt ein `\r` am Zeilenende, überspringt Zeilen ohne `|` und Zeilen, deren Text nach dem ersten `|` leer oder nur Leerzeichen ist, und nimmt höchstens die ersten 30. `addNewest` fügt vorne ein und entfernt hinten, was über 30 hinausgeht. `resolveIndex(index, date)`: passt `at(index).date` zu `date`, gilt `index`; sonst der erste Eintrag mit diesem Datum; sonst 0 (auch bei leerer Liste). `nextIndex`: leer → 0, sonst `(index + 1) % size()`. `at` mit ungültigem Index ist Aufruferfehler – die Aufrufer prüfen `empty()`.

- [ ] **Step 5: Tests laufen lassen, alle müssen bestehen**

Run: `cd esp && pio test -e native -f test_quote_list`
Expected: alle Tests PASSED.

- [ ] **Step 6: Gerätebuild unverändert**

Run: `cd esp && pio run`
Expected: SUCCESS (nur `esp12e` wird gebaut).

- [ ] **Step 7: Commit**

```bash
git add esp/platformio.ini esp/lib/core esp/test/test_quote_list
git commit   # "Zitatliste als reine Logik mit PC-Tests"
```

---

### Task 2: Zitatspeicher mit Umstieg und atomarem Schreiben

**Files:**
- Create: `esp/lib/core/src/QuoteStore.h`, `esp/lib/core/src/QuoteStore.cpp`
- Create: `esp/test/support/MemoryFs.h` (Test-Hilfe, header-only)
- Test: `esp/test/test_quote_store/test_main.cpp`

**Interfaces:**
- Consumes: `QuoteList` (Task 1).
- Produces:
  ```cpp
  namespace QuotePaths {
      constexpr char QUOTES[] = "/quotes.txt";
      constexpr char TEMP[]   = "/quotes.new";
      constexpr char LEGACY[] = "/text.txt";
  }
  class IFileSystem {
  public:
      virtual ~IFileSystem() = default;
      virtual bool exists(const char* path) = 0;
      virtual bool read(const char* path, std::string& out) = 0;
      virtual bool write(const char* path, const std::string& content) = 0;
      virtual bool rename(const char* from, const char* to) = 0;   // ersetzt ein vorhandenes Ziel
      virtual bool remove(const char* path) = 0;
  };
  class QuoteStore {
  public:
      explicit QuoteStore(IFileSystem& fs);
      QuoteList load();
      bool save(const QuoteList& list);
  };
  ```
- `MemoryFs : IFileSystem` hält Dateien in einer `std::map<std::string, std::string>` und hat `bool failRename = false;` zum Simulieren eines Abbruchs.

- [ ] **Step 1: Tests schreiben**

```cpp
void test_load_without_files_is_empty()            // leeres MemoryFs → load().empty()
void test_load_removes_leftover_temp_file()        // /quotes.new + /quotes.txt → nach load() fehlt /quotes.new, Liste aus /quotes.txt
void test_load_migrates_legacy_text() {
    MemoryFs fs; fs.files["/text.txt"] = "Alter Text\r\n";
    QuoteList l = QuoteStore(fs).load();
    TEST_ASSERT_EQUAL(1, l.size());
    TEST_ASSERT_EQUAL_STRING("", l.at(0).date.c_str());
    TEST_ASSERT_EQUAL_STRING("Alter Text", l.at(0).text.c_str());
    TEST_ASSERT_FALSE(fs.exists("/text.txt"));
    TEST_ASSERT_EQUAL_STRING("|Alter Text\n", fs.files["/quotes.txt"].c_str());
}
void test_load_ignores_empty_legacy_text()          // /text.txt = "\r\n" → leere Liste, /text.txt bleibt
void test_load_prefers_quotes_over_legacy()         // beide vorhanden → Liste aus /quotes.txt, /text.txt bleibt
void test_save_writes_quotes_and_no_temp_left()     // save → /quotes.txt == serialize(), /quotes.new fehlt
void test_save_keeps_old_file_when_rename_fails()   // failRename = true → save() == false, /quotes.txt unverändert
```

- [ ] **Step 2: Scheitern sehen**

Run: `cd esp && pio test -e native -f test_quote_store`
Expected: ERRORED – `QuoteStore.h` fehlt.

- [ ] **Step 3: `QuoteStore` umsetzen**

`load()`: `TEMP` löschen, falls vorhanden; `QUOTES` vorhanden → lesen und `QuoteList::parse`; sonst `LEGACY` vorhanden → erste Zeile ohne `\r` und ohne Rand-Leerzeichen; nicht leer → `addNewest("", zeile)`, `save`, bei Erfolg `LEGACY` löschen; sonst leere Liste. `save()`: `write(TEMP, list.serialize())` und `rename(TEMP, QUOTES)`; `false`, sobald ein Schritt scheitert.

- [ ] **Step 4: Tests bestehen**

Run: `cd esp && pio test -e native`
Expected: alle Tests aus Task 1 und 2 PASSED.

- [ ] **Step 5: Commit** – „Zitatspeicher mit Umstieg von /text.txt und atomarem Schreiben“

---

### Task 3: Regeln der Wand

**Files:**
- Create: `esp/lib/core/src/WallLogic.h`, `esp/lib/core/src/WallLogic.cpp`
- Test: `esp/test/test_wall_logic/test_main.cpp`

**Interfaces:**
- Produces:
  ```cpp
  enum class WallAction { None, ShowNewest, ShowNext, ShowCurrent };
  struct WallBoot {
      bool displayOn;        // Anzeige war beim letzten Durchlauf an
      bool displayWriting;   // letzter Durchlauf brach beim Schreiben ab
      bool radarHigh;        // INT_HLK jetzt HIGH
      bool button1;          // BT1-Ereignis in diesem Durchlauf
  };
  constexpr unsigned long BUTTON1_ON_MS = 60000;
  WallAction decideOnBoot(const WallBoot& boot);
  bool wallShouldTurnOff(bool radarHigh, bool button1Active, unsigned long msSinceBoot);
  ```

- [ ] **Step 1: Tests schreiben**

```cpp
void test_button1_on_dark_wall_shows_newest()       // {false,false,false,true} → ShowNewest
void test_button1_on_lit_wall_shows_next()          // {true,false,true,true}  → ShowNext
void test_radar_on_dark_wall_shows_newest()         // {false,false,true,false} → ShowNewest
void test_radar_on_lit_wall_does_nothing()          // {true,false,true,false} → None
void test_interrupted_write_shows_current_again()   // {true,true,false,false} → ShowCurrent
void test_button1_wins_over_interrupted_write()     // {true,true,false,true}  → ShowNext
void test_nothing_happens_on_dark_wall_without_cause() // {false,false,false,false} → None
void test_stays_on_while_radar_high()               // wallShouldTurnOff(true, true, 120000) == false
void test_stays_on_during_button1_minute()          // wallShouldTurnOff(false, true, 59999) == false
void test_turns_off_after_button1_minute()          // wallShouldTurnOff(false, true, 60000) == true
void test_turns_off_when_radar_low_without_button1()// wallShouldTurnOff(false, false, 0) == true
```

- [ ] **Step 2: Scheitern sehen** – `pio test -e native -f test_wall_logic` → ERRORED.

- [ ] **Step 3: `decideOnBoot` und `wallShouldTurnOff` umsetzen**

Reihenfolge in `decideOnBoot`: `button1` → (`displayOn` ? `ShowNext` : `ShowNewest`); sonst `displayWriting` → `ShowCurrent`; sonst `!displayOn && radarHigh` → `ShowNewest`; sonst `None`. `wallShouldTurnOff` = `!radarHigh && (!button1Active || msSinceBoot >= BUTTON1_ON_MS)`.

- [ ] **Step 4: Alle PC-Tests bestehen** – `pio test -e native` → PASSED.

- [ ] **Step 5: Commit** – „Regeln der Wand: was beim Aufwachen gezeigt wird und wann sie ausgeht“

---

### Task 4: Firmware anbinden

**Files:**
- Modify: `esp/lib/drivers/HT16K33.h`, `esp/lib/drivers/HT16K33.cpp` – `void setDisplayOn(bool on);` schreibt `0x80 | (on ? 1 : 0)`
- Modify: `esp/lib/display/display.h`, `esp/lib/display/display.cpp` – `void setPower(bool on);` ruft `setDisplayOn` für alle 12 Module zwischen `I2CMasterControl::enable()` und `disable()`
- Create: `esp/lib/storage/LittleFsAdapter.h`, `esp/lib/storage/LittleFsAdapter.cpp` – `class LittleFsAdapter : public IFileSystem` mit `bool begin();` (bindet LittleFS ein)
- Modify: `esp/lib/system/PersistentState.h`, `esp/lib/system/PersistentState.cpp`
- Modify: `esp/lib/app/application.h`, `esp/lib/app/application.cpp`
- Create: `esp/data/quotes.txt`; Delete: `esp/data/text.txt`
- Modify: `esp/README.md`, `README.md`

**Interfaces:**
- Consumes: `QuoteList`, `QuoteStore`, `IFileSystem`, `QuotePaths` (Task 1–2), `WallAction`, `WallBoot`, `decideOnBoot`, `wallShouldTurnOff`, `BUTTON1_ON_MS` (Task 3).
- `PersistentState::Data` neu (20 Bytes, Vielfaches von 4):
  ```cpp
  uint16_t lastExpanderState;
  uint8_t  displayState;    // 0 = aus, 1 = an, 2 = wird geschrieben
  uint8_t  button1Active;   // 1 = BT1-Minute läuft
  uint32_t wakeCount;
  uint8_t  shownIndex;
  char     shownDate[11];   // "JJJJ-MM-TT" oder "" für Eintrag ohne Datum
  ```
  `textIndex` und `reserved` entfallen; `MAGIC = 0x52574C32`; `setDefaults` setzt alles auf 0 bzw. leer, `lastExpanderState` wie bisher auf `0xFFFF`.
- `Application`: neue Mitglieder `LittleFsAdapter _fs;` und `QuoteStore _quotes;` (in dieser Reihenfolge deklarieren, `_quotes(_fs)` im Konstruktor). `showText()` entfällt; neu `void showQuote(WallAction action);`, `void runWallLoop();`, `void turnWallOff();`. `TextStorage _storage` und `_pi` bleiben unverändert (Teil 1 ersetzt sie).

- [ ] **Step 1: Anzeige aus- und einschaltbar machen** (HT16K33, Display) – Build: `pio run` → SUCCESS.

- [ ] **Step 2: `LittleFsAdapter` und neues `PersistentState`** – Build: `pio run` → SUCCESS.

- [ ] **Step 3: `Application::run()` umbauen**

Ablauf nach dem Lesen der Tasten (bestehender Code bis `collectEvents` bleibt):
1. Kaltstart zeigt **keinen** Text mehr (der Block `if (_coldBoot) showText();` entfällt).
2. Erst BT2 und die übrigen Ereignisse über `handleInput` abarbeiten; der `BT1`-Zweig dort tut nichts mehr (Kommentar: „über die Wand-Regeln“).
3. `button1` = ein BT1-Ereignis liegt vor; `radarHigh` = `digitalRead(Pins::INT_HLK) == HIGH`. `decideOnBoot({displayState != 0, displayState == 2, radarHigh, button1})`. Bei `button1`: `button1Active = 1`.
4. `showQuote(action)`, wenn die Aktion nicht `None` ist.
5. Ist `displayState == 1`: `runWallLoop()`.
6. Zustand sichern, Deep Sleep (wie bisher).

`showQuote`: `_fs.begin()`, `_quotes.load()`. Leer → Text `KEIN TEXT`, `shownIndex = 0`, `shownDate = ""`. Sonst Index: `ShowNewest` → 0; `ShowCurrent` → `resolveIndex(shownIndex, shownDate)`; `ShowNext` → `nextIndex(resolveIndex(shownIndex, shownDate))`. Vor dem Schreiben `displayState = 2` und `PersistentState::save`; dann `ensureDisplayReady()` und `_display.show(text)`; danach `displayState = 1`, Index und Datum merken, sichern. Log: `[WALL] <Aktion> -> #<Index> <Datum> "<Text>"`; länger als 96 Zeichen → Warnung wie bisher.

`runWallLoop`: alle 200 ms `radarHigh` lesen; `wallShouldTurnOff(radarHigh, button1Active, millis())` → `turnWallOff()` und zurück. `turnWallOff`: `_display.setPower(false)`, `displayState = 0`, `button1Active = 0`, sichern, Log `[WALL] aus`.

- [ ] **Step 4: Daten und Doku**

`esp/data/quotes.txt`: eine Zeile `2026-10-19|Wer nach innen schaut erwacht. Wer nach aussen schaut traeumt. Finde heute deinen neuen Weg.` – `esp/data/text.txt` löschen. `esp/README.md`: Tastentabelle (BT1 zeigt das neueste Zitat bzw. schaltet weiter), Abschnitt „Text im Flash“ → „Zitatliste im Flash“ mit Format, Umstieg und `KEIN TEXT`, Ablauf (Wand dunkel, Radar, BT1-Minute), neuer Abschnitt „Tests auf dem PC“ mit `pio test -e native`. `README.md` (Hauptordner): ESP-Zeile „zeigt das Zitat, wenn jemand davorsteht“.

- [ ] **Step 5: Prüfen**

Run: `cd esp && pio test -e native` → alle PASSED. `pio run` → SUCCESS ohne Warnungen.

- [ ] **Step 6: Commit** – „Wand dunkel, Radar und BT1 zeigen Zitate aus der Liste im Flash“

---

### Task 5: Abnahme am Gerät (mit dem Owner)

Braucht den USB-Flasher an X1 und jemanden an der Wand. Ergebnis jedes Schritts ist eine Zeile aus dem seriellen Log (74 880 Baud) oder die Beobachtung des Owners.

Ohne angeschlossenes Radar `RADAR_INSTALLED = false` (Schritte 1-3, 5); für Schritt 4 Radar anschliessen und auf `true` setzen.

- [ ] **Step 1: Umstieg** – nur Firmware flashen (`pio run -t upload`), **kein** `uploadfs`. Auf dem Gerät liegt noch `/text.txt`. Erwartet direkt nach dem Flashen: Wand ist **dunkel** (der Kaltstart schaltet sie ab; steht der alte Text noch, ist I1 nicht erfüllt). Danach BT1 drücken. Erwartet: Wand zeigt den bisherigen Text; Log `[WALL] neuestes -> #0  "..."`. (Die Aktionen heissen im Log `neuestes`, `naechstes`, `aktuelles`.)
- [ ] **Step 2: Liste** – `esp/data/quotes.txt` vorübergehend auf drei Zeilen erweitern, `pio run -t uploadfs`. BT1 bei dunkler Wand → Zitat 1; BT1 → 2; BT1 → 3; BT1 → 1. Danach `data/quotes.txt` zurücksetzen und erneut `uploadfs`.
- [ ] **Step 3: BT1-Minute** – vom Radar weg stehen (oder Radar abdecken), BT1 drücken. Erwartet: Wand geht nach etwa 60 s aus; Log `[WALL] aus`.
- [ ] **Step 4: Radar** – (Hinweis: INT_HLK ist `INPUT_PULLUP`; ein nicht angeschlossener oder unversorgter Radar liest HIGH und hält die Wand dauerhaft an.) Vor die Wand treten. Erwartet: neuestes Zitat erscheint; Wand bleibt an, solange man davorsteht; nach dem Gehen aus (Nachlaufzeit notieren – Offener Punkt im Entwurf).
- [ ] **Step 5: Leere Liste** – `uploadfs` mit leerem `data/` (Datei vorübergehend beiseitelegen), BT1. Erwartet: `KEIN TEXT`. Danach Liste wiederherstellen.
- [ ] **Step 6: Commit/Notiz** – gemessene Nachlaufzeit des Radars in den Entwurf (Abschnitt 15) eintragen und committen.
