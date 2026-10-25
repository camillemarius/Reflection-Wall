# Teil 4a: Menü und Pi-Anwendungen (ohne Teil 2) – Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Alles aus Teil 4, was ohne Teil 2 geht und sich auf dem PC prüfen lässt: Wandanzeige für 12 Module, Menü, Anwendungsrahmen, die fünf Anwendungen ohne ENTER, Webseite für die Themen, automatisches Aus.

**Architecture:** Ein neues Paket `app.ui` trägt Menü, Tasten, Anwendungsrahmen und Bildschirmfolge. `app.driver.display.wall_display` ist die einzige Stelle, die die 12 Module schreibt. Die Anwendungen bekommen einen `AppContext` statt `input()` und einer eigenen Anzeige. Tasten kommen über eine Quelle (`ButtonSource`): auf dem PC von der Tastatur, an der Wand später von PiLink oder vom Expander.

**Tech Stack:** Python 3 (Paket `app` unter `rpi/`, `unittest`), smbus2/lgpio nur verzögert importiert, pyserial; ESP: PlatformIO, C++14, native Unity-Tests.

**Spec:** `docs/superpowers/specs/2026-10-23-menue-und-anwendungen-design.md` (Teil 4, vom Owner angenommen 2026-10-25). Er baut auf `docs/superpowers/specs/2026-10-19-esp-pi-steuerung-design.md` auf.

## Global Constraints

- Branch `feature/menue-und-anwendungen`. Nicht pushen, nichts aufs Gerät laden.
- **Commits ohne Zuschreibung:** keine Zeile `Co-Authored-By`, kein „Generated with“. Betreff auf Deutsch.
- Python-Tests: `cd rpi && "C:\Users\cross-INGCamilleChat\.venvs\reflection-wall-rpi\Scripts\python.exe" -m unittest discover -s app -t .`
- ESP-Tests: `cd esp && pio test -e native` (MinGW-GCC 6.3, nur C++14; Pfade unter 260 Zeichen, sonst in `%TEMP%\fpb` bauen).
- Nur absolute Importe `app.…`. Kein Modul darf beim Import `smbus2` oder `lgpio` laden oder eine Datenbank, das Netz oder Hardware öffnen (`rpi/app/tests/test_imports.py` prüft das).
- Keine Anwendung ruft `input()` auf. Keine Anwendung öffnet die UART, GPIO23 oder I²C selbst.
- Anzeige: 4 Zeilen × 24 Zeichen. Texte gehen durch dieselbe Umbruchregel wie beim ESP (`app.driver.display.text_layout.wrap`). Grossbuchstaben, Umlaute umschrieben (`Ä→AE`, `Ö→OE`, `Ü→UE`, `ß→SS`).
- Adressen der Module, Zeile für Zeile: `0x70, 0x71, 0x72, 0x73, 0x74, 0x75, 0x76, 0x77, 0x7F, 0x79, 0x7B, 0x7D`.
- Expander PCF8575 an `0x20`, 16 Bit, Bitnummern der Tasten: BT1=3, BT2=4, BT3=5, BT4=8, BT5=9, BT6=10 (aus `esp/lib/gpioExpander/InputManager.cpp`).
- Menüpunkte in dieser Reihenfolge (D6, D15): `CHAT`, `QUIZ`, `REFLECTION`, `RADAR`, `STRICHMAENNCHEN`, `EINSTELLUNGEN`. Einstellungen: `THEMA AENDERN`, `RADAR EINRICHTEN`.
- Zeiger `>` hat das Muster `0x0840` (Spec §5.3).
- Fristen: Webseite 15 min ohne Speichern (D11); automatisches Aus 15 min ohne Aktivität, Schalter `AUTO_AUS_MINUTEN` (0 = aus, Standard 0) (D2, F6); höchstens 3 KI-Anfragen pro Text (D17).
- Themendateien: `rpi/app/config/thema.txt`, `rpi/app/config/thema_hand.txt`; Standardthema „Was ist der Sinn des Lebens“; ein Thema ist eine Zeile mit höchstens 120 Zeichen.

## Was dieser Plan anders macht als der Entwurf (Rulings)

- **R1:** Der Punkt auf eigener Stelle (V4) kommt nur auf den Pi. Der ESP zeigt keine Adressen; Spec §9.4 nennt ihn trotzdem. Kosten, falls falsch: eine Zeile in `Glyphs.cpp` und ein Testfall.
- **R2:** `RADAR EINRICHTEN` zeigt in 4a nur `KOMMT SPAETER / BT4 ZURUECK`. Der Entwurf der Radar-Einrichtung ist noch nicht freigegeben, und das Datenblatt fehlt. Die Einrichtung bekommt einen eigenen Plan.
- **R3:** BT4–BT6 als Pegelwechsel am ESP, `SESSION|…`, die Tasten je Zustand (Tabelle 5.2) und `PI STARTET` kommen in Teil 4b. Ohne Teil 2 bewirken sie nichts.
- **R4:** Der Pi-Dienst mit `READY`, `SESSION` und Herunterfahren gehört zu Teil 2 und 4b. 4a liefert die Funktion `run_wall(...)`, die der Dienst später aufruft, und einen PC-Modus `python -m app.main --pc`.
- **R5:** Regel B (Pause, wenn der ESP den Bus nimmt) liefert Teil 2. Wandanzeige und Expander bekommen dafür einen Haken `bus_guard` (Standard: nichts tun) und wiederholen eine Übertragung einmal bei `OSError`.

## Review Focus

1. **BT4 während einer blockierenden Arbeit** (KI, Umschrift, Sprachausgabe): Die Anwendung endet sofort; das spätere Ergebnis wird verworfen. Test in Task 5 (`test_run_blocking_stops_on_bt4`).
2. **Punkte im Text:** Ein `.` hängt am Zeichen davor und braucht keine Stelle. Eine Zeile ergibt nie mehr als 24 Stellen, auch mit vielen Punkten. Test in Task 2 (`test_dots_never_overflow`).
3. **Radar-Umschaltung bricht ab** (kein `OK`, Fehler im Radar): Danach ist immer zurückgeschaltet: GPIO23 LOW, 74 880 Baud, PiLink läuft, `MODE|NORMAL` gesendet. Test in Task 11 (`test_leave_runs_after_error`).
4. **Eingaben der Webseite:** leer, länger als 120 Zeichen, mit Zeilenumbruch, mit Umlauten. Gespeichert wird eine Zeile, gekürzt; die Datei wird atomar ersetzt. Test in Task 12 (`test_save_normalizes`).
5. **Tasten, die während `DENKE NACH` gedrückt werden:** BT5 und BT6 zählen nicht und kommen danach auch nicht nach; BT4 wirkt. Test in Task 5 (`test_presses_during_busy_are_dropped`).

---

### Task 1: Zeichen `>` in der gemeinsamen Schrift

**Files:**
- Modify: `esp/lib/core/src/Glyphs.cpp` (Fall `'>'`, und `'>'` in `displayable`)
- Modify: `rpi/app/driver/display/ascii_map.py` (`'>': 0x0840`)
- Modify: `tests/display_vectors.json` (ein Fall `glyph`)
- Test: `esp/test/test_text_layout/test_main.cpp`, `rpi/app/driver/display/tests/test_display_rules.py` (bestehend, lesen die Vektoren)

**Interfaces:**
- Produces: `Glyphs::segments('>') == 0x0840`, `Glyphs::displayable('>') == true`; `ASCII_16SEG['>'] == 0x0840`.

- [ ] **Step 1: Testfall in `tests/display_vectors.json` ergänzen** (eine Zeile, LF):
  `{"name": "glyph_pointer", "kind": "glyph", "char": ">", "segments": "0840", "displayable": 1}`
- [ ] **Step 2: Tests laufen lassen.** Erwartet: Python `test_font_matches_glyphs` und ESP `test_glyph_vectors` schlagen fehl (fehlendes Zeichen).
- [ ] **Step 3: `>` auf beiden Seiten eintragen** (Werte oben).
- [ ] **Step 4: Beide Testsuiten grün.**
- [ ] **Step 5: Commit** `Schrift: Zeichen > fuer den Menue-Zeiger`

### Task 2: Text zu Stellen, und Seiten für lange Texte

**Files:**
- Create: `rpi/app/driver/display/cells.py`
- Create: `rpi/app/ui/__init__.py`, `rpi/app/ui/pages.py`
- Test: `rpi/app/driver/display/tests/test_cells.py`, `rpi/app/ui/tests/__init__.py`, `rpi/app/ui/tests/test_pages.py`

**Interfaces:**
- Produces:
  - `cells.normalize(text: str) -> str` (Grossbuchstaben, Umlaute umschrieben, `\n`/`\r` → Leerzeichen)
  - `cells.line_to_cells(line: str, dots_own_cell: bool = False) -> list[int]` – genau 24 Muster. Ohne `dots_own_cell` setzt `.` das Bit `0x0004` am Zeichen davor (ein `.` am Zeilenanfang bleibt leer). Mit `dots_own_cell` ist `.` eine eigene Stelle mit `0x0004`. Unbekannte Zeichen → 0.
  - `cells.lines_to_cells(lines: Sequence[str], dots_own_cell=False) -> list[int]` – genau 96 Muster, fehlende Zeilen leer.
  - `pages.paginate(text: str) -> list[list[str]]` – D17: passt der Text (`wrap` meldet `fits`), eine Seite aus `wrap`. Sonst Seiten zu 4 Zeilen à 24 Zeichen, Umbruch an Wortgrenzen wie `wrap`; auf jeder Seite ausser der letzten hat Zeile 4 höchstens 23 Zeichen und an Stelle 24 ein `>`.

- [ ] **Step 1: Tests schreiben**
  ```python
  def test_dot_merges_into_previous(self):
      c = line_to_cells("ZIEL.")
      self.assertEqual(c[3], ASCII_16SEG["L"] | 0x0004); self.assertEqual(c[4], 0)
  def test_dot_own_cell(self):
      c = line_to_cells("WALL.LOCAL", dots_own_cell=True)
      self.assertEqual(c[4], 0x0004); self.assertEqual(c[5], ASCII_16SEG["L"])
  def test_dots_never_overflow(self):
      self.assertEqual(len(line_to_cells("A." * 30)), 24)
  def test_normalize(self):
      self.assertEqual(normalize("Grüße\nÄrger"), "GRUESSE AERGER")
  def test_short_text_one_page(self):
      self.assertEqual(paginate("HALLO WELT"), [wrap("HALLO WELT")[0]])
  def test_long_text_pages_with_pointer(self):
      p = paginate(" ".join(["WORT"] * 60))
      self.assertGreater(len(p), 1)
      for page in p[:-1]: self.assertEqual(page[3][23], ">")
      self.assertNotIn(">", "".join(p[-1]))
      for page in p: self.assertTrue(all(len(r) == 24 for r in page))
  ```
- [ ] **Step 2: laufen lassen, Erwartet: FAIL (Module fehlen).**
- [ ] **Step 3: `cells.py` und `pages.py` schreiben.** Glyphen aus `ascii_map.ASCII_16SEG`, Umbruch aus `text_layout.wrap`.
- [ ] **Step 4: Tests grün, ganze Suite grün.**
- [ ] **Step 5: Commit** `Pi: Text zu Segmentmustern und Seiten fuer lange Texte`

### Task 3: Wandanzeige für 12 Module (F5)

**Files:**
- Create: `rpi/app/driver/display/wall_display.py`
- Create: `rpi/app/driver/display/terminal_display.py`
- Test: `rpi/app/driver/display/tests/test_wall_display.py`

**Interfaces:**
- Consumes: `cells.lines_to_cells`, `cells.normalize`, `pages.paginate` (Task 2), `text_layout.wrap`.
- Produces:
  - `MODULE_ADDRESSES: tuple[int, ...]` (Global Constraints)
  - `class WallDisplay(bus=None, bus_guard=None)`: `bus` hat `write_i2c_block_data(addr, reg, data)` und `write_byte(addr, value)`; fehlt er, öffnet `start()` verzögert `smbus2.SMBus(1)`. `bus_guard` ist ein Kontextmanager um jede Übertragung (R5).
  - `start() -> None` (alle Module: Oszillator an, Anzeige an, Helligkeit 15, leeren)
  - `show_cells(masks: Sequence[int]) -> None` – 96 Muster; schreibt nur Module, deren 8 Stellen sich geändert haben; bei `OSError` einmal wiederholen, dann loggen.
  - `show_lines(lines: Sequence[str], dots_own_cell: bool = False) -> None`
  - `show_text(text: str) -> bool` – normalisieren, `wrap`, zeigen; gibt `fits` zurück.
  - `clear() -> None`
  - Zeichenfläche für das Strichmännchen des Radars: `WIDTH = 24`, `HEIGHT = 4`, `set_segments(x: int, y: int, mask: int)`, `refresh()` (schreibt die gepufferte Fläche mit `show_cells`).
  - `class TerminalDisplay` mit derselben Schnittstelle; `show_cells` druckt die 4 Zeilen als Text (Zeichen über die umgekehrte Glyphentabelle, unbekannte Muster als `#`). Für den PC-Modus.
  - Modulpuffer: Stelle `i` eines Moduls → Bytes `2i` (niedrig) und `2i+1` (hoch), Register `0x00`.

- [ ] **Step 1: Tests mit einem Fake-Bus schreiben** (zeichnet Aufrufe auf)
  ```python
  def test_addresses_row_major(self):
      self.assertEqual(MODULE_ADDRESSES, (0x70,0x71,0x72,0x73,0x74,0x75,0x76,0x77,0x7F,0x79,0x7B,0x7D))
  def test_only_changed_modules_written(self):
      d = WallDisplay(bus=fake); d.show_cells([0]*96); fake.clear()
      m = [0]*96; m[95] = 0x0840; d.show_cells(m)
      self.assertEqual([c.addr for c in fake.block_writes], [0x7D])
  def test_cell_bytes(self):
      ... show_cells with m[0] = 0xA6A2 → block write to 0x70 with data[0] == 0xA2 and data[1] == 0xA6
  def test_retry_once_on_oserror(self): ...  # erster Schreibversuch wirft, zweiter klappt
  def test_set_segments_refresh(self):
      d.set_segments(2, 3, 0x1111); d.refresh(); → Stelle 3*24+2 hat 0x1111
  ```
- [ ] **Step 2: FAIL. Step 3: implementieren. Step 4: grün, Suite grün** (auch `test_imports`: `smbus2` wird erst in `start()` geladen).
- [ ] **Step 5: Commit** `Pi: Wandanzeige fuer alle 12 Module mit den Adressen des ESP`

### Task 4: Tasten-Quellen

**Files:**
- Create: `rpi/app/ui/buttons.py`
- Test: `rpi/app/ui/tests/test_buttons.py`

**Interfaces:**
- Produces:
  - `BT1 … BT6 = 1 … 6` (Konstanten)
  - `class ButtonSource(Protocol)`: `get(timeout: float | None) -> int | None`; `drain() -> None` (verwirft Wartendes)
  - `class QueueButtons`: `put(n: int)`, `get`, `drain` (thread-sicher; Quelle für PiLink und Tastatur)
  - `class ExpanderButtons(bus=None, bus_guard=None, clock=time.monotonic, poll_s=0.05)`: liest PCF8575 (`0x20`, 2 Bytes, Bit = Global Constraints). `start()` liest den Stand als Bezug. Jeder Pegelwechsel eines Taster-Bits gegenüber dem letzten Stand ist ein Druck; mehrere Wechsel in einem Lesen kommen in der Reihenfolge BT1…BT6. Lesefehler: einmal wiederholen, dann `ExpanderError`.
  - `class KeyboardButtons` (PC): liest Ziffern 1–6 aus einer Zeile von `stdin` in einem Thread und füttert eine `QueueButtons`.

- [ ] **Step 1: Tests**
  ```python
  def test_level_change_is_press(self):
      bus = FakeExpander([0x0000, 0x0000 | (1 << 9)])  # BT5 kippt
      b = ExpanderButtons(bus=bus); b.start(); self.assertEqual(b.get(0.2), 5)
  def test_toggle_back_is_second_press(self): ...  # Bit wieder 0 → noch einmal 5
  def test_two_changes_in_order(self): ...  # BT4 und BT6 zugleich → 4, dann 6
  def test_queue_drain(self): q.put(5); q.drain(); self.assertIsNone(q.get(0))
  ```
- [ ] **Step 2: FAIL. Step 3: implementieren. Step 4: grün.**
- [ ] **Step 5: Commit** `Pi: Tasten aus PiLink, vom Expander und von der Tastatur`

### Task 5: Menü, Anwendungsrahmen und Bildschirmfolge

**Files:**
- Create: `rpi/app/ui/menu.py`, `rpi/app/ui/app_host.py`, `rpi/app/ui/shell.py`
- Test: `rpi/app/ui/tests/test_menu.py`, `test_app_host.py`, `test_shell.py`

**Interfaces:**
- Consumes: `WallDisplay`/`TerminalDisplay` (Task 3), `ButtonSource` (Task 4), `paginate` (Task 2).
- Produces:
  - `class Menu(items: Sequence[str])`: `down()`, `selected -> int`, `select(index)`, `lines() -> list[str]` (4 Zeilen, `"> NAME"` bzw. `"  NAME"`; rollt mit; nach dem letzten Punkt wieder oben)
  - `class StopApp(Exception)` – Grund `"back"` (BT4), `"shutdown"` oder `"idle"`
  - `class AppContext(display, buttons, activity, stop_event, radar=None, config_dir=…)`:
    - `wait_button(timeout: float | None = None) -> int | None`: BT4 → `StopApp("back")`; gesetztes `stop_event` → `StopApp(reason)`; sonst die Taste.
    - `run_blocking(fn, *args) -> Any`: führt `fn` in einem Thread aus, verwirft vorher und währenddessen gedrückte Tasten ausser BT4, meldet für die Dauer Aktivität (`activity.busy()`), wirft `StopApp` bei BT4 oder `stop_event`; das spätere Ergebnis wird verworfen.
    - `show_pages(text: str) -> None`: `paginate`, Seite zeigen, BT5 blättert; nach der letzten Seite zurück.
  - `class App(Protocol)`: `name: str`; `run(ctx: AppContext) -> None`
  - `run_app(app, ctx) -> str` – `"back"`, `"shutdown"`, `"idle"` oder `"error"`. Ein Fehler zeigt `FEHLER IN <NAME>` und wartet auf BT4 (Spec §9.3).
  - `class Shell(display, buttons, apps: Sequence[App], settings: Sequence[App], activity, stop_event)`: `run() -> str` – Menü, BT6/BT5, Anwendung, zurück aufs Menü mit dem Zeiger auf der Anwendung (V3); Einstellungen als Untermenü, BT4 zurück. Endet mit dem Grund aus `stop_event`.
  - `Shell.display_released: threading.Event` – wird gesetzt, sobald die Bildschirmfolge nach dem Stopp nichts mehr auf die Anzeige schreibt (F2).

- [ ] **Step 1: Tests**
  ```python
  def test_menu_scrolls_and_wraps(self):
      m = Menu(["A","B","C","D","E","F"])
      for _ in range(4): m.down()
      self.assertEqual(m.lines()[3], "> E"); self.assertEqual(m.lines()[0], "  B")
      m.down(); m.down(); self.assertEqual(m.lines()[0], "> A")
  def test_run_blocking_stops_on_bt4(self):
      ctx = …; slow = lambda: time.sleep(2) or "X"
      buttons.put(4); with self.assertRaises(StopApp): ctx.run_blocking(slow)   # unter 0,5 s
  def test_presses_during_busy_are_dropped(self):
      buttons.put(5); buttons.put(6); ctx.run_blocking(lambda: "ok"); self.assertIsNone(buttons.get(0))
  def test_error_screen(self): … App, die wirft → Anzeige zeigt "FEHLER IN TEST", BT4 → run_app gibt "error"
  def test_shell_returns_to_selected_app(self):
      Tasten: 6, 5 (startet QUIZ-Fake), 4 → Menü zeigt "> QUIZ"
  def test_settings_submenu_and_back(self): … 6×5, 5, 4 → Hauptmenü
  ```
- [ ] **Step 2: FAIL. Step 3: implementieren. Step 4: grün.**
- [ ] **Step 5: Commit** `Pi: Menue, Anwendungsrahmen und Bildschirmfolge`

### Task 6: Automatisches Aus (D2, F6)

**Files:**
- Create: `rpi/app/ui/activity.py`
- Test: `rpi/app/ui/tests/test_activity.py`

**Interfaces:**
- Produces:
  - `class Activity(clock=time.monotonic, idle_minutes: int = 0, person_present: Callable[[], bool] | None = None)`: `touch()`, `busy()` (Kontextmanager), `expired() -> bool` (immer `False`, wenn `idle_minutes == 0`).
  - `idle_minutes_from_env(env=os.environ) -> int` – liest `AUTO_AUS_MINUTEN`; fehlt oder ungültig → 0.
  - `class RadarPresence(gpio=22)`: `present() -> bool`, lgpio erst beim ersten Aufruf.
- [ ] **Step 1: Tests** (eingespeiste Uhr)
  ```python
  def test_off_by_default(self): a = Activity(clock=c); c.t = 10_000; self.assertFalse(a.expired())
  def test_expires_after_idle(self): a = Activity(clock=c, idle_minutes=15); c.t = 15*60+1; self.assertTrue(a.expired())
  def test_touch_resets(self): …
  def test_busy_counts_as_activity(self): … während busy() nie abgelaufen; danach zählt die Zeit ab Ende
  def test_person_present_counts(self): person_present=lambda: True → nie abgelaufen
  ```
- [ ] **Step 2: FAIL. Step 3: implementieren. Step 4: grün.**
- [ ] **Step 5: Commit** `Pi: automatisches Aus nach 15 min ohne Aktivitaet (Schalter, Standard aus)`

### Task 7: Tasten und Ausschalten über PiLink

**Files:**
- Create: `rpi/app/ui/link_dispatch.py`
- Test: `rpi/app/ui/tests/test_link_dispatch.py`

**Interfaces:**
- Consumes: `PiLink.incoming`, `PiLink.reply`, `PiLink.request` (Teil 1), `QueueButtons` (Task 4), `Activity` (Task 6).
- Produces: `class LinkDispatcher(link, buttons: QueueButtons, activity, stop_event, on_shutdown: Callable[[], None] = lambda: None)`:
  - `start()` / `stop()` (Thread liest `link.incoming`)
  - `BUTTON|n` → `reply OK`, `activity.touch()`, `buttons.put(n)` (n = 1…6; sonst `ERROR|BAD_BUTTON`)
  - `SHUTDOWN` → solange `radar_writing` gesetzt ist `BUSY`; sonst `stop_event` mit Grund `"shutdown"` setzen, auf `Shell.display_released` warten (höchstens 2 s), `OK` antworten, `on_shutdown()` aufrufen (F2). Der Dispatcher bekommt das Ereignis `display_released` im Konstruktor.
  - `radar_writing: threading.Event`
  - `send_done() -> bool` – `request("DONE")`; bei `LinkBusy` später erneut, bis `OK` oder Frist
  - Andere Anfragen des ESP (`GET`) bleiben unbeantwortet in einer eigenen Warteschlange `other` (Teil 3b).
- [ ] **Step 1: Tests mit den Fakes aus `rpi/app/link/tests/fakes.py`**
  ```python
  def test_button_forwarded_and_acked(self): …  # BUTTON|5 → reply OK, buttons.get() == 5
  def test_shutdown_stops_shell_then_ok(self): …  # stop_event gesetzt, Antwort OK, on_shutdown aufgerufen
  def test_shutdown_busy_while_radar_writing(self): …
  ```
- [ ] **Step 2: FAIL. Step 3: implementieren. Step 4: grün.**
- [ ] **Step 5: Commit** `Pi: Tasten und Ausschalten ueber die Verbindung`

### Task 8: Kurze Antworten und Chat (D17)

**Files:**
- Create: `rpi/app/ui/short_answer.py`
- Create: `rpi/app/applications/chat_app.py`
- Test: `rpi/app/ui/tests/test_short_answer.py`, `rpi/app/applications/tests/__init__.py`, `rpi/app/applications/tests/test_chat_app.py`

**Interfaces:**
- Consumes: `write_to_ai(messages, retries=4) -> str` (`app.driver.chatbot.groqAPI`), `fasterWhsiper` (`start_recording()`, `stop_recording() -> str`, `mic_available`), `SpeechAssistant.speak(text)` (blockierend), `AppContext` (Task 5).
- Produces:
  - `ask_short(ask: Callable[[], str], attempts: int = 3) -> str` – fragt, bis `wrap(normalize(antwort))` passt, höchstens `attempts` Mal; gibt die letzte Antwort zurück.
  - `SHORT_RULE = "Antworte in hoechstens 96 Zeichen. Nur Buchstaben, Ziffern, Leerzeichen und Punkt."` (wird jedem Auftrag als System-Nachricht vorangestellt)
  - `class ChatApp(recorder_factory, ask=write_to_ai, speaker=None)`: `name = "CHAT"`; Ablauf Spec §6: `BT5 UND SPRECHEN` → BT5 Aufnahme → BT5 Ende → `DENKE NACH` → Antwort (Seiten) + sprechen → wieder `BT5 UND SPRECHEN`. Ohne Mikrofon `KEIN MIKROFON`. Der Recorder entsteht erst beim ersten `run` (er lädt ein Modell).
  - Fehler der KI (Rückgabe beginnt mit `"Fehler"` oder Ausnahme) → `KI NICHT ERREICHBAR`; BT5 versucht es noch einmal.
- [ ] **Step 1: Tests mit Fakes für KI, Recorder, Lautsprecher**
  ```python
  def test_ask_short_retries_until_fit(self): Antworten ["X"*200, "KURZ"] → "KURZ", 2 Aufrufe
  def test_ask_short_gives_up_after_three(self): immer zu lang → 3 Aufrufe, letzte Antwort
  def test_chat_flow(self): Tasten 5,5 → Recorder start/stop, Anzeige zeigt die Antwort, speak aufgerufen
  def test_chat_without_mic(self): mic_available False → "KEIN MIKROFON"
  ```
- [ ] **Step 2: FAIL. Step 3: implementieren. Step 4: grün.**
- [ ] **Step 5: Commit** `Pi: Chat mit den Tasten der Wand und kurzen Antworten`

### Task 9: Quiz und Reflection von Hand (V7)

**Files:**
- Create: `rpi/app/topics.py`
- Create: `rpi/app/applications/quiz_app.py`, `rpi/app/applications/reflection_app.py`
- Modify: `rpi/app/applications/Quiz/AIQuizGenerator.py` (Auftrag um „jede Angabe höchstens 96 Zeichen“ ergänzen)
- Test: `rpi/app/tests/test_topics.py`, `rpi/app/applications/tests/test_quiz_app.py`, `test_reflection_app.py`

**Interfaces:**
- Produces:
  - `topics.DEFAULT_TOPIC = "Was ist der Sinn des Lebens"`, `topics.CONFIG_DIR` (= `rpi/app/config`)
  - `topics.read_daily(config_dir) -> str`, `topics.read_hand(config_dir) -> str` (fehlt oder leer → tägliches Thema → Standard)
  - `topics.clean(text: str) -> str` (eine Zeile, Leerraum zusammengefasst, höchstens 120 Zeichen)
  - `topics.save(config_dir, daily: str, hand: str) -> None` (beide über eine Hilfsdatei und `os.replace`)
  - `class QuizApp(generator_factory)`: `name = "QUIZ"`; `FRAGE WIRD ERZEUGT` → Frage → BT5 Hinweis 1 → BT5 Hinweis 2 → BT5 Lösung → BT5 neue Frage; längere Texte als Seiten. Die Datenbank des Quiz bleibt, wie sie ist.
  - `build_reflection_messages(topic: str, previous: str | None) -> list[dict]`
  - `class ReflectionApp(ask=write_to_ai, config_dir=CONFIG_DIR)`: `name = "REFLECTION"`; `REFLECTION / BT5 NEUER GEDANKE`; BT5 → `DENKE NACH` → Gedanke (`ask_short`); der nächste bekommt den vorherigen mit; beim Verlassen vergessen; keine Datenbank.
- [ ] **Step 1: Tests**
  ```python
  def test_hand_topic_falls_back(self): leere thema_hand.txt, thema.txt "Mut" → read_hand == "Mut"
  def test_clean(self): clean("a\nb" + "x"*200) → eine Zeile, len <= 120
  def test_reflection_chain_in_memory(self): zwei BT5 → zweiter Auftrag enthält den ersten Gedanken; nach Verlassen neue App-Runde ohne
  def test_reflection_never_touches_db(self): mysql-Funktionen gepatcht, dürfen nicht gerufen werden
  def test_quiz_steps(self): Tasten 5,5,5 → Anzeigen Hinweis 1, Hinweis 2, Lösung in dieser Reihenfolge
  ```
- [ ] **Step 2: FAIL. Step 3: implementieren. Step 4: grün.**
- [ ] **Step 5: Commit** `Pi: Quiz und Reflection mit den Tasten der Wand`

### Task 10: Strichmännchen

**Files:**
- Create: `rpi/app/applications/stickman_app.py`
- Delete: `rpi/app/applications/Animations/Stickman.py` (ersetzt)
- Test: `rpi/app/applications/tests/test_stickman_app.py`

**Interfaces:**
- Consumes: `WallDisplay.show_cells` (Task 3); die Bilder in `rpi/app/applications/Animations/videoframes/*.py` (`VIDEO_FRAMES`: Liste von `{(spalte, zeile): muster}`, `FRAME_TIME` in s; Spalte 0–23, Zeile 0–3).
- Produces: `load_frames(directory) -> list[tuple[list[int], float]]` (96 Muster, Dauer); `class StickmanApp(frames_dir=…)`, `name = "STRICHMAENNCHEN"`, Schleife bis BT4.
- [ ] **Step 1: Tests** – `load_frames` liest die 9 Dateien zu 9 Bildern; Zelle `(2,1)` des ersten Bildes landet an Stelle `1*24+2`; `run` zeigt Bilder nacheinander und endet bei BT4.
- [ ] **Step 2: FAIL. Step 3: implementieren** (Laden ohne `exec`: `ast.literal_eval` auf den Ausdruck nach `VIDEO_FRAMES =` und `FRAME_TIME =`). **Step 4: grün.**
- [ ] **Step 5: Commit** `Pi: Strichmaennchen als Anwendung im Menue`

### Task 11: Radar-Umschaltung (F4) und Anwendung Radar

**Files:**
- Modify: `rpi/app/link/pi_link.py` (`pause()`, `resume()`)
- Modify: `rpi/app/link/serial_port.py` (`set_baud(baud)`, `select_radar(on: bool)`, Eigenschaft `serial`)
- Create: `rpi/app/link/radar_switch.py`
- Create: `rpi/app/applications/radar_app.py`
- Delete: `rpi/app/applications/Animations/Radar.py` (ersetzt)
- Test: `rpi/app/link/tests/test_radar_switch.py`, `rpi/app/applications/tests/test_radar_app.py`, Ergänzung in `rpi/app/link/tests/test_pi_link.py`

**Interfaces:**
- Consumes: `PiLink.request` (Teil 1), `UARTHLK(uart)` mit `update()`, `present`, `distance` (cm), `data.timestamp` (`app.driver.uart.uart_hlk`); `Stickman(display, min_distance=0.7, max_distance=2.0)` mit `show(m)`/`clear()` (`app.driver.display.animations.stickman`); `ExpanderButtons` (Task 4).
- Produces:
  - `PiLink.pause()` – der Lese-Thread fasst den Port nicht mehr an (keine offene eigene Anfrage erlaubt, sonst `LinkBusy`); `PiLink.resume()` – verwirft, was im Puffer liegt, und liest weiter.
  - `class RadarSwitch(link, port)`: `enter() -> RadarUart` (`MODE|RADAR`, `OK` abwarten, sonst `RadarSwitchError`; `pause()`; GPIO23 HIGH; 115 200 Baud) und `leave()` (74 880 Baud; GPIO23 LOW; `resume()`; `MODE|NORMAL` alle 0,25 s, bis `OK` kommt, höchstens 30 s). Als Kontextmanager: `leave()` läuft immer, auch nach einem Fehler.
  - `class RadarUart(serial)`: was `UARTDevice`/`UARTHLK` brauchen: `select(device)` (tut nichts), `write`, `read(size)`, `readline()`, `available`, `read_all()`.
  - `class RadarApp(switch_factory, sensor_factory=UARTHLK, buttons_factory=ExpanderButtons)`: `name = "RADAR"`; Strichmännchen folgt der Entfernung; BT4 und BT2 → zurückschalten und zurück ins Menü; nach BT2 schickt der ESP danach selbst `SHUTDOWN` (er hat sich den Druck gemerkt, §7), und der Dispatcher beendet alles; ohne Daten 5 s → `RADAR ANTWORTET NICHT`, BT4.
- [ ] **Step 1: Tests**
  ```python
  def test_enter_order(self): Aufzeichnung: request MODE|RADAR → pause → GPIO23 HIGH → baud 115200
  def test_enter_without_ok_raises_and_stays_esp(self): …
  def test_leave_runs_after_error(self):
      with RadarSwitch(link, port) as uart: raise RuntimeError
      → baud 74880, GPIO23 LOW, resume, MODE|NORMAL gesendet
  def test_pause_stops_port_access(self): … poll liest nach pause() nichts mehr
  def test_radar_app_bt4(self): Fake-Sensor, Fake-Tasten [4] → leave aufgerufen, Rückgabe "back"
  ```
- [ ] **Step 2: FAIL. Step 3: implementieren. Step 4: grün.**
- [ ] **Step 5: Commit** `Pi: gemeinsame Radar-Umschaltung, Radar als Anwendung im Menue`

### Task 12: Themen-Webseite und Einstellungen

**Files:**
- Create: `rpi/app/web/__init__.py`, `rpi/app/web/topic_server.py`
- Create: `rpi/app/applications/settings_apps.py`
- Test: `rpi/app/web/tests/__init__.py`, `rpi/app/web/tests/test_topic_server.py`, `rpi/app/applications/tests/test_settings_apps.py`

**Interfaces:**
- Consumes: `topics` (Task 9), `AppContext` (Task 5), `Activity.touch()` (Task 6).
- Produces:
  - `class TopicServer(config_dir, port: int = 80, host: str = "", on_save: Callable[[], None] = …)`: `start()` (Thread, `http.server.ThreadingHTTPServer`), `stop()`, `port` (tatsächlicher Port; Tests nutzen `port=0`). `GET /` zeigt beide Felder mit dem gespeicherten Inhalt und den Satz zur neuen Kette (Spec §8). `POST /` speichert über `topics.save` und zeigt „Gespeichert.“. Kein Passwort.
  - `wall_address() -> tuple[str, str]` – (`<hostname>.local`, IPv4 im eigenen Netz; ohne Netz `"KEIN NETZ"`).
  - `class ThemaApp(server_factory, clock=time.monotonic)`: `name = "THEMA AENDERN"`; startet den Server; zeigt (`dots_own_cell=True`) `WEBSEITE IM BROWSER` / Name / `ODER <IP>` / `BT4 BEENDET SIE`; 15 min ohne Speichern → `WEBSEITE AUS`, zurück; Server läuft nicht → `WEBSEITE GEHT NICHT`; stoppt den Server immer (auch bei `StopApp`).
  - `class RadarSetupPlaceholder`: `name = "RADAR EINRICHTEN"`; zeigt `RADAR EINRICHTEN` / `KOMMT SPAETER` / `BT4 ZURUECK` (R2).
- [ ] **Step 1: Tests**
  ```python
  def test_get_shows_topics(self): urllib GET → Seite enthält beide Themen
  def test_save_normalizes(self): POST mit "Zeile1\nZeile2" + "x"*300 → Datei hat eine Zeile, <= 120 Zeichen
  def test_save_touches_activity(self): …
  def test_thema_app_timeout(self): Uhr +15 min ohne Speichern → Anzeige "WEBSEITE AUS", Server gestoppt
  def test_thema_app_stops_server_on_bt4(self): …
  ```
- [ ] **Step 2: FAIL. Step 3: implementieren. Step 4: grün.**
- [ ] **Step 5: Commit** `Pi: Webseite fuer die beiden Themen, Einstellungen im Menue`

### Task 13: Start: PC-Modus und Wand-Modus

**Files:**
- Modify: `rpi/app/main.py` (alte `input()`-Schleife ersetzen)
- Modify: `rpi/README.md` (Start, PC-Modus, Schalter `AUTO_AUS_MINUTEN`, Themendateien, Webseite)
- Delete: die alten ENTER-Anwendungen `rpi/app/applications/VoiseAssistant/VoiceAssistant.py`, `rpi/app/applications/Quiz/QuizGame.py`, `rpi/app/applications/ReflectionAI/Reflection.py` (ersetzt durch Task 8–9; `AIQuizGenerator.py` und `prompt*.py` bleiben, soweit noch benutzt)
- Test: `rpi/app/tests/test_main.py`

**Interfaces:**
- Consumes: alles oben.
- Produces:
  - `build_apps(config_dir) -> tuple[list[App], list[App]]` (Hauptmenü, Einstellungen; Reihenfolge Global Constraints)
  - `run_wall(display, buttons, activity, stop_event, link=None, radar_factory=None) -> str` – startet `Shell`; prüft alle 1 s `activity.expired()` und schickt dann über `LinkDispatcher.send_done()` `DONE` (F6); Teil 2 ruft diese Funktion aus dem Dienst auf.
  - `main(argv)`: `--pc` → `TerminalDisplay` + `KeyboardButtons`, KI und Datenbank wie sonst; ohne `--pc` → `WallDisplay`, PiLink auf dem ESP-Port, `LinkDispatcher`. (Den Handschlag mit `READY` und `SESSION` bringt Teil 2/4b.)
- [ ] **Step 1: Tests** – `build_apps` liefert die Namen in der richtigen Reihenfolge; `run_wall` mit Fake-Anzeige und Tasten `[6, 5, 4]` endet nicht von selbst und zeigt nach BT4 das Menü; `run_wall` schickt `DONE`, sobald `activity.expired()` wahr ist; `main(["--pc"])` lässt sich mit gepatchter Shell aufrufen.
- [ ] **Step 2: FAIL. Step 3: implementieren. Step 4: grün, ganze Suite grün, `test_imports` grün.**
- [ ] **Step 5: README nachführen, Commit** `Pi: Start im PC-Modus und an der Wand, alte ENTER-Anwendungen entfernt`

---

## Am Ende

- Ganze Python-Suite und `pio test -e native` grün.
- Von Hand am PC: `python -m app.main --pc`, mit 6/5/4 durch alle Menüpunkte; Chat, Quiz und Reflection brauchen dafür `GROQ_API_KEY` und die Datenbank wie heute.
- Nicht in 4a, sondern in 4b: Tasten am ESP je Zustand, BT4–BT6 als Pegelwechsel, `SESSION|HAND`/`SESSION|NACHT`, `PI STARTET`, Abnahme an der Wand (Spec §11, Teil „Am Gerät“).

---

## Stand nach der Umsetzung (2026-10-25)

Alle 13 Aufgaben sind umgesetzt und einzeln geprüft. Eine Schlussprüfung über den ganzen Branch fand 3 wichtige Punkte und 14 kleinere; die wichtigen und 10 kleinere sind in einer Korrekturrunde behoben und nachgeprüft. Python: 305 Tests grün.

### Entscheide während der Umsetzung (Rulings)

- Vorab-Ruling P1: Reihenfolge 1, 2, 3, 4, **6, 5**, 7 … — T6 vor T5, damit T5 das echte `Activity` nutzt — kostet nichts, falls falsch.
- Vorab-Ruling P2: Die Löschungen von `rpi/app/applications/Animations/Stickman.py` (T10) und `Animations/Radar.py` (T11) wandern in Task 13, wo `main.py` neu geschrieben wird — sonst ist die Suite zwischen T10 und T13 rot — kostet zwei Zeilen Umplanung, falls falsch.
- Task 2: Ruling: fuehrender Punkt belegt eine leere Stelle (".A" → [0, A]) – Brief mehrdeutig, Pruefer akzeptiert; ob der ESP es gleich macht, ist offen → Schlusspruefung – kostet eine Zeile, falls falsch
- Task 3: Ruling: clear() bleibt "Wand sofort leeren"; neu clear_canvas() (nur Puffer, kein Bus); in Task 11 ruft animations/stickman.py pro Bild clear_canvas() statt clear() – verhindert Flackern ohne die Bedeutung von clear() fuer Menue/Anwendungen zu aendern – kostet eine Methode, falls falsch
- Task 6: Ruling: GPIO22 mit internem Pull-down einlesen (lgpio.SET_PULL_DOWN) – ohne Radar sonst zufaellig HIGH, Pi bliebe wach; ein Push-Pull-Ausgang des Radars ueberstimmt den Pull-down – kostet eine Flag, falls die Platine schon einen Pull-down hat
- Task 5: Ruling: StopSignal (set(reason)/is_set/reason/wait) statt nacktem Event; Tasten beruehren Activity in Shell/AppContext; run_blocking/show_pages/Shell-Details im Auftrag festgelegt – Brief liess sie offen – kostet Umbenennungen, falls falsch
- Task 5: Ruling: Abhaengigkeiten (Radar-Umschaltung, config_dir, Server) kommen ueber die Konstruktoren der Anwendungen (wie im Plan: RadarApp(switch_factory…), ReflectionApp(config_dir=…), ThemaApp(server_factory)), nicht ueber AppContext; Shell bleibt ohne radar/config_dir – kostet ein Feld in AppContext, falls falsch
- Task 7: Ruling: send_done(timeout_s=30) – bei LinkBusy alle 0,25 s, bei None nach 10 s erneut (§6.2) – Brief sagte nur "bis OK oder Frist" – kostet eine Zahl, falls falsch
- Task 8: Ruling: Antwort zuerst als Seiten zeigen, danach einmal ganz sprechen; leere Umschrift → NICHTS VERSTANDEN; Recorder/Lautsprecher erst beim ersten run erzeugen – Brief liess es offen – kostet eine Reihenfolge, falls falsch
- Task 8: Ruling: leere KI-Antwort zaehlt als KI-Fehler; BT4 waehrend der Aufnahme stoppt den Recorder in einem Hintergrund-Thread (Ergebnis verworfen) – sonst Sekunden Verzoegerung bis zum Menue – kostet einen Thread, falls falsch
- Task 9: Ruling: Quiz erzeugt bis zu dreimal neu, wenn ein Feld nicht auf 4 Zeilen passt, danach Seiten; Quiz-Auftrag in prompt.py; Kette der Reflection nur lokal in run – Brief liess es offen – kostet Umbau der Wiederholung, falls falsch
- Task 10: Ruling: kaputte Bilddatei wird mit Warnung uebersprungen statt die Animation zu stoppen; Dateien als utf-8-sig lesen – Brief schwieg – kostet eine Zeile, falls falsch
- Task 10: Ruling: nicht-numerisches FRAME_TIME → Datei wird uebersprungen (Entscheid 3), nur nicht-positive Zahlen fallen auf 0,4 s – so stand es im Fix-Auftrag; der Nachpruef-Auftrag hatte es falsch zusammengefasst – kostet nichts, falls falsch
- Task 11: Ruling: Umsetzer auf dem staerksten Modell (opus) – PiLink-Thread und Leitungsumschaltung sind heikel – kostet nur Geld
- Task 11: Ruling: pause() wartet eine laufende Abfrage ab und ist danach portfrei; resume() verwirft gepufferte Radar-Bytes; RadarApp beendet sich auch bei gesetztem Stopp-Signal; ExpanderError → zurueck ins Menue mit Log – Brief liess es offen – kostet Umbau, falls falsch
- Task 11: Ruling: nach ausdruecklichem ERROR/BUSY auf MODE|RADAR kein MODE|NORMAL – der ESP hat dann nicht umgeschaltet (§6.4); weicht vom Wortlaut von Review Focus 3 ab – kostet eine einzelne Nachricht, falls falsch
- Task 13: Ruling: im PC-Modus zeigt RADAR "RADAR NUR AN DER WAND"; ReflectionAI/prompt*.py bleiben als Vorlage fuer Teil 3b; on_shutdown im Wand-Modus nur Log (Herunterfahren bringt Teil 2); ein gemeinsamer SMBus(1) fuer Anzeige und Expander; bei Ablauf von F6 erst Stopp "idle", Shell-Ende abwarten, dann DONE – Brief liess es offen – kostet Umbau der Verdrahtung, falls falsch
- Final: Ruling: eine Korrekturrunde mit I-1..I-3, drei Pflicht-Minors aus dem Ledger (Verwerf-Thread, test_chat_flow, run_wall-Absturz) und den neuen Minors M-1, M-2, M-3, M-4, M-6, M-7, M-10, M-12, M-13, M-11 (ein E2E-Test) – billig und fuer die Person an der Wand sichtbar – kostet eine groessere Runde, falls zu viel
- Final: Ruling: M-5, M-8, M-9, M-14 und alle uebrigen Minors bleiben fuer spaeter; M-9 (Punkte ESP vs. Pi) ist ein Entscheid des Owners in 4b – kostet spaetere Nacharbeit

### Hinweise für Teil 2 und 4b

- Task 11: note fuer Task 13: waehrend PiLink pausiert wirft request() LinkBusy → run_wall muss erst das Stopp-Signal setzen und nach dem Radar DONE senden; ExpanderButtons fuer das Radar mit dem Bus/bus_guard des Dienstes bauen
- Task 11: note fuer Teil 2/4b: Die ESP-Firmware beantwortet MODE heute mit ERROR|UNKNOWN; RADAR im Menue zeigt an der Wand FEHLER IN RADAR, bis der ESP RADAR-DEBUG kann (Teil 2)
- Offen aus der Schlussprüfung: M-5 (Sprechen nach BT4 abbrechen), M-8 (Quiz speichert Fragen, die niemand sah), M-9 (ESP und Pi zeichnen Punkte verschieden; Entscheid des Owners in 4b), M-14 (Wiederholung beim Expander, gehört zu Regel B), Rest von M-11 (Testlücken).

### Aufgeschobene kleinere Punkte

- Task 2: minor (deferred): cells.py:47-53 mehrere fuehrende Punkte ("..A") leuchten uneinheitlich
- Task 2: minor (deferred): cells.normalize ohne NFC – zerlegte Umlaute (U+0308) werden leer
- Task 2: minor (deferred): cells nutzt ASCII_16SEG.get, text_layout.displayable getrennt – koennten auseinanderlaufen
- Task 3: minor (deferred): start() verwirft Rueckgabe der Init-Transfers (nur Warnung) – Kommentar fehlt
- Task 3: minor (deferred): show_lines/show_text lassen die Zeichenflaeche stehen; spaeteres refresh() zeigt alte Flaeche
- Task 3: minor (deferred): TerminalDisplay druckt bei jedem refresh()
- Task 4: minor (deferred): ExpanderButtons – Wiederholung ohne Log; `log` ungenutzt
- Task 4: minor (deferred): KeyboardButtons – bei EOF endet der Thread still, get(None) blockiert; zweites start() startet zweiten Thread
- Task 4: minor (deferred): ExpanderButtons nur fuer einen Verbraucher, nicht dokumentiert
- Task 4: minor (deferred): Tests fehlen fuer drain()-Neubezug, Lesefehler in start(), bus_guard bei Wiederholung
- Task 6: minor (deferred): int() akzeptiert "1_5" und "+15" beim Schalter
- Task 6: minor (deferred): test_failed_import_is_not_retried patcht builtins.__import__ global
- Task 5: minor (deferred): test_buttons_before_start_are_drained prueft das Leeren nicht (vakuum)
- Task 5: minor (deferred): test_settings_app_starts_and_returns_to_submenu kann ohne Rueckkehr gruen sein; sleep(0.1)
- Task 5: minor (deferred): _choose zeichnet das Menue vor der Stopp-Pruefung (ein Bild zu viel)
- Task 5: minor (deferred): leere settings → Menu([]) ValueError
- Task 5: minor (deferred): vor dem Fehlerbild nicht geleert – altes BT4 schliesst "FEHLER IN …" sofort
- Task 5: minor (deferred): Shell-drain beruehrt Activity nicht (anders als run_blocking)
- Task 5: minor (deferred): ungetestet: BT4 oben tut nichts, Menu.select-Wrap, wait_button(timeout=0)
- Task 7: minor (deferred): Fehler im Handler vor der Antwort → keine Antwort (ERROR|INTERNAL fehlt)
- Task 7: minor (deferred): zweites SHUTDOWN (neue Nummer) ruft on_shutdown erneut
- Task 7: minor (deferred): send_done kann timeout_s um bis zu 10 s ueberziehen
- Task 7: minor (deferred): test_stop_ends_thread_quickly prueft is_alive nicht
- Task 8: minor (deferred): echte Antwort, die mit "Fehler" beginnt, gilt als KI-Fehler (Vertrag von write_to_ai)
- Task 8: minor (deferred): test_chat_flow prueft die Reihenfolge der Anzeigen nicht
- Task 8: minor (deferred): Verwerf-Thread der Aufnahme wird nicht abgewartet; neue Aufnahme koennte sich mit altem stop_recording ueberschneiden
- Task 7: minor (deferred): test_shutdown_answers_after_wait_limit druckt die Warnung "Anzeige nach 0.1 s nicht freigegeben" in die Testausgabe (assertLogs fehlt)
- Task 9: minor (deferred): topics.save – mkstemp setzt 0600 auf thema*.txt
- Task 9: minor (deferred): save schreibt zwei Dateien nacheinander (nicht gemeinsam atomar)
- Task 9: minor (deferred): schwache Tests: test_long_thought_asks_again, test_save_uses_replace, test_reflection_never_touches_db
- Task 9: minor (deferred): Quiz zeigt Platzhalter, wenn nur Loesung/Hinweis fehlen
- Task 10: minor (deferred): Schluessel mit float-Werten werden nicht als int geprueft (wird durch das Ueberspringen kaputter Dateien teilweise abgefangen)
- Task 10: minor (deferred): eingespeiste Bilder mit Dauer 0 umgehen die Pruefung in load_frames (nur ueber Konstruktor erreichbar)
- Task 11: minor (deferred): _send_normal nicht abgesichert – OSError ueberspringt _forget() und ersetzt die urspruengliche Ausnahme
- Task 11: minor (deferred): toter Link → leave() wartet 30 s, ohne zu senden
- Task 11: minor (deferred): reply() waehrend pause geht verloren (nur bei SHUTDOWN-Wettlauf mit RADAR)
- Task 11: minor (deferred): keine Wartezeit nach dem Umschalten des Multiplexers vor reset_input_buffer
- Task 11: minor (deferred): Menue friert bis 33 s ohne Hinweis ein, wenn der ESP schweigt
- Task 11: minor (deferred): Ergebnis von leave() wird ignoriert; Testluecken (Fehler in der Radar-Schleife, Link nach Abbruch)
- Task 12: minor (deferred): Handler ohne Socket-Timeout (haengender Client haelt einen Thread)
- Task 12: minor (deferred): >64 KB Body vor 413 nicht gelesen; stop() ohne Schutz bei totem Thread; Ausnahme aus stop() ersetzt die urspruengliche
- Task 12: minor (deferred): irrefuehrender Kommentar und privater Zugriff (_last) in test_settings_apps
- Task 13: minor (deferred): Fehler in shell.run() im Thread → run_wall gibt still "shutdown" zurueck
- Task 13: minor (deferred): Bus nie geschlossen; Aufraeumen fehlt, wenn open_esp_port/PiLink beim Start scheitern
- Task 13: minor (deferred): main importiert privates _SmbusReader
- Task 13: minor (deferred): README Zeile 68 nennt die geloeschten Klassen
- Task 13: minor (deferred): altes driver/display/display.py ist jetzt unbenutzt
