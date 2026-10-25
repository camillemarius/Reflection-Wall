# Reflection Wall – Firmware ESP8266

PlatformIO-Projekt (Arduino-Framework) für den ESP-12E.

## Bauen und Flashen

```bash
cd esp
pio run                 # bauen
pio run -t upload       # flashen über USB (esptool)
pio device monitor      # serielle Konsole, 74880 Baud
```

**Erstes Flashen dieser Firmware (Sitzung mit dem Pi):** Der Zustand im RTC-Speicher hat ein neues Format (`MAGIC` „RWL3“). Der erste Start nach dem Flashen gilt deshalb als Kaltstart, und der ESP hält den Pi für aus. Läuft der Pi gerade, macht man die Wand vor dem ersten BT2 kurz stromlos; das Flipflop der Speisung steht dann wieder auf aus. Den Pi fährt man davor am besten selbst herunter. Sonst schaltet der erste BT2 den Pi hart aus: Der ESP will ihn einschalten, und der Puls kippt die Speisung auf aus.

**OTA:** Zurzeit nicht nutzbar. Kein Code startet WLAN oder OTA: `WifiController::begin` und `OtaManager::begin` hat keine Stelle aufgerufen. Darum haben die Zeilen unter `#OTA` in `platformio.ini` und die VS-Code-Aufgabe „Upload ESP + Telnet“ heute keine Wirkung. Geflasht wird nur über USB. Teil 3b der Umsetzung (Mitternacht, siehe Spezifikation Abschnitt 16) bringt WLAN zurück. Er holt außerdem die Uhrzeit aus dem Internet (NTP).

## Ablauf im Normalbetrieb

Es gibt keine Hauptschleife. Der ESP liegt im Deep Sleep; ein Tastendruck am PCF8575 löst über dessen INT-Ausgang einen Reset aus, ebenso der Radar (INT_HLK). `Application::run()` läuft dann durch und legt den ESP wieder schlafen. Solange die Wand mit dem Radar an ist, bleibt der ESP in `run()` wach und liest den Radar (siehe unten). Auch ohne Radar bleibt der ESP nach BT1 etwa 60 s wach. So lange bleibt die Wand an. Ebenso bleibt er wach, solange eine Sitzung mit dem Pi läuft (siehe „Sitzung mit dem Pi“). Danach legt er sich schlafen und wacht mit dem nächsten Reset auf:

1. WLAN aus (spart Strom und Bootzeit)
2. Weckgrund lesen
3. Zustand aus dem RTC-Speicher laden (`PersistentState`): Wand, Sitzung mit dem Pi, Speisung des Pi, Nummern der Verbindung
4. Expander lesen, Taster auswerten, Tastenstand sichern
5. Läuft eine Sitzung mit dem Pi: die Sitzung weiterführen, bis sie zu Ende ist, dann Deep Sleep. Die Wand-Regeln ruhen so lange.
6. Sonst die Wand-Regeln anwenden: Radar (INT_HLK) und BT1 entscheiden, ob ein Zitat angezeigt wird (siehe unten)
7. Zustand sichern, Deep Sleep

| Taster | Pi aus | In einer Sitzung |
|---|---|---|
| BT1 | Wand an: zeigt das neueste Zitat, bei jedem weiteren Druck das nächste in der Liste; die Wand geht 1 min nach dem letzten Druck aus | im Betrieb als `BUTTON\|1` an den Pi, sonst nichts |
| BT2 | Pi einschalten, Sitzung HAND, Anzeige `PI STARTET` | im Betrieb Pi herunterfahren (`SHUTDOWN`); beim Einschalten und im Radar-Debug gemerkt; beim Herunterfahren und danach nichts |
| BT3 | Verbindungstest zum Pi: `PING` senden, 3 s lang Anfragen des Pi beantworten, Ergebnis im Log | im Betrieb als `BUTTON\|3`, sonst nichts |
| BT4–BT6 | nichts | im Betrieb als `BUTTON\|4` bis `BUTTON\|6`, sonst nichts |

Die Tabelle folgt Tabelle 5.2 im Entwurf `docs/superpowers/specs/2026-10-23-menue-und-anwendungen-design.md`. „Im Betrieb“ heisst: Der Pi hat `READY` gemeldet und ist nicht im Radar-Debug.

Alle sechs Tasten laufen über Toggle-Flipflops (Blatt „Button Debouncing“; BT1–BT3 über die Jumper J10/J12/J14, BT4–BT6 nachgerüstet, Spezifikation Abschnitt 4, F9): jeder Druck kippt den Pegel am Expander, und der neue Pegel bleibt stehen, bis der ESP ihn liest. Die Firmware wertet deshalb jeden Wechsel als einen Druck (`InputTrigger::ANY_EDGE`), auch einen ganz kurzen.

## Wand dunkel, Radar und BT1

Nach dem Einschalten (Kaltstart, auch nach dem ersten Flashen) schaltet der ESP die Wand dunkel und lässt sie dunkel. Sie geht an, wenn der Radar (INT_HLK) HIGH meldet oder BT1 gedrückt wird, und zeigt dann ein Zitat aus der Liste im FRAM:

- **Radar:** zeigt das neueste Zitat. Bleibt der Radar HIGH, bleibt die Wand an; der ESP bleibt dann wach und liest den Radar alle 200 ms. Fällt der Radar auf LOW, geht die Wand aus (die Regeln stehen in `lib/core/src/WallLogic.cpp`).
- **BT1:** schaltet die Wand ein und zeigt das neueste Zitat; jeder weitere Druck zeigt das nächste in der Liste. Die Wand bleibt dann mindestens 60 s an (`BUTTON1_ON_MS`), unabhängig vom Radar.
- **Radar-Schalter:** `Features::RADAR_INSTALLED` in `lib/config/features.h` steht auf `false`, solange kein Radar angeschlossen ist. Ohne Radar liest GPIO13 durch den Pull-up dauerhaft HIGH. Die Firmware ignoriert INT_HLK dann. Die Wand geht nur mit BT1 an. Nach 60 s geht sie wieder aus. Ist der Radar angeschlossen, setzt man den Schalter auf `true`.
- **Ausschalten:** die Anzeige wird dunkel geschaltet (HT16K33 Display-off), der Inhalt bleibt in den Modulen erhalten. Der Zustand (aus / an / wird geschrieben) liegt im RTC-Speicher; bricht ein Durchlauf beim Schreiben ab, schreibt der nächste genau dasjenige Zitat neu, das beim abgebrochenen Durchlauf gewählt war (Index und Datum werden vor dem Schreiben im RTC-Speicher abgelegt).
- **Sitzung:** Solange eine Sitzung mit dem Pi läuft, gilt nichts davon. Die Anzeige gehört dann dem Pi; Radar und BT1 ändern sie nicht.

## Sitzung mit dem Pi

BT2 bei ausgeschaltetem Pi startet eine Sitzung: Der ESP schaltet die Speisung ein und zeigt `PI STARTET`. Die Logik steht in `lib/core/src/PiSession.cpp` und wird auf dem PC getestet. `Application` führt nur aus, was die Sitzung verlangt: Speisung schalten, senden, antworten, Text zeigen, Anzeige aus, Log. Zustände und Fristen stehen in der Spezifikation (`docs/superpowers/specs/2026-10-19-esp-pi-steuerung-design.md`, Abschnitte 7 und 12):

| Zustand | Was der ESP tut | Wie es weitergeht |
|---|---|---|
| EINSCHALTEN | wartet auf `READY`, höchstens 120 s | `READY` → `OK`, dann `SESSION\|HAND` → BETRIEB. War BT2 gemerkt: gleich HERUNTERFAHREN, ohne `SESSION`. Kein `READY` → hart aus |
| BETRIEB | `PING` alle 10 s, Tasten als `BUTTON\|n` | BT2 oder `DONE` → HERUNTERFAHREN, `MODE\|RADAR` → RADAR-DEBUG, 3 `PING` ohne Antwort → hart aus |
| RADAR-DEBUG | sendet nichts, merkt sich BT2 | `MODE\|NORMAL` oder `READY` → BETRIEB, mit gemerktem BT2 → HERUNTERFAHREN; nach 60 min → HERUNTERFAHREN |
| HERUNTERFAHREN | `SHUTDOWN`, nach `BUSY` alle 30 s noch einmal | `OK` → HALT-WARTEN; keine Antwort in 60 s oder 10 min `BUSY` → hart aus |
| HALT-WARTEN | wartet 30 s (`T_halt`), bis der Pi gehalten hat | Speisung aus, Anzeige aus, Sitzung zu Ende |

„Hart aus“ heisst: Speisung trennen, ohne dass der Pi heruntergefahren ist, mit Eintrag im Log.

**Anzeigetexte.** Der ESP setzt sie wie ein Zitat, also oben links (`Display::show`):

- `PI STARTET` nach BT2, bis der Pi nach `SESSION|HAND` sein Menü zeigt.
- `PI FAEHRT HERUNTER` nach `OK` auf `SHUTDOWN`, bis die Speisung aus ist. Danach geht die Anzeige aus.
- `PI ANTWORTET NICHT` für 10 s nach einem harten Aus, weil `READY` nicht kam oder drei `PING` ohne Antwort blieben. Danach geht die Anzeige aus. BT2 startet in dieser Zeit gleich eine neue Sitzung, die anderen Tasten tun nichts.
- Ein hartes Aus beim Herunterfahren (keine Antwort auf `SHUTDOWN`, 10 min `BUSY`) zeigt keinen Text. Die Anzeige geht nur aus.

**Was sonst gilt:**

- **Bus:** In der Sitzung schreibt der Pi auf die Anzeige. Der ESP gibt den I²C-Bus gleich nach dem Lesen des Expanders frei. Er nimmt ihn nur für seine eigenen Texte und für „Anzeige aus“. Das kommt nur vor, wenn der Pi nicht schreibt: beim Einschalten, nach `OK` auf `SHUTDOWN` und nach einem harten Aus.
- **Reset in der Sitzung:** Jede Taste und jede Radar-Flanke setzt den ESP auch jetzt zurück. Sitzung, Speisung und die Nummern der Verbindung liegen im RTC-Speicher. Der ESP macht deshalb im selben Zustand weiter und schaltet die Speisung nicht noch einmal. Eine abgebrochene eigene Anfrage geht noch einmal raus (`SESSION`, `SHUTDOWN`). Ein abgebrochenes `BUTTON` geht nicht noch einmal raus, es steht nur im Log. Die Zeit des Resets selbst (etwa 0,1–0,3 s) geht verloren.
- **Takt:** Der ESP liest die Leitung alle 20 ms und beantwortet jede Anfrage des Pi sofort. Den Zustand sichert er, sobald sich etwas ändert, sonst jede Sekunde.
- **Nach der Sitzung** schläft der ESP sofort. Die Wand bleibt dunkel, bis die nächste Radar-Flanke oder BT1 sie einschaltet.
- **Speisung:** Ein Puls auf GPIO12 kippt das Flipflop am Relais. Der ESP kann es nicht zurücklesen und merkt sich im RTC-Speicher, was er zuletzt geschaltet hat. Er sichert den neuen Stand vor dem Puls.
- Eine Sitzung `NACHT` (Start um Mitternacht, Teil 3b) fasst die Anzeige nicht an. Die Firmware startet sie noch nicht.

## Zitate im FRAM

Die Zitatliste liegt im FRAM MB85RC256V auf 0x50. Dafür muss `Features::FRAM_INSTALLED = true` in `lib/config/features.h` stehen. Das FRAM ist seit 2026-10-20 bestückt. Der Code dazu steht in `FramBus`, `FramQuoteStore`, `SlotStore` und `Crc32`.

Die Liste steht doppelt im FRAM, in zwei Plätzen. Ein Platz ist ein Bereich von 4 KB: Platz A beginnt bei 0x0000, Platz B bei 0x1000. Jeder Platz beginnt mit einem Kopf von 16 Byte. Der Kopf enthält Kennung, laufende Nummer, Länge und CRC-32. Die CRC-32 ist eine Prüfsumme; sie zeigt, ob der Platz vollständig geschrieben wurde. Geschrieben wird immer in den älteren Platz. Zuerst kommt die Liste, zuletzt der Kopf. Bricht ein Reset mitten im Schreiben ab, gilt die alte Liste weiter. Der Entwurf steht in `docs/superpowers/specs/2026-10-19-esp-pi-steuerung-design.md` (Abschnitt 11).

**Briefkasten:** Eine `/quotes.txt` im Flash (LittleFS) übernimmt der ESP beim nächsten Lesen einmal ins FRAM und löscht sie danach. Dabei löscht er auch `/quotes.new` und eine alte `/text.txt`. Eine leere `/text.txt` wird ignoriert.

**Liste laden:** Datei nach `data/quotes.txt` legen, `pio run -t uploadfs`, dann BT1 drücken.

**Achtung:** Entferne `data/quotes.txt` danach wieder. Sonst ersetzt die Datei beim nächsten `uploadfs` die Liste, die die KI geschrieben hat. Darum bleibt `data/` normalerweise leer (nur `.gitkeep`). Eine Beispielliste liegt in `data-beispiel/quotes.txt`.

Der Bus läuft mit 10 kHz und einer SDA-Haltezeit (Hold) von 10 µs. Die Haltezeit ist die Zeit, die der ESP SDA ruhig hält, nachdem SCL gefallen ist. Nur das FRAM wird mit 100 kHz angesprochen (`FramBus::CLOCK_HZ`). Das geschieht in Stücken von 30 Byte. Danach stellt der ESP den Takt wieder auf 10 kHz und die Haltezeit auf 10 µs. Gemessen wurde: Das Lesen von 30 Zitaten (2730 Byte) dauert 0,56 s.

## Format der Zitatliste

Höchstens 30 Zitate, das neueste zuerst. Pro Zeile ein Zitat im Format `JJJJ-MM-TT|Text`; ein Eintrag ohne Datum wird `|Text` geschrieben. Eine Zeile ohne `|` wird übersprungen. Leerzeichen und Tabs am Rand von Datum und Text werden entfernt; ein Datum mit mehr als 10 Zeichen wird verworfen (der Eintrag bleibt, ohne Datum).

Die Anzeige fasst 96 Zeichen (12 Module × 8). Umlaute müssen umschrieben sein. Die Segmentschrift kennt nur `A–Z`, `0–9` und `- . / : + *`. Ist ein Text länger, meldet das Log die Länge. Ist die Liste leer oder nicht lesbar, zeigt die Wand „KEIN TEXT“.

## Ohne FRAM (`Features::FRAM_INSTALLED = false`)

Dann liegt die Liste in `/quotes.txt` im LittleFS des ESP (`QuoteStore`). Die erste Liste legt man in `data/quotes.txt` ab und lädt sie einmal hoch:

```bash
pio run -t uploadfs     # überschreibt das ganze Dateisystem
```

**Umstieg:** Gibt es noch keine `/quotes.txt`, aber die alte `/text.txt`, übernimmt die Firmware deren Text beim ersten Lesen als einziges Zitat.

## Tests auf dem PC

Die Logik ohne Arduino-Abhängigkeit (`lib/core`: Zitatliste, Zitatspeicher, Wand-Regeln, Verbindung zum Pi, Sitzung mit dem Pi, Umbruch) wird auf dem PC getestet:

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
lib/app/                  Ablauf, Taster, Sitzung ausführen (application.cpp), Verbindungstest (LinkTest)
lib/display/              Display (12 Module), DisplayGrid (Anzeigeraster, nutzt TextLayout und Glyphs aus lib/core), SegmentChain
lib/drivers/              HT16K33, PCF8575, I2CMasterControl (Master-Umschaltung, Bus-Befreiung)
lib/Wire/                 eigene Software-I²C (ersetzt die Core-Bibliothek, siehe unten)
lib/gpioExpander/         Taster-Auswertung (Flanken, Pegel)
lib/system/               Weckgrund, Zustand im RTC-Speicher (Wand, Sitzung, Speisung, Nummern),
                          PowerSwitchPin (Pin GPIO12 für die Pi-Speisung)
lib/core/                 ohne Arduino, Tests auf dem PC: Zitatliste, Zitatspeicher, Wand-Regeln,
                          LinkCodec (Zeilenformat), PiLink (Nummern, Wiederholung, Fristen), PiPower (Pi-Speisung),
                          PiSession (Sitzung mit dem Pi), TextLayout (Umbruch) und Glyphs (Segmentschrift)
lib/communication/        UartPort: Serial für die Verbindung zum Pi
lib/storage/              LittleFS-Anbindung (LittleFsAdapter), FRAM-Bus (FramBus)
data/                     Briefkasten für pio run -t uploadfs (normalerweise leer)
data-beispiel/quotes.txt  Startliste als Beispiel zum Hochladen
lib/ota/                  WLAN, OTA, Debug-Logger (Telnet); WLAN und OTA hat zurzeit niemand aufgerufen, Teil 3b braucht sie
                          Der alte Code für die Verbindung zum Pi und der alte Textspeicher sind entfernt.
lib/config/pinMapping.h   Pinbelegung
lib/config/features.h     alle Bauschalter (FRAM, Radar, Funkteil beim Aufwachen, Baudrate der Verbindung)
```

## Verbindung zum Pi

Der ESP spricht mit dem Pi über `Serial`. Das ist dieselbe Leitung wie das Debug-Log. Beide laufen mit 74 880 Baud (`Features::LINK_BAUD`). Darum schreibt `PiLink` vor jede Nachricht ein Zeilenende-Zeichen (`\n`). Eine Nachricht ist eine Zeile mit Nummer, Befehl und Daten sowie einer Prüfsumme. `LinkCodec` baut und liest die Zeile. `PiLink` vergibt die Nummern, wiederholt nach 250 ms und erkennt doppelte Nachrichten. Der Empfangspuffer fasst 1024 Byte, denn eine Zeile hat bis zu 257 Byte. Die Testfälle liegen in `tests/` und gelten für ESP und Pi gemeinsam. Das Format steht in der Spezifikation, Abschnitt 6.

Die Nummern liegen im RTC-Speicher. Ein Reset fängt deshalb nicht wieder bei `00` an. In einer Sitzung gehört die Leitung `PiSession`. Den Verbindungstest mit BT3 gibt es nur ohne Sitzung.

### Eigene Wire-Bibliothek (`lib/Wire`)

Ersetzt die Software-I²C des ESP8266-Cores und hat Vorrang vor ihr. Unterschiede:

- **SDA-Hold:** wartet nach jedem „SCL low“ 10 µs, bevor SDA wechselt
- **Clock-Stretch-Limit:** 20 ms
- **Puffer:** 32 Byte; das FRAM wird deshalb in Stücken von 30 Byte gelesen und geschrieben
- Diagnose: `setIgnoreDataNack()`, `setAckTrace()`, `lastAckFallAfterStartUs()` – die Firmware ruft sie derzeit nicht auf
