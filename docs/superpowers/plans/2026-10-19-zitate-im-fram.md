# Teil 3a-2: Zitate im FRAM – Umsetzungsplan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Die Zitatliste kann im FRAM liegen. Sie liegt dort auf zwei Plätzen, damit ein Reset mitten im Schreiben die alte Liste nicht zerstört. Eine `/quotes.txt` im Flash wird einmal ins FRAM übernommen und danach gelöscht. Das FRAM ist seit 2026-10-20 bestückt; der Schalter `FRAM_INSTALLED` steht auf `true`. Mit `false` läuft die Firmware wie heute aus dem Flash.

**Architecture:** Das Format der Plätze, die Prüfsumme und der Briefkasten sind reines C++ ohne Arduino in `esp/lib/core` und werden auf dem PC mit einem nachgebildeten FRAM getestet. Die Firmware bindet sie mit einem dünnen I²C-Adapter an das MB85RC256V und wählt über `FRAM_INSTALLED` zwischen FRAM und dem bestehenden Flash-Speicher. Das Zitat der Nacht (P1-a, RTC-Feld `nightQuote`) gehört zu Teil 3b und ist nicht Teil dieses Plans.

**Tech Stack:** ESP8266 Arduino-Core über PlatformIO (`env:esp12e`), Wire (I²C), LittleFS, Unity-Tests in der PlatformIO-Umgebung `native` mit MinGW GCC 6.3.

**Spec:** `docs/superpowers/specs/2026-10-19-esp-pi-steuerung-design.md` – Abschnitt 2 (P1-a bis F1-a und die zwei Zeilen danach), 11 (Liste der Zitate, FRAM, Flash), 15 (FRAM mit 100 kHz), 16 (Teil 3a-2).

## Global Constraints

- Code in `esp/lib/core/` bindet **keine** Arduino-Header ein und bleibt bei **C++14** (MinGW GCC 6.3: kein `std::optional`, kein `std::string_view`).
- FRAM: MB85RC256V, 32 KB (`0x0000`–`0x7FFF`), I²C-Adresse **0x50**, 16-Bit-Adresse, höherwertiges Byte zuerst.
- Zwei Plätze: **A ab `0x0000`, B ab `0x1000`**, je **4096 Bytes**. Kopf **16 Bytes**, danach die Liste im Textformat von `QuoteList::serialize()`. Höchstens **4080 Bytes** Liste pro Platz.
- Kopf, alle Zahlen als `uint32_t` little-endian: Byte 0–3 Kennung **`0x31515752`** (die Bytes `R W Q 1`), Byte 4–7 laufende Nummer, Byte 8–11 Länge der Liste, Byte 12–15 **CRC-32** über Byte 4–11 und die Liste.
- CRC-32 nach IEEE 802.3 (Polynom `0xEDB88320` gespiegelt, Startwert `0xFFFFFFFF`, Ende XOR `0xFFFFFFFF`). Prüfwert: `"123456789"` → `0xCBF43926`.
- Lesen: gültig ist ein Platz mit richtiger Kennung, Länge ≤ 4080 und passender Prüfsumme. Massgeblich ist der gültige Platz mit der höheren Nummer. Kein Platz gültig → leere Liste.
- Schreiben: in den anderen Platz als den massgeblichen (keiner gültig → Platz A), Nummer = massgebliche Nummer + 1 (keiner gültig → 1). **Erst die Liste, dann der Kopf.**
- Briefkasten (P3-b): Liegt `/quotes.txt` im Flash, wird ihr Inhalt ins FRAM geschrieben und danach `/quotes.txt` gelöscht, ebenso ein übriggebliebenes `/quotes.new`. Fehlt `/quotes.txt`, gilt dasselbe für `/text.txt` (erste Zeile, ohne Datum, wie im heutigen Umstieg). **Keine Datei → das FRAM bleibt unverändert. Eine leere Datei → die Liste im FRAM wird leer.**
- Lesefehler am Bus → leere Liste (die Wand zeigt `KEIN TEXT`), und `save()` verweigert in diesem Durchlauf.
- `FRAM_INSTALLED = true` als `constexpr bool` neben `RADAR_INSTALLED` in `esp/lib/app/application.cpp`. Mit `false` verhält sich die Firmware **genau wie heute**.
- Für FRAM-Zugriffe taktet `FramBus` den Bus mit **100 kHz** (`FramBus::CLOCK_HZ = 100000`) und stellt danach auf jedem Weg wieder `I2CMasterControl::I2C_CLOCK_HZ` (10 kHz) ein. Alle anderen Zugriffe bleiben bei 10 kHz. Jeder Buszugriff wird mit `I2CMasterControl::enable()` / `disable()` geklammert.
- Gemessen 2026-10-20 mit 3,3 KB bei 100 kHz: Schreiben 415 ms, Lesen 429 ms, 5 von 5 fehlerfrei.
- `esp/data/quotes.txt` bleibt, bis die Liste am Gerät ins FRAM übernommen ist (Task 4).
- Die alten Dateien `esp/lib/storage/textStorage.*`, `framTextStorage.*`, `espTextStorage.*`, `ITextStorage.h` **nicht anfassen**: Die alte Pi-Kommunikation nutzt sie bis Teil 1.

## Review Focus

1. **Watchdog und Taktrate:** Eine volle Liste braucht bei 100 kHz etwa 0,4 s am Bus, bei versehentlich 10 kHz über 4 s. Ohne `yield()` zwischen den Stücken setzt der Watchdog den ESP zurück, und ein vergessenes Zurückstellen des Takts liesse die Anzeigen mit 100 kHz laufen. → Kein PC-Test möglich; der Adapter in Task 3 ruft `yield()` nach jedem Stück und stellt den Takt auf jedem Weg zurück; Task 4 misst die Zeit am Gerät.
2. **I²C-Puffer:** Der Wire-Puffer des ESP8266 fasst 128 Bytes. Ein Stück darf mit den 2 Adressbytes nicht darüber liegen. → Der Adapter in Task 3 überträgt Stücke von **32 Bytes**.
3. **Reset mitten im Schreiben:** Die alte Liste muss gültig bleiben. → Test `test_interrupted_write_keeps_previous_list` in Task 1.
4. **`uploadfs` ohne Datei:** Ein Hochladen ohne `quotes.txt` darf die Liste im FRAM nicht löschen; eine leere `quotes.txt` dagegen leert sie. → Tests `test_load_without_mailbox_keeps_fram_list` und `test_load_imports_empty_mailbox_file` in Task 2.
5. **Bus bleibt belegt:** Bricht ein Lese- oder Schreibvorgang ab, muss der Adapter den Bus trotzdem freigeben (`disable()` und Takt zurück auf jedem Weg). → Prüfpunkt im Review von Task 3.

---

### Task 1: Prüfsumme und zwei Plätze im FRAM

**Files:**
- Create: `esp/lib/core/src/Crc32.h`, `esp/lib/core/src/Crc32.cpp`
- Create: `esp/lib/core/src/SlotStore.h`, `esp/lib/core/src/SlotStore.cpp`
- Create: `esp/test/support/MemoryBytes.h`
- Test: `esp/test/test_slot_store/test_main.cpp`

**Interfaces:**
- Produces:
  ```cpp
  // Crc32.h
  uint32_t crc32(const uint8_t* data, std::size_t length, uint32_t crc = 0);  // fortsetzbar: crc32(b, n, crc32(a, m))

  // SlotStore.h
  class IByteStore {                      // ein Speicher mit 16-Bit-Adressen
  public:
      virtual ~IByteStore() = default;
      virtual bool read(uint16_t address, uint8_t* out, std::size_t length) = 0;
      virtual bool write(uint16_t address, const uint8_t* data, std::size_t length) = 0;
  };

  namespace SlotLayout {
      constexpr uint16_t SLOT_A = 0x0000;
      constexpr uint16_t SLOT_B = 0x1000;
      constexpr std::size_t SLOT_SIZE = 4096;
      constexpr std::size_t HEADER_SIZE = 16;
      constexpr std::size_t MAX_CONTENT = SLOT_SIZE - HEADER_SIZE;   // 4080
      constexpr uint32_t MAGIC = 0x31515752;                          // "RWQ1"
  }

  class SlotStore {
  public:
      enum class ReadResult { Ok, Empty, BusError };
      explicit SlotStore(IByteStore& bytes);
      ReadResult read(std::string& content);       // Inhalt des massgeblichen Platzes
      bool write(const std::string& content);      // false: zu lang oder Busfehler
  };
  ```
- `MemoryBytes` (Test-Hilfe): 32 KB, anfangs mit `0x00` gefüllt; Felder `bool failRead`, `bool failWrite`, `long writeBudget = -1` (≥ 0: nach so vielen geschriebenen Bytes scheitert jedes weitere `write`, die Bytes davor stehen schon im Speicher – das ist ein Reset mitten im Schreiben).

- [ ] **Step 1: Tests schreiben**

```cpp
void test_crc32_check_value()      // crc32("123456789", 9) == 0xCBF43926
void test_crc32_can_continue()     // crc32("6789",4, crc32("12345",5)) == 0xCBF43926
void test_read_blank_is_empty()    // frisches MemoryBytes → ReadResult::Empty, content leer
void test_write_then_read()        // write("2026-10-19|Eins\n") → read == Ok, gleicher Inhalt
void test_first_write_goes_to_slot_a_with_number_1()
    // nach write: Bytes 0..3 = 52 57 51 31, Bytes 4..7 = 01 00 00 00, Platz B unverändert 0
void test_second_write_goes_to_slot_b()
    // zwei writes → Kopf bei 0x1000 mit Nummer 2, read liefert den zweiten Inhalt
void test_third_write_goes_back_to_slot_a()   // Nummer 3 bei 0x0000
void test_interrupted_write_keeps_previous_list()
    // write("alt1"); write("alt2"); writeBudget = 5; write("neu") == false; writeBudget = -1;
    // (der dritte write überschreibt den gültigen Platz A mit "alt1" und bricht ab)
    // neues SlotStore auf denselben Bytes: read == Ok, Inhalt "alt2"
void test_corrupt_newest_slot_falls_back()
    // zwei writes, dann ein Byte der Liste in Platz B kippen → read liefert den ersten Inhalt
void test_too_long_content_is_refused()
    // write(std::string(4081, 'x')) == false, Speicher unverändert; 4080 Zeichen gehen
void test_read_error_is_bus_error()  // failRead = true → ReadResult::BusError
void test_write_without_read_continues_numbering()
    // SlotStore s1 schreibt zweimal; neues SlotStore s2 schreibt ohne read → Nummer 3 in Platz A
```

- [ ] **Step 2: Tests laufen lassen, sie müssen scheitern**

Run: `cd esp && pio test -e native -f test_slot_store`
Expected: FAIL beim Übersetzen (`Crc32.h` / `SlotStore.h` fehlen).

- [ ] **Step 3: `crc32` und `SlotStore` umsetzen**

`read()`: beide Köpfe lesen; Kandidaten mit richtiger Kennung und Länge ≤ `MAX_CONTENT`, die mit der höheren Nummer zuerst; Liste lesen, Prüfsumme vergleichen; der erste gültige ist massgeblich. Jeder gescheiterte `IByteStore::read` → `BusError`. `SlotStore` merkt sich Platz und Nummer des massgeblichen Platzes. `write()` ruft zuerst `read()`, wenn es noch keinen Stand kennt, schreibt dann die Liste bei Platz + 16 und zuletzt den Kopf, und merkt sich bei Erfolg den neuen Platz. Zahlen im Kopf von Hand als little-endian zerlegen, kein `memcpy` einer Struktur.

- [ ] **Step 4: Tests bestehen**

Run: `cd esp && pio test -e native`
Expected: alle Tests PASSED (die 47 bestehenden und die neuen).

- [ ] **Step 5: Commit** – „Zwei Plätze mit CRC-32 für die Zitatliste im FRAM“

---

### Task 2: Zitatspeicher im FRAM mit Briefkasten

**Files:**
- Create: `esp/lib/core/src/IQuoteStore.h`
- Create: `esp/lib/core/src/FramQuoteStore.h`, `esp/lib/core/src/FramQuoteStore.cpp`
- Modify: `esp/lib/core/src/QuoteStore.h` (`QuoteStore` erbt von `IQuoteStore`), `esp/lib/core/src/QuoteStore.cpp` nur falls nötig
- Modify: `esp/test/support/MemoryFs.h` (`bool failWrite`, falls ein Test es braucht)
- Test: `esp/test/test_fram_quote_store/test_main.cpp`

**Interfaces:**
- Consumes: `IByteStore`, `SlotStore` (Task 1); `IFileSystem`, `QuotePaths`, `QuoteList` (bestehend).
- Produces:
  ```cpp
  // IQuoteStore.h
  class IQuoteStore {
  public:
      virtual ~IQuoteStore() = default;
      virtual QuoteList load() = 0;
      virtual bool save(const QuoteList& list) = 0;
  };

  // FramQuoteStore.h
  struct FramLoadInfo {
      bool imported = false;       // Briefkasten übernommen und gelöscht
      bool importFailed = false;   // Briefkasten gelesen, aber Schreiben ins FRAM gescheitert
      bool busError = false;       // FRAM nicht lesbar
      std::size_t bytes = 0;       // Länge der gelesenen oder übernommenen Liste
  };

  class FramQuoteStore : public IQuoteStore {
  public:
      FramQuoteStore(IByteStore& fram, IFileSystem& mailbox);
      QuoteList load() override;
      bool save(const QuoteList& list) override;
      const FramLoadInfo& lastLoad() const;
  };
  ```

- [ ] **Step 1: Tests schreiben**

```cpp
void test_load_imports_mailbox_and_removes_file()
    // fs: /quotes.txt = "2026-10-21|Neu\n" → load().at(0).text == "Neu", /quotes.txt fehlt,
    // lastLoad().imported, ein zweites FramQuoteStore auf denselben Bytes liest "Neu"
void test_import_removes_leftover_temp_file()     // /quotes.new fehlt danach ebenfalls
void test_load_imports_legacy_text()
    // nur /text.txt = "Alter Text\r\n" → ein Eintrag ohne Datum, /text.txt gelöscht
void test_mailbox_replaces_existing_fram_list()   // FRAM hat "A", Briefkasten "B" → Liste "B"
void test_load_without_mailbox_keeps_fram_list()  // FRAM hat Liste, fs leer → Liste unverändert, fs unberührt
void test_load_imports_empty_mailbox_file()       // FRAM hat Liste, /quotes.txt = "" → Liste leer, Datei gelöscht
void test_bus_error_gives_empty_list_and_refuses_save()
    // failRead → load().empty(), lastLoad().busError, save(...) == false
void test_failed_import_keeps_file_shows_list_and_refuses_save()
    // failWrite → load() liefert die Liste aus /quotes.txt, Datei bleibt, importFailed, save == false
void test_save_then_load_round_trip()             // save(Liste mit 2 Einträgen) → load() gleich
```

- [ ] **Step 2: Tests laufen lassen, sie müssen scheitern**

Run: `cd esp && pio test -e native -f test_fram_quote_store`
Expected: FAIL beim Übersetzen (`FramQuoteStore.h` fehlt).

- [ ] **Step 3: `IQuoteStore` und `FramQuoteStore` umsetzen; `QuoteStore` erbt von `IQuoteStore`**

`load()` setzt `lastLoad()` zurück. Briefkasten zuerst (`QUOTES`, sonst `LEGACY` mit derselben Regel für die erste Zeile wie `QuoteStore`; die kleine Hilfsfunktion dafür in eine gemeinsame Stelle ziehen statt sie zu kopieren). Danach `SlotStore::read`. Ein `save()` nach einem Busfehler oder einem gescheiterten Import gibt `false` zurück und schreibt nichts.

- [ ] **Step 4: Tests bestehen**

Run: `cd esp && pio test -e native`
Expected: alle Tests PASSED.

- [ ] **Step 5: Commit** – „Zitatspeicher im FRAM mit Briefkasten im Flash“

---

### Task 3: Firmware anbinden, Schalter `FRAM_INSTALLED`

**Files:**
- Create: `esp/lib/storage/FramBus.h`, `esp/lib/storage/FramBus.cpp`
- Modify: `esp/lib/app/application.h` (Mitglieder), `esp/lib/app/application.cpp` (Schalter, `showQuote`, Log)
- Modify: `esp/README.md` (I²C-Tabelle: FRAM nicht mehr „optional“; Abschnitt „Zitate im FRAM“)

**Interfaces:**
- Consumes: `IByteStore`, `FramQuoteStore`, `FramLoadInfo`, `IQuoteStore` (Task 1, 2); `I2CMasterControl::enable()` / `disable()`.
- Produces:
  ```cpp
  class FramBus : public IByteStore {     // MB85RC256V auf 0x50
  public:
      static constexpr uint8_t ADDRESS = 0x50;
      static constexpr std::size_t CHUNK = 32;
      static constexpr uint32_t CLOCK_HZ = 100000;   // nur fuer das FRAM
      bool read(uint16_t address, uint8_t* out, std::size_t length) override;
      bool write(uint16_t address, const uint8_t* data, std::size_t length) override;
  };
  ```

- [ ] **Step 1: `FramBus` umsetzen**

Zugriffe ausserhalb `0x0000`–`0x7FFF` → `false`. Jeder Aufruf: `enable()`, `Wire.setClock(CLOCK_HZ)`, dann Stücke zu höchstens `CHUNK` Bytes (Schreiben: Adresse + Daten in einer Übertragung; Lesen: Adresse senden mit `endTransmission(false)`, dann `requestFrom`), nach jedem Stück `yield()`, am Ende auf **jedem** Weg `Wire.setClock(I2CMasterControl::I2C_CLOCK_HZ)` und `disable()`. Gescheitertes `endTransmission` oder zu wenig Bytes → `false`.

- [ ] **Step 2: Anwendung umstellen**

- `constexpr bool FRAM_INSTALLED = true;` direkt unter `RADAR_INSTALLED`, mit Kommentar: MB85RC256V auf 0x50; mit `false` liegt die Liste wie früher in `/quotes.txt` im Flash.
- Mitglieder in dieser Reihenfolge: `LittleFsAdapter _fs; FramBus _framBus; QuoteStore _flashQuotes; FramQuoteStore _framQuotes;` und eine private Methode `IQuoteStore& quotes();`, die je nach `FRAM_INSTALLED` einen der beiden zurückgibt.
- `showQuote`: `_fs.begin()` wie bisher, dann `quotes().load()`. Ist `FRAM_INSTALLED`, die Ladezeit messen und loggen:
  - `[QUOTES] FRAM: <bytes> Bytes in <ms> ms gelesen`
  - bei `imported`: `[QUOTES] Liste aus dem Flash ins FRAM uebernommen`
  - bei `importFailed`: `[QUOTES] FEHLER: Uebernahme ins FRAM gescheitert, Datei bleibt`
  - bei `busError`: `[QUOTES] FEHLER: FRAM 0x50 nicht lesbar`
- Die Meldung `[WALL] FEHLER: kein Zitat im Flash` wird zu `[WALL] FEHLER: kein Zitat gespeichert`.

- [ ] **Step 3: README nachziehen**

Abschnitt „Zitate im FRAM“: Plätze, 100 kHz und Briefkasten in wenigen Sätzen, Verweis auf Spezifikation Abschnitt 11. Wie man eine Liste lädt: Datei nach `esp/data/quotes.txt` legen, `pio run -t uploadfs`, BT1 – der ESP übernimmt sie und löscht sie im Flash; Achtung, das ersetzt die Zitate der KI. Eine Beispielliste liegt in `esp/data-beispiel/` (ab Task 4).

- [ ] **Step 4: Prüfen**

Run: `cd esp && pio test -e native` → alle PASSED. `pio run` → SUCCESS ohne neue Warnungen.
Zusätzlich einmal mit `FRAM_INSTALLED = false` übersetzen (`pio run`, danach zurück auf `true`), damit der Flash-Zweig sicher kompiliert.

- [ ] **Step 5: Commit** – „FRAM-Anbindung mit Schalter FRAM_INSTALLED, Bus fuer das FRAM mit 100 kHz“

---

### Task 4: Abnahme am Gerät mit FRAM (mit dem Owner)

- [ ] **Step 1: Übernahme** – flashen. Auf dem Gerät liegt noch `/quotes.txt` aus Teil 3a. BT1 bei dunkler Wand. Erwartet: Log `[QUOTES] Liste aus dem Flash ins FRAM uebernommen`, das Zitat erscheint, `[WALL] neuestes -> #0 ...`.
- [ ] **Step 2: Aus dem FRAM** – Wand ausgehen lassen, BT1. Erwartet: dasselbe Zitat, Log `[QUOTES] FRAM: … Bytes in … ms gelesen`, keine Übernahme mehr (die Datei im Flash ist weg).
- [ ] **Step 3: Stromunterbruch** – Speisung **und** Flasher trennen, wieder anschliessen, BT1. Erwartet: dasselbe Zitat aus dem FRAM.
- [ ] **Step 4: Volle Liste** – 30 Zitate nach `esp/data/quotes.txt`, `uploadfs`, BT1, dann BT1 weiterschalten (1 → 2 → …). Erwartet: Übernahme, Durchschalten wie in Teil 3a; Ladezeit aus dem Log in Spezifikation Abschnitt 15 eintragen (Zeile „FRAM mit 100 kHz“ schliessen).
- [ ] **Step 5: Startliste zurück** – `esp/data/quotes.txt` mit der Startliste aus Teil 3a (ein Zitat) hochladen, BT1, Übernahme prüfen. Danach die Datei nach `esp/data-beispiel/quotes.txt` verschieben, damit `esp/data/` leer ist (P3-b), README-Verweis prüfen, committen.
