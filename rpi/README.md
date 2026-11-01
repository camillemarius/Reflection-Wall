# Reflection Wall – Raspberry Pi

Python-Anwendung für die interaktiven Funktionen der Reflection Wall. Der Raspberry Pi steuert die Anzeigen direkt über I²C (smbus2), sobald er über die Master-Umschaltung den Bus bekommt.

## Start

Alles startet im Ordner `rpi/`.

Am PC: `python -m app.main --pc`. Die Anzeige erscheint als Text im Terminal. Die Tasten tippst du als Ziffer 1 bis 6, danach Enter.

An der Wand: `python -m app.main`. Das Programm öffnet die Anzeigen über I²C und die Verbindung zum ESP. Im Betrieb startet es als Dienst, siehe Abschnitt Dienst einrichten. Der Handschlag mit dem ESP ist umgesetzt, aber ungeprüft bis zur Abnahme.

Die Zugangsdaten (`GROQ_API_KEY`, Datenbank, `AUTO_AUS_MINUTEN`) liest das Programm beim Start aus der Datei `.env`. Chat, Quiz und Reflection brauchen den Groq-Schlüssel. Die Datenbank braucht nur das Quiz.

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
| CHAT | Sprachassistent: BT5 startet und beendet die Aufnahme (nach 60 s endet sie von selbst), Spracherkennung, Groq-LLM, Anzeige und Sprachausgabe. Die Antwort bleibt stehen, bis BT5 wieder `BT5 UND SPRECHEN` zeigt. | `applications/chat_app.py` |
| QUIZ | Quiz mit KI-generierten Fragen | `applications/quiz_app.py` |
| REFLECTION | Ein Gedanke zum Thema aus `thema_hand.txt`. BT5 holt den nächsten, er baut auf dem vorigen auf. Nichts wird gespeichert. | `applications/reflection_app.py` |
| RADAR | Radar-Anzeige mit dem HLK LD2410S, nur an der Wand | `applications/radar_app.py` |
| STRICHMAENNCHEN | Strichmännchen-Animation | `applications/stickman_app.py` |
| EINSTELLUNGEN | THEMA AENDERN und RADAR EINRICHTEN (kommt später) | `applications/settings_apps.py` |

Beim ersten Eintritt in CHAT lädt das Programm das Modell für die Spracherkennung. Dabei zeigt die Wand `MIKROFON WIRD VORBEREITET`. Danach bleibt das Modell geladen.

RADAR funktioniert mit der ESP-Firmware dieses Stands. Der ESP versteht `MODE|RADAR` und `MODE|NORMAL`. Der Pi schaltet die Leitung um und wieder zurück (`app/link/radar_switch.py`). Das ist ungeprüft bis zur Abnahme am Gerät. Nach 55 min endet das Radar, siehe Ablauf mit dem ESP.

Stürzt eine Anwendung ab, zeigt die Wand `FEHLER IN <NAME>` und `BT4 ZURUECK`. Den Grund schreibt das Programm ins Log.

Die alten Anwendungen, die mit Enter im Terminal liefen, gibt es nicht mehr. Dazu gehören `VoiceAssistant`, `QuizGame`, `Reflection` und die alten Klassen `Radar` und `Stickman`. Die Dateien `prompt.py` und `prompt_template.py` in `applications/ReflectionAI` bleiben als Vorlage für Teil 3b.

## Automatisches Aus

Der Schalter `AUTO_AUS_MINUTEN` steht in `.env`. Der Wert 0 schaltet das automatische Aus aus. Das ist die Voreinstellung. Ein Wert wie 15 schaltet die Wand nach 15 Minuten ohne Aktivität aus.

Aktivität ist ein Tastendruck, das Speichern auf der Webseite, eine Person vor dem Radar oder eine Arbeit des Pi: eine Anfrage an die KI, eine Aufnahme, die Spracherkennung oder die Sprachausgabe. Eine Animation allein zählt nicht.

Läuft gerade das Radar, beendet das Programm zuerst das Radar. Danach schickt es `DONE` an den ESP.

## Thema und Webseite

`app/config/thema.txt` enthält das Thema der täglichen Reflexion um Mitternacht. `app/config/thema_hand.txt` enthält das Thema für REFLECTION im Menü. Ein Thema ist eine Zeile mit höchstens 120 Zeichen. Ist `thema.txt` leer oder fehlt sie, gilt „Was ist der Sinn des Lebens“. Ist `thema_hand.txt` leer oder fehlt sie, gilt das Thema aus `thema.txt`.

Unter EINSTELLUNGEN, THEMA AENDERN startet eine kleine Webseite. Dort änderst du die Themen. Die Felder zeigen den Inhalt der beiden Dateien. Ist ein Feld leer, zeigt es das geltende Ersatzthema grau an. Speichern mit leerem Feld lässt die Datei leer, damit das Ersatzthema weiter gilt. Die Seite nimmt ein Speichern nur von sich selbst an, nicht von einer fremden Seite. Sie schliesst sich nach 15 Minuten ohne Speichern.

Die Webseite läuft auf Port 80. Dafür setzt die systemd-Unit `AmbientCapabilities=CAP_NET_BIND_SERVICE` (ungeprüft bis zur Abnahme).

## Treiber (`app/driver`)

| Ordner | Inhalt |
|---|---|
| `display/` | `wall_display.py` (Wandanzeige, alle 12 Module), `cells.py` (Text zu Segmentmustern), `text_layout.py` (Umbruch wie beim ESP), `terminal_display.py` (Anzeige im PC-Modus), Graphen, dazu der alte HT16K33-Treiber mit DisplayGrid |
| `uart/` | UART zum Radar LD2410S und Umschaltung per GPIO23 (HIGH = Radar, LOW = ESP); die Verbindung zum ESP liegt in `app/link/` |
| `chatbot/` | Groq-API |
| `speechRecognition/` | faster-whisper (lokal) bzw. Groq-Spracherkennung |
| `speech/` | Sprachausgabe |
| `database/` | MariaDB/MySQL für das Quiz (die Tabelle `reflections` liest REFLECTION nicht mehr) |

## Zitat der Nacht

Dieser Abschnitt ist ungeprüft bis zur Abnahme am Gerät.

Jede Nacht schaltet der ESP den Pi ein (`SESSION|NACHT`) und schickt `GET|QUOTE|<Text vom Vortag>`. Der Text vom Vortag ist leer, wenn es keinen gültigen gibt. Der Pi fragt die KI nach einem Gedanken zum Thema aus `thema.txt`. Der Gedanke baut auf dem Text vom Vortag auf (`app/night_quote.py`: `make_night_quote`, `build_night_messages`).

- `clean_quote` ersetzt Umlaute, entfernt unerlaubte Zeichen und macht aus Leerraum ein Leerzeichen.
- `quote_fits` prüft: 1 bis 96 erlaubte Zeichen, und der Text passt in die vier Zeilen der Wand.
- Passt eine Antwort nicht, fragt der Pi noch einmal. Er nimmt höchstens 3 Antworten.

`app/config/.thema_zuletzt` merkt sich das Thema der letzten gelungenen Nacht. Ist das Thema heute ein anderes, vergisst die KI den Gedanken von gestern und beginnt neu. Die Datei wird nur nach einem gelungenen Zitat geschrieben. Scheitert das Schreiben, etwa auf einer nur lesbaren SD-Karte, steht das im Log, und das Zitat gilt trotzdem.

Der Pi antwortet mit einer dieser Zeilen:

| Antwort | Bedeutung |
|---|---|
| `QUOTE\|<Text>` | das Zitat |
| `ERROR\|ZU_LANG` | alle 3 Antworten waren zu lang oder unbrauchbar |
| `ERROR\|KI` | Fehler der KI (auch „Leere Antwort“), kein Rechner für das Zitat angeschlossen, oder die Rechnung warf eine Ausnahme |
| `ERROR\|BAD_GET` | `GET` ohne `QUOTE\|` in den Daten |

Das Zitat rechnet ein eigener Thread (`app/ui/link_dispatch.py`). Tasten beantwortet der Pi währenddessen weiter. Zählen darf nur das neueste `GET`. Jede Taste setzt den ESP zurück; ein offenes `GET` sendet er danach noch einmal, mit neuer Nummer. Rechnet der Thread noch, geht seine Antwort an dieses neue `GET`. Ist er schon fertig und ging seine Antwort nicht mehr raus, bekommt es dasselbe Zitat ohne zweite KI-Runde. Gemerkt bleibt nur ein Zitat, kein `ERROR`, und nur, bis es zugestellt ist, höchstens bis zum Ende der Sitzung. In einer Sitzung `NACHT` schreibt der Pi die Anzeige nie und beendet die Sitzung nie selbst. Sie endet mit dem `SHUTDOWN` des ESP.

## Verbindung zum ESP (`app/link`)

`codec.py` baut und liest die Zeilen der Verbindung (Nummer, Befehl, Daten, Prüfsumme). `PiLink` vergibt die Nummern, wiederholt Anfragen und erkennt doppelte Nachrichten. Dafür läuft ein eigener Thread. `serial_port.py` öffnet `/dev/ttyAMA0` mit 74 880 Baud und setzt GPIO23 auf LOW. Damit gehört die UART dem ESP.

Das Prüfwerkzeug startet im Ordner `rpi/`:

```bash
python -m app.link.probe [--port /dev/ttyAMA0] [--baud 74880] [--seconds N] [--no-gpio]
```

Es sendet `READY`, bis der ESP antwortet, und gibt die Antwort aus. Danach beantwortet es die Anfragen des ESP: `BUTTON` mit `OK`, `SHUTDOWN` mit `BUSY` und alles andere mit `ERROR|PROBE`. Der Pi wird dabei nie heruntergefahren. `--seconds 0` läuft bis Ctrl+C. Mit `--no-gpio` bleibt GPIO23 unberührt. Läuft der Dienst, hält man ihn vorher an: `sudo systemctl stop reflection-wall`. Sonst teilen sich zwei Programme die UART.

Das Prüfwerkzeug und die Radar-Anwendung (Menüpunkt RADAR) dürfen nicht gleichzeitig laufen. Beide schalten GPIO23, und damit den CD4053. Der CD4053 legt fest, ob die UART des Pi mit dem ESP oder mit dem Radar spricht (Spezifikation F1, Abschnitt 6.4).

## Ablauf mit dem ESP

Dieser Abschnitt ist ungeprüft bis zur Abnahme am Gerät.

Nach dem Start schickt der Pi `READY`, etwa alle 3 s, bis der ESP mit `OK` antwortet. Der ESP kann dabei noch booten. Danach wartet der Pi auf die Sitzung des ESP:

- `SESSION|HAND`: BT2 hat den Pi eingeschaltet. Das Menü erscheint. Erst jetzt schreibt der Pi die Anzeige.
- `SESSION|NACHT`: Der Auftrag der Nacht hat den Pi eingeschaltet. Die Anzeige bleibt unberührt, siehe Abschnitt Zitat der Nacht. Folgt auf `NACHT` noch `SESSION|HAND` (BT2 am ESP), startet das Menü.

Kommt kein `SESSION`, schickt der Pi etwa alle 10 s noch einmal `READY`.

Bei `SHUTDOWN` des ESP beendet der Pi die laufende Anwendung und schreibt die Anzeige nicht mehr. Er wartet bis zu 45 s, bis die Anzeige frei ist. Dann antwortet er `OK` und ruft `sudo -n /usr/bin/systemctl poweroff` auf. Den Strom schaltet der ESP `T_halt` später ab.

Nach diesem `OK` bedient der Dienst die Verbindung weiter, bis systemd ihn beim Herunterfahren beendet, und wegen `ExecStop` noch 3 s länger. Sendet der ESP nach einem Reset `SHUTDOWN` noch einmal, bekommt es so sein `OK`. Kommt das neue `SHUTDOWN`, während das erste noch auf die Anzeige wartet, bekommt nur das neue ein `OK`, und erst danach fährt der Pi herunter. `poweroff` ruft der Pi nur einmal auf. Auch `systemctl stop` dauert deshalb 3 s länger.

Der Pi schickt `DONE`, wenn die Leerlaufzeit abläuft, die Shell abstürzt oder das Radar 55 min gelaufen ist. Beim Radar endet die Anwendung zuerst selbst und schaltet die UART zurück auf den ESP (GPIO23 LOW, 74 880 Baud, `MODE|NORMAL`). Erst dann schickt der Pi `DONE`. Danach schickt der ESP `SHUTDOWN`. Kommt nach einem bestätigten `DONE` innerhalb von 120 s kein `SHUTDOWN`, fährt der Pi sich selbst herunter.

## Regel B (I²C-Bus)

Dieser Abschnitt ist ungeprüft bis zur Abnahme am Gerät.

ESP und Pi teilen sich den I²C-Bus. Darum wartet der Pi vor jeder Übertragung:

- solange INT_GPIO_EXP (GPIO4) LOW ist, und danach 5 ms, wenn der Pin HIGH wird;
- 250 ms nach einer steigenden Flanke an INT_HLK (GPIO22, Radar).

Er wartet höchstens 1 s. Dann schreibt er trotzdem und schreibt eine Warnung ins Log. Eine Übertragung, die dabei abreißt, wiederholt er einmal. GPIO22 liest der Pi nur über diese Wache. Die Anwesenheit für das automatische Aus kommt ebenfalls von dort.

## Installation

```bash
sudo raspi-config              # I2C und Serial aktivieren
sudo apt install mariadb-server
sudo apt install liblgpio-dev libportaudio2 git-lfs   # lgpio wird beim pip install gebaut; sounddevice braucht PortAudio
git lfs pull                   # die Stimmen für piper (*.onnx) liegen in Git LFS
cd rpi
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

`pyserial` braucht die UART-Verbindung. Das Paket `piper-tts` liefert den Befehl `piper`, den die Sprachausgabe aufruft (am Pi geprüft, 2026-11-01). Die Sprachausgabe startet ihn mit dem Python des venv (`python -m piper`), weil unter dem Dienst der Ordner `bin/` des venv nicht im PATH steht. Zum Abspielen braucht es außerdem `aplay` (`sudo apt install alsa-utils`).

Auf dem Pi der Wand ist `fstrim.timer` abgeschaltet (`sudo systemctl disable --now fstrim.timer`). Der wöchentliche Lauf blockierte am 2026-11-01 die SD-Karte über 40 Minuten; pip, SSH und cron standen still. Er fiele außerdem jeden Montag auf 00:00, genau auf das Zitat der Nacht.

Die einzelnen Komponenten lassen sich in `tests/<Komponente>/` getrennt testen (`chatbot_groq`, `ht16k33`, `ioExpander`, `ld2410s`, `lichtsensor`, `microphone`, `mysql`, `speechrecognition`, `wakeWord`); dort steht jeweils eine `installation.txt`. `tests/ld2410s` nutzt den App-Treiber und startet im Ordner `rpi/` mit `python -m tests.ld2410s.test [--simulation] [--seconds N]`; auf dem PC mit `--simulation` (Windows: `python -X utf8 …`, sonst scheitert die Konsole an den Zeichen für Balken und Pfeile). `tests/microphone` nimmt auf und legt die Aufnahmen in `tests/microphone/recordings/` ab (nicht im Repository).

## Dienst einrichten

Dieser Abschnitt ist ungeprüft bis zur Abnahme am Gerät. Am Pi der Wand ist alles hier seit Teil 0 (2026-11-01) eingerichtet: Gruppen, `sudo` ohne Passwort, die Unit mit dem venv `~/.venvs/reflection-wall-rpi`. Die Unit ist aktiviert und startet beim nächsten Booten.

Die Unit liegt unter `rpi/systemd/reflection-wall.service`. Sie startet `python -m app.main` ohne `--pc`. Im Repository-Ordner auf dem Pi:

```bash
sudo cp rpi/systemd/reflection-wall.service /etc/systemd/system/
sudo nano /etc/systemd/system/reflection-wall.service   # Benutzer und Pfade anpassen
sudo systemctl daemon-reload
sudo systemctl enable --now reflection-wall
journalctl -u reflection-wall -f                         # Log mitlesen
```

Die Unit erwartet das venv unter `/home/pi/.venvs/reflection-wall-rpi`. Liegt es woanders, passt `ExecStart` an. Das venv aus dem Abschnitt Installation (`rpi/.venv`) funktioniert ebenso, wenn `ExecStart` darauf zeigt.

Der Benutzer braucht die Gruppen `dialout` (UART), `i2c` und `gpio`:

```bash
sudo usermod -aG dialout,i2c,gpio <benutzer>
```

Danach einmal neu anmelden.

Der Pi schaltet sich über `sudo -n` aus. Dafür braucht der Benutzer eine Regel ohne Passwort. Sie kommt mit `sudo visudo -f /etc/sudoers.d/reflection-wall` in die Datei:

```
<benutzer> ALL=(root) NOPASSWD: /usr/bin/systemctl poweroff
```

Beim Start prüft der Dienst diese Regel mit `sudo -n -l /usr/bin/systemctl poweroff`. Fehlt sie, schreibt er einen ERROR ins Log. Ohne die Regel kann sich der Pi nicht selbst herunterfahren, und am Ende jeder Sitzung trennt ihn der ESP hart.

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
USE quiz_db;
SELECT * FROM questions;
```

Weitere Befehle in `doc/commands.txt`.

## Bekannte Baustellen

- Der Dienst, der Ablauf mit dem ESP (READY, SESSION, SHUTDOWN, DONE) und Regel B sind ungeprüft bis zur Abnahme am Gerät.
- Der alte Anzeigetreiber (`display.py`, `display_grid.py`, `ht16k33_driver.py`, `displayGraph.py`) adressiert die Module als `0x70 + Index`. Das Menü und die Anwendungen nutzen ihn nicht mehr. Sie schreiben über `WallDisplay`, und `WallDisplay` erreicht alle 12 Module, auch die hinter den LTC4316 (0x7F, 0x79, 0x7B, 0x7D).
