# Reflection Wall

Eine Wand aus 12 alphanumerischen 16-Segment-Anzeigen (4 Zeilen × 3 Module, je 8 Zeichen), die Reflexionssätze, KI-Antworten und kleine Animationen zeigt.

Zwei Steuerungen teilen sich denselben I²C-Bus:

| Teil | Ordner | Aufgabe |
|---|---|---|
| **ESP8266** | [`esp/`](esp/README.md) | Stromsparender Normalbetrieb: Die Wand bleibt dunkel, bis BT1 (später der Radar) sie weckt. BT1 zeigt das neueste Zitat, jeder weitere Druck das nächste ältere. Eine Minute nach dem letzten Druck geht die Wand aus und der ESP schläft (Deep Sleep). Dazu schaltet er den Pi ein und aus (BT2 startet eine Sitzung) und gibt in einer Sitzung die Tasten an den Pi weiter. Nachts weckt er den Pi, holt das Gedanken-Zitat der Nacht und legt es im FRAM vorne in die Zitatliste |
| **Raspberry Pi** | [`rpi/`](rpi/README.md) | Interaktive Funktionen: das Menü und die Anwendungen auf der Wand (Sprachassistent, Quiz, Reflection, Radar, Strichmännchen), die Webseite für die Themen und nachts das Zitat der KI |

## Hardware im Überblick

```
ESP8266 ─┐                                      ┌─ Zeile 1: 0x70 0x71 0x72
         ├─ 74HC4053 ─ Pegelwandler ─ 5-V-Bus ──┼─ Zeile 2: 0x73 0x74 0x75
Raspi  ──┘  (Master-     3,3 → 5 V              ├─ Zeile 3: 0x76 0x77 | LTC4316 A → 0x7F
            Umschaltung,                         └─ Zeile 4: LTC4316 B → 0x79 0x7B 0x7D
            GPIO15 ESP)
```

- **Anzeigen:** 12 × HT16K33. Die Jumper reichen nur für 0x70–0x77, deshalb sitzen vier Module hinter zwei Adress-Translatoren **LTC4316** (XOR 0x08).
- **Master-Umschaltung:** Analogschalter 74HC4053. ESP-GPIO15 HIGH = ESP hat den Bus.
- **Weitere I²C-Teilnehmer:** GPIO-Expander PCF8575 (0x20, Taster, INT weckt den ESP über RST), FRAM (0x50, enthält die Zitatliste).
- **UART:** Der Raspberry Pi schaltet seine UART per GPIO23 zwischen ESP8266 und dem Radarsensor HLK LD2410S um.

## Zusammenspiel ESP und Pi

ESP und Pi sprechen über eine serielle Leitung (UART, 74 880 Baud). Den I²C-Bus hat der Pi nur während einer Sitzung von Hand (HAND, BT2). Sonst gehört er dem ESP. Auch nachts bleibt die Wand beim ESP: Der Pi rechnet nur das Zitat und schreibt nichts auf die Anzeige.

Einzelheiten stehen hier:

- [`esp/README.md`](esp/README.md): Ablauf, Sitzung, Uhr und Nacht
- [`rpi/README.md`](rpi/README.md): Ablauf mit dem ESP, Regel B, Zitat der Nacht
- Hauptentwurf: [`docs/superpowers/specs/2026-10-19-esp-pi-steuerung-design.md`](docs/superpowers/specs/2026-10-19-esp-pi-steuerung-design.md)

## Bekanntes Problem: ACK-Verlust hinter den LTC4316

Hinter den Translatoren verloren einzelne Module (0x7B, 0x7F) ihr ACK nach Bytes mit Bit 0 = 1. Die Ursache ist gemessen: SCL fällt auf dem 5-V-Bus zu langsam (> 1 µs statt ≤ 300 ns), weil sich die ganze Buskapazität über Analogschalter und BSS138-Pegelwandler entlädt. Der LTC4316 deutet das ACK dann als START und trennt.

**Gelöst:** Der I²C-Buffer **PCA9517A** sitzt jetzt zwischen Pegelwandler und Bus (VCCA = VCCB = 5 V). Die Anzeigen laufen damit fehlerfrei bei voller Helligkeit (100 %).

## Repository-Struktur

```
docs/     Entwurf und Pläne (docs/superpowers)
esp/      PlatformIO-Projekt für den ESP8266 (Arduino)
  data-beispiel/  Beispiel für die Zitatliste
rpi/      Python-Anwendung für den Raspberry Pi
  app/    Hauptprogramm, Anwendungen und Treiber
  tests/  Einzeltests pro Komponente (mit installation.txt), auch tests/microphone
  doc/    Notizen, z. B. Datenbankbefehle
tests/    gemeinsame Testfälle für ESP und Pi (Verbindung, Anzeige, Zitat: quote_vectors.json)
```

## Auf einem neuen Rechner weiterarbeiten

```bash
git clone https://github.com/camillemarius/Reflection-Wall.git
cd Reflection-Wall/esp
pio run                      # Firmware bauen
pio run -t upload            # flashen (Port in platformio.ini bzw. automatisch)
pio device monitor           # 74880 Baud
```

Für den Raspberry Pi siehe [`rpi/README.md`](rpi/README.md). Zugangsdaten (Groq-API, Datenbank) liegen in einer `.env`-Datei, die nicht im Repository ist.
