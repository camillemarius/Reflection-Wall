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

Es gibt keine Hauptschleife. Der ESP liegt im Deep Sleep; ein Tastendruck am PCF8575 löst über dessen INT-Ausgang einen Reset aus, ebenso der Radar (INT_HLK). `Application::run()` läuft dann durch und legt den ESP wieder schlafen. Solange die Wand mit dem Radar an ist, bleibt der ESP in `run()` wach und liest den Radar (siehe unten). Ohne Radar legt er sich nach dem Durchlauf schlafen und wacht mit dem nächsten Reset auf:

1. WLAN aus (spart Strom und Bootzeit)
2. Weckgrund lesen
3. Zustand aus dem RTC-Speicher laden (`PersistentState`)
4. Expander lesen, Taster auswerten
5. Wand-Regeln anwenden: Radar (INT_HLK) und BT1 entscheiden, ob ein Zitat angezeigt wird (siehe unten)
6. Zustand sichern, Deep Sleep

| Taster | Aktion |
|---|---|
| BT1 | Wand an: zeigt das neueste Zitat, bei jedem weiteren Druck das nächste in der Liste; die Wand geht 1 min nach dem letzten Druck aus |
| BT2 | Raspberry Pi ein-/ausschalten (Puls auf das Flipflop am Relais, GPIO12) |
| BT3–BT6 | noch nicht belegt |

BT1–BT3 laufen über Toggle-Flipflops (Blatt „Button Debouncing“, Jumper J10/J12/J14): jeder Druck kippt den Pegel am Expander, und der neue Pegel bleibt stehen, bis der ESP ihn liest. Die Firmware wertet deshalb jeden Wechsel als einen Druck (`InputTrigger::ANY_EDGE`), auch einen ganz kurzen. BT4–BT6 hängen direkt am Expander; ein kurzer Druck ist dort vorbei, bevor der ESP nach dem Reset liest, deshalb lösen sie nichts aus.

## Wand dunkel, Radar und BT1

Nach dem Einschalten (Kaltstart, auch nach dem ersten Flashen) schaltet der ESP die Wand dunkel und lässt sie dunkel. Sie geht an, wenn der Radar (INT_HLK) HIGH meldet oder BT1 gedrückt wird, und zeigt dann ein Zitat aus der Liste im FRAM:

- **Radar:** zeigt das neueste Zitat. Bleibt der Radar HIGH, bleibt die Wand an; der ESP bleibt dann wach und liest den Radar alle 200 ms. Fällt der Radar auf LOW, geht die Wand aus (die Regeln stehen in `lib/core/src/WallLogic.cpp`).
- **BT1:** schaltet die Wand ein und zeigt das neueste Zitat; jeder weitere Druck zeigt das nächste in der Liste. Die Wand bleibt dann mindestens 60 s an (`BUTTON1_ON_MS`), unabhängig vom Radar.
- **Radar-Schalter:** `RADAR_INSTALLED` in `lib/app/application.cpp` steht auf `false`, solange kein Radar angeschlossen ist. Ohne Radar liest GPIO13 durch den Pull-up dauerhaft HIGH; die Firmware ignoriert INT_HLK dann, und die Wand geht nur mit BT1 an und nach 60 s wieder aus. Nach dem Anschliessen des Radars muss der Schalter auf `true` gesetzt werden.
- **Ausschalten:** die Anzeige wird dunkel geschaltet (HT16K33 Display-off), der Inhalt bleibt in den Modulen erhalten. Der Zustand (aus / an / wird geschrieben) liegt im RTC-Speicher; bricht ein Durchlauf beim Schreiben ab, schreibt der nächste genau dasjenige Zitat neu, das beim abgebrochenen Durchlauf gewählt war (Index und Datum werden vor dem Schreiben im RTC-Speicher abgelegt).

## Zitate im FRAM

Die Zitatliste liegt im FRAM MB85RC256V auf 0x50. Dafür muss `FRAM_INSTALLED = true` in `lib/app/application.cpp` stehen. Das FRAM ist seit 2026-10-20 bestückt. Der Code dazu steht in `FramBus`, `FramQuoteStore`, `SlotStore` und `Crc32`.

Die Liste steht doppelt im FRAM, in zwei Plätzen. Ein Platz ist ein Bereich von 4 KB: Platz A beginnt bei 0x0000, Platz B bei 0x1000. Jeder Platz beginnt mit einem Kopf von 16 Byte. Der Kopf enthält Kennung, laufende Nummer, Länge und CRC-32. Die CRC-32 ist eine Prüfsumme; sie zeigt, ob der Platz vollständig geschrieben wurde. Geschrieben wird immer in den älteren Platz. Zuerst kommt die Liste, zuletzt der Kopf. Bricht ein Reset mitten im Schreiben ab, gilt die alte Liste weiter. Der Entwurf steht in `docs/superpowers/specs/2026-10-19-esp-pi-steuerung-design.md` (Abschnitt 11).

**Briefkasten:** Eine `/quotes.txt` im Flash (LittleFS) übernimmt der ESP beim nächsten Lesen einmal ins FRAM und löscht sie danach. Dabei löscht er auch `/quotes.new` und eine alte `/text.txt`. Eine leere `/text.txt` wird ignoriert.

**Liste laden:** Datei nach `data/quotes.txt` legen, `pio run -t uploadfs`, dann BT1 drücken. Danach `data/quotes.txt` wieder entfernen.

**Achtung:** Bleibt die Datei in `data/` liegen, ersetzt sie beim nächsten `uploadfs` die Liste, die die KI geschrieben hat. Darum bleibt `data/` normalerweise leer (nur `.gitkeep`). Eine Beispielliste liegt in `data-beispiel/quotes.txt`.

Der Bus läuft mit 10 kHz und einer SDA-Haltezeit (Hold) von 10 µs. Die Haltezeit ist die Zeit, die der ESP SDA ruhig hält, nachdem SCL gefallen ist. Nur das FRAM wird mit 100 kHz angesprochen (`FramBus::CLOCK_HZ`). Das geschieht in Stücken von 30 Byte. Danach stellt der ESP den Takt wieder auf 10 kHz und die Haltezeit auf 10 µs. Gemessen wurde: Das Lesen von 30 Zitaten (2730 Byte) dauert 0,56 s.

## Format der Zitatliste

Höchstens 30 Zitate, das neueste zuerst. Pro Zeile ein Zitat im Format `JJJJ-MM-TT|Text`; ein Eintrag ohne Datum wird `|Text` geschrieben. Eine Zeile ohne `|` wird übersprungen. Leerzeichen und Tabs am Rand von Datum und Text werden entfernt; ein Datum mit mehr als 10 Zeichen wird verworfen (der Eintrag bleibt, ohne Datum).

Die Anzeige fasst 96 Zeichen (12 Module × 8). Umlaute müssen umschrieben sein. Die Segmentschrift kennt nur `A–Z`, `0–9` und `- . / : + *`. Ist ein Text länger, meldet das Log die Länge. Ist die Liste leer oder nicht lesbar, zeigt die Wand „KEIN TEXT“.

## Ohne FRAM (`FRAM_INSTALLED = false`)

Dann liegt die Liste in `/quotes.txt` im LittleFS des ESP (`QuoteStore`). Die erste Liste legt man in `data/quotes.txt` ab und lädt sie einmal hoch:

```bash
pio run -t uploadfs     # überschreibt das ganze Dateisystem
```

**Umstieg:** Gibt es noch keine `/quotes.txt`, aber die alte `/text.txt`, übernimmt die Firmware deren Text beim ersten Lesen als einziges Zitat.

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
| 0x50 | FRAM MB85RC256V (Zitatliste) |
| 0x70–0x77 | Anzeigen Zeile 1–3, direkt am Bus |
| 0x7F | Zeile 3, Spalte 3 – hinter LTC4316 A (nativ 0x77) |
| 0x79, 0x7B, 0x7D | Zeile 4 – hinter LTC4316 B (nativ 0x71, 0x73, 0x75) |

Der Takt ist 10 kHz (`I2CMasterControl::I2C_CLOCK_HZ`), gemessen sind etwa 9 kHz. Die SDA-Haltezeit (Hold) beträgt 10 µs. Nur das FRAM läuft mit 100 kHz (`FramBus::CLOCK_HZ`).

## Aufbau

```
src/main.cpp              ruft nur Application::run() auf
lib/app/                  Ablauf, Taster (application.cpp)
lib/display/              Display (12 Module), DisplayGrid (Zeilenumbruch), 16-Segment-Font
lib/drivers/              HT16K33, PCF8575, I2CMasterControl (Master-Umschaltung, Bus-Befreiung)
lib/Wire/                 eigene Software-I²C (ersetzt die Core-Bibliothek, siehe unten)
lib/gpioExpander/         Taster-Auswertung (Flanken, Pegel)
lib/system/               Weckgrund, Zustand im RTC-Speicher
lib/core/                 Zitatliste, Zitatspeicher, Wand-Regeln (ohne Arduino, Tests auf dem PC)
lib/storage/              LittleFS-Anbindung (LittleFsAdapter), FRAM-Bus (FramBus);
                          textStorage, espTextStorage, framTextStorage: alter Code, ersetzt in Teil 1 der Umsetzung (neue Verbindung zwischen ESP und Pi, siehe Spezifikation Abschnitt 16)
data/                     Briefkasten für pio run -t uploadfs (normalerweise leer)
data-beispiel/quotes.txt  Startliste als Beispiel zum Hochladen
lib/communication/        UART-Protokoll zum Raspberry Pi (COMMAND|DATA); alter Code, ersetzt in Teil 1
lib/ota/                  WLAN, OTA, Debug-Logger (Telnet)
lib/config/pinMapping.h   Pinbelegung
```

### Eigene Wire-Bibliothek (`lib/Wire`)

Ersetzt die Software-I²C des ESP8266-Cores und hat Vorrang vor ihr. Unterschiede:

- **SDA-Hold:** wartet nach jedem „SCL low“ 10 µs, bevor SDA wechselt
- **Clock-Stretch-Limit:** 20 ms
- **Puffer:** 32 Byte; das FRAM wird deshalb in Stücken von 30 Byte gelesen und geschrieben
- Diagnose: `setIgnoreDataNack()`, `setAckTrace()`, `lastAckFallAfterStartUs()` – die Firmware ruft sie derzeit nicht auf
