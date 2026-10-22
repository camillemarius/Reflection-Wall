# Teil 1: Verbindung zwischen ESP und Pi – Umsetzungsplan

**Stand 2026-10-22:** Entwurf, überarbeitet nach der Wartbarkeits-Durchsicht vom selben Tag (Top-10, Punkte 5–8). Noch nicht umgesetzt.

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** ESP und Pi tauschen über die UART Nachrichten im Format `$NN:BEFEHL|DATEN*hh` aus, mit Prüfsumme, laufender Nummer, Bestätigung und Wiederholung. Vorher wird der Pi-Code ein testbares Paket, Umbruch und Schrift der Anzeige liegen als geprüfte Regel auf beiden Seiten, und die Pi-Speisung hat eine eigene Klasse.

**Architecture:** Der Pi-Code wird ein Paket `app` mit einer Importschreibweise, das auf dem PC ohne Hardware lädt und mit `unittest` geprüft wird. Codec und PiLink gibt es auf beiden Seiten: auf dem ESP als reines C++ in `esp/lib/core` hinter einer Schnittstelle `ISerialPort`, auf dem Pi als Paket `app.link` mit eigenem Thread für die Leitung (S4-a). Zwei gemeinsame Dateien in `tests/` prüfen ESP und Pi mit denselben Fällen: `protocol_vectors.json` (Nachrichten) und `display_vectors.json` (Umbruch und Schrift). Sitzung, Speisung nach Zustand, Mitternacht und Tasten für die Pi-Anwendungen gehören zu Teil 2, 3b und 4.

**Tech Stack:** ESP8266 Arduino-Core über PlatformIO (`env:esp12e`), Unity-Tests in `env:native` mit MinGW GCC 6.3; Python 3.13 mit `unittest`, `pyserial` 3.5, `lgpio` (nur auf dem Pi).

**Spec:** `docs/superpowers/specs/2026-10-19-esp-pi-steuerung-design.md` – Abschnitte 2 (E1-b, E2-a, E3, E5-c, Regel, S4-a), 3 (Z1, Z2, Z4, Z9, Z12, Z13), 5, 6, 9 (Schritte 4 und 5: Zeichen und Umbruch), 12, 13, 14, 15, 16 (Teil 1).

## Annahmen dieses Plans

Wo die Spezifikation offen ist, gilt hier die kleinste Wahl, die sie erfüllt. Der Owner kann jede Zeile überstimmen.

**Verbindung**

1. **Antwort oder Anfrage** erkennt der Empfänger am Befehl: `PONG`, `QUOTE`, `OK`, `BUSY`, `ERROR` sind Antworten, alles andere ist eine Anfrage. Eine Anfrage, die der Empfänger nicht kennt, bekommt `ERROR|UNKNOWN` – auch `PING` an den ESP oder `READY` an den Pi.
2. **Ohne Daten kein `|`:** gesendet wird `$00:PING*2A`; `$00:PING|*56` wird gleich gelesen.
3. **Nur druckbares ASCII** (0x20–0x7E) in einer Zeile; Zeilenumbruch und Wagenrücklauf nur maskiert. Andere Bytes → Zeile verworfen, Senden verweigert (`BAD_CHAR`). Anzeige und KI-Texte sind ASCII (Abschnitt 9), und Boot-Müll fällt so sicher heraus.
4. **256 Bytes ohne das `\n`.** Ein `\r` direkt vor dem `\n` wird beim Lesen entfernt. Leere Zeilen werden übergangen und nicht gezählt.
5. **Hex-Ziffern** werden gross geschrieben und beim Lesen auch klein angenommen.
6. **Nummern beginnen bei `00`** (ESP ohne gespeicherten Stand, Start des Pi-Programms). Wiederholungen tragen dieselbe Nummer, Antworten verbrauchen keine.
7. **Wiederholte Nummer ohne bekannte Antwort** (Anfrage noch in Arbeit, oder ESP nach einem Reset) wird übergangen: keine Antwort, nichts doppelt. Der Absender wiederholt bis zur Frist.
8. **Fristen stehen im Codec:** `GET` 120 s, `SHUTDOWN` 60 s (`T_shutdown`), alle anderen Anfragen 3 s. Die Verbindung meldet nur den Ablauf; was danach geschieht (Tabelle 6.2), entscheidet Teil 2.
9. **`PING` beantwortet der PiLink auf dem Pi selbst** in seinem Thread. `PONG` heisst damit: Programm und Verbindung leben – nicht: die Anwendung reagiert.
10. **Der ESP schreibt vor jede Nachricht ein `\n`.** Sein Debug-Log nutzt dieselbe Leitung und schreibt Zeilen ohne Ende (`[INPUT] BT3 -> `); sonst stünde die Nachricht nicht am Zeilenanfang.
11. **Gemeinsame Testfälle** liegen in `tests/` im Wurzelverzeichnis (Spezifikation 14 nennt `tests/protocol_vectors.json`), ein Testfall pro Zeile, die Datei reines ASCII. Der ESP-Test liest sie zur Laufzeit mit einem kleinen Leser für genau diese Form; `pio test` läuft im Ordner `esp/`, der Pfad ist also `../tests/…`.
12. **Python-Tests mit `unittest`** aus der Standardbibliothek, wie Spezifikation 14 sagt; pytest wird nicht installiert. Testpakete liegen als `tests/` neben dem Code in `rpi/app/…`; Aufruf `cd rpi && python -m unittest discover -s app -t . -v`.
13. **BT3 ohne Sitzung startet bis Teil 2 einen Verbindungstest:** `PING` senden und 3 s lang Anfragen des Pi mit `OK` beantworten, Ergebnis im Log. Teil 2 ersetzt das durch `BUTTON|3`.
14. **Alter Code:** Den alten ESP-Code (`esp/lib/communication/*`, Textspeicher, unbenutzte Mitglieder von `Application`) hat die Aufräumrunde vom 2026-10-22 schon entfernt (Commit 75acafc). Die alten Pi-Dateien `uart_esp.py`, `protocol.py`, `commands.py`, `test.py` in `rpi/app/driver/uart/` löscht Task 1; niemand nutzt sie, und `test.py` würde beim Import Hardware ansprechen.
15. **`txSeq`/`rxSeq`** gibt der ESP-PiLink über `state()`/`restore()` heraus. Sie im RTC-Speicher abzulegen gehört zu Teil 2 – bis dahin beginnt der ESP nach jedem Wecken bei `00`, und der Pi beantwortet ein zweites `PING #00` aus seinem Speicher.
16. **Fehler 1–5** aus der „ersten Durchsicht“ stehen nirgends im Repo. Dieser Plan benennt sie aus dem alten Code neu (nächster Abschnitt).
17. **Arbeitszweig** `feature/verbindung-esp-pi`, abgezweigt vom Zweig mit der Aufräumrunde (heute `feature/anzeige-radar-zitatliste`).
18. **Baudrate als Schalter:** `Features::LINK_BAUD = 74880` in `esp/lib/config/features.h`, auf dem Pi `ESP_BAUD` in `app/link/serial_port.py` (Z12: beide auf 115 200, falls nötig).

**Pi-Aufräumrunde (Tasks 1–2)**

19. **Ein Paket `app`:** Start mit `cd rpi && python -m app.main`. Alle Importe absolut ab `app.` – auch im Ordner `driver/uart`, der heute relativ importiert. Ordner, die Python-Module enthalten, bekommen ein leeres `__init__.py` – ausser `videoframes/`, dessen Dateien Daten sind. Ordner- und Klassennamen bleiben (auch `VoiseAssistant`).
20. **Nichts beim Import:** `smbus2` und `lgpio` werden erst beim ersten Gebrauch importiert (`smbus2` lässt sich unter Windows gar nicht importieren, es fehlt `fcntl`), der Bus erst dann geöffnet. Groq-Schlüssel und Client erst beim ersten `write_to_ai`. `setup_db` läuft im Konstruktor von `QuizGame` und `ReflectionAI` statt beim Import – die Datenbank wird also beim Wählen des Modus eingerichtet statt beim Start. `logging.basicConfig` wandert aus `groqAPI.py` nach `main()`.
21. **`QuizGame`:** Es bleibt die zweite Fassung der Klasse (heute Zeilen 52–99). Sie ist die, die heute läuft, weil sie die erste beim Import überschreibt.
22. **`rpi/requirements.txt` ohne Versionsnummern;** `lgpio` und `piper-tts` nur unter Linux. Die Versionen hält Teil 0 mit `pip freeze` auf dem Pi fest.
23. **Radar-Test:** `rpi/tests/ld2410s/test.py` läuft schon heute nicht: Er ruft `RadarGraph(min_distance=…, smoothing=…)` und `distance_to_x`, und beides gibt es in keiner Kopie. Er wird auf die App-Klassen `DisplayGraph` und `RadarGraph` umgestellt (eine Modulreihe, vier Höhenstufen) und bekommt `--simulation` und `--seconds`. Die Aufrufe, die es nicht gibt, entfallen. Damit `python -m tests.ld2410s.test` sicher den eigenen Ordner findet, bekommen `rpi/tests/` und `rpi/tests/ld2410s/` ein leeres `__init__.py`.

**Anzeige-Regeln (Task 5)**

24. **Umbruch = heutige ESP-Regel** (`DisplayGrid::splitText`), unverändert: 24 Zeichen pro Zeile, 4 Zeilen, Leerzeichen am Zeilenanfang überspringen, am letzten Leerzeichen umbrechen, ein Wort über 24 Zeichen hart trennen. Neu ist nur `fits` (der ganze Text steht in den vier Zeilen). Ein Punkt belegt eine Zelle; der Treiber zeichnet ihn ins vorherige Zeichen, das ändert sich nicht.
25. **Schrift:** Darstellbar sind Leerzeichen, `- . / : + *`, `0–9`, `A–Z`; Kleinbuchstaben wie Grossbuchstaben. Alles andere ist dunkel (`0000`) und nicht darstellbar.
26. **Die '7' wird `0x8022`** statt `0x8002` (dasselbe Muster wie die '1'): oberer Balken `0x0020` wie in '2', '3', 'O', 'T', dazu die rechte Seite `0x8002` der '1'. Gilt für ESP und Pi; Task 11 prüft es an der Wand.
27. **Auf dem Pi** wird `app/driver/display/text_layout.py` (heute unbenutzt) zu dieser Regel. Die Pi-Anwendungen behalten ihren eigenen Umbruch mit Silbentrennung in `display.py`; die Regel braucht erst das Zitat in Teil 3b.

**Pi-Speisung (Task 6)**

28. **`PiPower`** kapselt den Puls auf GPIO12 und merkt sich, was der ESP zuletzt geschaltet hat (`isOn()`; F5: zurücklesen geht nicht). BT2 bleibt in Teil 1 ein reines Umschalten (`toggle()`); `switchTo()` und `restore()` sind für Teil 2 da.

## Alter Code und Fehler 1–5

Z13 legt die Fehler 1–3 in den Pi-Code; 4 und 5 stammen aus dem ESP-Code, den die Aufräumrunde schon entfernt hat. Die Testfälle sichern, dass der neue Code sie nicht wiederholt.

| Nr. | Ort (alt) | Fehler | Testfall |
|---|---|---|---|
| 1 | `rpi/app/driver/uart/protocol.py`, `uart_esp.py` | `readline()` liefert Bytes, `Protocol.decode` ruft `partition("\|")` mit Text auf → `TypeError` bei der ersten Zeile | Vektor `bytes_not_text`; `test_decode_takes_bytes`, `test_garbage_bytes_do_not_raise` |
| 2 | `uart_esp.py` | `request()` liest sofort nach dem Senden und gibt `None` zurück; kein Warten, keine Wiederholung | `test_request_repeats_every_250ms_until_answer` (Python) |
| 3 | `protocol.py` | kein Startzeichen, keine Prüfsumme: jede Debug-Zeile des ESP mit `\|` gilt als Befehl | Vektoren `debug_line_with_pipe`, `boot_message` |
| 4 | `esp/lib/communication/protocol.cpp`, `uartHandler.cpp` (entfernt) | `encode` hängte `\n` an, `send` schrieb mit `println` → nach jeder Nachricht eine leere Zeile | `test_send_writes_newline_and_one_frame` (C++) |
| 5 | `protocol.cpp` (entfernt) | `decode` kürzte die Daten mit `trim()` → Leerzeichen am Rand gingen verloren | Vektor `data_keeps_edge_spaces` |

Ausserdem: `UARTMaster`/`UART` öffnen `/dev/serial0` mit 115 200 Baud – auf dem Pi 5 zeigt `serial0` in der Grundeinstellung auf den Debug-Anschluss (`ttyAMA10`), nicht auf GPIO14/15. Der Radar-Treiber behält das, bis die Radar-Einrichtung ihn neu schreibt.

## Dateien

| Datei | Aufgabe | Task |
|---|---|---|
| `rpi/requirements.txt` | Abhängigkeiten des Pi | 1 |
| `rpi/app/tests/test_imports.py` | jedes Modul lädt ohne Hardware und Netz | 1 |
| `rpi/tests/ld2410s/test.py` | Radar-Graph-Test auf den App-Treiber | 2 |
| `rpi/app/driver/display/tests/test_radar_graph.py` | Radar-Graph in der Simulation | 2 |
| `tests/protocol_vectors.json`, `tests/display_vectors.json` | gemeinsame Testfälle ESP und Pi | 3, 5 |
| `esp/test/support/VectorFile.h` | Testfall-Dateien im C++-Test lesen | 3 |
| `esp/lib/core/src/LinkCodec.h/.cpp` | Codec (Spezifikation 5) für den ESP | 3 |
| `rpi/app/link/codec.py`, `rpi/app/tests/vectors.py` | Codec für den Pi; Testfall-Dateien lesen und ihre Form prüfen | 4 |
| `esp/lib/core/src/TextLayout.h/.cpp`, `Glyphs.h/.cpp` | Umbruch und Schrift der Anzeige | 5 |
| `rpi/app/driver/display/text_layout.py`, `ascii_map.py` | dieselbe Regel und Schrift auf dem Pi | 5 |
| `esp/lib/core/src/PiPower.h/.cpp`, `esp/lib/system/PowerSwitchPin.h/.cpp` | Puls auf GPIO12 und Buchhaltung | 6 |
| `esp/lib/core/src/ISerialPort.h`, `PiLink.h/.cpp` | PiLink des ESP | 7 |
| `rpi/app/link/pi_link.py`, `serial_port.py` | PiLink des Pi mit Thread; `/dev/ttyAMA0` | 8 |
| `esp/lib/communication/UartPort.h/.cpp`, `esp/lib/app/LinkTest.h/.cpp` | `Serial` als `ISerialPort`; Verbindungstest auf BT3 | 9 |
| `rpi/app/link/probe.py` | Prüfwerkzeug für die Abnahme | 10 |

## Global Constraints

- Format nach E1-b und Z2: `$NN:BEFEHL|DATEN*hh` gefolgt von `\n`. `NN` = laufende Nummer, zwei Hex-Ziffern, je Absender `00`–`FF`, danach wieder `00`. `BEFEHL` = Grossbuchstaben `A–Z`, endet am ersten `|`.
- Prüfsumme: XOR aller Bytes zwischen `$` und dem **letzten** `*`, zwei Hex-Ziffern.
- Maskierung in `DATEN`: `\` → `\\`, Zeilenumbruch → `\n`, Wagenrücklauf → `\r`. `|`, `$`, `*` dürfen unmaskiert vorkommen.
- Eine Zeile höchstens **256 Bytes**; längere werden verworfen. Eine verworfene Zeile wird gezählt und im Log gemeldet, aber nicht beantwortet.
- Jede Anfrage bekommt genau eine Antwort mit derselben Nummer. Der Absender wiederholt alle **250 ms**, bis die Antwort da ist oder die Frist abläuft. Pro Richtung höchstens **eine** offene Anfrage. Kommt eine Nummer zweimal hintereinander, schickt der Empfänger seine letzte Antwort noch einmal und führt nichts doppelt aus. Unbekannter Befehl → `ERROR|UNKNOWN`.
- Fristen (Abschnitt 12): einfache Anfrage **3 s** (`PING`, `BUTTON`, `READY`, `DONE`, `MODE`), `GET|QUOTE` **120 s**, `SHUTDOWN` **60 s** (`T_shutdown`).
- Befehle (6.3): ESP → Pi `PING`, `GET`, `BUTTON`, `SHUTDOWN`; Pi → ESP `READY`, `DONE`, `MODE`; Antworten `PONG`, `QUOTE`, `OK`, `BUSY`, `ERROR`.
- Leitung (6.4, E2-a): **74 880 Baud** auf beiden Seiten; der Pi öffnet `/dev/ttyAMA0` und setzt **GPIO23 LOW** (ESP). Nimmt der Pi 5 keine 74 880 Baud an, wechseln beide auf **115 200** (Z12).
- Fehlercodes, auf beiden Seiten gleich geschrieben: `NO_START`, `TOO_LONG`, `BAD_CHAR`, `BAD_FORMAT`, `BAD_CHECKSUM`, `BAD_COMMAND`, `BAD_ESCAPE`.
- Prüfreihenfolge beim Lesen (damit beide Seiten denselben Code liefern): 1 länger als 256 → `TOO_LONG`; 2 leer oder erstes Byte nicht `$` → `NO_START`; 3 ein Byte ausserhalb 0x20–0x7E → `BAD_CHAR`; 4 kein `*`, oder das letzte `*` steht nicht an drittletzter Stelle, oder danach keine zwei Hex-Ziffern → `BAD_FORMAT`; 5 XOR passt nicht → `BAD_CHECKSUM`; 6 keine zwei Hex-Ziffern nach `$` oder kein `:` danach → `BAD_FORMAT`; 7 Befehl leer oder nicht nur `A–Z` → `BAD_COMMAND`; 8 `\` am Ende oder vor etwas anderem als `\`, `n`, `r` → `BAD_ESCAPE`.
- Beim Senden: Befehl nicht nur `A–Z` → `BAD_COMMAND`; ein Datenzeichen ausserhalb 0x20–0x7E, das nicht Zeilenumbruch oder Wagenrücklauf ist → `BAD_CHAR`; fertige Zeile über 256 → `TOO_LONG`. Ohne Daten kein `|`. Hex gross.
- Rollen in Testfällen und Code: `esp_request`, `pi_request`, `response`, `unknown`.
- Anzeige (Abschnitt 9, Schritt 5): **24 Zeichen pro Zeile, 4 Zeilen**, Umbruch an Wortgrenzen. Zeichen (Schritt 4): `A–Z 0–9 - . / : + *` und Leerzeichen.
- Testfall-Dateien: ein JSON-Objekt `{"vectors": [ … ]}`; `{` und `"vectors": [` auf eigenen Zeilen; **jeder Testfall ein flaches Objekt auf genau einer Zeile**; Werte nur Zeichenketten oder ganze Zahlen; Datei reines ASCII, Steuerzeichen als JSON-Escape (`\n`, `\r`, `\t` oder `\u00XX`), Bytes über 0x7E nur als `\u00XX` (höchstens `\u00ff`). Wahrheitswerte als `1`/`0`.
- Code in `esp/lib/core/` bindet **keine** Arduino-Header ein und bleibt bei **C++14** (MinGW GCC 6.3: kein `std::optional`, kein `std::string_view`). `#include` in genauer Gross-/Kleinschreibung. Schalter stehen in `esp/lib/config/features.h` (`namespace Features`).
- Testsuiten-Namen kurz halten: MinGW GCC 6.3 scheitert an Pfaden über 260 Zeichen.
- Python: `$PY` = `C:\Users\cross-INGCamilleChat\.venvs\reflection-wall-rpi\Scripts\python.exe` (Windows, alles ausser `lgpio`); auf dem Pi das venv aus Teil 0. Alle Python-Tests: `cd rpi && $PY -m unittest discover -s app -t . -v`. Importe nur absolut ab `app.`.
- Dieser Plan ändert `SlotStore*`, `FramQuoteStore*`, ihre Tests und Abschnitt 11 der Spezifikation nicht.
- Commit-Nachrichten auf Deutsch, eine Zeile Betreff, ohne Zusatzzeilen.

## Review Focus

1. **Debug-Text ohne Zeilenende vor einer Nachricht:** `DebugSerial.printf("[INPUT] %s -> ", …)` steht direkt vor `handleInput`; eine Nachricht danach stünde nicht am Zeilenanfang, und der Pi würde sie verwerfen. → ESP schreibt `\n` vor jede Nachricht; Test `test_send_writes_newline_and_one_frame` in Task 7.
2. **Späte Antwort nach einer neuen Anfrage:** Der Absender hat wiederholt, der Empfänger hat zweimal geantwortet; die zweite Antwort trifft ein, wenn schon die nächste Anfrage offen ist. Sie darf nicht als deren Antwort gelten. → Tests `test_late_answer_for_previous_number_is_ignored` in Task 7 und Task 8.
3. **Langsame Anfrage:** `GET|QUOTE` wird bis 120 s lang alle 250 ms wiederholt, während die KI rechnet. Die Wiederholungen dürfen weder einen zweiten Auftrag auslösen noch eine leere Antwort erzeugen. → Test `test_repeated_get_quote_before_reply_is_delivered_once` in Task 8 (und `test_duplicate_before_reply_is_ignored` in Task 7).
4. **Empfangspuffer des ESP:** Der Arduino-Core puffert 256 Bytes; eine Zeile hat mit `\n` bis 257. Schreibt der ESP gerade die Anzeige (I²C mit 10 kHz) oder liest das FRAM (0,4 s), läuft der Puffer über, und die Zeile kommt kaputt an. → Kein PC-Test möglich; Task 9 setzt `Serial.setRxBufferSize(1024)` vor `begin`, Task 11 Schritt 6 zählt kaputte Zeilen.
5. **Thread auf dem Pi stirbt:** Ein Fehler am Port (Gerät weg) beendet den Thread; eine Anwendung, die auf eine Antwort wartet, darf nicht ewig hängen. → Test `test_port_error_ends_thread_and_open_request` in Task 8.

---

### Task 1: Pi aufräumen – ein Paket, nichts beim Import, erster PC-Test

Ändert die Struktur, nicht das Verhalten der Anwendungen (Ausnahme: Annahme 20, Datenbank beim Wählen des Modus).

**Files:**
- Create: `rpi/requirements.txt`
- Create: `rpi/app/tests/__init__.py`, Test `rpi/app/tests/test_imports.py`
- Create: leeres `__init__.py` in `rpi/app/applications/`, `applications/Animations/`, `applications/ReflectionAI/`, `applications/VoiseAssistant/`, `driver/display/animations/`, `driver/speech/`, `driver/speechRecognition/`, `driver/uart/` – **nicht** in `applications/Animations/videoframes/`: `Stickman` führt dort jede `.py`-Datei mit `exec` als Bild aus
- Delete: `rpi/app/driver/uart/uart_esp.py`, `protocol.py`, `commands.py`, `test.py`
- Modify (Importe auf `app.`): `rpi/app/main.py`, `applications/Animations/Radar.py`, `applications/Quiz/AIQuizGenerator.py`, `applications/Quiz/QuizGame.py`, `applications/ReflectionAI/Reflection.py`, `applications/VoiseAssistant/VoiceAssistant.py`, `driver/display/display.py`, `displayGraph.py`, `display_grid.py`, `ht16k33_driver.py`, `segment_chain.py`, `segment_module.py`, `driver/uart/uart_device.py`, `uart_hlk.py`, `uart_master.py`
- Modify (nichts beim Import): `driver/display/ht16k33_driver.py`, `driver/uart/uart_switch.py`, `driver/chatbot/groqAPI.py`, `driver/speechRecognition/groqSpeechRecognition.py`, `applications/Quiz/QuizGame.py`, `applications/ReflectionAI/Reflection.py`, `main.py`
- Modify: `rpi/README.md`

**Interfaces:**
- Produces: Paket `app` (Start `cd rpi && python -m app.main`); `app.driver.display.ht16k33_driver` mit unveränderten Funktionen, der Bus kommt aus einer internen Funktion `_bus()`, die beim ersten Aufruf `smbus2` importiert und `SMBus(1)` öffnet; `app.driver.chatbot.groqAPI.write_to_ai` unverändert, der Client kommt aus `_client()` (beim ersten Aufruf: Schlüssel prüfen, wie heute `ValueError("GROQ_API_KEY fehlt")`, dann `Groq(...)`).

- [ ] **Step 1: Test schreiben**

```python
# rpi/app/tests/test_imports.py
RPI = Path(__file__).resolve().parents[2]

class ImportTest(unittest.TestCase):
    def test_every_module_imports_without_hardware_or_network(self)
        # In einem frischen Interpreter (subprocess, cwd=RPI, Umgebung ohne GROQ_API_KEY, timeout 120 s):
        # mysql.connector.connect und groq.Groq per unittest.mock.patch durch side_effect=AssertionError ersetzen,
        # dann jedes Modul aus pkgutil.walk_packages(app.__path__, "app.") importieren, ausser Namen mit ".tests";
        # danach: "smbus2" not in sys.modules und "lgpio" not in sys.modules.
        # Erwartet: Rueckgabecode 0 (bei Fehler stderr in der Meldung).
    def test_imports_use_the_app_package(self)
        # keine Zeile in RPI/app/**/*.py beginnt nach Leerraum mit
        # "from rpi.", "import rpi.", "from driver.", "from applications.", "from ."
```

Der Import von `faster_whisper` dauert auf dem PC rund 10 s; der Test ist trotzdem einer.

- [ ] **Step 2: Test laufen lassen, er muss scheitern**

Run: `cd rpi && $PY -m unittest discover -s app -t . -v`
Expected: FAIL in beiden Tests (alte Importe; `ModuleNotFoundError: No module named 'fcntl'` aus `smbus2` bzw. `No module named 'driver'`).

- [ ] **Step 3: Alte Dateien löschen, `__init__.py` anlegen, Importe umstellen**

Die vier alten Dateien in `driver/uart/` löschen. Jeden Import in den Dateien oben auf `from app.… import …` umstellen, auch die relativen im Ordner `driver/uart`.

- [ ] **Step 4: Arbeit beim Import entfernen**

- `ht16k33_driver.py`: `import smbus2` und `SMBus(1)` in `_bus()`; `init_module` und `write_buffer` holen den Bus dort.
- `uart_switch.py`: `import lgpio` in `UARTSwitch.__init__` und in `close()` über das gemerkte Modul.
- `groqAPI.py`: Schlüsselprüfung und `Groq(...)` in `_client()`; `logging.basicConfig(level=logging.INFO)` nach `main()` in `main.py`.
- `groqSpeechRecognition.py`: `Groq(...)` erst in `record_and_transcribe()`.
- `QuizGame.py`: die erste Fassung der Klasse (Zeilen 1–51) löschen; `setup_db("quiz")` in `__init__`.
- `Reflection.py`: `setup_db("reflection")` in `__init__`.

- [ ] **Step 5: `requirements.txt` und README**

`rpi/requirements.txt`, eine Zeile pro Paket, mit einer Kopfzeile „Versionen nach Teil 0 mit pip freeze festhalten“: `smbus2`, `lgpio; sys_platform == "linux"`, `pyserial`, `groq`, `python-dotenv`, `mysql-connector-python`, `faster-whisper`, `sounddevice`, `numpy`, `pyphen`, `piper-tts; sys_platform == "linux"`.
`rpi/README.md`: Start `cd rpi && python -m app.main` (die `PYTHONPATH`-Zeile und den Punkt „Importe sind gemischt“ unter „Bekannte Baustellen“ entfernen); Installation `pip install -r requirements.txt`; Abschnitt „Tests auf dem PC“ mit dem Aufruf aus den Global Constraints.

- [ ] **Step 6: Tests bestehen**

Run: `cd rpi && $PY -m unittest discover -s app -t . -v`
Expected: `OK`.
Run: `grep -rn "from rpi\.\|from driver\.\|from applications\." rpi/app`
Expected: keine Treffer.

- [ ] **Step 7: Commit** – „Pi: ein Paket app, nichts beim Import, erster PC-Test“

---

### Task 2: Pi aufräumen – Radar-Test auf den App-Treiber

**Files:**
- Delete: `rpi/tests/ld2410s/ascii_map.py`, `display.py`, `displayGraph.py`, `display_grid.py`, `ht16k33_driver.py`, `radarGraph.py`, `segment_chain.py`, `segment_module.py`
- Create: `rpi/tests/__init__.py`, `rpi/tests/ld2410s/__init__.py` (leer)
- Modify: `rpi/tests/ld2410s/test.py`
- Create: `rpi/app/driver/display/tests/__init__.py`, Test `rpi/app/driver/display/tests/test_radar_graph.py`
- Modify: `rpi/README.md`

**Interfaces:**
- Consumes: `app.driver.display.displayGraph.DisplayGraph(modules_per_row=3, simulation=False)`, `app.driver.display.radarGraph.RadarGraph(display, max_distance=6.0)` mit `update(distance)` (beide bestehend, nach Task 1 importierbar).
- Produces: `cd rpi && python -m tests.ld2410s.test [--simulation] [--seconds N]` (`N` = 0: bis Ctrl+C; Rückgabe 0).

- [ ] **Step 1: Test schreiben**

```python
class RadarGraphTest(unittest.TestCase):          # Ausgabe von refresh() mit contextlib.redirect_stdout schlucken
    def test_full_distance_fills_newest_column(self)
        # d = DisplayGraph(modules_per_row=3, simulation=True); r = RadarGraph(d, max_distance=6.0)
        # r.update(6.0) → d.modules[2].buffer[7] == "█"; d.modules[0].buffer[0] == " "
    def test_columns_move_left(self)
        # r.update(6.0); r.update(0.0) → d.modules[2].buffer[6] == "█", d.modules[2].buffer[7] == " "
```

- [ ] **Step 2: Test laufen lassen** – Run wie in Task 1. Expected: PASS ist möglich (die App-Klassen gibt es); er sichert, dass die Simulation auf dem PC ohne `smbus2` läuft. Scheitert er, zuerst Task 1 prüfen.

- [ ] **Step 3: Kopien löschen, Skript umstellen**

`test.py` importiert `DisplayGraph` und `RadarGraph` aus `app.driver.display`, baut `DisplayGraph(modules_per_row=3, simulation=args.simulation)` und `RadarGraph(display, max_distance=MAX_DISTANCE)`, lässt `min_distance`, `smoothing` und `distance_to_x` weg (die Ausgabezeile zeigt Distanz, Geschwindigkeit und Richtung) und endet nach `--seconds`. Die Simulation der Distanzen bleibt, wie sie ist.

- [ ] **Step 4: Prüfen ohne Pi**

Run: `cd rpi && $PY -m unittest discover -s app -t . -v`
Expected: `OK`.
Run: `cd rpi && $PY -m tests.ld2410s.test --simulation --seconds 1`
Expected: Rückgabe 0; die Konsole zeigt den Graphen (eine Zeile `█`/Leerzeichen, 24 Zeichen breit) und die Distanzzeile.

- [ ] **Step 5: README** – in `rpi/README.md` bei `tests/`: `ld2410s` startet mit `cd rpi && python -m tests.ld2410s.test` und nutzt den App-Treiber; auf dem PC mit `--simulation`.

- [ ] **Step 6: Commit** – „Pi: Radar-Test nutzt den App-Treiber, Kopien entfernt“

---

### Task 3: Gemeinsame Testfälle und Codec im ESP

**Files:**
- Create: `tests/protocol_vectors.json`
- Create: `esp/test/support/VectorFile.h`
- Create: `esp/lib/core/src/LinkCodec.h`, `esp/lib/core/src/LinkCodec.cpp`
- Test: `esp/test/test_link_codec/test_main.cpp`

**Interfaces:**
- Produces:
  ```cpp
  // LinkCodec.h – Nachricht <-> Zeile, ohne Arduino
  namespace LinkCodec
  {
      constexpr std::size_t MAX_LINE = 256;   // Bytes ohne '\n'

      enum class Error { None, NoStart, TooLong, BadChar, BadFormat, BadChecksum, BadCommand, BadEscape };
      enum class Role { Unknown, EspRequest, PiRequest, Response };

      struct Message
      {
          uint8_t seq = 0;
          std::string command;
          std::string data;   // unmaskiert
      };

      Error encode(const Message& msg, std::string& line);   // line ohne '\n'; bei Fehler unveraendert
      Error decode(const std::string& line, Message& msg);   // line ohne '\n'
      Role roleOf(const std::string& command);
      unsigned long deadlineMs(const std::string& command);  // GET 120000, SHUTDOWN 60000, sonst 3000
      const char* errorName(Error e);   // "NONE", "NO_START", "TOO_LONG", "BAD_CHAR", "BAD_FORMAT", "BAD_CHECKSUM", "BAD_COMMAND", "BAD_ESCAPE"
      const char* roleName(Role r);     // "unknown", "esp_request", "pi_request", "response"
  }

  // test/support/VectorFile.h – nur fuer Tests, header-only
  struct Vector
  {
      std::map<std::string, std::string> text;
      std::map<std::string, long> number;
      std::string str(const char* key) const;   // "" wenn nicht vorhanden
      long num(const char* key) const;          // -1 wenn nicht vorhanden
      bool has(const char* key) const;
  };
  constexpr char PROTOCOL_VECTORS[] = "../tests/protocol_vectors.json";   // pio test laeuft in esp/
  bool loadVectors(const char* path, std::vector<Vector>& out, std::string& error);
  ```

- [ ] **Step 1: Testfall-Datei schreiben**

Form wie in den Global Constraints. `kind`: `both` (Senden und Lesen), `decode` (nur Lesen), `error` (Lesen scheitert), `encode_error` (Senden scheitert), `command` (Rolle und Frist).

```json
{"name": "ping_00", "kind": "both", "line": "$00:PING*2A", "seq": 0, "command": "PING", "data": ""},
{"name": "pong_ff", "kind": "both", "line": "$FF:PONG*2C", "seq": 255, "command": "PONG", "data": ""},
{"name": "get_quote_new_chain", "kind": "both", "line": "$10:GET|QUOTE|*37", "seq": 16, "command": "GET", "data": "QUOTE|"},
{"name": "get_quote_with_text", "kind": "both", "line": "$11:GET|QUOTE|DER WEG IST DAS ZIEL.*1C", "seq": 17, "command": "GET", "data": "QUOTE|DER WEG IST DAS ZIEL."},
{"name": "quote_answer", "kind": "both", "line": "$11:QUOTE|WAS BLEIBT IST DIE FRAGE.*32", "seq": 17, "command": "QUOTE", "data": "WAS BLEIBT IST DIE FRAGE."},
{"name": "button_3", "kind": "both", "line": "$2A:BUTTON|3*10", "seq": 42, "command": "BUTTON", "data": "3"},
{"name": "error_unknown", "kind": "both", "line": "$07:ERROR|UNKNOWN*51", "seq": 7, "command": "ERROR", "data": "UNKNOWN"},
{"name": "mode_radar_checksum_00", "kind": "both", "line": "$01:MODE|RADAR*00", "seq": 1, "command": "MODE", "data": "RADAR"},
{"name": "escape_backslash", "kind": "both", "line": "$02:QUOTE|A\\\\B*1D", "seq": 2, "command": "QUOTE", "data": "A\\B"},
{"name": "escape_newline_and_cr", "kind": "both", "line": "$03:QUOTE|ZEILE1\\nZEILE2\\r*00", "seq": 3, "command": "QUOTE", "data": "ZEILE1\nZEILE2\r"},
{"name": "data_with_star_dollar_pipe", "kind": "both", "line": "$04:QUOTE|1*2$3|4**44", "seq": 4, "command": "QUOTE", "data": "1*2$3|4*"},
{"name": "data_keeps_edge_spaces", "kind": "both", "line": "$05:QUOTE| A B *3A", "seq": 5, "command": "QUOTE", "data": " A B "},
{"name": "lowercase_hex_is_read", "kind": "decode", "line": "$0a:PING*7B", "seq": 10, "command": "PING", "data": ""},
{"name": "lowercase_checksum_is_read", "kind": "decode", "line": "$00:PING*2a", "seq": 0, "command": "PING", "data": ""},
{"name": "empty_data_with_pipe", "kind": "decode", "line": "$00:PING|*56", "seq": 0, "command": "PING", "data": ""},
{"name": "esp_debug_line", "kind": "error", "line": "[WALL] aus", "error": "NO_START"},
{"name": "debug_line_with_pipe", "kind": "error", "line": "[QUOTES] 2026-10-21|DER WEG IST DAS ZIEL.", "error": "NO_START"},
{"name": "boot_message", "kind": "error", "line": " ets Jan  8 2013,rst cause:2, boot mode:(3,6)", "error": "NO_START"},
{"name": "garbage_before_start", "kind": "error", "line": "\u0000\u00ff$00:PING*2A", "error": "NO_START"},
{"name": "empty_line", "kind": "error", "line": "", "error": "NO_START"},
{"name": "bytes_not_text", "kind": "error", "line": "$00:BUTTON|\u00e4*B4", "error": "BAD_CHAR"},
{"name": "raw_tab", "kind": "error", "line": "$00:QUOTE|A\tB*16", "error": "BAD_CHAR"},
{"name": "bad_checksum", "kind": "error", "line": "$00:PING*2B", "error": "BAD_CHECKSUM"},
{"name": "missing_checksum", "kind": "error", "line": "$00:PING", "error": "BAD_FORMAT"},
{"name": "checksum_one_digit", "kind": "error", "line": "$00:PING*A", "error": "BAD_FORMAT"},
{"name": "checksum_not_hex", "kind": "error", "line": "$00:PING*G1", "error": "BAD_FORMAT"},
{"name": "number_not_hex", "kind": "error", "line": "$G0:PING*5D", "error": "BAD_FORMAT"},
{"name": "missing_colon", "kind": "error", "line": "$00PING*10", "error": "BAD_FORMAT"},
{"name": "lowercase_command", "kind": "error", "line": "$00:ping*2A", "error": "BAD_COMMAND"},
{"name": "digit_in_command", "kind": "error", "line": "$00:BUTTON1*1D", "error": "BAD_COMMAND"},
{"name": "empty_command", "kind": "error", "line": "$00:|X*1E", "error": "BAD_COMMAND"},
{"name": "unknown_escape", "kind": "error", "line": "$00:QUOTE|A\\xB*3B", "error": "BAD_ESCAPE"},
{"name": "trailing_backslash", "kind": "error", "line": "$00:QUOTE|A\\*01", "error": "BAD_ESCAPE"},
{"name": "encode_umlaut", "kind": "encode_error", "seq": 0, "command": "BUTTON", "data": "\u00e4", "error": "BAD_CHAR"},
{"name": "encode_tab", "kind": "encode_error", "seq": 0, "command": "QUOTE", "data": "A\tB", "error": "BAD_CHAR"},
{"name": "encode_lowercase_command", "kind": "encode_error", "seq": 0, "command": "Ping", "data": "", "error": "BAD_COMMAND"},
{"name": "cmd_ping", "kind": "command", "command": "PING", "role": "esp_request", "deadline_ms": 3000},
{"name": "cmd_get", "kind": "command", "command": "GET", "role": "esp_request", "deadline_ms": 120000},
{"name": "cmd_button", "kind": "command", "command": "BUTTON", "role": "esp_request", "deadline_ms": 3000},
{"name": "cmd_shutdown", "kind": "command", "command": "SHUTDOWN", "role": "esp_request", "deadline_ms": 60000},
{"name": "cmd_ready", "kind": "command", "command": "READY", "role": "pi_request", "deadline_ms": 3000},
{"name": "cmd_done", "kind": "command", "command": "DONE", "role": "pi_request", "deadline_ms": 3000},
{"name": "cmd_mode", "kind": "command", "command": "MODE", "role": "pi_request", "deadline_ms": 3000},
{"name": "cmd_pong", "kind": "command", "command": "PONG", "role": "response"},
{"name": "cmd_quote", "kind": "command", "command": "QUOTE", "role": "response"},
{"name": "cmd_ok", "kind": "command", "command": "OK", "role": "response"},
{"name": "cmd_busy", "kind": "command", "command": "BUSY", "role": "response"},
{"name": "cmd_error", "kind": "command", "command": "ERROR", "role": "response"},
{"name": "cmd_unknown", "kind": "command", "command": "TEXT", "role": "unknown"}
```

Dazu drei lange Fälle, ausgeschrieben (am einfachsten mit einer Zeile Python erzeugt):
- `max_line_256`, `both`: Zeile `$00:QUOTE|` + 243 × `A` + `*5D` (256 Bytes), `seq` 0, `command` `QUOTE`, `data` 243 × `A`.
- `too_long_257`, `error`: Zeile `$00:QUOTE|` + 244 × `A` + `*1C` (257 Bytes), `error` `TOO_LONG`.
- `encode_too_long`, `encode_error`: `seq` 0, `command` `QUOTE`, `data` 244 × `A`, `error` `TOO_LONG`.

Alle Prüfsummen oben sind nachgerechnet; 52 Testfälle.

- [ ] **Step 2: Tests schreiben**

Jede Prüfung meldet den Namen des Testfalls (`…_MESSAGE(…, v.str("name").c_str())`); Bytefolgen mit `==` auf `std::string` vergleichen, nicht mit `TEST_ASSERT_EQUAL_STRING` (Nullbytes).

```cpp
void test_vector_file_is_read()
    // loadVectors(PROTOCOL_VECTORS, v, err) == true, v.size() >= 52;
    // "escape_backslash": str("line") == "$02:QUOTE|A\\\\B*1D" (C++-Literal: ein doppelter Backslash);
    // "garbage_before_start": str("line").size() == 13, [0] == '\0', (uint8_t)[1] == 0xFF
void test_both_vectors_encode_and_decode()   // encode == Error::None und == line; decode == None und gleiche seq/command/data
void test_decode_vectors()                   // decode == None und gleiche seq/command/data
void test_error_vectors()                    // errorName(decode(line, m)) == error
void test_encode_error_vectors()             // std::string out = "x"; errorName(encode(m, out)) == error; out == "x"
void test_command_vectors()                  // roleName(roleOf(command)) == role; has("deadline_ms") → deadlineMs(command) == num("deadline_ms")
```

- [ ] **Step 3: Tests laufen lassen, sie müssen scheitern**

Run: `cd esp && pio test -e native -f test_link_codec`
Expected: FAIL beim Übersetzen (`LinkCodec.h` fehlt).

- [ ] **Step 4: `VectorFile.h` und `LinkCodec` umsetzen**

`loadVectors`: Datei ganz lesen (`std::ifstream`, binär); Zeile für Zeile, ein `\r` am Zeilenende entfernen (Git checkt mit CRLF aus); nur Zeilen, die nach Leerraum mit `{"` beginnen, als flaches Objekt lesen: `"Schlüssel": Wert`, durch `,` getrennt, `}` am Ende, ein `,` danach erlaubt. Wert ist `"…"` mit den Escapes `\"`, `\\`, `\/`, `\n`, `\r`, `\t`, `\u00XX` (→ ein Byte; grösser als `00FF` → Fehler) oder eine ganze Zahl. Bei einem Fehler `false` und in `error` Zeilennummer und Grund; fehlt die Datei: `false`, `error` = Pfad.

`decode` und `encode` folgen der Prüfreihenfolge in den Global Constraints. `roleOf` und `deadlineMs` sind feste Tabellen der Befehle aus 6.3.

- [ ] **Step 5: Tests bestehen**

Run: `cd esp && pio test -e native`
Expected: alle Suiten PASSED, auch die bestehenden.

- [ ] **Step 6: Commit** – „Gemeinsame Testfaelle und Codec der Verbindung im ESP“

---

### Task 4: Codec auf dem Pi

**Files:**
- Create: `rpi/app/link/__init__.py` (leer), `rpi/app/link/codec.py`
- Create: `rpi/app/link/tests/__init__.py` (leer)
- Create: `rpi/app/tests/vectors.py`
- Test: `rpi/app/link/tests/test_codec.py`, `rpi/app/tests/test_vectors.py`

**Interfaces:**
- Consumes: `tests/protocol_vectors.json` (Task 3).
- Produces:
  ```python
  # app/tests/vectors.py – Hilfe fuer Tests
  REPO = Path(__file__).resolve().parents[3]
  def load_vectors(file_name: str) -> list[dict]
      # liest REPO/"tests"/file_name; AssertionError, wenn die Datei nicht reines ASCII ist, wenn die Zeilen,
      # die nach Leerraum mit '{"' beginnen (ohne Komma am Ende per json.loads gelesen), nicht genau
      # json.load(...)["vectors"] in derselben Reihenfolge sind, oder wenn eine Zeichenkette nicht in
      # latin-1 passt (sonst saehe der ESP-Leser andere Faelle)

  # app/link/codec.py
  MAX_LINE = 256                      # Bytes ohne b"\n"

  @dataclass(frozen=True)
  class Message:
      seq: int                        # 0..255
      command: str
      data: str = ""                  # unmaskiert

  class CodecError(ValueError):
      code: str                       # "NO_START", "TOO_LONG", ... wie in C++
  class EncodeError(CodecError): ...
  class DecodeError(CodecError): ...

  def encode(msg: Message) -> bytes   # ohne b"\n"; EncodeError(code); seq ausserhalb 0..255 -> EncodeError("BAD_FORMAT")
  def decode(line: bytes) -> Message  # ohne b"\n"; DecodeError(code); str statt bytes -> TypeError
  def role_of(command: str) -> str    # "esp_request" | "pi_request" | "response" | "unknown"
  def deadline_ms(command: str) -> int
  ```

- [ ] **Step 1: Tests schreiben**

```python
# app/tests/test_vectors.py
class VectorFileTest(unittest.TestCase):
    def test_protocol_vectors_have_the_shared_form(self)   # load_vectors("protocol_vectors.json") wirft nicht, >= 52 Faelle

# app/link/tests/test_codec.py – je Testfall self.subTest(name=v["name"]); Bytes = s.encode("latin-1")
class CodecVectorTest(unittest.TestCase):
    def test_both(self)          # encode(Message(seq, command, data)) == line; decode(line) == Message(...)
    def test_decode(self)
    def test_error(self)         # with assertRaises(DecodeError) as cm: ...; cm.exception.code == v["error"]
    def test_encode_error(self)  # with assertRaises(EncodeError) as cm: ...; cm.exception.code == v["error"]
    def test_command(self)       # role_of == role; "deadline_ms" in v → deadline_ms(command) == v["deadline_ms"]

class CodecTypeTest(unittest.TestCase):
    def test_decode_takes_bytes(self)   # decode("$00:PING*2A") → TypeError (Fehler 1)
```

- [ ] **Step 2: Tests laufen lassen, sie müssen scheitern**

Run: `cd rpi && $PY -m unittest discover -s app -t . -v`
Expected: FAIL mit `ModuleNotFoundError: No module named 'app.link.codec'` bzw. `'app.tests.vectors'`.

- [ ] **Step 3: `vectors.py` und `codec.py` umsetzen**

Gleiche Prüfreihenfolge wie Task 3. Auf Bytes arbeiten; Text erst nach der `BAD_CHAR`-Prüfung mit `ascii` dekodieren.

- [ ] **Step 4: Tests bestehen**

Run: `cd rpi && $PY -m unittest discover -s app -t . -v`
Expected: `OK`, keine übersprungenen Tests.

- [ ] **Step 5: Commit** – „Codec der Verbindung auf dem Pi, gleiche Testfaelle wie der ESP“

---

### Task 5: Umbruch und Schrift der Anzeige als gemeinsame Regel

**Files:**
- Create: `tests/display_vectors.json`
- Create: `esp/lib/core/src/TextLayout.h`, `TextLayout.cpp`, `Glyphs.h`, `Glyphs.cpp`
- Modify: `esp/test/support/VectorFile.h` (Konstante `DISPLAY_VECTORS`)
- Test: `esp/test/test_text_layout/test_main.cpp`
- Delete: `esp/lib/display/ASCII16Seg.h`, `ASCII16Seg.cpp`
- Modify: `esp/lib/display/DisplayGrid.h/.cpp`, `esp/lib/drivers/HT16K33.cpp`, `esp/lib/display/display.h`, `esp/lib/app/application.cpp`
- Modify: `rpi/app/driver/display/text_layout.py` (ersetzt), `rpi/app/driver/display/ascii_map.py`
- Test: `rpi/app/driver/display/tests/test_display_rules.py`, `rpi/app/tests/test_vectors.py`

**Interfaces:**
- Consumes: `loadVectors`, `Vector` (Task 3); `load_vectors` (Task 4).
- Produces:
  ```cpp
  // TextLayout.h
  namespace TextLayout
  {
      constexpr std::size_t CHARS_PER_ROW = 24;
      constexpr std::size_t ROWS = 4;
      struct Layout
      {
          std::string rows[ROWS];   // je genau CHARS_PER_ROW Zeichen, rechts mit Leerzeichen aufgefuellt
          bool fits = true;         // der ganze Text steht in den vier Zeilen
      };
      Layout wrap(const std::string& text);
  }

  // Glyphs.h
  namespace Glyphs
  {
      uint16_t segments(char c);   // 16-Segment-Muster; a-z wie A-Z; nicht darstellbar -> 0
      bool displayable(char c);    // Leerzeichen, - . / : + *, 0-9, A-Z, a-z
  }

  // VectorFile.h
  constexpr char DISPLAY_VECTORS[] = "../tests/display_vectors.json";
  ```
  ```python
  # app/driver/display/text_layout.py
  CHARS_PER_ROW = 24
  ROWS = 4
  def wrap(text: str) -> tuple[list[str], bool]   # (vier Zeilen zu je 24 Zeichen, passt)
  def displayable(ch: str) -> bool                # ch.upper() ist ein Schluessel von ASCII_16SEG
  ```

- [ ] **Step 1: Testfall-Datei schreiben**

`kind` `wrap` (Felder `text`, `row1`–`row4` je 24 Zeichen, `fits` 1/0) und `glyph` (Felder `char`, `segments` als vier Hex-Ziffern gross, `displayable` 1/0).

```json
{"name": "empty", "kind": "wrap", "text": "", "row1": "                        ", "row2": "                        ", "row3": "                        ", "row4": "                        ", "fits": 1},
{"name": "kein_text", "kind": "wrap", "text": "KEIN TEXT", "row1": "KEIN TEXT               ", "row2": "                        ", "row3": "                        ", "row4": "                        ", "fits": 1},
{"name": "one_full_row", "kind": "wrap", "text": "ABCDEFGHIJKLMNOPQRSTUVWX", "row1": "ABCDEFGHIJKLMNOPQRSTUVWX", "row2": "                        ", "row3": "                        ", "row4": "                        ", "fits": 1},
{"name": "break_at_word", "kind": "wrap", "text": "DER SINN DES LEBENS LIEGT NICHT AM ZIEL.", "row1": "DER SINN DES LEBENS     ", "row2": "LIEGT NICHT AM ZIEL.    ", "row3": "                        ", "row4": "                        ", "fits": 1},
{"name": "space_exactly_after_24", "kind": "wrap", "text": "ABCDEFGHIJKLMNOPQRSTUVWX YZ", "row1": "ABCDEFGHIJKLMNOPQRSTUVWX", "row2": "YZ                      ", "row3": "                        ", "row4": "                        ", "fits": 1},
{"name": "leading_spaces_skipped", "kind": "wrap", "text": "   HALLO", "row1": "HALLO                   ", "row2": "                        ", "row3": "                        ", "row4": "                        ", "fits": 1},
{"name": "inner_spaces_kept", "kind": "wrap", "text": "A  B", "row1": "A  B                    ", "row2": "                        ", "row3": "                        ", "row4": "                        ", "fits": 1},
{"name": "long_word_hard_split", "kind": "wrap", "text": "AAAAAAAAAAAAAAAAAAAAAAAAAAAAAA", "row1": "AAAAAAAAAAAAAAAAAAAAAAAA", "row2": "AAAAAA                  ", "row3": "                        ", "row4": "                        ", "fits": 1},
{"name": "short_text_does_not_fit", "kind": "wrap", "text": "ABCDEFGHIJKLM ABCDEFGHIJKLM ABCDEFGHIJKLM ABCDEFGHIJKLM ABCDEFGHIJKLM", "row1": "ABCDEFGHIJKLM           ", "row2": "ABCDEFGHIJKLM           ", "row3": "ABCDEFGHIJKLM           ", "row4": "ABCDEFGHIJKLM           ", "fits": 0},
{"name": "dot_takes_a_cell", "kind": "wrap", "text": "ENDE. NEU.", "row1": "ENDE. NEU.              ", "row2": "                        ", "row3": "                        ", "row4": "                        ", "fits": 1},
{"name": "sample_quote", "kind": "wrap", "text": "Wer nach innen schaut erwacht. Wer nach aussen schaut traeumt. Finde heute deinen neuen Weg.", "row1": "Wer nach innen schaut   ", "row2": "erwacht. Wer nach aussen", "row3": "schaut traeumt. Finde   ", "row4": "heute deinen neuen Weg. ", "fits": 1},
{"name": "sample_quote_2", "kind": "wrap", "text": "Im Innehalten wird es still. In der Stille hoerst du was dein Herz dir lange sagen wollte.", "row1": "Im Innehalten wird es   ", "row2": "still. In der Stille    ", "row3": "hoerst du was dein Herz ", "row4": "dir lange sagen wollte. ", "fits": 1},
{"name": "glyph_lower_a", "kind": "glyph", "char": "a", "segments": "83A3", "displayable": 1},
{"name": "glyph_seven", "kind": "glyph", "char": "7", "segments": "8022", "displayable": 1},
{"name": "glyph_excl", "kind": "glyph", "char": "!", "segments": "0000", "displayable": 0},
{"name": "glyph_umlaut", "kind": "glyph", "char": "\u00e4", "segments": "0000", "displayable": 0},
{"name": "glyph_newline", "kind": "glyph", "char": "\n", "segments": "0000", "displayable": 0}
```

Dazu ausgeschrieben:
- `ninety_six_fit`: `text` 96 × `A` → vier Zeilen zu 24 × `A`, `fits` 1.
- `ninety_seven_do_not_fit`: 97 × `A` → vier Zeilen zu 24 × `A`, `fits` 0.
- `trailing_spaces_fit`: 96 × `A` + 3 Leerzeichen → wie `ninety_six_fit`, `fits` 1.
- je ein `glyph` für Leerzeichen, `- . / : + *`, `0`–`9` ohne die `7` (steht oben), `A`–`Z` (Name `glyph_` + Zeichen bzw. `space`, `minus`, `dot`, `slash`, `colon`, `plus`, `star`), `displayable` 1, `segments` aus `esp/lib/display/ASCII16Seg.cpp`.

Die Umbruch-Ergebnisse sind mit der heutigen ESP-Regel nachgerechnet.

- [ ] **Step 2: Tests schreiben**

```cpp
// esp/test/test_text_layout/test_main.cpp
void test_wrap_vectors()            // wrap(text): rows[0..3] == row1..row4, fits == (num("fits") == 1)
void test_glyph_vectors()           // segments(char[0]) == strtoul(segments, 16); displayable == (num == 1)
void test_seven_differs_from_one()  // segments('7') != segments('1')
```
```python
# app/driver/display/tests/test_display_rules.py – je Testfall subTest
class DisplayRulesTest(unittest.TestCase):
    def test_wrap_vectors(self)          # wrap(text) == ([row1, row2, row3, row4], fits == 1)
    def test_font_matches_glyphs(self)   # ASCII_16SEG.get(char.upper(), 0) == int(segments, 16)
    def test_displayable(self)           # displayable(char) == (v["displayable"] == 1)

# app/tests/test_vectors.py, dazu:
    def test_display_vectors_have_the_shared_form(self)
```

- [ ] **Step 3: Tests laufen lassen, sie müssen scheitern**

Run: `cd esp && pio test -e native -f test_text_layout` → FAIL beim Übersetzen (`TextLayout.h` fehlt).
Run: `cd rpi && $PY -m unittest discover -s app -t . -v` → FAIL (`wrap` fehlt; '7' falsch).

- [ ] **Step 4: ESP umsetzen**

`TextLayout::wrap` ist `DisplayGrid::splitText` mit `std::string` (Annahme 24); `fits`: nach der vierten Zeile Leerzeichen überspringen, dann muss der Text zu Ende sein. `Glyphs::segments` ist die Tabelle aus `ASCII16Seg.cpp` mit '7' = `0x8022`, ohne `toupper` aus `<cctype>` mit Gebietsschema (selbst `'a'`–`'z'` abbilden).
Danach: `ASCII16Seg.*` löschen, `HT16K33.cpp` ruft `Glyphs::segments`; `DisplayGrid::setText` nutzt `TextLayout::wrap` und gibt die Zeilen als `String` weiter, `splitText` entfällt; `display.h` nimmt `ROWS = TextLayout::ROWS`. In `application.cpp` ersetzt `if (!TextLayout::wrap(text).fits)` die Prüfung gegen `DISPLAY_CHARS`, Log `[TEXT] Warnung: passt nicht auf die Anzeige (4 x 24, Umbruch an Wortgrenzen): "%s"`; `DISPLAY_CHARS` entfällt.

- [ ] **Step 5: Pi umsetzen**

`text_layout.py` neu schreiben (alter Inhalt wird nirgends importiert). In `ascii_map.py` die '7' auf `0x8022` setzen und den doppelten Eintrag `'-'` entfernen.

- [ ] **Step 6: Tests bestehen**

Run: `cd esp && pio test -e native` → alle Suiten PASSED. `cd esp && pio run` → SUCCESS ohne neue Warnungen.
Run: `cd rpi && $PY -m unittest discover -s app -t . -v` → `OK`.

- [ ] **Step 7: Commit** – „Umbruch und Schrift der Anzeige als gemeinsame Regel fuer ESP und Pi, 7 berichtigt“

---

### Task 6: Pi-Speisung als eigene Klasse `PiPower`

Hält `application.cpp` schlank, bevor die Verbindung dazukommt, und gibt der PiSession aus Teil 2 einen festen Platz.

**Files:**
- Create: `esp/lib/core/src/PiPower.h`, `esp/lib/core/src/PiPower.cpp`
- Create: `esp/lib/system/PowerSwitchPin.h`, `esp/lib/system/PowerSwitchPin.cpp`
- Create: `esp/test/support/RecordingPin.h`
- Test: `esp/test/test_pi_power/test_main.cpp`
- Modify: `esp/lib/app/application.h`, `esp/lib/app/application.cpp`

**Interfaces:**
- Produces:
  ```cpp
  // PiPower.h
  class IPowerPin                               // GPIO12 zum Flipflop der Pi-Speisung (F5)
  {
  public:
      virtual ~IPowerPin() = default;
      virtual bool readIdle() = 0;              // Pin als Eingang, Pegel lesen
      virtual void drive(bool high) = 0;        // Pegel setzen, Pin ist danach Ausgang
      virtual void waitMs(unsigned long ms) = 0;
  };

  class PiPower
  {
  public:
      static constexpr unsigned long PULSE_MS = 50;
      explicit PiPower(IPowerPin& pin);
      void toggle();                  // ein Puls gegen den gemessenen Ruhepegel; kippt isOn()
      bool switchTo(bool on);         // pulst nur, wenn isOn() != on; true, wenn gepulst
      bool isOn() const;              // was der ESP zuletzt geschaltet hat; anfangs false
      void restore(bool on);          // Teil 2: Wert aus dem RTC-Speicher, ohne Puls
  };

  // PowerSwitchPin.h (Arduino)
  class PowerSwitchPin : public IPowerPin   // Pins::ESP_GPIO12_PS
  {
  public:
      bool readIdle() override;             // pinMode(INPUT), digitalRead
      void drive(bool high) override;       // erst digitalWrite, dann pinMode(OUTPUT)
      void waitMs(unsigned long ms) override;   // delay
  };

  // test/support/RecordingPin.h
  class RecordingPin : public IPowerPin
  {
  public:
      bool idle = true;          // Pegel, den readIdle() liefert
      std::string log;           // "R" lesen, "H"/"L" ausgeben, "W50" warten, durch Leerzeichen getrennt
  };
  ```

- [ ] **Step 1: Tests schreiben**

```cpp
void test_toggle_with_idle_high_pulses_low()   // idle = true; toggle() → log == "R H L W50 H"
void test_toggle_with_idle_low_pulses_high()   // idle = false; toggle() → log == "R L H W50 L"
void test_toggle_flips_is_on()                 // isOn() false; toggle → true; toggle → false
void test_switch_to_same_state_does_not_pulse()   // switchTo(false) == false, log leer
void test_switch_to_other_state_pulses_once()     // switchTo(true) == true, log == "R H L W50 H", isOn() true
void test_restore_sets_state_without_pulse()      // restore(true) → isOn() true, log leer; switchTo(false) pulst
```

Das erste `H`/`L` nach `R` ist derselbe Pegel wie der gelesene: Der Pin wird Ausgang, ohne eine Flanke zu erzeugen.

- [ ] **Step 2: Tests laufen lassen, sie müssen scheitern**

Run: `cd esp && pio test -e native -f test_pi_power`
Expected: FAIL beim Übersetzen (`PiPower.h` fehlt).

- [ ] **Step 3: `PiPower`, `RecordingPin` und `PowerSwitchPin` umsetzen**

Die Kommentare aus `configurePowerSwitchPin` und `togglePowerSwitch` (Ruhepegel messen, keine Flanke, Pin sonst Eingang, Reihenfolge `digitalWrite` vor `pinMode`) wandern zu `PowerSwitchPin` und `PiPower`.

- [ ] **Step 4: Anwendung umstellen**

In `Application`: `configurePowerSwitchPin`, `togglePowerSwitch`, `_pulseIdle` und `PULSE_MS` entfernen; neue Mitglieder `PowerSwitchPin _powerPin; PiPower _piPower;` (in dieser Reihenfolge). BT2 ruft `_piPower.toggle()`; Log wie heute.

- [ ] **Step 5: Prüfen**

Run: `cd esp && pio test -e native` → alle Suiten PASSED.
Run: `cd esp && pio run` → SUCCESS ohne neue Warnungen.
Run: `grep -n "ESP_GPIO12_PS\|_pulseIdle" esp/lib/app/application.*` → keine Treffer.

- [ ] **Step 6: Commit** – „Pi-Speisung als eigene Klasse PiPower mit PC-Tests“

---

### Task 7: PiLink im ESP

**Files:**
- Create: `esp/lib/core/src/ISerialPort.h`
- Create: `esp/lib/core/src/PiLink.h`, `esp/lib/core/src/PiLink.cpp`
- Create: `esp/test/support/MemorySerial.h`
- Test: `esp/test/test_pi_link/test_main.cpp`

**Interfaces:**
- Consumes: `LinkCodec::Message`, `Error`, `Role`, `encode`, `decode`, `roleOf`, `deadlineMs` (Task 3).
- Produces:
  ```cpp
  // ISerialPort.h
  class ISerialPort
  {
  public:
      virtual ~ISerialPort() = default;
      virtual int read() = 0;                           // naechstes Byte 0..255, -1 wenn keines wartet
      virtual void write(const std::string& bytes) = 0;
  };

  // PiLink.h
  struct LinkEvent
  {
      enum class Kind { None, Request, Response, Expired };
      Kind kind = Kind::None;
      LinkCodec::Message message;   // Request: Anfrage des Pi; Response: Antwort; Expired: die eigene Anfrage
  };

  struct LinkState { uint8_t txSeq = 0; uint8_t rxSeq = 0; bool rxValid = false; };

  class PiLink
  {
  public:
      static constexpr unsigned long REPEAT_MS = 250;
      explicit PiLink(ISerialPort& port);
      // false: schon eine Anfrage offen oder nicht kodierbar; verbraucht dann keine Nummer
      bool send(const std::string& command, const std::string& data, unsigned long nowMs);
      // liest, bis ein Ereignis da ist oder nichts mehr wartet; danach Frist und Wiederholung
      LinkEvent poll(unsigned long nowMs);
      // beantwortet die zuletzt gemeldete Anfrage des Pi; false, wenn keine offen ist
      bool reply(const std::string& command, const std::string& data = std::string());
      bool busy() const;                    // eigene Anfrage offen
      unsigned long discarded() const;      // verworfene Zeilen
      LinkCodec::Error lastError() const;
      LinkState state() const;              // txSeq = naechste Nummer
      void restore(const LinkState& s);
  };

  // test/support/MemorySerial.h
  class MemorySerial : public ISerialPort
  {
  public:
      std::string rx;        // was "der Pi" schickt; read() nimmt vorne weg
      std::string tx;        // was der ESP geschrieben hat
      int read() override;
      void write(const std::string& bytes) override;
      std::string takeTx();  // tx zurueckgeben und leeren
  };
  ```

- [ ] **Step 1: Tests schreiben**

```cpp
void test_send_writes_newline_and_one_frame()
    // send("PING","",0) == true → takeTx() == "\n$00:PING*2A\n"  (kein "\r", keine Leerzeile danach; Fehler 4)
void test_repeats_every_250ms_until_answer()
    // send PING bei 0, takeTx(); poll(249) → tx leer; poll(250) → "\n$00:PING*2A\n";
    // rx = "$00:PONG*2C\n"; poll(300) → Response, seq 0, "PONG"; busy() == false; poll(600) → tx leer
void test_expires_after_deadline_with_12_frames()
    // send PING bei 0, poll alle 10 ms bis 2990 → keine Ereignisse; poll(3000) → Expired, message.command "PING";
    // in tx genau 12 Mal "$00:PING*2A"; busy() == false
void test_get_quote_waits_120s()
    // send("GET","QUOTE|",0) → "\n$00:GET|QUOTE|*36\n"; poll(119999) nicht Expired; poll(120000) → Expired
void test_numbers_count_per_request_not_per_repeat()
    // PING → $00, Wiederholung → $00, Antwort $00:PONG*2C, naechstes send → "\n$01:PING*2B\n"
void test_number_wraps_from_ff_to_00()
    // restore({0xFF, 0, false}); send → "$FF:PING*2A"; rx "$FF:PONG*2C\n" → Response; send → "$00:PING*2A"
void test_second_send_while_open_is_refused()      // zweites send("BUTTON","1",10) == false, tx nur der PING
void test_send_refuses_unencodable_data()
    // send("GET", "QUOTE|\xC4", 0) == false, busy() == false, tx leer; danach send PING → "$00:PING*2A"
void test_late_answer_for_previous_number_is_ignored()
    // PING #00 beantwortet; send PING (#01); rx "$00:PONG*2C\n" → poll Kind::None, busy() == true
void test_answer_without_open_request_is_ignored() // rx "$00:PONG*2C\n" → None, discarded() == 0
void test_request_from_pi_is_delivered_and_answered()
    // rx "$05:READY*74\n" → Request, seq 5, "READY"; reply("OK") == true → takeTx() == "\n$05:OK*3B\n"
void test_duplicate_gets_previous_answer_again()
    // wie oben, danach nochmals rx "$05:READY*74\n" → None, takeTx() == "\n$05:OK*3B\n"
void test_duplicate_before_reply_is_ignored()
    // rx "$05:READY*74\n$05:READY*74\n" → erstes poll Request, zweites None; tx leer
void test_new_number_is_new_request()              // nach #05 beantwortet: rx "$06:READY*77\n" → Request seq 6
void test_unknown_command_is_answered_with_error_unknown()
    // rx "$07:PING*2D\n" → None, takeTx() == "\n$07:ERROR|UNKNOWN*51\n"; dieselbe Zeile nochmals → dieselbe Antwort
void test_bad_line_is_counted_and_not_answered()
    // rx "$00:PING*2B\n" → None, discarded() == 1, lastError() == Error::BadChecksum, tx leer
void test_too_long_line_is_dropped_and_next_line_is_read()
    // rx = 300 × 'A' + "\n$05:READY*74\n" → poll → Request; discarded() == 1, lastError() == TooLong
void test_partial_line_waits_for_newline()         // rx "$05:REA" → None; rx += "DY*74\n" → Request
void test_crlf_is_accepted()                       // rx "$05:READY*74\r\n" → Request
void test_empty_lines_are_not_counted()            // rx "\n\r\n\n" → None, discarded() == 0
void test_reply_without_request_is_refused()       // reply("OK") == false, tx leer
void test_state_survives_restore()
    // a: send PING bei 0; rx "$00:PONG*2C\n$05:READY*74\n"; poll → Response; poll → Request; reply("OK");
    // a.state(): txSeq 1, rxSeq 5, rxValid true; b.restore(a.state()); b.send PING → "\n$01:PING*2B\n";
    // b: rx "$05:READY*74\n" → None, keine Antwort geschrieben (Annahme 7)
```

- [ ] **Step 2: Tests laufen lassen, sie müssen scheitern**

Run: `cd esp && pio test -e native -f test_pi_link`
Expected: FAIL beim Übersetzen (`PiLink.h` fehlt).

- [ ] **Step 3: `MemorySerial` und `PiLink` umsetzen**

Zeilenpuffer höchstens `MAX_LINE + 1` Bytes (Platz für ein `\r`); was darüber kommt, wird bis zum `\n` verworfen und als eine `TooLong`-Zeile gezählt. Jede Nachricht wird als `"\n" + line + "\n"` in **einem** `write` geschrieben. Eine Antwort gilt nur, wenn eine eigene Anfrage offen ist und die Nummer passt. Eine Anfrage mit `rxValid && seq == rxSeq` ist doppelt: bekannte Antwort noch einmal schreiben, sonst nichts. Sonst `rxSeq = seq`; Rolle nicht `PiRequest` → `ERROR|UNKNOWN` schreiben und merken; sonst als `Request` melden und bis `reply` als „in Arbeit“ führen. `poll` prüft nach dem Lesen zuerst die Frist (`now - start >= deadlineMs`), dann die Wiederholung (`now - lastSent >= REPEAT_MS`, danach `lastSent = now`).

- [ ] **Step 4: Tests bestehen**

Run: `cd esp && pio test -e native`
Expected: alle Suiten PASSED.

- [ ] **Step 5: Commit** – „PiLink im ESP: Nummern, Wiederholung, doppelte Nachrichten“

---

### Task 8: PiLink auf dem Pi mit eigenem Thread

**Files:**
- Create: `rpi/app/link/pi_link.py`, `rpi/app/link/serial_port.py`
- Create: `rpi/app/link/tests/fakes.py`
- Test: `rpi/app/link/tests/test_pi_link.py`, `rpi/app/link/tests/test_serial_port.py`

**Interfaces:**
- Consumes: `Message`, `encode`, `decode`, `DecodeError`, `EncodeError`, `role_of`, `deadline_ms`, `MAX_LINE` (Task 4).
- Produces:
  ```python
  # app/link/pi_link.py
  REPEAT_S = 0.25

  class LinkBusy(RuntimeError): ...

  class Port(typing.Protocol):
      def read_available(self) -> bytes: ...   # darf kurz warten (echter Port 50 ms); b"" wenn nichts kam
      def write(self, data: bytes) -> None: ...

  class PiLink:
      incoming: queue.Queue[Message]          # Anfragen des ESP ausser PING, in Eingangsreihenfolge
      discarded: collections.Counter[str]     # verworfene Zeilen je Fehlercode
      def __init__(self, port: Port, clock: Callable[[], float] = time.monotonic,
                   log: logging.Logger | None = None) -> None   # Standard: logging.getLogger("link")
      @property
      def alive(self) -> bool                 # Thread laeuft
      def request(self, command: str, data: str = "") -> concurrent.futures.Future[Message | None]
          # LinkBusy, wenn eine offen ist; EncodeError; Ergebnis None = Frist abgelaufen
      def reply(self, request: Message, command: str, data: str = "") -> bool   # False: nicht (mehr) in Arbeit
      def poll(self) -> None                  # ein Durchgang: lesen, Zeilen verarbeiten, Frist, Wiederholung
      def start(self) -> None                 # Thread "pi-link": while not stopped: poll()
      def stop(self, timeout: float = 2.0) -> None

  # app/link/serial_port.py
  ESP_DEVICE = "/dev/ttyAMA0"
  ESP_BAUD = 74880           # E2-a; Z12: sonst 115200 auf beiden Seiten (ESP: Features::LINK_BAUD)
  UART_SELECT_GPIO = 23      # LOW = ESP (F1)
  GPIO_CHIP = 0              # wie driver/uart/uart_switch.py
  READ_TIMEOUT_S = 0.05

  class SerialPort:          # erfuellt Port
      def __init__(self, serial: serial.SerialBase, gpio_handle: int | None = None) -> None
      def read_available(self) -> bytes       # read(max(1, in_waiting))
      def write(self, data: bytes) -> None
      def close(self) -> None                 # Port und GPIO-Handle schliessen

  def open_esp_port(device: str = ESP_DEVICE, baud: int = ESP_BAUD,
                    select_gpio: bool = True) -> SerialPort
      # select_gpio: lgpio erst hier importieren, GPIO23 als Ausgang LOW beanspruchen und den
      # Handle offen halten; dann serial.serial_for_url(device, baudrate=baud, timeout=READ_TIMEOUT_S)

  # app/link/tests/fakes.py
  class FakeClock:            # now: float; __call__() -> float; advance(seconds) -> None
  class FakePort:             # feed(data); read_available() (leer: 1 ms schlafen, b""); write(data);
                              # take_tx() -> bytes; fail: Exception | None (read_available wirft sie); thread-sicher
  ```
- Threads (S4-a): Der Thread `pi-link` besitzt das Lesen. `request()`, `reply()` und `poll()` teilen sich **ein** `threading.Lock` für Zustand und Schreiben; gelesen wird ausserhalb der Sperre. Anfragen des ESP gehen über `incoming` an die Anwendung, Antworten auf eigene Anfragen über das `Future`.
- Log `link`: verworfene Zeile ohne `$` (Debug-Log des ESP) als INFO `ESP| <Text>` (Bytes mit `errors="replace"`), andere verworfene Zeilen als WARNING `verworfen (<Code>): <Zeile>`, jede gesendete und empfangene Nachricht als DEBUG `-> …` / `<- …`.

- [ ] **Step 1: Tests schreiben**

`FakeClock` beginnt bei 0.0; ohne Thread ruft der Test `poll()` selbst.

```python
class PiLinkTest(unittest.TestCase):
    def test_request_writes_one_frame(self)        # request("READY") → take_tx() == b"$00:READY*71\n"
    def test_request_repeats_every_250ms_until_answer(self)   # Fehler 2
        # request, take_tx(); Uhr 0.249: poll → tx leer; 0.25: poll → b"$00:READY*71\n"; feed b"$00:OK*3E\n", poll →
        # future.done(), result() == Message(0, "OK"); Uhr 0.75: poll → tx leer
    def test_request_expires_after_3s_with_12_frames(self)
        # poll alle 0.25 s bis 2.75 → 12 Rahmen; Uhr 3.0: poll → future.result() is None
    def test_numbers_count_per_request_not_per_repeat(self)   # zweite Anfrage nach OK → b"$01:READY*70\n"
    def test_second_request_while_open_raises_link_busy(self)
    def test_unencodable_request_raises_and_keeps_number(self)
        # request("GET", "QUOTE|\u00c4") → EncodeError; danach request("READY") → b"$00:READY*71\n"
    def test_late_answer_for_previous_number_is_ignored(self)
        # #00 beantwortet; request #01 offen; feed b"$00:OK*3E\n", poll → zweites Future nicht done
    def test_ping_is_answered_by_the_link(self)    # feed b"$03:PING*29\n" → tx b"$03:PONG*2F\n", incoming leer
    def test_button_goes_to_incoming_and_reply_is_sent(self)
        # feed b"$09:BUTTON|1*68\n" → incoming.get_nowait() == Message(9, "BUTTON", "1");
        # reply(msg, "OK") is True → tx b"$09:OK*37\n"
    def test_duplicate_gets_previous_answer_again(self)   # dieselbe Zeile nochmals → tx b"$09:OK*37\n", incoming leer
    def test_repeated_get_quote_before_reply_is_delivered_once(self)
        # 4 × feed b"$11:GET|QUOTE|DER WEG IST DAS ZIEL.*1C\n" mit poll → incoming.qsize() == 1, tx leer;
        # reply(msg, "QUOTE", "WAS BLEIBT IST DIE FRAGE.") → tx b"$11:QUOTE|WAS BLEIBT IST DIE FRAGE.*32\n"
    def test_second_reply_is_refused(self)         # zweites reply(msg, "OK") is False, nichts geschrieben
    def test_unknown_command_is_answered_with_error_unknown(self)
        # feed b"$05:READY*74\n" → tx b"$05:ERROR|UNKNOWN*53\n", incoming leer
    def test_bad_line_is_counted_logged_and_not_answered(self)
        # assertLogs("link", "WARNING"); feed b"$00:PING*2B\n" → discarded["BAD_CHECKSUM"] == 1, tx leer
    def test_esp_debug_line_is_logged(self)
        # assertLogs("link", "INFO"); feed b"[WALL] aus\r\n" → Ausgabe enthaelt "ESP| [WALL] aus",
        # discarded["NO_START"] == 1
    def test_too_long_line_is_dropped_and_next_line_is_read(self)
        # feed b"A" * 300 + b"\n$03:PING*29\n" → discarded["TOO_LONG"] == 1, tx b"$03:PONG*2F\n"
    def test_partial_line_waits_for_newline(self)  # b"$03:PI" → tx leer; b"NG*29\n" → PONG
    def test_garbage_bytes_do_not_raise(self)      # feed b"\xff\xfe\x00\n$03:PING*29\n" → PONG (Fehler 1)

class PiLinkThreadTest(unittest.TestCase):         # echte Uhr, hoechstens 1 s warten
    def test_thread_round_trip(self)
        # start(); feed PING → b"$03:PONG*2F\n" erscheint in tx; fut = request("READY");
        # feed b"$00:OK*3E\n" → fut.result(timeout=1) == Message(0, "OK"); stop() → alive is False
    def test_port_error_ends_thread_and_open_request(self)
        # assertLogs("link", "ERROR"); start(); fut = request("READY"); port.fail = OSError("Port weg")
        # → fut.result(timeout=1) is None; alive wird False

# test_serial_port.py
class SerialPortTest(unittest.TestCase):
    def test_loop_port_round_trip_through_link(self)
        # port = open_esp_port("loop://", select_gpio=False); PiLink(port).start();
        # request("PING").result(timeout=2) == Message(0, "PONG")
        # (die Schleife liefert das eigene PING zurueck, der Link beantwortet es selbst)
```

- [ ] **Step 2: Tests laufen lassen, sie müssen scheitern**

Run: `cd rpi && $PY -m unittest discover -s app -t . -v`
Expected: FAIL mit `ModuleNotFoundError: No module named 'app.link.pi_link'`.

- [ ] **Step 3: `fakes.py`, `pi_link.py` und `serial_port.py` umsetzen**

Ablauf von `poll()` und die Regeln für Antwort, Doppeltes und Unbekanntes wie Task 7 Step 3, mit drei Unterschieden: kein `\n` vor der Nachricht; bekannte Anfragen sind die mit Rolle `esp_request`; `PING` wird sofort mit `PONG` beantwortet statt in `incoming` gelegt. Wirft `poll()` im Thread, wird der Fehler mit `log.exception` gemeldet, ein offenes `Future` mit `None` beendet und der Thread verlassen.

- [ ] **Step 4: Tests bestehen**

Run: `cd rpi && $PY -m unittest discover -s app -t . -v`
Expected: `OK`.

- [ ] **Step 5: Commit** – „PiLink auf dem Pi mit eigenem Thread und Port fuer ttyAMA0“

---

### Task 9: Firmware anbinden – `UartPort` und Verbindungstest auf BT3

Baut auf dem Stand nach der Aufräumrunde auf: `esp/lib/communication/` ist leer, `Application` hat keine Mitglieder `_uart`, `_storage`, `_pi`, `_wifi` mehr, Schalter stehen in `Features`, `displayState` ist `DisplayState`.

**Files:**
- Create: `esp/lib/communication/UartPort.h`, `esp/lib/communication/UartPort.cpp`
- Create: `esp/lib/app/LinkTest.h`, `esp/lib/app/LinkTest.cpp`
- Modify: `esp/lib/config/features.h`, `esp/lib/app/application.h`, `esp/lib/app/application.cpp`
- Modify: `esp/README.md`, `esp/test/README`

**Interfaces:**
- Consumes: `ISerialPort`, `PiLink`, `LinkEvent`, `LinkCodec::errorName` (Task 3, 7).
- Produces:
  ```cpp
  // UartPort.h
  class UartPort : public ISerialPort
  {
  public:
      explicit UartPort(HardwareSerial& serial);
      int read() override;                              // serial.read(), -1 wenn leer
      void write(const std::string& bytes) override;    // serial.write(data, size), ohne flush
  };

  // LinkTest.h – BT3 ohne Sitzung, bis Teil 2 (Annahme 13)
  void runLinkTest(PiLink& link, unsigned long durationMs);

  // features.h
  constexpr unsigned long LINK_BAUD = 74880;   // E2-a, wie das Boot-ROM; Z12: sonst 115200 hier und in rpi/app/link/serial_port.py
  ```

- [ ] **Step 1: `UartPort` und `LinkTest` umsetzen**

`runLinkTest`: `send("PING", "", millis())`; dann `poll(millis())` mit `yield()` dazwischen, bis `durationMs` vergangen **und** keine eigene Anfrage mehr offen ist (das `Expired` kommt genau bei 3000 ms). Ereignisse loggen und beantworten:
- Start: `[LINK] Verbindungstest: PING #%02X`
- `Response`: `[LINK] PING -> %s nach %lu ms`
- `Expired`: `[LINK] keine Antwort auf PING nach %lu ms`
- `Request`: `reply("OK")`, Log `[LINK] Anfrage #%02X %s -> OK`
- am Ende, wenn `discarded() > 0`: `[LINK] %lu Zeilen verworfen, zuletzt %s` (mit `errorName(lastError())`)

- [ ] **Step 2: Anwendung umstellen**

- `features.h`: `LINK_BAUD` wie oben.
- `application.h`: `#include "UartPort.h"`, `#include "PiLink.h"`; Mitglieder `UartPort _port; PiLink _link;` (in dieser Reihenfolge) und `bool _linkTestRequested;`.
- `run()`: vor dem Start der Konsole `Serial.setRxBufferSize(1024);` (eine Zeile hat bis 257 Bytes, Review Focus 4), dann `DebugSerial.begin(Features::LINK_BAUD);` statt der Zahl.
- `_inputs.setTrigger(InputEvent::BT3, InputTrigger::ANY_EDGE);` – BT3 hat ein Flipflop wie BT1/BT2; den Kommentar darüber nachziehen.
- `handleInput`, Fall BT3: `DebugSerial.println("Verbindungstest zum Pi");` und `_linkTestRequested = true;`.
- Nach dem ersten `PersistentState::save(_state);` (Tastenstand gesichert, ein Reset im Test wiederholt ihn nicht): `if (_linkTestRequested) runLinkTest(_link, 3000);`.

- [ ] **Step 3: Doku nachziehen**

- `esp/README.md`: Tasten-Tabelle BT3 = „Verbindungstest zum Pi (bis Teil 2): `PING` senden, 3 s lang Anfragen des Pi beantworten, Ergebnis im Log“. Ordnerliste: `lib/core/` nennt Codec, PiLink, PiPower, Umbruch und Schrift; `lib/communication/` = „`UartPort`: `Serial` für die Verbindung zum Pi“. Kurzer Abschnitt „Verbindung zum Pi“: Format, 74 880 Baud auf derselben Leitung wie das Log, gemeinsame Testfälle in `tests/`, Verweis auf Spezifikation Abschnitt 6.
- `esp/test/README`: Suiten `test_link_codec`, `test_text_layout`, `test_pi_power`, `test_pi_link`; Hilfen `VectorFile`, `RecordingPin`, `MemorySerial`.

- [ ] **Step 4: Prüfen**

Run: `cd esp && pio run`
Expected: SUCCESS ohne neue Warnungen.
Run: `cd esp && pio test -e native`
Expected: alle Suiten PASSED.

- [ ] **Step 5: Commit** – „ESP: Verbindung zum Pi ueber PiLink, BT3 als Verbindungstest“

---

### Task 10: Pi – Prüfwerkzeug und Doku

**Files:**
- Create: `rpi/app/link/probe.py`
- Test: `rpi/app/link/tests/test_probe.py`
- Modify: `rpi/README.md`, `README.md`

**Interfaces:**
- Consumes: `PiLink`, `open_esp_port`, `ESP_DEVICE`, `ESP_BAUD`, `Message` (Task 4, 8).
- Produces:
  ```python
  # app/link/probe.py – Aufruf auf dem Pi: cd rpi && python -m app.link.probe
  def answer_for(request: Message) -> tuple[str, str]
      # BUTTON -> ("OK", ""); SHUTDOWN -> ("BUSY", "") (das Werkzeug faehrt den Pi nie herunter);
      # alles andere -> ("ERROR", "PROBE")
  def main(argv: list[str] | None = None) -> int
      # --port (ESP_DEVICE), --baud (ESP_BAUD), --seconds (0 = bis Ctrl+C), --no-gpio
  ```
- Ablauf von `main`: Log `link` auf DEBUG mit Uhrzeit nach stdout; Port öffnen, `PiLink` starten; `READY` senden, bis eine Antwort kommt (nach Ablauf neu senden), dann `READY -> <Befehl> (#NN)` ausgeben, bei Daten `READY -> <Befehl>|<Daten> (#NN)`; dabei `incoming` mit 0,1 s Wartezeit leeren und jede Anfrage mit `answer_for` beantworten und ausgeben; am Ende `verworfen: <dict(discarded)>` ausgeben, Link stoppen, Port schliessen, `0` zurückgeben.

- [ ] **Step 1: Tests schreiben**

```python
class ProbeTest(unittest.TestCase):
    def test_button_is_ok(self)            # answer_for(Message(9, "BUTTON", "1")) == ("OK", "")
    def test_shutdown_is_busy(self)        # answer_for(Message(10, "SHUTDOWN")) == ("BUSY", "")
    def test_get_is_error_probe(self)      # answer_for(Message(11, "GET", "QUOTE|")) == ("ERROR", "PROBE")
    def test_main_runs_on_loop_port(self)  # main(["--port", "loop://", "--no-gpio", "--seconds", "0.5"]) == 0
```

- [ ] **Step 2: Tests laufen lassen, sie müssen scheitern**

Run: `cd rpi && $PY -m unittest discover -s app -t . -v`
Expected: FAIL mit `ModuleNotFoundError: No module named 'app.link.probe'`.

- [ ] **Step 3: `probe.py` umsetzen**

- [ ] **Step 4: Doku nachziehen**

- `rpi/README.md`: Treiber-Tabelle `uart/` = „UART zum Radar LD2410S und Umschaltung per GPIO23 (HIGH = Radar, LOW = ESP); die Verbindung zum ESP liegt in `app/link/`“. Neuer Abschnitt „Verbindung zum ESP (`app/link`)“: Codec, PiLink mit eigenem Thread, `/dev/ttyAMA0` mit 74 880 Baud, GPIO23 LOW; Prüfwerkzeug `python -m app.link.probe`; Hinweis, dass die Radar-Anwendung (Taste 4 in `main.py`) dieselbe UART öffnet und nicht gleichzeitig laufen darf. Den Satz „wird in Teil 1 der Umsetzung ersetzt“ entfernen.
- `README.md`: in der Repository-Struktur `tests/    gemeinsame Testfälle für ESP und Pi (Verbindung, Anzeige)`.

- [ ] **Step 5: Prüfen**

Run: `cd rpi && $PY -m unittest discover -s app -t . -v` → `OK`.
Run: `cd esp && pio test -e native` → alle Suiten PASSED.

- [ ] **Step 6: Commit** – „Pi: Pruefwerkzeug fuer die Verbindung, Doku“

---

### Task 11: Abnahme am Gerät (erst nach Teil 0)

**Zurückgestellt**, bis Teil 0 erledigt ist: Pi mit SSH, `dtparam=uart0=on`, I²C an, `/dev/ttyAMA0` vorhanden und **ohne** Anmeldekonsole darauf, venv aus `rpi/requirements.txt`, Repo auf dem Pi auf dem Stand dieses Zweigs. Firmware aus Task 9 mit dem Flasher aufspielen, danach den **Flasher abziehen** – solange er steckt, gibt es keine Verbindung (F2). Das Log des ESP liest man dann über den Pi. Für Schritte am I²C-Bus muss der ESP schlafen (Wand dunkel), dann hat der Pi den Bus (F7).

- [ ] **Step 1: Pi-Code auf dem Pi** – `cd rpi && python -m unittest discover -s app -t . -v` → `OK`. `python -m app.main` → das Menü erscheint im Terminal und auf der Anzeige; Ctrl+C.
- [ ] **Step 2: Schrift, die '7'** – `cd rpi && python -c "from app.driver.display.display import Display; Display().set_text('0123456789 1 7')"`. Erwartet: die 7 mit oberem Balken und rechter Seite, die 1 nur mit rechter Seite. Stimmt es nicht: den Wert in `ascii_map.py`, `Glyphs.cpp` und `tests/display_vectors.json` anpassen und erneut prüfen.
- [ ] **Step 3: Radar-Graph** – `cd rpi && python -m tests.ld2410s.test --seconds 10`. Erwartet: In der obersten Modulreihe läuft der Graph von rechts nach links.
- [ ] **Step 4: 74 880 Baud am Pi 5** – BT2 (Pi ein), `cd rpi && python -m app.link.probe`. BT1 drücken. Erwartet: lesbare Zeilen `ESP| === REFLECTION WALL (Wakeup #…) ===` und folgende. Unlesbar oder Müll: Z12 – `Features::LINK_BAUD`, `ESP_BAUD` und `monitor_speed` auf 115 200, neu flashen, wiederholen. In einer zweiten SSH-Sitzung `pinctrl get 23` → Ausgang, LOW.
- [ ] **Step 5: Beide Richtungen** – BT3. Erwartet im Prüfwerkzeug: `<- $NN:PING*hh`, `-> $NN:PONG*hh`, `ESP| [LINK] PING -> PONG nach … ms`, `READY -> OK (#NN)` und `ESP| [LINK] Anfrage #NN READY -> OK`.
- [ ] **Step 6: Zuverlässigkeit** – 20 × BT3 im Abstand von einigen Sekunden, zwischendurch BT1 (Anzeige schreiben), dann Ctrl+C. Erwartet: 20 × `PONG`; in `verworfen:` nur `NO_START` (Debug-Zeilen), kein `BAD_CHECKSUM`, `BAD_FORMAT`, `BAD_CHAR` oder `TOO_LONG`; keine Zeile `[LINK] … verworfen` vom ESP.
- [ ] **Step 7: Pi antwortet nicht** – Prüfwerkzeug beenden (es gibt GPIO23 dabei frei), `pinctrl set 23 op dl`, dann `python -m serial.tools.miniterm /dev/ttyAMA0 74880`, BT3. Erwartet: zwölfmal `$NN:PING*hh` im Abstand von etwa 250 ms, dann `[LINK] keine Antwort auf PING nach 3000 ms`.
- [ ] **Step 8: Reset mitten im Test** – Prüfwerkzeug wieder starten, BT3 und innerhalb von 3 s BT1. Erwartet: Der ESP startet neu (F4) und zeigt das Zitat; der nächste BT3 bekommt wieder `PONG`.
- [ ] **Step 9: Pi-Speisung** – BT2 zweimal mit Pause: Pi fährt hoch bzw. verliert die Speisung wie vor Task 6.
- [ ] **Step 10: Abschluss** – Ergebnis von Step 4 in Spezifikation Abschnitt 15 eintragen (Zeile „74 880 Baud am Pi 5“ schliessen bzw. auf 115 200 umstellen), mit `pip freeze` die Versionen in `rpi/requirements.txt` eintragen, den Stand oben in diesem Plan nachführen, committen – „Teil 1 am Geraet abgenommen“.

---

## Nicht in diesem Plan

- Sitzung des ESP (Abschnitt 7): `PING` alle 10 s, drei Aussetzer, `READY`/`DONE`/`SHUTDOWN`/`BUSY` als Zustände, Speisung nach gespeichertem Zustand, Dienst mit systemd, `txSeq`/`rxSeq` und `piPowered` im RTC-Speicher – Teil 2.
- Radar-Debug mit `MODE`, Baudwechsel auf 115 200 und GPIO23 HIGH (6.4) – Teil 2.
- `GET|QUOTE` mit KI, Thema und Prüfung des Zitats (nutzt `wrap`/`displayable` aus Task 5) – Teil 3b.
- `BUTTON|n` an die Pi-Anwendungen – Teil 2 und 4.
- Aus der Durchsicht, nicht freigegeben: Adressliste und vier Zeilen im Pi-Treiber, eine Bus-Sitzung für alle I²C-Geräte, doppelte CRC, CI unter Linux, `CLAUDE.md`, Tabelle der Logmeldungen.

## Bekannte Mängel, die dieser Plan nicht behebt

- **Radar-Modus (Taste 4 in `main.py`) läuft heute nicht:** `Radar` zeichnet mit `driver/display/animations/stickman.py`, das `display.WIDTH`, `set_segments` und `refresh` braucht; die `Display`-Klasse hat keines davon. Die Radar-Einrichtung (eigener Entwurf, §11) verlangt, dass `Radar.py` weiter läuft – das muss sie erst herstellen.
- `VoiceAssistant` ignoriert die übergebene Anzeige und baut eine eigene.
- `rpi/tests/lichtsensor/test.py` importiert `bh1750`, die Datei heisst `BH1750.py` (scheitert unter Linux).

## Lücken und Widersprüche in der Spezifikation (für Teil 1)

- **Fehler 1–5** (und Z13: „Fehler 1–3“) sind nirgends aufgeschrieben; dieser Plan benennt sie aus dem alten Code.
- **Antwort oder Anfrage:** Das Format trägt kein Merkmal, und die Antwort hat dieselbe Nummer wie die Anfrage. Annahme 1 entscheidet am Befehl.
- **„Letzte Antwort noch einmal“** ist nicht festgelegt, solange die Antwort noch nicht existiert (`GET|QUOTE` wird bis 120 s alle 250 ms wiederholt, bis zu 480 Mal) oder nach einem ESP-Reset (Abschnitt 11 sichert `rxSeq`, aber keine Antwort). Annahme 7.
- **`READY`:** Abschnitt 12 gibt 3 s Frist, Tabelle 6.2 sagt „weiter senden, bis `OK` kommt“. Der Plan meldet den Ablauf; das Neusenden entscheidet Teil 2.
- **`PING` während `GET|QUOTE`:** Pro Richtung ist höchstens eine Anfrage offen, also kann der ESP bis 120 s lang kein `PING` senden – gegen E3 (alle 10 s). Teil 2 muss das klären.
- **„`DATEN` – beliebiger Text“** passt nicht zur Anzeige, die nur ASCII zeigt. Annahme 3.
- **Python-Tests:** Abschnitt 14 verlangt `unittest`; der Auftrag zu diesem Plan nannte pytest. Der Plan folgt der Spezifikation.
- **Zeichen für das Zitat:** Abschnitt 9, Schritt 4 lässt nur `A–Z` zu, die Beispielzitate sind gemischt geschrieben und die Anzeige zeigt Kleinbuchstaben als Grossbuchstaben. Annahme 25 lässt `a–z` als darstellbar gelten.
