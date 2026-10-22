# Reflection Wall – Raspberry Pi

Python-Anwendung für die interaktiven Funktionen der Reflection Wall. Der Raspberry Pi steuert die Anzeigen direkt über I²C (smbus2), sobald er über die Master-Umschaltung den Bus bekommt.

## Funktionen

Start im Ordner `rpi/`: `python -m app.main` (ohne Pi nicht getestet). Dann Modus wählen:

| Taste | Modus | Ordner |
|---|---|---|
| 1 | Sprachassistent (Spracherkennung → Groq-LLM → Anzeige und Sprachausgabe) | `applications/VoiseAssistant` |
| 2 | Quiz mit KI-generierten Fragen | `applications/Quiz` |
| 3 | Reflection AI: Reflexionsfrage, Antwort wird in MariaDB gespeichert | `applications/ReflectionAI` |
| 4 | Radar-Animation mit dem HLK LD2410S | `applications/Animations/Radar.py` |
| 5 | Strichmännchen-Animation | `applications/Animations/Stickman.py` |

## Treiber (`app/driver`)

| Ordner | Inhalt |
|---|---|
| `display/` | HT16K33-Treiber, DisplayGrid, Textlayout, Graphen |
| `uart/` | alter Code, wird in Teil 1 der Umsetzung ersetzt (neue Verbindung zwischen ESP und Pi, siehe Spezifikation Abschnitt 16): UART zum ESP8266 (`COMMAND\|DATA`) und zum Radar LD2410S; Umschaltung per GPIO23 (HIGH = Radar, LOW = ESP) |
| `chatbot/` | Groq-API |
| `speechRecognition/` | faster-whisper (lokal) bzw. Groq-Spracherkennung |
| `speech/` | Sprachausgabe |
| `database/` | MariaDB/MySQL für Reflexionen und Quiz |

## Installation

```bash
sudo raspi-config              # I2C und Serial aktivieren
sudo apt install mariadb-server
cd rpi
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

`pyserial` braucht die UART-Verbindung. Das Paket `piper-tts` liefert den Befehl `piper`, den die Sprachausgabe aufruft (Paketname ungeprüft). Zum Abspielen braucht es außerdem `aplay` (`sudo apt install alsa-utils`).

Die einzelnen Komponenten lassen sich in `tests/<Komponente>/` getrennt testen (`chatbot_groq`, `ht16k33`, `ioExpander`, `ld2410s`, `lichtsensor`, `microphone`, `mysql`, `speechrecognition`, `wakeWord`); dort steht jeweils eine `installation.txt`. `tests/microphone` nimmt auf und legt die Aufnahmen in `tests/microphone/recordings/` ab (nicht im Repository).

## Tests auf dem PC

Ohne Pi und ohne Netz (alle Python-Tests, im Ordner `rpi/`):

```bash
cd rpi && python -m unittest discover -s app -t . -v
```

Auf dem PC fehlt `lgpio`, und `smbus2` lässt sich unter Windows nicht importieren. Darum öffnet kein Modul beim Import Hardware, Datenbank oder Netz; der I²C-Bus, `lgpio` und der Groq-Client entstehen erst beim ersten Gebrauch.

## Zugangsdaten

In `rpi/app/.env` (nicht im Repository):

```
GROQ_API_KEY=...
DB_HOST=localhost
DB_USER=...
DB_PASSWORD=...
```

## Datenbank

```
sudo mariadb
USE reflection_db;
SELECT * FROM reflections;
```

Weitere Befehle in `doc/commands.txt`.

## Bekannte Baustellen

- Der Python-Treiber adressiert die Module als `0x70 + Index` und nutzt standardmässig nur 2 Zeilen (6 Module). Die Adressen hinter den LTC4316 (0x7F, 0x79, 0x7B, 0x7D) fehlen noch.
