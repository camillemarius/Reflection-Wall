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
5. Bei Kaltstart den ersten Text anzeigen, sonst auf Taster reagieren
6. Zustand sichern, Deep Sleep

| Taster | Aktion |
|---|---|
| BT5 | Raspberry Pi ein-/ausschalten (Puls auf das Flipflop am Relais, GPIO12) |
| BT6 | nächsten Reflexionstext anzeigen |
| BT1–BT4 | noch nicht belegt |

Die 12 Texte stehen in `lib/app/application.cpp` (max. 96 Zeichen, wird beim Kompilieren geprüft).

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
lib/app/                  Ablauf, Taster, Testmodi (application.cpp), BufferTest
lib/display/              Display (12 Module), DisplayGrid (Zeilenumbruch), 16-Segment-Font
lib/drivers/              HT16K33, PCF8575, I2CMasterControl (Master-Umschaltung, Bus-Befreiung)
lib/Wire/                 eigene Software-I²C (ersetzt die Core-Bibliothek, siehe unten)
lib/gpioExpander/         Taster-Auswertung (Flanken, Pegel)
lib/system/               Weckgrund, Zustand im RTC-Speicher
lib/storage/              Textspeicher im ESP bzw. FRAM
lib/communication/        UART-Protokoll zum Raspberry Pi (COMMAND|DATA)
lib/ota/                  WLAN, OTA, Debug-Logger (Telnet)
lib/config/pinMapping.h   Pinbelegung
```

### Eigene Wire-Bibliothek (`lib/Wire`)

Ersetzt die Software-I²C des ESP8266-Cores und hat Vorrang vor ihr. Unterschiede:

- **SDA-Hold:** wartet nach jedem „SCL low“ 10 µs, bevor SDA wechselt
- **Clock-Stretch-Limit:** 20 ms
- Diagnose: `setIgnoreDataNack()`, `setAckTrace()`, `lastAckFallAfterStartUs()`

## Testmodi

Alle Testmodi sind Schalter (`constexpr bool`) in `lib/app/application.cpp` und laufen endlos statt in den Deep Sleep zu gehen. Ist mehrere aktiv, gewinnt der oberste:

| Schalter | Zweck |
|---|---|
| `BUFFER_TEST` | **Test für den PCA9517A:** ganzer Bildschirm zeigt „ADR xx n“, prüft pro angeschlossenem Modul Befehl 0x81 und liest den Text zurück. Nicht angeschlossene Module werden übersprungen. Code in `lib/app/BufferTest.cpp` |
| `SCOPE_TEST` | Oszi-Modus: wiederholt 0x7B + 0x81 alle 20 ms |
| `ID_TEST` | jedes Modul zeigt „ADR xx n“ (ohne Prüfung) |
| `ACK_TRACE_TEST` | tastet SDA im ACK-Takt ab |
| `PATTERN_TEST`, `CMD_MATRIX_TEST`, `I2C_HOLD_TEST`, `SEGMENT_SWEEP_TEST`, `I2C_PROBE_TEST`, `I2C_LOAD_TEST` | frühere Diagnosen zur Fehlersuche |
| `I2C_DIAG`, `DISPLAY_CYCLE_TEST` | Diagnose-Ausgaben bzw. alle 6 s ein neuer Text statt Deep Sleep |

**Für den Normalbetrieb alle Testschalter auf `false` setzen.**

### Ausgabe des Buffer-Tests

```
[BUF] #12  0x7B ok
[BUF] ---- Stand nach 10 Runden ----
[BUF]   0x7B: 10 ok, 0 Fehler (0x81 NACK 0, Text abgebrochen 0, Lesen 0, Text falsch 0, Bus 0)
```

Bestanden, wenn alle angeschlossenen Module über längere Zeit 0 Fehler zeigen – vor allem 0x7B und 0x7F.
