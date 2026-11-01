# ESP als Master über den Raspberry Pi – Entwurf

Stand: 2026-10-19 · Status: **vom Owner angenommen** (2026-10-19), ergänzt um
Runde 6 (Zitate im FRAM, 2026-10-19) und um Teil 4 (Menü, 2026-10-25)

Dieses Dokument sammelt, was in sechs Entscheidungsrunden festgelegt wurde, und
ergänzt, was für die Umsetzung noch fehlt. Abschnitt 2 listet die Entscheide.
Abschnitt 3 nennt, was dieser Entwurf zusätzlich festlegt; der Owner hat diese
Punkte nach Durchsicht angenommen (Z3, Z5 und Z8 ersetzt durch T1-a und T2-a).

---

## 1. Ziel

Der ESP8266 ist der Master. Er schaltet die Speisung des Raspberry Pi 5 ein,
redet über die UART mit ihm und fährt ihn sauber herunter, bevor er die
Speisung trennt. Der Pi wird für zwei Dinge gebraucht:

- **Von Hand:** Du schaltest ihn mit einer Taste ein und löst etwas aus,
  zum Beispiel ein Gespräch mit der KI.
- **Um Mitternacht:** Der ESP schaltet ihn selbst ein, lässt die KI einen neuen
  Text schreiben, speichert ihn im FRAM und schaltet den Pi wieder ab. Mit dem
  Schalter `FRAM_INSTALLED = false` liegt die Liste stattdessen im Flash (F1-a).

Die Wand zeigt diesen Text, wenn jemand davorsteht oder BT1 gedrückt wird.
Sonst ist sie dunkel.

Erfolg heisst: Ein- und Ausschalten funktionieren zuverlässig, die SD-Karte des
Pi nimmt keinen Schaden, und keine Nachricht geht unbemerkt verloren.

---

## 2. Was entschieden ist

| Nr. | Entscheid | Runde |
|---|---|---|
| A1 | Auslöser: eine Taste von Hand und Mitternacht automatisch | 1, 3 |
| A2 | Solange der Pi Strom hat, bleibt der ESP wach | 1 |
| A3 | Ablauf: Strom ein → Pi meldet bereit → Betrieb → ESP fragt „darf ich?“ → Pi ja oder „noch beschäftigt“ → warten → Strom aus; hängt der Pi, nach Frist hart aus | 1 |
| A4 | Ob der Pi läuft, fragt der ESP über die UART ab | 1 |
| A6 | Die Uhrzeit holt der ESP selbst per WLAN (NTP) | 3 |
| E1-b | Nachrichtenformat `$BEFEHL\|DATEN*hh` mit XOR-Prüfsumme; in den Daten werden `\`, Zeilenumbruch und Wagenrücklauf maskiert | 1 |
| E2-a | Der ESP bleibt bei 74 880 Baud; der Pi stellt beim Umschalten die Baudrate mit um | 1 |
| E3 | Im Betrieb steht die UART des Pi fest auf dem ESP. Der ESP wiederholt Anfragen bis zu einer Frist, schickt alle 10 s ein PING und schaltet nach drei verpassten PINGs hart ab | 1 |
| E4-a | Nach `OK` wartet der ESP eine feste, bei der Inbetriebnahme gemessene Zeit, dann trennt er die Speisung | 1 |
| E5-c | Der ESP liest die Tasten immer zuerst (er holt sich kurz den I²C-Bus), reagiert auf das, was ihn betrifft, und schickt den Rest an den Pi | 1 |
| Regel | Jede Nachricht wird bestätigt; der Absender wiederholt sie bis zur Bestätigung oder bis zur Frist | 2 |
| S1-a | Eine Sitzung von Hand endet mit der Ein/Aus-Taste oder wenn der Pi `DONE` meldet (Anwendung fertig oder 15 min ohne Taste); ~~Obergrenze 3 h~~ (entfällt, Teil 4 D1); `DONE` nach 15 min ohne Aktivität nur, wenn der Schalter an ist (Teil 4 D2, F6); 10 min nach dem ersten `SHUTDOWN` hart aus | 2 |
| S2-a | Die Ein/Aus-Taste gehört dem ESP, die anderen Tasten gehen als `BUTTON` an den Pi; die Pi-Anwendungen auf Tasten umzustellen ist ein eigener Teil 4 | 2 |
| S3-a | Radar-Debug ~~nur zum Einstellen~~: Der Pi meldet ihn an und ab, der ESP pausiert solange, höchstens 60 min. Die Anwendung Radar nutzt ihn auch (Teil 4 D8, V6) | 2 |
| S4-a | Ein systemd-Dienst, ein Prozess besitzt die UART, eigener Thread für die Verbindung | 2 |
| M1-d | Ohne Person ist die Wand dunkel. Radar erkennt jemanden → Zitat an, ESP bleibt wach, solange INT_HLK HIGH ist, danach Anzeige aus und schlafen. BT1 → Zitat an, nach 1 min aus | 4 |
| M2-c | Ein Thema steht in einer Datei auf dem Pi (Anfangsinhalt „Was ist der Sinn des Lebens“); der ESP schickt den Text vom Vortag mit; neues Thema = neue Kette | 4 |
| — | Kein Scrollen: Der Auftrag an die KI verbietet ausdrücklich Texte, die länger sind als die Anzeige; Pi und ESP prüfen zusätzlich | 4 |
| M3-a | Weckplan mit Terminen (00:00, 01:00, 02:00), höchstens 3 h am Stück, Ortszeit samt Sommerzeit. WLAN nur zum Zeitabgleich: um Mitternacht und nach einem Kaltstart, höchstens 15 s, nie das Einrichtungsportal (ausser nach Kaltstart ohne Zugangsdaten, 3 min). Kennt der ESP nach einem Kaltstart die Zeit nicht, versucht er den Abgleich bei jedem ~~Weckvorgang~~ Timer-Weckvorgang (höchstens alle 3 h) wieder, nicht nach einer Taste, und lässt bis dahin den Mitternachts-Auftrag aus | 3, 2026-10-31 |
| M4-a | Bei Fehlern in der Nacht bleibt das alte Zitat; neue Versuche um 01:00 und 02:00, danach erst in der nächsten Nacht; läuft gerade eine Sitzung, wird das Zitat darin geholt; endet sie vorher, gilt das als Fehlversuch | 3 |
| — | Die zwölf festen Texte sind entfallen; die Wand zeigt `/text.txt` aus dem Flash | nach Runde 4 |
| — | BT1–BT3 laufen über Toggle-Flipflops; BT1 zeigt das Zitat, BT2 schaltet den Pi, BT3 ist frei. Seit 2026-10-23 haben alle sechs Tasten Flipflops | nach Runde 4 |
| T1-a | Während einer Sitzung gehen alle Tasten ausser BT2 an den Pi (BT1, BT3–BT6); BT1 schaltet dann kein Zitat weiter; ~~BT4–BT6 verlieren kurze Drücke, bis Flipflops nachgerüstet sind~~. Der Pi beachtet BT1 und BT3 nicht (Teil 4 D5) | 5 |
| T2-a | Der Flash hält bis zu 30 Zitate (neuestes zuerst). Wand dunkel + Radar oder BT1 → neuestes Zitat. Wand leuchtet + BT1 → nächstälteres, nach dem ältesten wieder das neueste. Wand aus, wenn INT_HLK LOW und der letzte BT1-Druck 1 min zurückliegt. Beim nächsten Einschalten wieder das neueste | 5 |
| Z1–Z15 | Die Zusatzpunkte aus Abschnitt 3 sind angenommen, ausser Z3 (ersetzt durch T1-a) und Z5, Z8 (ersetzt durch T2-a) | 5 |
| — | Die Zitate liegen im FRAM (MB85RC256V, 32 KB, I²C 0x50) statt im Flash des ESP | nach Runde 5 |
| P1-a | Der ESP schreibt das Zitat der Nacht ins FRAM. Der Pi schickt es über die UART (`QUOTE`); der ESP prüft es, hält es im RTC-Speicher und schreibt es, nachdem er den Pi ausgeschaltet hat | 6 |
| P2-a | Die Liste liegt im FRAM auf zwei Plätzen, jeder mit Kopf (Kennung, laufende Nummer, Länge, CRC-32). Geschrieben wird in den älteren Platz, gelesen der gültige mit der höheren Nummer | 6 |
| P3-b | Der Flash dient als Briefkasten: Liegt dort `/quotes.txt`, übernimmt der ESP die Liste ins FRAM und löscht die Datei. `esp/data/` im Repo bleibt leer, sobald `FRAM_INSTALLED = true` ist | 6 |
| P4-a | Der FRAM-Speicher kommt als eigener Teil 3a-2 nach Teil 3a, vor Teil 0 und 1, nur auf dem ESP | 6 |
| F1-a | Das FRAM ist noch nicht bestückt. Der FRAM-Speicher wird trotzdem jetzt gebaut, mit dem Schalter `FRAM_INSTALLED = false`; bis zur Bestückung läuft alles aus dem Flash | 6 |
| — | Das FRAM ist bestückt (2026-10-20). `FRAM_INSTALLED` steht auf `true`; die Abnahme mit FRAM gehört zu Teil 3a-2 | nach Runde 6 |
| — | Für FRAM-Zugriffe schaltet der ESP den Bus auf 100 kHz und danach zurück auf 10 kHz | nach Runde 6 |
| B | I²C in einer Sitzung: Der Pi pausiert den Bus bei jedem Tastendruck und jeder Radar-Flanke, bis der ESP den Expander gelesen hat. Niemand fragt vorher. Gilt, sofern die Messung genug Reserve zeigt; sonst kommt die Frage zurück zum Owner (Abschnitt 10) | 2026-10-22 |
| Teil 4 | Menü und Pi-Anwendungen an der Wand: Entscheide D1–D18, Vorschläge V1–V7 und Festlegungen F1–F7 in `2026-10-23-menue-und-anwendungen-design.md` | 2026-10-25 |
| L1 | `READY` ohne Antwort bis zur Frist (3 s): Der Pi schickt ein neues `READY` mit neuer Nummer, so lange, bis `OK` kommt; jede Runde ins Log | 2026-10-25 |
| L2 | Solange `GET\|QUOTE` offen ist, pausiert das `PING`. Die Frist von 120 s ersetzt es; ohne Antwort gilt die Nacht als Fehlversuch, und der ESP fährt den Pi herunter | 2026-10-25 |
| L3 | Der ESP behandelt `READY` nie als Wiederholung (gleiche Nummer nach einem Neustart des Pi-Dienstes). Kommt `READY` in einer Sitzung, antwortet er `OK` und schickt das `SESSION\|…` noch einmal | 2026-10-25 |
| L4 | Teil 4b (die ESP-Seite von Teil 4: `SESSION`, BT4–BT6, Tasten je Zustand, Anzeigen beim Start und Ausschalten, `MODE`) wird Teil von Teil 2, mit einem gemeinsamen Plan | 2026-10-25 |
| R15 | Die Anwendung Radar des Pi endet nach 55 min von selbst. Der Pi schaltet die UART zurück (`MODE\|NORMAL`) und schickt `DONE`. Grund: Im Radar-Debug gehört die UART dem Radar, ein `SHUTDOWN` des ESP käme nie an. Die 60 min des ESP bleiben als Rückfall für einen Pi, der im Radar-Debug hängt (Plan Teil 2, vom Owner bestätigt) | 2026-10-25 |
| N1 | Weckt eine Taste oder das Radar den ESP vor der geplanten Zeit, nimmt er an, die geplante Strecke sei ganz abgelaufen. Seine Uhr geht dann höchstens vor (bis zu 3 h), nie nach. Vor dem Mitternachts-Auftrag gleicht er per NTP ab; ist es dann noch vor 00:00, schläft er den Rest. Grund: Der RTC-Zähler des ESP8266 übersteht das Wecken nicht verlässlich | 2026-10-25 |
| N2 | In einer Sitzung `NACHT` laufen die Wand-Regeln (§8) weiter; BT1, BT3–BT6 gehen nicht an den Pi. Ist das neue Zitat da und die Anzeige an, zeigt der ESP es sofort aus dem RTC-Speicher (Z11). Die Wand hält den Pi nie an: Ist das Zitat da, fährt der ESP den Pi herunter | 2026-10-25 |
| N3 | BT2 in einer Sitzung `NACHT` macht daraus eine Sitzung von Hand: `PI STARTET`, dann `SESSION\|HAND`, der Pi zeigt das Menü; das Zitat holt der ESP weiter in dieser Sitzung (M4-a). Bootet der Pi noch, heisst BT2 „danach HAND“. BT2 setzt den ESP zurück (§10): Ein offenes `GET\|QUOTE` verfällt, `SESSION\|HAND` geht zuerst, dann sendet der ESP das `GET` noch einmal mit neuer Nummer. Der Pi gibt es dem Arbeits-Thread, der noch rechnet, oder antwortet mit dem Zitat, das er schon hat. Ist das Zitat da, gilt die Nacht als gelungen, wie auch immer die Sitzung endet. Auf dem Pi startet ein zweites `SESSION\|HAND` nach `NACHT` das Menü (ändert Teil 2) | 2026-10-25 |
| N4 | Zum Testen: ein Schalter in `features.h`, ab Werk aus. Nach dem ersten NTP-Abgleich nach einem Kaltstart stellt der ESP seine Uhr einmal so, dass in 2 min Mitternacht ist; ist der Schalter an, steht das bei jedem Wecken im Log | 2026-10-25 |

A1–A6 waren in Runde 1 als Annahmen formuliert; du hast sie bestätigt. Die
Begründungen und Gegenprüfungen standen in den Rundendateien der
Arbeitssitzung und liegen nicht im Repo. Massgeblich ist diese Tabelle.

---

## 3. Was dieser Entwurf zusätzlich festlegt

Diese Punkte ergaben sich aus dem Ausarbeiten. Der Owner hat sie nach
Durchsicht angenommen; **Z3, Z5 und Z8 gelten nicht mehr** – an ihre Stelle
treten T1-a und T2-a (Abschnitt 2).

| Nr. | Festlegung | Warum |
|---|---|---|
| Z1 | Jede Nachricht trägt eine **laufende Nummer** (0–255, je Absender). Die Antwort wiederholt die Nummer. Kommt eine Nachricht mit derselben Nummer noch einmal, schickt der Empfänger nur die alte Antwort noch einmal und führt nichts doppelt aus. | Ohne Nummer würde eine wiederholte Nachricht doppelt ausgeführt, wenn nur die Antwort verloren ging – zum Beispiel zweimal `BUTTON`. |
| Z2 | Das Format wird damit `$NN:BEFEHL\|DATEN*hh` (NN = Nummer, zwei Hex-Ziffern). | Folgt aus Z1. |
| Z3 | *Ersetzt durch T1-a.* ~~BT2 als Ein/Aus-Taste hast du entschieden. Neu ist: BT1 und BT3 gehen während einer Sitzung als `BUTTON` an den Pi (BT3 hat ausserhalb einer Sitzung keine Funktion). BT4–BT6 werden **gar nicht** verwendet, auch nicht vom Pi – abweichend von S2-a, wo alle anderen Tasten an den Pi gehen sollten.~~ | |
| Z4 | Der Code für das Nachrichtenformat ist auf dem ESP **reines C++ ohne Arduino-Typen**, damit er auf dem PC getestet werden kann. Beide Seiten prüfen dieselben Testfälle aus einer gemeinsamen Datei. | So ist belegt, dass ESP und Pi dasselbe Format sprechen. |
| Z5 | *Ersetzt durch T2-a.* ~~`/text.txt` bekommt eine zweite Zeile mit dem Datum der Nacht (`JJJJ-MM-TT`). Die Anzeige zeigt nur die erste Zeile. Geschrieben wird erst in `/text.new`, dann umbenannt.~~ | |
| Z6 | Lehnt der ESP ein Zitat ab, fragt er mit `GET\|QUOTE` noch einmal; nach drei abgelehnten Zitaten gilt die Nacht als Fehlversuch. | Bildet „höchstens dreimal“ aus M2 im Ablauf ab. |
| Z7 | Während der Radar-Anzeige oder der BT1-Minute bleibt der ESP wach und schläft nicht dazwischen. | Folgt aus M1-d; der ESP muss INT_HLK beobachten und die Minute messen. |
| Z8 | *Ersetzt durch T2-a.* ~~**BT1 und Radar gleichzeitig:** Endet die BT1-Minute, während das Radar noch jemanden sieht, bleibt die Anzeige an, bis INT_HLK LOW ist. Die Minute allein gilt nur, wenn das Radar niemanden sieht.~~ | |
| Z9 | Protokolldetails: eine Zeile höchstens 256 Bytes; pro Richtung höchstens eine offene Anfrage; unbekannter Befehl → `ERROR\|UNKNOWN`; was bei abgelaufener Frist passiert, steht in 6.2. | Damit beide Seiten gleich reagieren. |
| Z10 | Bricht ein Reset das Schreiben der Anzeige ab, merkt der ESP das am Zustand „wird geschrieben“ und schreibt beim nächsten Durchlauf neu. | Am Gerät beobachtet: Ein Reset kam mitten im Schreiben. |
| Z11 | Mitternacht, während der ESP wegen des Radars wach ist: Er prüft die Uhrzeit selbst (nicht über den Weckgrund) und startet den Auftrag. Ist die Anzeige an, zeigt er das neue Zitat sofort. | Wach gibt es kein Timer-Wecken, das den Auftrag auslösen würde. |
| Z12 | Nimmt der Pi 5 keine 74 880 Baud an, wechseln beide Seiten auf 115 200 Baud (die Alternative E2-b aus Runde 1). | E2-a hängt an einer ungeprüften Annahme. |
| Z13 | Der alte Code wird ersetzt: `esp/lib/communication/*`, `rpi/app/driver/uart/uart_esp.py`, `protocol.py`, `commands.py`, `test.py`; die alte Kopie `rpi/tests/uart/` wird gelöscht. | Sie enthält die Fehler 1–3 und würde sonst weiter verwirren. |
| Z14 | Die Zahlen in Abschnitt 12, die kein Entscheid vorgibt, sind Startwerte dieses Entwurfs; die Spalte „Herkunft“ zeigt, welche. | Damit klar ist, was du entschieden hast und was ich gewählt habe. |
| Z15 | Die Umsetzung hat fünf Teile (Abschnitt 16): 0 Pi einrichten, 1 Verbindung, 2 Ein- und Ausschalten, 3 Anzeige/Radar und Mitternacht, 4 Tasten für die Pi-Anwendungen. | Teil 4 bleibt wie in S2-a die Tastenumstellung; „Anzeige und Radar“ kam mit M1-d dazu. |

---

## 4. Hardware, auf der der Entwurf aufbaut

Quelle: Schaltplan „Schematic PDF [No Variations]“ vom 08.03.2026.

| Nr. | Fakt | Seite |
|---|---|---|
| F1 | UART0 des ESP (TXD0/RXD0) geht über einen Analogschalter CD4053 (D9) an GPIO14/15 des Pi 5. Der Pi wählt mit GPIO23: LOW = ESP, HIGH = Radar. | 15, 17, 7 |
| F2 | Steckt der USB-Flasher (X1), hängt der ESP am Flasher und der Pi am Radar, egal was GPIO23 sagt. Die Verbindung ESP–Pi ist dann getrennt. | 17 |
| F3 | GPIO16 ist über R39 mit RST verbunden: der ESP kann sich per Timer wecken. | 15 |
| F4 | Jede Änderung am Tasten-Expander (INT_GPIO_EXP) und jede steigende Flanke des Radars (INT_HLK) setzt den ESP über Monoflops zurück – auch wenn er wach ist. | 15, 8, 18 |
| F5 | Die Speisung des Pi hält ein Flipflop (U13A), das der ESP mit einem Puls auf GPIO12 umschaltet. Ein ESP-Reset ändert sie nicht. Der ESP kann sie nicht zurücklesen. | 6 |
| F6 | Der Pi ist ein Raspberry Pi 5. Er sieht INT_GPIO_EXP (GPIO4) und INT_HLK (GPIO22) ebenfalls. | 7 |
| F7 | Den I²C-Bus hat der Pi, solange ESP-GPIO15 LOW ist. | 17 |
| F8 | INT_HLK (Radar-Ausgang, ESP-GPIO13) ist HIGH, solange jemand erkannt wird, und bleibt danach noch einige Zeit HIGH (Werkseinstellung etwa 60 s). | 18 |
| F9 | Alle sechs Tasten laufen über Toggle-Flipflops: jeder Druck kippt den Pegel am Expander, und der bleibt stehen. BT4–BT6 hat der Owner nachgerüstet (2026-10-22/23). | 10, 11; am Gerät gemessen |

Was am Gerät noch zu prüfen ist, steht in Abschnitt 15.

---

## 5. Aufbau

Frage, die die Zeichnung beantwortet: *Welche Teile gibt es, und worüber reden sie?*

```
 ESP8266 (Master)                                            Raspberry Pi 5
 ┌────────────────────────────────┐                          ┌──────────────────────────────┐
 │ Application (je Wecken)        │                          │ reflection-wall.service      │
 │  ├─ PiSession  (Zustände)      │  UART 74 880 Baud        │  ├─ PiLink (Thread)          │
 │  ├─ PiLink     (Nummer, Wdh.)  │◄───── über CD4053 ─────► │  │   Nummer, Wiederholung    │
 │  │   └─ Codec  (Format)        │  GPIO23 LOW = ESP        │  │   └─ codec (Format)       │
 │  ├─ WakePlan   (wann wecken)   │                          │  ├─ Zitat (KI, Thema, Kette) │
 │  ├─ Clock      (NTP, Schätzung)│                          │  ├─ Tasten → Anwendungen     │
 │  ├─ DisplayCtl (an/aus/Text)   │                          │  └─ Herunterfahren           │
 │  ├─ QuoteStore (FRAM / Flash)  │                          │      (systemctl poweroff)    │
 │  └─ Tasten (Expander lesen)    │                          └──────────────────────────────┘
 └────┬───────────────────────────┘
      ├ GPIO12 Puls ──► Flipflop ──► Relais ──► Speisung Pi
      ├ GPIO15 ──► I²C-Umschalter (HIGH = ESP hat den Bus)
      ├ GPIO13 ◄── INT_HLK (Radar)
      └ GPIO16 ──► RST (Timer-Wecken)
```

*Gezeichnet 2026-10-19 aus den Entscheiden in Abschnitt 2 und dem Schaltplan.*

Was jeder Teil tut:

| Teil | Seite | Aufgabe |
|---|---|---|
| Codec | beide | Nachricht in eine Zeile verwandeln und zurück: Nummer, Befehl, Daten, Maskierung, Prüfsumme. Kein Zugriff auf Hardware. |
| PiLink | beide | Zeilen senden und empfangen, Antworten zuordnen, wiederholen, doppelte Nachrichten erkennen. |
| PiSession | ESP | Zustände einer Sitzung (Abschnitt 7) und ihre Fristen. |
| WakePlan | ESP | Rechnet aus, wann der ESP das nächste Mal aufwacht. |
| Clock | ESP | Uhrzeit per NTP holen und zwischen den Abgleichen weiterzählen. |
| DisplayCtl | ESP | Anzeige ein- und ausschalten, Text schreiben. |
| QuoteStore | ESP | Liste (bis 30 Zitate) lesen, prüfen und sicher schreiben: im FRAM auf zwei Plätzen, bis zur Bestückung in `/quotes.txt`; Briefkasten im Flash und Umstieg von `/text.txt` (Abschnitt 11). |
| Zitat | Pi | Thema lesen, KI fragen, Text bereinigen und prüfen. |
| Dienst | Pi | Startet beim Booten, besitzt die UART, meldet `READY`, fährt auf Anfrage herunter. |

Der bestehende Code wird ersetzt, nicht erweitert: `esp/lib/communication/*`
und `rpi/app/driver/uart/uart_esp.py`, `protocol.py`, `commands.py`,
`test.py`. Die alte Kopie `rpi/tests/uart/` wird gelöscht.

---

## 6. Protokoll

### 6.1 Eine Nachricht

Format nach E1-b, erweitert um die laufende Nummer aus Z1/Z2:

```
$NN:BEFEHL|DATEN*hh\n
```

- `$` – Startzeichen. Zeilen ohne `$` am Anfang werden verworfen (Debug-Log, Boot-Meldung).
- `NN` – laufende Nummer, zwei Hex-Ziffern, je Absender von 00 bis FF und dann wieder 00 (Z1).
- `BEFEHL` – Grossbuchstaben, endet am ersten `|`.
- `DATEN` – beliebiger Text; `\` → `\\`, Zeilenumbruch → `\n`, Wagenrücklauf → `\r`. `|`, `$`, `*` dürfen vorkommen.
- `hh` – XOR aller Bytes zwischen `$` und dem **letzten** `*`, zwei Hex-Ziffern.
- Eine Zeile ist höchstens 256 Bytes lang. Längere Zeilen werden verworfen.

Eine verworfene Zeile wird gezählt und im Log gemeldet, aber nicht beantwortet.
Der Absender merkt es an der fehlenden Antwort und wiederholt.

### 6.2 Antworten und Wiederholung

- Jede Nachricht bekommt **genau eine** Antwort mit derselben Nummer.
- Der Absender wiederholt alle 250 ms, bis die Antwort da ist oder die Frist des Befehls abläuft (Tabelle 6.3, Fristen in Abschnitt 12).
- Kommt eine Nummer zweimal hintereinander, schickt der Empfänger seine letzte Antwort noch einmal und führt nichts doppelt aus.
- Zu jedem Zeitpunkt ist pro Richtung höchstens **eine** Anfrage offen.

Was passiert, wenn die Frist ohne Antwort abläuft:

| Nachricht | Absender | Frist abgelaufen |
|---|---|---|
| `PING` | ESP | zählt als ein Aussetzer (drei hintereinander → hart aus) |
| `GET\|QUOTE` | ESP | Fehlversuch der Nacht (M4-a); solange er offen ist, pausiert `PING` (L2) |
| `BUTTON` | ESP | Taste verworfen, Eintrag im Log |
| `SHUTDOWN` | ESP | nach `T_shutdown` hart aus |
| `READY` | Pi | weiter senden, bis `OK` kommt (der ESP bootet vielleicht gerade); jede Runde mit neuer Nummer (L1). Der ESP wertet `READY` nie als Wiederholung (L3) |
| `DONE` | Pi | alle 10 s erneut senden |
| `MODE\|RADAR` | Pi | nicht umschalten, Radar-Debug startet nicht |
| `MODE\|NORMAL` | Pi | weiter senden, bis `OK` kommt |
| `SESSION` | ESP | den Pi herunterfahren wie nach BT2 (Teil 4) |

### 6.3 Befehle

| Richtung | Anfrage | Antwort | Bedeutung |
|---|---|---|---|
| ESP → Pi | `PING` | `PONG` | Lebt der Pi? |
| ESP → Pi | `GET\|QUOTE\|<Text vom Vortag>` | `QUOTE\|<Text>` oder `ERROR\|<Grund>` | Neues Zitat holen. Leerer Vortag = neue Kette. |
| ESP → Pi | `SESSION\|HAND` oder `SESSION\|NACHT` | `OK` | Warum der ESP den Pi eingeschaltet hat: BT2 oder der tägliche Timer (Teil 4 F1) |
| ESP → Pi | `BUTTON\|<n>` | `OK` | Taste BT1 oder BT3–BT6 während einer Sitzung |
| ESP → Pi | `SHUTDOWN` | `OK` oder `BUSY` | Darf ich ausschalten? Nach `OK` fährt der Pi herunter. |
| Pi → ESP | `READY` | `OK` | Der Dienst läuft. |
| Pi → ESP | `DONE` | `OK` | Der Pi ist fertig und will ausgeschaltet werden. |
| Pi → ESP | `MODE\|RADAR` / `MODE\|NORMAL` | `OK` | Radar-Debug beginnt / endet. Der Pi schaltet erst nach `OK` um. |

Ein unbekannter Befehl wird mit `ERROR|UNKNOWN` beantwortet.

### 6.4 Leitung und Baudrate

- Der Pi öffnet `/dev/ttyAMA0` mit 74 880 Baud und setzt GPIO23 auf LOW (ESP).
- Nur im Radar-Debug schaltet er auf 115 200 Baud und GPIO23 HIGH. Reihenfolge:
  `MODE|RADAR` senden → `OK` abwarten → GPIO23 HIGH → 115 200 Baud.
  Zurück: 74 880 Baud → GPIO23 LOW → `MODE|NORMAL` senden, bis `OK` kommt.
- Der ESP schreibt sein Debug-Log weiter auf dieselbe Leitung. Der Pi filtert es über das Startzeichen und die Prüfsumme heraus.
- Mit eingestecktem USB-Flasher gibt es keine Verbindung (F2). Zum Testen der Verbindung liest man das Log auf der Pi-Seite.

---

## 7. Ablauf einer Sitzung (ESP)

Frage, die die Zeichnung beantwortet: *In welchen Zuständen ist der ESP, während er den Pi steuert, und was bringt ihn weiter?*

```
                 BT2 (Pi aus) oder Mitternachts-Termin
   ┌──────────┐ ─────────────────────────────────► ┌───────────────┐
   │   AUS    │                                    │  EINSCHALTEN  │ kein PING, der Pi wiederholt READY
   │Deep Sleep│ ◄── kein READY bis T_boot ──────── │ wartet READY  │
   └──────────┘     (hart aus)                     └───────┬───────┘
        ▲                                                  │ READY
        │                                                  ▼
        │                                          ┌───────────────┐  MODE|RADAR  ┌─────────────┐
        │ ◄── 3 PING ohne Antwort (hart aus) ───── │    BETRIEB    │ ───────────► │ RADAR-DEBUG │
        │                                          │ PING alle 10 s│ ◄─────────── │ kein PING   │
        │                                          └───────┬───────┘ MODE|NORMAL  └─────────────┘
        │                                                  │ BT2 · DONE · Auftrag erledigt
        │                                                  │ (aus RADAR-DEBUG: nach 60 min)
        │                                                  ▼
        │ ◄── keine Antwort bis T_shutdown ─────── ┌───────────────┐
        │     oder 10 min BUSY (hart aus)          │HERUNTERFAHREN │ SHUTDOWN, bei BUSY nach 30 s nochmal
        │                                          └───────┬───────┘
        │                                                  │ OK
        │                                                  ▼
        │                                          ┌───────────────┐
        └──────────── T_halt abgelaufen ────────── │  HALT-WARTEN  │
                      (Speisung aus)               └───────────────┘
```

*Gezeichnet 2026-10-19 aus den Entscheiden A3, E3, E4-a, S1-a, S3-a; „3 h“ entfernt nach Teil 4 D1;
„PING wiederholt“ in EINSCHALTEN ersetzt nach L1 und Plan Teil 2 R7 (2026-10-25).
„Hart aus“ heisst: Speisung trennen ohne Herunterfahren, mit Eintrag im Log.*

Regeln, die die Zeichnung nicht zeigt:

- **Startgrund (Teil 4 F1):** Nach `READY` schickt der ESP `SESSION|HAND`, wenn BT2 den
  Pi eingeschaltet hat, sonst `SESSION|NACHT`. Nur bei `HAND` zeigt der Pi das Menü.
  BT2 während EINSCHALTEN merkt sich der ESP und fährt den Pi nach `READY` gleich
  wieder herunter.
- **PING (E3)** läuft im Zustand BETRIEB. In EINSCHALTEN schickt der ESP kein PING
  (Plan Teil 2, R7): Der Pi wiederholt `READY` selbst, bis `OK` kommt (L1), und
  `T_boot` fängt einen Pi ab, der nie meldet. In HERUNTERFAHREN übernimmt die
  Wiederholung von `SHUTDOWN` mit ihrer Frist die Rolle des PING. In RADAR-DEBUG ist
  es nach S3-a ausgesetzt.
- Der Zustand liegt im RTC-Speicher (Abschnitt 11). Jeder Reset durch eine Taste
  oder das Radar (F4) führt zurück in denselben Zustand; der ESP liest dann den
  Grund und macht weiter.
- **Speisung umschalten** heisst immer: ein Puls auf GPIO12 (F5). Der ESP schaltet
  nur, wenn sein gespeicherter Zustand sagt, dass der Pi an ist bzw. aus ist.
  Nach einem Kaltstart (Strom war weg) ist auch das Flipflop zurückgesetzt, der
  Pi also aus.
- Während einer Sitzung gehört die Anzeige dem Pi. Radar und BT1 ändern sie dann
  nicht; BT1 geht als `BUTTON|1` an den Pi.
- In RADAR-DEBUG merkt sich der ESP einen Druck auf BT2 und fährt herunter,
  sobald der Pi zurück ist. Nach 60 min fährt er ohnehin herunter.
- Ein Mitternachts-Auftrag während einer Sitzung von Hand: Der ESP schickt
  `GET|QUOTE` innerhalb der Sitzung und schaltet nichts. Solange eine Anfrage
  offen ist, schickt der Pi kein `DONE`. Endet die Sitzung trotzdem vorher
  (zum Beispiel mit BT2), gilt das als Fehlversuch, und der nächste Termin holt
  das Zitat nach (M4-a).

---

## 8. Anzeige und Radar (M1-d, T2-a)

Frage, die die Zeichnung beantwortet: *Welches Zitat zeigt die Wand nach welchem Ereignis?*

```
                 Radar erkennt jemanden            BT1                BT1
 Wand dunkel  ───────────────────────────►  Zitat 1  ──────────►  Zitat 2  ──────────►  Zitat 3 …
                 oder BT1 bei dunkler Wand  (neuestes)            (gestern)           (vorgestern)

 nach dem ältesten gespeicherten Zitat folgt wieder Zitat 1
 Wand geht aus (Radar LOW und BT1-Minute vorbei) → beim nächsten Einschalten wieder Zitat 1
```

*Gezeichnet 2026-10-19 aus T2-a.*

| Ereignis | Was passiert |
|---|---|
| Radar erkennt jemanden, Wand dunkel (INT_HLK steigt → Reset) | Neuestes Zitat schreiben, Anzeige ein. Der ESP bleibt wach und liest GPIO13 alle 200 ms. |
| BT1, Wand dunkel | Neuestes Zitat schreiben, Anzeige ein, die BT1-Minute beginnt. |
| BT1, Wand leuchtet | Nächstälteres Zitat schreiben; nach dem ältesten wieder das neueste. Die BT1-Minute beginnt neu. |
| Wand ausschalten | Wenn INT_HLK LOW ist **und** der letzte BT1-Druck mindestens 60 s zurückliegt: Anzeige aus, schlafen. |
| Mitternacht, während der ESP wegen der Anzeige wach ist | Der ESP prüft in seiner Warteschleife die Uhrzeit und startet den Auftrag (Z11). Kommt ein neues Zitat, zeigt er es sofort; die Position steht dann wieder beim neuesten. |
| Sitzung läuft | Anzeige gehört dem Pi; nichts davon gilt. BT1 geht an den Pi (T1-a). |

Welches Zitat gerade zu sehen ist, steht im RTC-Speicher als **Datum des Zitats**,
nicht als Platz in der Liste. So zeigt die Position auch dann auf das richtige
Zitat, wenn vorne ein neues dazukommt.

Grenzen: Die Wand wird erst dunkel, wenn INT_HLK LOW wird – das ist die
Nachlaufzeit des Radars nach dem Gehen (Werkseinstellung etwa 60 s, nicht
gemessen; im Radar-Debug einstellbar). Steht jemand sehr ruhig, kann das Radar
ihn verlieren, und die Wand geht aus.

- **Anzeige aus** heisst: Befehl „Display aus“ an alle 12 Module. Beim Einschalten
  schreibt der ESP den Text neu, statt sich auf den Inhalt der Chips zu verlassen.
- **Bricht ein Reset das Schreiben ab** (zum Beispiel das Radar), merkt der ESP das
  am Zustand „Anzeige wird geschrieben“ im RTC-Speicher und schreibt neu.
- Ob die Anzeige an ist, steht im RTC-Speicher. Damit unterscheidet der ESP einen
  neuen Radar-Treffer von einem Reset, der nichts Neues bringt – der Weckgrund
  allein taugt dafür nicht (am Gerät gemessen, als BT4–BT6 noch keine Flipflops
  hatten: kurze Taps wurden als Radar gemeldet).

---

## 9. Mitternacht (M2-c, M3-a, M4-a)

```
 21:00          23:47*              00:00                                        ~00:05
   │              │                   │                                            │
   ●──────────────●───────────────────●────────────────────────────────────────────●
 Timer          Timer               Timer, Funk an
 Funk aus       letzte Strecke      1  WLAN + NTP (höchstens 15 s, nie das Portal)
                bis 00:00 gekürzt,     noch vor 00:00? → Rest schlafen
                nächster Start      2  Pi EIN, warten auf READY
                mit Funk            3  GET|QUOTE → prüfen → im RTC-Speicher halten
                                    4  SHUTDOWN → OK → T_halt → Pi AUS
                                    5  Zitat vorne in die Liste schreiben (FRAM, P1-a)
                                    6  Deep Sleep, Funk aus (Anzeige bleibt dunkel)

 * Beispiel. Der Zeitpunkt ergibt sich aus der eigenen Uhr des ESP.
```

*Gezeichnet 2026-10-19 aus M3-a und M4-a, Schritte 3–5 nachgeführt nach P1-a.*

**Weckplan.** Der ESP schläft nie länger als 3 h am Stück. Er weckt sich zum
nächsten Termin: 00:00, und nach einem Fehlversuch 01:00 und 02:00. Die Termine
rechnet er in Ortszeit (Europa/Zürich mit Sommerzeit). Nur der Mitternachts-Start
läuft mit eingeschaltetem Funk; dafür schläft der ESP davor mit Funk ein.

**Uhr.** NTP-Abgleich um Mitternacht und nach jedem Kaltstart; nach einem
Kaltstart ist der Funk ohnehin an. Dazwischen zählt der ESP seine Schlafzeiten
zusammen. Kennt er die Zeit nach einem Kaltstart nicht, versucht er den Abgleich
bei jedem Timer-Weckvorgang (höchstens alle 3 h, dafür schläft er vorher mit
Funk ein) und lässt bis dahin den Mitternachts-Auftrag aus (M3-a).
Die Uhr zählt in UTC; Ortszeit und Sommerzeit rechnet der ESP daraus. Weckt
eine Taste oder das Radar den ESP vor der geplanten Zeit, gilt die geplante
Strecke als ganz abgelaufen (N1): Die Uhr geht danach höchstens vor, und der
Abgleich vor Mitternacht korrigiert sie.

**Kaltstart in der Nacht.** Kommt der Strom zwischen 00:00 und 03:00 zurück und
ist die Uhrzeit bekannt, vergleicht der ESP das Datum des neuesten Eintrags der Liste mit dem
heutigen. Fehlt das Zitat dieser Nacht, startet er den Auftrag sofort; die
Termine 01:00 und 02:00 gelten danach wie sonst.

**Zitat.** Der ESP schickt das neueste Zitat der Liste als Text vom Vortag mit.
Der Pi:

1. liest das Thema aus `rpi/app/config/thema.txt` – eine Zeile, Anfangsinhalt „Was ist der Sinn des Lebens“; fehlt die Datei, gilt dieser Satz,
2. vergleicht es mit dem Thema der letzten Nacht (`rpi/app/config/.thema_zuletzt`); ist es neu, lässt er den Vortag weg,
3. fragt die KI: Thema, Gedanke von gestern, „Entwickle daraus den nächsten Gedanken. Höchstens 96 Zeichen, auf keinen Fall länger. Nur Buchstaben, Ziffern, Leerzeichen und Punkt, keine Umlaute.“,
4. ersetzt Umlaute (`ä→ae`, `ö→oe`, `ü→ue`, `ß→ss`), entfernt Zeichen ausserhalb von `A–Z a–z 0–9 - . / : + *` und Leerzeichen. Kleinbuchstaben bleiben erlaubt. Die Anzeige zeigt sie als Grossbuchstaben,
5. prüft mit derselben Umbruchregel wie die Anzeige (24 Zeichen pro Zeile, Umbruch an Wortgrenzen, höchstens 4 Zeilen), dass der Text passt; sonst fragt er die KI noch einmal – höchstens drei KI-Anfragen pro `GET|QUOTE`, danach antwortet er `ERROR|ZU_LANG`,
6. antwortet `QUOTE|<Text>`.

Der ESP prüft dasselbe noch einmal (Zeichen, Umbruch). Passt es, hält er das
Zitat im RTC-Speicher und schreibt es mit Datum vorne in die Liste, sobald der Pi
aus ist (P1-a; Abschnitt 11; das älteste fällt bei mehr als 30 weg). Fällt der
Strom vorher aus, holt die Regel „Kaltstart in der Nacht“ das Zitat neu. Passt es
nicht, fragt er noch einmal, höchstens dreimal (Z6). Gescrollt wird nie.

**Die Wand in der Nacht** (N2, N3). Während der Nacht-Sitzung gelten die
Wand-Regeln aus §8, und die Tasten bleiben beim ESP. BT2 macht aus der
Nacht-Sitzung eine Sitzung von Hand; das Zitat wird darin weiter geholt.
BT2 setzt den ESP zurück: Ein offenes `GET` verfällt, `SESSION|HAND` geht
zuerst, dann das `GET` noch einmal mit neuer Nummer. Der Pi gibt es dem
Arbeits-Thread, der noch rechnet, oder antwortet mit dem Zitat, das er schon hat.

**Fehler in der Nacht** (kein `READY`, keine Antwort, `ERROR`, drei abgelehnte
Zitate, Sitzung vorher beendet): Pi aus, sauber wenn möglich; altes Zitat bleibt;
neue Versuche um 01:00 und 02:00. Scheitert auch 02:00, versucht der ESP es erst in
der nächsten Nacht wieder. Das Ergebnis der Nacht (ok oder Grund) steht im
RTC-Speicher und erscheint beim nächsten Weckvorgang im Log.

---

## 10. Tasten (E5-c, S2-a, T1-a)

| Taste | Ohne Sitzung | Während einer Sitzung |
|---|---|---|
| BT1 | Zitat anzeigen bzw. weiterschalten (Abschnitt 8) | `BUTTON\|1` an den Pi; der Pi beachtet ihn nicht (Teil 4 D5) |
| BT2 | Sitzung von Hand starten | Sitzung beenden (`SHUTDOWN`, der Pi darf `BUSY` antworten) |
| BT3 | Verbindungstest (Teil 1) | `BUTTON\|3` an den Pi; der Pi beachtet ihn nicht (Teil 4 D5) |
| BT4–BT6 | – | `BUTTON\|4` bis `BUTTON\|6` an den Pi; Menü und Anwendungen (Teil 4) |

Ein Druck während der Sitzung setzt den ESP zurück. Er bootet, liest seinen
Sitzungszustand aus dem RTC-Speicher, liest den Expander und schickt `BUTTON|n`.
In einer Sitzung `NACHT` gelten N2 und N3 (Abschnitt 9).
Was der ESP in den anderen Zuständen mit einer Taste tut, steht in Teil 4,
Tabelle 5.2.

Jeder Pegelwechsel an einer der sechs Tasten ist ein Druck (`InputTrigger::ANY_EDGE`).
Seit Teil 2 stehen auch BT4–BT6 in der Firmware auf `InputTrigger::ANY_EDGE`.

**I²C während einer Sitzung (Entscheid B, 2026-10-22).** Ein Tastendruck oder
eine Radar-Flanke setzt den ESP zurück. Danach holt er sich sofort den I²C-Bus
(GPIO15 HIGH), liest den Expander und gibt den Bus zurück. Der Pi sieht dieselben
Leitungen (F6) und hält sich deshalb an diese Regel:

1. Sieht der Pi eine fallende Flanke an INT_GPIO_EXP (GPIO4) oder eine steigende
   an INT_HLK (GPIO22), schreibt er die laufende Übertragung an ein Modul zu Ende.
2. Danach beginnt er keine neue Übertragung.
3. Er macht weiter, wenn INT_GPIO_EXP wieder HIGH ist und danach `T_bus_frei`
   vergangen ist.
4. Wird eine Übertragung trotzdem abgeschnitten, wiederholt er sie (Rückfall).

Niemand fragt vorher, und der ESP wartet nie. Die Regel trägt nur, wenn der Pi
seine Übertragung beenden kann, bevor der ESP den Bus nimmt. Gerechnet: Der ESP
braucht vom Tastendruck bis zum Bus etwa 60–100 ms (Reset-Impuls, Start, Funk).
Der Pi braucht unter 20 ms (Flanke bemerken, höchstens 17 Bytes zu Ende schreiben).
Gemessen wird beides bei der Inbetriebnahme (Abschnitt 15). Reicht die Reserve
nicht, kommt die Frage zurück zum Owner.

---

## 11. Gespeicherter Zustand

**RTC-Speicher** (`PersistentState`, überlebt Resets und Deep Sleep, nicht einen
Stromausfall). Das Layout ändert sich, deshalb neue `MAGIC`.

Der Zustand ist `PersistentState::Data` mit 300 Bytes, `MAGIC` ist „RWL4“
(`0x52574C34`). Die Felder, wie sie gebaut sind:

| Feld | Inhalt |
|---|---|
| `lastExpanderState` | wie heute: Referenz für die Tasten-Auswertung |
| `displayState` | aus / an / wird geschrieben |
| `button1Active` | die BT1-Minute läuft. Sie zählt ab dem Start des Durchlaufs, denn jeder BT1-Druck setzt den ESP zurück |
| `wakeCount` | wie heute: Anzahl Weckvorgänge, im Log |
| `shownIndex`, `shownDate` | Platz und Datum des Zitats, das gerade zu sehen ist (T2-a); massgeblich ist das Datum, der Platz hilft bei gleichen Daten |
| `session` (`SessionData`, 28 Bytes) | Zustand aus Abschnitt 7: `state`, `reason`, `awaiting`, `flags`, `missedPings`, `buttonCount`, `buttons[6]`, `inStateMs`, `sincePingMs`, `sinceBusyMs`, `sessionMs`. Das Flag `PendingShutdown` in `flags` ist BT2 während RADAR-DEBUG. `sessionMs` ist die verstrichene Sitzungszeit (im Entwurf `sessionSeconds`), in jedem Takt der Sitzung gesichert (etwa alle 20 ms); nur noch fürs Log, die 3 h entfallen (Teil 4 D1) |
| `piPowered` | ob der ESP die Speisung zuletzt eingeschaltet hat |
| `txSeq`, `rxSeq`, `rxValid` | laufende Nummern der Verbindung (Z1): nächste eigene Nummer, letzte Nummer des Pi, ob sie gilt |
| `clock` (`ClockData`, 24 Bytes) | `utc` (UTC-Sekunden seit 1970), `plannedS` (geplante Strecke des letzten Deep Sleep), `lastSyncUtc` (`utc` beim letzten Abgleich), `testOffsetS` (Verschiebung des Testschalters `NIGHT_TEST`), `ms` (Rest unter einer Sekunde), `valid` (Zeit bekannt, nur durch einen Abgleich), `exact` (seit dem Abgleich nie vor der Zeit geweckt), `radio` (Funk beim nächsten Start) |
| `night` (`NightData`, 224 Bytes) | `status` (Idle, Wanted, Got, Failed), `attempts` (Versuche der Nacht von `date`), `rejects` (abgelehnte Zitate im laufenden Versuch), `result` (Ergebnis der Nacht), `pendingWrite` (das Zitat fehlt noch in der Liste, P1-a), `date` (Nacht des laufenden Auftrags, `JJJJ-MM-TT`), `doneDate` (Nacht mit Zitat), `yesterday` (neuester Text der Liste, R6), `quote` (das geprüfte Zitat der Nacht, bis es nach dem Ausschalten des Pi in der Liste steht) |

`yesterday` und `quote` sind je 97 Bytes (96 Zeichen und das Ende). `result` ist
`None`, `Ok`, `NoReady`, `NoAnswer`, `Error`, `Rejected`, `SessionEnded`,
`NoClock` oder `StoreFailed`.

Das Feld `textIndex` entfällt.

**Liste der Zitate** (T2-a): eine Zeile pro Zitat, `JJJJ-MM-TT|Text`, das
neueste zuerst, höchstens 30 Zeilen. Ein Text hat höchstens 96 Zeichen, eine
Zeile also höchstens 107 Bytes, die ganze Liste höchstens etwa 3,2 KB. Wo die
Liste liegt, entscheidet der Schalter `FRAM_INSTALLED` in der Firmware (F1-a).

**FRAM** (`FRAM_INSTALLED = true`; P2-a, P3-b):

- MB85RC256V, 32 KB, I²C-Adresse 0x50, am selben Bus wie Expander und Anzeigen.
  Der ESP holt sich den Bus dafür mit GPIO15 (F7) und taktet ihn für das FRAM
  mit 100 kHz statt 10 kHz. Gemessen 2026-10-20 mit 3,3 KB: Schreiben 0,42 s,
  Lesen 0,43 s (bei 10 kHz 4,4 s; bei 400 kHz 0,1 s, mit den Anzeigen nicht geprüft).
  Abnahme 2026-10-20 mit der Firmware (Stücke zu 30 Bytes, eigene Wire): 30 Zitate,
  2730 Bytes, in 0,56 s gelesen; die Übernahme aus dem Briefkasten dauerte 0,61 s.
- **Zwei Plätze** A und B zu je 4 KB. Jeder Platz beginnt mit einem Kopf:
  Kennung, laufende Nummer, Länge der Liste, CRC-32 über Nummer, Länge und
  Liste. Danach folgt die Liste im Textformat oben.
- **Lesen:** Gültig ist ein Platz mit richtiger Kennung, erlaubter Länge und
  passender Prüfsumme. Massgeblich ist der gültige Platz mit der höheren Nummer.
  Der ESP liest beide Köpfe zweimal. Ein Kopf zählt erst, wenn beide Lesungen
  gleich sind; sonst entscheidet eine dritte, und passt auch die nicht, gilt der
  Durchlauf als Lesefehler am Bus.
  Passt die Prüfsumme eines Platzes nicht, liest der ESP die Liste noch einmal.
  Erst wenn auch das zweite Lesen scheitert, gilt der Platz als ungültig.
  Trägt kein Kopf eine Kennung, ist das FRAM leer und die Liste ebenfalls.
- **Beschädigt:** Trägt mindestens ein Kopf die Kennung, aber kein Platz ist gültig,
  gilt das FRAM als beschädigt. Die Wand zeigt `KEIN TEXT`. Der ESP speichert in
  diesem Durchlauf nichts. Nur eine Liste aus dem Briefkasten repariert das FRAM.
- **Schreiben:** immer in den anderen Platz als den gültigen. Ist keiner gültig,
  nimmt der ESP den Platz mit der niedrigeren Nummer. Die Nummer ist die höchste
  gefundene Nummer plus 1. So bekommt ein Schreiben nie eine niedrigere Nummer
  als ein Platz, der schon da ist. Die Liste kommt zuerst und der Kopf zuletzt.
  Bricht ein Reset das Schreiben ab, bleibt der alte Platz gültig. Das ersetzt das Umbenennen von `/quotes.new`.
- **Briefkasten:** Liegt beim Start `/quotes.txt` im Flash, übernimmt der ESP
  die Liste ins FRAM. Danach liest er die Liste aus dem FRAM zurück. Nur wenn sie
  übereinstimmt, löscht er die Datei. Stimmt sie nicht, bleibt die Datei, und der
  ESP speichert in diesem Durchlauf nichts. Fällt der Strom dazwischen
  aus, übernimmt er dieselbe Datei beim nächsten Start noch einmal. Dasselbe gilt
  für `/text.txt` (Umstieg wie unten). `esp/data/` im Repo bleibt leer; eine
  Liste zum Hochladen liegt als Beispiel in `esp/data-beispiel/quotes.txt`.
- **Lesefehler am Bus:** Die Wand zeigt `KEIN TEXT`, und der ESP schreibt in
  diesem Durchlauf nichts in die Liste.

**Flash** (`FRAM_INSTALLED = false`; LittleFS):

- `/quotes.txt` mit der Liste.
- **Schreiben** immer atomar: die ganze Liste nach `/quotes.new`, dann umbenennen.
  Findet der ESP beim Start ein übriggebliebenes `/quotes.new`, löscht er es.
- **Umstieg:** Fehlt `/quotes.txt`, aber `/text.txt` ist da, wird dessen erste
  Zeile der einzige Eintrag (ohne Datum, gilt als ältester), danach wird
  `/text.txt` gelöscht. Fehlt beides, zeigt die Wand „KEIN TEXT“.
- `pio run -t uploadfs` lädt `esp/data/` hoch. Solange `FRAM_INSTALLED = false`
  ist, liegt dort `quotes.txt` mit der Startliste.

---

## 12. Fristen und Startwerte

Kein Wert ist gemessen. „Entscheid“ heisst: du hast die Zahl in einer Runde
angenommen. „Entwurf“ heisst: Startwert dieses Entwurfs (Z14), zum Einstellen.

| Name | Wert | Wofür | Herkunft |
|---|---|---|---|
| Wiederholabstand | 250 ms | jede unbeantwortete Nachricht | Entscheid (E3) |
| Frist einfache Anfrage | 3 s | `PING`, `BUTTON`, `READY`, `DONE`, `MODE`, `SESSION` | Entwurf |
| Frist `GET\|QUOTE` | 120 s | KI-Antwort kann dauern | Entwurf |
| PING-Abstand | 10 s | im Zustand BETRIEB | Entscheid (E3) |
| PING-Aussetzer bis hart aus | 3 | | Entscheid (E3) |
| `T_boot` | 120 s | vom Einschalten bis `READY` | Entwurf |
| `T_shutdown` | 60 s | auf `SHUTDOWN` keine Antwort | Entwurf |
| BUSY-Wiederholung | 30 s | | Entwurf |
| BUSY höchstens | 10 min | ab Eintritt in HERUNTERFAHREN, also ab dem Moment, in dem das erste `SHUTDOWN` fällig ist | Entscheid (S1-a) |
| `T_halt` | 30 s | **wird bei der Inbetriebnahme gemessen** und auf das Doppelte gesetzt | Entscheid (E4-a) |
| ~~Sitzung höchstens~~ | ~~3 h~~ | entfällt | Teil 4 D1 |
| Pi ohne Aktivität bis `DONE` | 15 min | nur wenn der Schalter an ist, Standard aus | Teil 4 D2, F6 |
| Webseite ohne Speichern höchstens | 15 min | | Teil 4 D11 |
| Radar-Debug höchstens | 60 min | | Entscheid (S3-a) |
| BT1-Anzeige | 60 s | | Entscheid (M1-d) |
| INT_HLK abfragen | alle 200 ms | | Entwurf |
| `T_bus_frei` | 5 ms | Pi wartet nach INT_GPIO_EXP HIGH, bevor er den Bus wieder nutzt (Abschnitt 10) | Entwurf |
| WLAN + NTP höchstens | 15 s | | Entscheid (M3-a) |
| Einrichtungsportal | 3 min | nur Kaltstart ohne Zugangsdaten | Entscheid (M3-a) |
| Längster Deep Sleep | 3 h | | Entscheid (M3-a) |
| `PI_MIN_OFF_MS` | 5000 ms | so lange bleibt der Pi mindestens aus, bevor der ESP ihn wieder einschaltet; vorläufig, wird am Gerät geprüft (Task 10 des Plans Mitternacht) | Plan |
| `NIGHT_TEST_LEAD_S` | 120 s | Testschalter `NIGHT_TEST`: so lange nach dem ersten Abgleich ist Mitternacht; negativ heisst danach (−5400: die Uhr zeigt 01:30) | Plan |
| Nachtversuche | 00:00, 01:00, 02:00 | | Entscheid (M4-a) |
| KI-Anfragen pro `GET\|QUOTE` | 3 | | Entscheid (M2-c) |

---

## 13. Fehlerfälle

| Fall | Verhalten |
|---|---|
| Pi bootet nicht (kein `READY` bis `T_boot`) | hart aus, Log; bei Mitternacht Versuch zum nächsten Termin |
| Pi hängt im Betrieb (3 PINGs ohne Antwort) | hart aus, Log |
| Pi antwortet nicht auf `SHUTDOWN` | nach `T_shutdown` hart aus |
| Dienst auf dem Pi stürzt ab | systemd startet ihn neu; dauert das länger als 3 PINGs, hart aus |
| Zeile mit falscher Prüfsumme | verworfen, gezählt; Absender wiederholt |
| Antwort geht verloren | Absender wiederholt; Empfänger erkennt die Nummer und führt nicht doppelt aus |
| ESP-Reset mitten in der Sitzung (Taste, Radar) | Zustand aus RTC-Speicher, weiter wie vorher |
| ESP-Reset während des Schreibens der Anzeige | beim nächsten Durchlauf neu schreiben |
| Stromausfall | Kaltstart: Pi ist aus (Flipflop zurückgesetzt), Uhr unbekannt → NTP; die Liste bleibt (FRAM oder `/quotes.txt`) |
| WLAN fehlt um Mitternacht | Auftrag nach eigener Uhr; der Pi braucht aber Internet für die KI – meist folgt ein KI-Fehler und der nächste Termin |
| Flasher steckt | keine Verbindung; wie „Pi bootet nicht“ |
| Pi hängt im Radar-Debug | Ein laufender Pi beendet das Radar schon nach 55 min selbst und schickt `DONE` (R15). Hängt er, schickt der ESP nach 60 min `SHUTDOWN`; ohne Antwort nach `T_shutdown` hart aus |
| Frist einer Nachricht abgelaufen | siehe Tabelle in 6.2 |

---

## 14. Prüfen

**Auf dem PC, ohne Gerät:**

- **Codec, beide Seiten:** Eine gemeinsame Datei `tests/protocol_vectors.json`
  enthält Zeilen und das erwartete Ergebnis: gültige Nachrichten, Maskierung,
  Prüfsummenfehler, fehlendes Startzeichen, Bytes statt Text, zu lange Zeilen,
  Debug-Zeilen mit `|`, die Boot-Meldung. Python liest sie mit `unittest`, der ESP
  mit einem PlatformIO-Test in einer `native`-Umgebung (MinGW-g++ ist auf diesem
  Rechner vorhanden). Die Fehler 1–5 aus der ersten Durchsicht bekommen je einen
  Fall.
- **PiLink:** Wiederholung, Frist, doppelte Nummer, eine offene Anfrage – mit einer
  Test-Leitung im Speicher statt der UART.
- **PiSession und WakePlan:** reine Logik mit eingespeister Zeit; jede Kante der
  Zeichnung in Abschnitt 7 ist ein Testfall, ebenso Sommerzeitwechsel und
  „Uhr unbekannt“.
- **Zitat (Pi):** Bereinigung und Umbruchprüfung mit festen Texten; die KI wird
  im Test durch feste Antworten ersetzt.
- **Zitatliste und Anzeige-Regeln (ESP):** Liste lesen und schreiben (höchstens 30,
  neuestes zuerst, ältestes fällt weg), übriggebliebenes `/quotes.new`, Umstieg von
  `/text.txt`, Weiterschalten mit Rückkehr zum neuesten, Position über ein neues
  Zitat hinweg, Ausschaltregel (INT_HLK und BT1-Minute) – mit einem Dateisystem
  und einer Uhr im Speicher statt LittleFS und `millis()`.

**Am Gerät (Abnahme):**

1. Pi 5 nimmt 74 880 Baud an.
2. `T_halt` messen.
3. Sitzung von Hand: BT2 ein, BT1/BT3 kommen beim Pi an, BT2 aus, Pi fährt sauber herunter.
4. Pi hängt (Dienst stoppen): ESP schaltet nach 3 PINGs ab.
5. Mitternacht mit vorgestellter Uhr (Schalter aus N4): Zitat kommt, wird gespeichert, Pi aus.
6. Radar: Wand an, solange jemand davorsteht, danach dunkel.
7. Stromaufnahme bei 100 % Helligkeit mit allen Segmenten an und laufendem Pi.

---

## 15. Offen und Risiken

| Punkt | Warum offen | Wie es geschlossen wird |
|---|---|---|
| 74 880 Baud am Pi 5 | nicht gemessen | Abnahme 1; sonst überall 115 200 (E2-b) |
| `T_halt` | nicht gemessen | Abnahme 2 |
| Strom bei 100 % Helligkeit | nicht gemessen; Anzeigen und Pi am selben 5-V-Wandler | Abnahme 7 |
| Rückspeisung | ESP-TX liegt kurz am RX des stromlosen Pi | prüfen, ob der ESP seinen TX bei ausgeschaltetem Pi hochohmig lassen kann |
| COM8 zeitweise blockiert, Datenmüll im Schlaf | Ursache unbekannt. 2026-11-01: Während der ESP schlief, lieferte COM8 dieselben paar Bytes rund 98 000 Mal pro Sekunde; bei 74 880 Baud ist das unmöglich, es kam also nicht vom ESP | nur Entwicklung; beobachten |
| Ruhig stehende Person | Radar kann sie verlieren | Radar-Parameter im Radar-Debug einstellen |
| Kette driftet vom Thema ab | nicht beobachtet | Themenwechsel startet neu |
| ~~BT4–BT6 ohne Flipflop~~ | erledigt: nachgerüstet (2026-10-22/23) | – |
| Pi per Taste bedienen | Bis Teil 4 warten die Pi-Anwendungen auf ENTER; ein per BT2 gestarteter Pi lässt sich nur über SSH bedienen (S2-a) | wird mit Teil 4 erledigt (`2026-10-23-menue-und-anwendungen-design.md`) |
| Zeichen `:` | Die Schrift zeigt `:` wie `/` | eigenes Muster suchen; Teil 4 umgeht es mit Port 80 (V5) |
| Nachlaufzeit des Radars | Werkseinstellung etwa 60 s, nicht gemessen; bestimmt, wie lange die Wand nach dem Gehen an bleibt | im Radar-Debug messen und einstellen |
| Boot-Modus 7 (GPIO15 HIGH im Reset) | Nach dem Bestücken des FRAM (2026-10-20) antworteten die Anzeigen nicht, und der ESP startete bei jedem Reset mit `boot mode:(7,7)`. Ein vollständiger Stromunterbruch hat beides behoben. Wieder am 2026-11-01: Nachdem BT2 den Pi zum ersten Mal eingeschaltet hatte, endete jeder Reset über den Flasher mit `boot mode:(7,6)` und `waiting for host`, auch bei ausgeschaltetem Relais. Nach einem Unterbruch von Netzteil und Flasher lief der ESP wieder normal; einmal hing er danach wieder ohne Reset über den Flasher, vermutlich beim Wecken. Vermutung, nicht gemessen: GPIO15 bleibt HIGH, wenn der ESP ihn loslässt (Pull-down fehlt oder ist zu schwach); die Firmware setzt ihn HIGH, solange sie den I²C-Bus hat | Spannung an GPIO15 messen, während der ESP hängt; den Pull-down an GPIO15 prüfen (ESP-12: etwa 10 kΩ gegen GND). Bestätigt es sich, kann der ESP nach jedem Reset und jedem Wecken hängen bleiben: vor der Abnahme von Teil 2 lösen |
| Zeit für die I²C-Pause (Entscheid B) | gerechnet: ESP braucht 60–100 ms bis zum Bus, Pi unter 20 ms bis zur Pause; nicht gemessen | Mit dem Logikanalysator den Abstand von der INT_GPIO_EXP-Flanke bis zur ersten SCL-Flanke des ESP messen; in Teil 2 die Reaktionszeit des Pi messen. Reicht die Reserve nicht: zurück zum Owner |
| Flipflops ohne Strom, ESP mit Strom | Speist der Flasher den ESP weiter, während die Platine keinen Strom hat, laufen die Flipflops aller sechs Tasten in einem anderen Zustand an. Der ESP liest das als Tastendruck (beobachtet: BT2 schaltete die Speisung des Pi um). 2026-11-01: Nach zwei von drei Stromunterbrüchen (Netzteil zuerst, Flasher danach) bekam der Pi Strom und war gut 2 min später wieder aus, wie bei einer Sitzung ohne `READY` (`T_boot`); kein Log | nur in der Entwicklung mit Flasher; beobachten |
| Sprachausgabe unter dem Dienst | Unter systemd liegt der Ordner `bin/` des venv nicht im PATH; `speaker.py` startet piper deshalb seit 2026-11-01 mit dem Python des venv (`python -m piper`, Entscheid des Owners). Die Stimmen (`*.onnx`, Git LFS) sind seit 2026-11-01 auf dem Pi geholt. Gehört hat die Ausgabe am Gerät noch niemand; das Ausgabegerät `plughw:2,0` ist ungeprüft | am Gerät einen Satz sprechen lassen |

---

## 16. Umsetzung in Teilen

| Teil | Inhalt | Braucht |
|---|---|---|
| 0 | Pi einrichten: `dtparam=uart0=on`, I²C, venv mit `lgpio` und `pyserial`, `piper` (Sprachausgabe, ruft die README schon auf), `.env`, sudoers-Regel | laufenden Pi mit SSH |
| 1 | Verbindung: Codec und PiLink auf beiden Seiten, gemeinsame Testfälle, Fehler 1–5 | – |
| 2 | Ein- und Ausschalten: PiSession, Dienst auf dem Pi, BT2, Regel B; dazu die ESP-Seite von Teil 4 (L4) | 0, 1 |
| 3a | Anzeige, Radar und Zitatliste (Abschnitte 8 und 11): Anzeige aus/an, Zitatliste `/quotes.txt` mit Umstieg, BT1 weiterschalten, wach bleiben solange INT_HLK HIGH | – |
| 3a-2 | Zitate im FRAM (Abschnitt 11): FRAM-Speicher mit zwei Plätzen, Briefkasten im Flash, Schalter `FRAM_INSTALLED` | – |
| 3b | Mitternacht: WakePlan, Clock, Zitat, QuoteStore | 1, 2 |
| 4 | Menü und Pi-Anwendungen an der Wand, einschliesslich Radar-Einrichtung (`2026-10-23-menue-und-anwendungen-design.md`) | 0, 1, 2 |
| 5 | Tanz-Show, Animationen, Spiel; Vorlage in `docs/werkstatt/wand-werkstatt.html`; eigener Entwurf | 4 |

Teil 3a und Teil 3a-2 hängen nicht am Pi und kommen als Erstes. Jeder Teil bekommt einen
eigenen Plan und endet mit Tests und einer Abnahme am Gerät.

---

## 17. Nicht Teil dieses Entwurfs

- OTA-Updates. Eine Weboberfläche gibt es nur für die beiden Themen (Teil 4).
- Scrollen zu langer Texte (verworfen in Runde 4).
- Was die Pi-Anwendungen inhaltlich tun (Sprachassistent, Quiz, Reflection AI).
- Neue Hardware. Die Flipflops für BT4–BT6 hat der Owner inzwischen selbst nachgerüstet.
