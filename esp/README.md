# Reflection Wall – Firmware ESP8266

PlatformIO-Projekt (Arduino-Framework) für den ESP-12E.

## Bauen und Flashen

```bash
cd esp
pio run                 # bauen
pio run -t upload       # flashen über USB (esptool)
pio device monitor      # serielle Konsole, 74880 Baud
```

**OTA:** In `platformio.ini` die Zeilen unter `#OTA` aktivieren (`upload_protocol = espota`, `upload_port = reflectionwall.local`). Dafür muss `WAKE_RF_MODE` in `application.cpp` auf `WAKE_RF_DEFAULT` stehen, sonst bleibt das WLAN aus.

## Ablauf im Normalbetrieb

Es gibt keine Hauptschleife. Der ESP liegt im Deep Sleep; ein Tastendruck am PCF8575 löst über dessen INT-Ausgang einen Reset aus. `Application::run()` läuft dann genau einmal durch:

1. WLAN aus (spart Strom und Bootzeit)
2. Weckgrund lesen
3. Zustand aus dem RTC-Speicher laden (`PersistentState`)
4. Expander lesen, Taster auswerten
5. Wand-Regeln anwenden: Radar (INT_HLK) und BT1 entscheiden, ob ein Zitat angezeigt wird (siehe unten)
6. Zustand sichern, Deep Sleep

| Taster | Aktion |
|---|---|
| BT1 | Wand an: zeigt das neueste Zitat, bei jedem weiteren Druck das nächste in der Liste; die Wand bleibt danach 60 s an |
| BT2 | Raspberry Pi ein-/ausschalten (Puls auf das Flipflop am Relais, GPIO12) |
| BT3–BT6 | noch nicht belegt |

BT1–BT3 laufen über Toggle-Flipflops (Blatt „Button Debouncing“, Jumper J10/J12/J14): jeder Druck kippt den Pegel am Expander, und der neue Pegel bleibt stehen, bis der ESP ihn liest. Die Firmware wertet deshalb jeden Wechsel als einen Druck (`InputTrigger::ANY_EDGE`), auch einen ganz kurzen. BT4–BT6 hängen direkt am Expander; ein kurzer Druck ist dort vorbei, bevor der ESP nach dem Reset liest, deshalb lösen sie nichts aus.

## Wand dunkel, Radar und BT1

Nach dem Einschalten bleibt die Wand dunkel. Sie geht an, wenn der Radar (INT_HLK) HIGH meldet oder BT1 gedrückt wird, und zeigt dann ein Zitat aus der Liste im Flash:

- **Radar:** zeigt das neueste Zitat. Bleibt der Radar HIGH, bleibt die Wand an; der ESP bleibt dann wach und liest den Radar alle 200 ms. Fällt der Radar auf LOW, geht die Wand aus (die Regeln stehen in `lib/core/src/WallLogic.cpp`).
- **BT1:** schaltet die Wand ein und zeigt das neueste Zitat; jeder weitere Druck zeigt das nächste in der Liste. Die Wand bleibt dann mindestens 60 s an (`BUTTON1_ON_MS`), unabhängig vom Radar.
- **Ausschalten:** die Anzeige wird dunkel geschaltet (HT16K33 Display-off), der Inhalt bleibt in den Modulen erhalten. Der Zustand (aus / an / wird geschrieben) liegt im RTC-Speicher; bricht ein Durchlauf beim Schreiben ab, schreibt der nächste das Zitat neu.

## Zitatliste im Flash

Die Zitate stehen in `/quotes.txt` im LittleFS des ESP (`lib/storage`, `lib/core`), höchstens 30, das neueste zuerst. Pro Zeile ein Zitat im Format `JJJJ-MM-TT|Text`; eine Zeile ohne Datum ist ebenfalls erlaubt. Die erste Liste legt man in `data/quotes.txt` ab und lädt sie einmal hoch:

```bash
pio run -t uploadfs     # überschreibt das ganze Dateisystem
```

**Umstieg:** Gibt es noch keine `/quotes.txt`, aber die alte `/text.txt`, übernimmt die Firmware deren Text beim ersten Lesen als einziges Zitat.

Die Anzeige fasst 96 Zeichen (12 Module × 8); Umlaute müssen umschrieben sein, die Segmentschrift kennt nur `A–Z`, `0–9` und `- . / : + *`. Ist ein Text länger, meldet das Log die Länge. Ist die Liste leer oder fehlt die Datei, zeigt die Wand „KEIN TEXT“.

## Tests auf dem PC

Die Logik ohne Arduino-Abhängigkeit (`lib/core`: Zitatliste, Zitatspeicher, Wand-Regeln) wird auf dem PC getestet:

```bash
cd esp
pio test -e native
```

## Pins

| Funktion | GPIO |
|---|---|
| I²C SDA / SCL | 4 / 5 |
| I²C-Master-Auswahl (HIGH = ESP) | 15 |
| Power-Switch Raspberry Pi | 12 |
| INT GPIO-Expander | 14 |
| INT HLK-Radar | 13 |
| Status-LED | 0 |

## I²C-Adressen

| Adresse | Teilnehmer |
|---|---|
| 0x20 | PCF8575 GPIO-Expander (Taster) |
| 0x50 | FRAM (Textspeicher, optional) |
| 0x70–0x77 | Anzeigen Zeile 1–3, direkt am Bus |
| 0x7F | Zeile 3, Spalte 3 – hinter LTC4316 A (nativ 0x77) |
| 0x79, 0x7B, 0x7D | Zeile 4 – hinter LTC4316 B (nativ 0x71, 0x73, 0x75) |

Takt: 10 kHz (`I2CMasterControl::I2C_CLOCK_HZ`), gemessen ~9 kHz.

## Aufbau

```
src/main.cpp              ruft nur Application::run() auf
lib/app/                  Ablauf, Taster (application.cpp), Buffer-Test (BufferTest.cpp)
lib/display/              Display (12 Module), DisplayGrid (Zeilenumbruch), 16-Segment-Font
lib/drivers/              HT16K33, PCF8575, I2CMasterControl (Master-Umschaltung, Bus-Befreiung)
lib/Wire/                 eigene Software-I²C (ersetzt die Core-Bibliothek, siehe unten)
lib/gpioExpander/         Taster-Auswertung (Flanken, Pegel)
lib/system/               Weckgrund, Zustand im RTC-Speicher
lib/core/                 Zitatliste, Zitatspeicher, Wand-Regeln (ohne Arduino, Tests auf dem PC)
lib/storage/              LittleFS-Anbindung der Zitatliste (LittleFsAdapter), Textspeicher ESP bzw. FRAM
data/quotes.txt           Zitatliste für pio run -t uploadfs
lib/communication/        UART-Protokoll zum Raspberry Pi (COMMAND|DATA)
lib/ota/                  WLAN, OTA, Debug-Logger (Telnet)
lib/config/pinMapping.h   Pinbelegung
```

### Eigene Wire-Bibliothek (`lib/Wire`)

Ersetzt die Software-I²C des ESP8266-Cores und hat Vorrang vor ihr. Unterschiede:

- **SDA-Hold:** wartet nach jedem „SCL low“ 10 µs, bevor SDA wechselt
- **Clock-Stretch-Limit:** 20 ms
- Diagnose: `setIgnoreDataNack()`, `setAckTrace()`, `lastAckFallAfterStartUs()` – die Firmware ruft sie derzeit nicht auf

## Buffer-Test

Abnahmetest für den I²C-Buffer PCA9517A. Eingeschaltet wird er mit `BUFFER_TEST = true` in `lib/app/application.cpp`; er läuft dann endlos statt in den Deep Sleep zu gehen. Der ganze Bildschirm zeigt „ADR xx n“, der Test prüft pro angeschlossenem Modul den Befehl 0x81 und liest den Text zurück. Nicht angeschlossene Module werden übersprungen. Code in `lib/app/BufferTest.cpp`.

**Für den Normalbetrieb `BUFFER_TEST = false`.**

### Ausgabe des Buffer-Tests

```
[BUF] #12  0x7B ok
[BUF] ---- Stand nach 10 Runden ----
[BUF]   0x7B: 10 ok, 0 Fehler (0x81 NACK 0, Text abgebrochen 0, Lesen 0, Text falsch 0, Bus 0)
```

Bestanden, wenn alle angeschlossenen Module über längere Zeit 0 Fehler zeigen – vor allem 0x7B und 0x7F.
