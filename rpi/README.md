# Reflection Wall – Raspberry Pi

Python-Anwendung für die interaktiven Funktionen der Reflection Wall. Der Raspberry Pi steuert die Anzeigen direkt über I²C (smbus2), sobald er über die Master-Umschaltung den Bus bekommt.

## Start

Alles startet im Ordner `rpi/`.

Am PC: `python -m app.main --pc`. Die Anzeige erscheint als Text im Terminal. Die Tasten tippst du als Ziffer 1 bis 6, danach Enter.

An der Wand: `python -m app.main`. Das Programm öffnet die Anzeigen über I²C und die Verbindung zum ESP. Den Handschlag mit dem ESP (`READY`, `SESSION`, Herunterfahren) bringt erst Teil 2. Bis dahin ist der Wandstart nicht vollständig.

Die Zugangsdaten (`GROQ_API_KEY`, Datenbank, `AUTO_AUS_MINUTEN`) liest das Programm beim Start aus der Datei `.env`. Chat, Quiz und Reflection brauchen den Groq-Schlüssel und die Datenbank.

## Tasten

| Taste | Wirkung |
|---|---|
| BT6 | Im Menü einen Punkt nach unten |
| BT5 | Auswählen, in Anwendungen weiter |
| BT4 | Zurück |

Im PC-Modus stehen die Ziffern 6, 5 und 4 für diese Tasten.

## Menü

| Punkt | Was er tut | Datei |
|---|---|---|
| CHAT | Sprachassistent: Spracherkennung, Groq-LLM, Anzeige und Sprachausgabe | `applications/chat_app.py` |
| QUIZ | Quiz mit KI-generierten Fragen | `applications/quiz_app.py` |
| REFLECTION | Reflexionsfrage zum eingestellten Thema | `applications/reflection_app.py` |
| RADAR | Radar-Anzeige mit dem HLK LD2410S, nur an der Wand | `applications/radar_app.py` |
| STRICHMAENNCHEN | Strichmännchen-Animation | `applications/stickman_app.py` |
| EINSTELLUNGEN | THEMA AENDERN und RADAR EINRICHTEN (kommt später) | `applications/settings_apps.py` |

Die alten Anwendungen, die mit Enter im Terminal liefen, gibt es nicht mehr. Dazu gehören `VoiceAssistant`, `QuizGame`, `Reflection` und die alten Klassen `Radar` und `Stickman`. Die Dateien `prompt.py` und `prompt_template.py` in `applications/ReflectionAI` bleiben als Vorlage für Teil 3b.

## Automatisches Aus

Der Schalter `AUTO_AUS_MINUTEN` steht in `.env`. Der Wert 0 schaltet das automatische Aus aus. Das ist die Voreinstellung. Ein Wert wie 15 schaltet die Wand nach 15 Minuten ohne Aktivität aus.

Aktivität ist ein Tastendruck, das Speichern auf der Webseite, eine laufende Anfrage an die KI oder eine Person vor dem Radar. Eine Animation allein zählt nicht.

Läuft gerade das Radar, beendet das Programm zuerst das Radar. Danach schickt es `DONE` an den ESP.

## Thema und Webseite

Das Thema für Reflection steht in `app/config/thema.txt`, das Thema für den Handbetrieb in `app/config/thema_hand.txt`. Ein Thema ist eine Zeile mit höchstens 120 Zeichen. Ohne Datei gilt „Was ist der Sinn des Lebens“.

Unter EINSTELLUNGEN, THEMA AENDERN startet eine kleine Webseite. Dort änderst du die Themen. Die Seite schliesst sich nach 15 Minuten ohne Speichern.

Die Webseite läuft auf Port 80. Dafür braucht der Dienst das Recht `CAP_NET_BIND_SERVICE`, zum Beispiel mit `AmbientCapabilities=CAP_NET_BIND_SERVICE` in der systemd-Unit (ungeprüft).

## Treiber (`app/driver`)

| Ordner | Inhalt |
|---|---|
| `display/` | HT16K33-Treiber, DisplayGrid, Textlayout, Graphen |
| `uart/` | UART zum Radar LD2410S und Umschaltung per GPIO23 (HIGH = Radar, LOW = ESP); die Verbindung zum ESP liegt in `app/link/` |
| `chatbot/` | Groq-API |
| `speechRecognition/` | faster-whisper (lokal) bzw. Groq-Spracherkennung |
| `speech/` | Sprachausgabe |
| `database/` | MariaDB/MySQL für Reflexionen und Quiz |

## Verbindung zum ESP (`app/link`)

`codec.py` baut und liest die Zeilen der Verbindung (Nummer, Befehl, Daten, Prüfsumme). `PiLink` vergibt die Nummern, wiederholt Anfragen und erkennt doppelte Nachrichten. Dafür läuft ein eigener Thread. `serial_port.py` öffnet `/dev/ttyAMA0` mit 74 880 Baud und setzt GPIO23 auf LOW. Damit gehört die UART dem ESP.

Das Prüfwerkzeug startet im Ordner `rpi/`:

```bash
python -m app.link.probe [--port /dev/ttyAMA0] [--baud 74880] [--seconds N] [--no-gpio]
```

Es sendet `READY`, bis der ESP antwortet, und gibt die Antwort aus. Danach beantwortet es die Anfragen des ESP: `BUTTON` mit `OK`, `SHUTDOWN` mit `BUSY` und alles andere mit `ERROR|PROBE`. Der Pi wird dabei nie heruntergefahren. `--seconds 0` läuft bis Ctrl+C. Mit `--no-gpio` bleibt GPIO23 unberührt.

Das Prüfwerkzeug und die Radar-Anwendung (Menüpunkt RADAR) dürfen nicht gleichzeitig laufen. Beide schalten GPIO23, und damit den CD4053. Der CD4053 legt fest, ob die UART des Pi mit dem ESP oder mit dem Radar spricht (Spezifikation F1, Abschnitt 6.4).

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

Die einzelnen Komponenten lassen sich in `tests/<Komponente>/` getrennt testen (`chatbot_groq`, `ht16k33`, `ioExpander`, `ld2410s`, `lichtsensor`, `microphone`, `mysql`, `speechrecognition`, `wakeWord`); dort steht jeweils eine `installation.txt`. `tests/ld2410s` nutzt den App-Treiber und startet im Ordner `rpi/` mit `python -m tests.ld2410s.test [--simulation] [--seconds N]`; auf dem PC mit `--simulation` (Windows: `python -X utf8 …`, sonst scheitert die Konsole an den Zeichen für Balken und Pfeile). `tests/microphone` nimmt auf und legt die Aufnahmen in `tests/microphone/recordings/` ab (nicht im Repository).

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
