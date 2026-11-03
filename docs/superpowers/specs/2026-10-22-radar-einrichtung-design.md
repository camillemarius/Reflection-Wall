# Radar-Einrichtung an der Wand – Entwurf

Stand: 2026-11-03 · Status: **vom Owner beauftragt** („arbeite ein Konzept aus und setze um“,
2026-11-03). Frühere Fassungen: 2026-10-22, an Teil 4 angepasst am 2026-10-25.

Neu in dieser Fassung: der **Zielwert** (R11), die Messung **dahinter** (R12) und was die
Messungen am Gerät am 2026-11-03 über den LD2410S gezeigt haben (Abschnitt 3). Punkte, die
ich selbst entschieden habe, sind als „Entscheid Claude“ markiert.

Baut auf `docs/superpowers/specs/2026-10-19-esp-pi-steuerung-design.md` auf (im
Folgenden „Hauptentwurf“) und auf Teil 4 (`2026-10-23-menue-und-anwendungen-design.md`).

---

## 1. Zweck

Die Wand soll nur angehen, wenn jemand vor ihr steht, und zwar näher als eine Entfernung,
die der Owner wählt. Leute weiter hinten, Bewegung im Hintergrund oder Dinge im Raum sollen
sie nicht einschalten.

Wie der Raum aussieht und bis wohin man erkannt werden will, ist erst bekannt, wenn die Wand
an ihrem Platz hängt. Jeder Platz hat andere Störungen. Deshalb wird das Radar dort
eingestellt, von einem Programm auf dem Pi, bedient mit den Tasten an der Wand: erst wird
der leere Raum gemessen, dann die Person an bestimmten Entfernungen. Ein Laptop ist nicht
nötig.

## 2. Ziele, Nicht-Ziele, Anti-Ziele

**Ziele**
- Der Owner wählt einen Zielwert, zum Beispiel 2,0 m. Wer näher kommt, wird erkannt.
- Wer weiter weg steht als der Zielwert, schaltet die Wand nicht ein, soweit das Radar das
  auflösen kann (ein Tor ist etwa 0,7 m lang; die Grenze ist weich).
- Bei leerem Raum bleibt die Wand dunkel.
- Nach dem Weggehen bleibt die Wand noch etwa **30 Sekunden** an.
- Die Einstellungen bleiben im Radar gespeichert, auch nach einem Stromausfall.
- Ein Bericht hält fest, was gemessen und eingestellt wurde.

**Nicht-Ziele**
- Richtung oder Winkel erkennen. Das Radar misst nur Entfernung und Signalstärke.
- Personen unterscheiden.
- Die Firmware des Radars ändern.
- Laufend nachstellen. Eingestellt wird nur, wenn jemand die Einrichtung startet.
- Eine genaue Entfernung für die Anwendung RADAR (eigene Aufgabe, Abschnitt 12).

**Anti-Ziele** (wäre ein Misserfolg, auch wenn es technisch läuft)
- Die Wand geht nach der Einrichtung im leeren Raum von selbst an.
- Die Einrichtung startet aus Versehen.
- Nach einem Abbruch oder Fehler hat das Radar halbe oder unsinnige Werte.
- Für die Einrichtung braucht es einen Laptop.

## 3. Rahmen

- **Radar:** HLK-LD2410S, Protokoll „HLK-LD2410S Serial Communication Protocol V1.00“
  (2024-08-23), 115 200 Baud, Little Endian. Ausgang OT2 = INT_HLK an ESP-GPIO13 und
  Pi-GPIO22: HIGH, solange jemand erkannt wird, und danach die Nachlaufzeit lang.
- **Radar-Debug** (Teil 4 F4): Der Pi schaltet mit `RadarSwitch` (`MODE|RADAR`, GPIO23
  HIGH, 115 200 Baud) auf das Radar; höchstens 60 min. Ab da liest der Pi die Tasten selbst
  am Expander (`ExpanderButtons`), wie die Anwendung RADAR.
- **Was das Radar kann** (Datenblatt):
  - Einstellmodus ein (`0x00FF`, Wert `0x0001`) und aus (`0x00FE`); nur dazwischen gelten
    Befehle. Antworten: `FD FC FB FA` Länge Befehl|`0x0100` Status … `04 03 02 01`.
  - Allgemeine Werte lesen `0x0071` / schreiben `0x0070`: fernstes Tor (`0x05`, 1–16),
    nächstes Tor (`0x0A`, 0–16), Nachlaufzeit (`0x06`, 10–120 s), Meldetakt Zustand
    (`0x02`) und Entfernung (`0x0C`) in 0,1 Hz (5–80), Ansprechen (`0x0B`, 5 normal,
    10 schnell).
  - Auslöseschwellen je Tor 0–15 lesen `0x0073` / schreiben `0x0072`, Halteschwellen
    lesen `0x0077` / schreiben `0x0076`.
  - Ausgabe umschalten `0x007A`: Kurzmodus (`6E` Zustand Entfernung `62`) oder Messmodus
    (`F4 F3 F2 F1` … 16 Energiewerte zu 4 Byte … `F8 F7 F6 F5`).
  - Eine eingebaute Schwellen-Automatik (`0x0009`) gibt es; sie wird nicht verwendet
    (Entscheid Claude: sie kennt weder Zielwert noch „dahinter“).
- **Was die Messungen am Gerät gezeigt haben** (2026-11-03, Wand an ihrem Probeplatz):
  - Die Schwellen des Radars sind **Dezibel der Energiewerte**: 10·log10(Energie). Die
    Werkswerte 28–48 liegen genau im Bereich der gemessenen Werte.
  - **Ein Tor ist etwa 0,7 m lang.** Die Person stand bei 1 m vor allem in Tor 2, bei 2 m in
    Tor 3 und 4, bei 2,5 m in Tor 3 bis 5.
  - Leerer Raum: meist 26–30 dB, Spitzen bis etwa 33 dB; in Tor 0 und 1 (nah am Radar)
    Spitzen bis 42 und 47 dB.
  - Person bei 2 m liegt nur etwa 4 dB über den Spitzen des leeren Raums, und 2 m und 2,5 m
    unterscheiden sich im selben Tor nur um etwa 2 dB. Die Berechnung muss mit so kleinen
    Abständen umgehen.
  - Die Zentimeter-Angabe im Kurzmodus folgt der Person nicht (blieb 50 s auf 175 cm).
    Für die Einrichtung zählt sie nicht.
  - Der Zustand im Kurzmodus (jemand / niemand) und INT_HLK stimmten in allen Tests überein.
  - Nach dem Umschalten in den Messmodus ist die erste Meldung leer (lauter Nullen), die
    zweite hat in Tor 0 und 1 eine Spitze von 42 und 47 dB, in allen fünf Messungen, leer
    wie mit Person. Das ist das Umschalten, nicht der Raum: ohne diese Meldungen liegt der
    leere Raum auch in Tor 0 und 1 bei höchstens etwa 35 dB. Zudem kommt mitten in jeder
    Messung einmal eine leere Meldung.
  - **Fernstes Tor = Nummer des letzten Tors, das zählt** (Wert 3 heisst Tore 0 bis 3): Mit
    Wert 2 wurde die Person bei 2 m (stärkstes Tor 3, 35 dB) nicht erkannt, mit Wert 3 schon.
  - Die Energien hängen nicht von den eingestellten Schwellen und vom fernsten Tor ab: auch
    mit fernstem Tor 2 kamen alle 16 Tore.
  - Die erste Leer-Messung war verdorben, weil der Owner noch im Raum war (Tor 3 bis
    37 dB statt 31 dB). Mit solchen Werten wäre die Person bei 2 m nicht mehr sichtbar, die
    Berechnung meldet dann `NOCHMAL`. Ein solcher Fehler ist also sicher, kostet aber einen
    Anlauf; deshalb ein ausreichend langer Countdown vor der Leer-Messung.
  - Die Werkswerte dieses Radars: fernstes Tor 2, Nachlaufzeit 10 s, Ansprechen schnell,
    Auslöseschwellen 48 42 36 34 32 31…, Halteschwellen 45 42 33 32 28….
- **Tasten:** Alle sechs Tasten haben Toggle-Flipflops; jeder Pegelwechsel ist ein Druck.
  Jeder Druck setzt den ESP zurück (F4).
- **Voraussetzungen:** Menü aus Teil 4, Radar-Umschaltung, angeschlossenes Radar.
  Damit die Wand später wirklich auf das Radar reagiert, braucht es zusätzlich R48 und
  `Features::RADAR_INSTALLED = true` im ESP (nicht Teil dieser Arbeit).

## 4. Was der Owner entschieden hat

| Nr. | Entscheid |
|---|---|
| R1 | Das Radar wird vor Ort mit einem Programm auf dem Pi eingestellt, wenn die Wand an ihrem Platz hängt. |
| R2 | Bedient wird direkt an der Wand: Anweisungen auf der Anzeige, Bestätigung mit einer Taste. |
| R3 | Start im Einstellungsmenü mit `RADAR EINRICHTEN` (Teil 4 D14). |
| R5 | Nachlaufzeit etwa **30 Sekunden**. |
| R6 | Erkannt wird nur, wer davorsteht. Vorbeigehen soll die Wand nicht einschalten. |
| R7 | Das Radar wird über seine UART eingestellt. |
| R9 | Die Erkennung am gewählten Platz hat Vorrang. |
| R10 | Der Leer-Test ist streng: eine einzige Meldung gilt als nicht bestanden. Höchstens drei Anläufe; danach `FEHLER - ALTE WERTE`. |
| R11 | (2026-11-03) Man stellt einen **Zielwert** ein, zum Beispiel 2 m; erkannt wird nur, wer näher ist. |
| R12 | (2026-11-03) Die Einrichtung misst **zuerst den leeren Raum** und dann die Person **an bestimmten Entfernungen**, weil jeder Platz andere Störungen und andere Wunsch-Entfernungen hat. |
| – | (2026-11-03) Mit fernstem Tor 3 und Werks-Schwellen („etwa 2 m“) ist der Owner zufrieden: „passt so“. |

R4 und R8 sind mit R3 entfallen.

**Tasten in der Einrichtung:**
- **BT5** bestätigt bzw. wählt.
- **BT6** blättert zum nächsten Zielwert bzw. überspringt einen überspringbaren Schritt.
- **BT4** bricht ab. Das Radar bekommt seine alten Werte zurück.
- **BT2** bricht ebenso ab; danach fährt der ESP den Pi herunter.

## 5. Ablauf

### 5.1 Rahmen der Anwendung

1. Im Einstellungsmenü wählt man `RADAR EINRICHTEN` mit BT5.
2. Der Pi schaltet mit `RadarSwitch` auf das Radar und liest die Tasten selbst.
3. Am Ende schaltet `RadarSwitch` zurück; das Menü erscheint wieder. Der Pi bleibt an.

### 5.2 Schritte

Die Texte passen auf die Anzeige: 4 Zeilen zu 24 Zeichen, Umlaute umschrieben.

| Schritt | Anzeige (Beispiel) | Was passiert |
|---|---|---|
| 0 | `RADAR EINRICHTEN` / `LESE ALTE WERTE` | Der Pi liest alle Einstellungen und speichert sie als Sicherung, mit Status „laufend“. |
| 1 | `ZIELWERT 2,0 M` / `BT6 WEITER BT5 OK` | Zielwert wählen: 1,0 1,5 2,0 2,5 3,0 3,5 m, im Kreis. Vorgabe: der zuletzt gewählte, sonst 2,0 m. |
| 2 | `RAUM VERLASSEN` / `DANN BT5` | Warten auf BT5. |
| 3 | `NOCH 15 S` … | Countdown zum Hinausgehen. |
| 4 | `MESSE LEER 30 S` | Messmodus, 30 s Energien je Tor. |
| 5 | `STELL DICH AUF 2,0 M` / `DANN BT5` | Warten auf BT5. |
| 6 | `NOCH 10 S` … | Countdown. |
| 7 | `MESSE 2,0 M 20 S` / `RUHIG STEHEN` | 20 s Energien. |
| 8 | `STELL DICH AUF 2,7 M` / `BT5 OK BT6 UEBERSPR.` | Dahinter = Zielwert + 0,7 m. BT6 überspringt (Raum zu klein). |
| 9 | `NOCH 10 S` … / `MESSE 2,7 M 20 S` | Countdown, 20 s Energien. |
| 10 | `BERECHNE` | Abschnitt 6. Nicht unterscheidbar: `NOCHMAL` und zurück zu Schritt 2. |
| 11 | `SPEICHERE` | Alle Werte in einem Einstellvorgang schreiben, zurücklesen und vergleichen. Für die Tests Nachlaufzeit 10 s. |
| 12 | `TEST LEER` / `RAUM VERLASSEN - BT5` | Countdown, dann 30 s: niemand darf gemeldet werden (R10). Sonst zurück zu Schritt 2. |
| 13 | `TEST AUF 2,0 M` / `DANN BT5` | Countdown, dann bis 20 s: jemand muss gemeldet werden. Sonst zurück zu Schritt 2. |
| 14 | `TEST AUF 2,7 M` / `DANN BT5` | Nur wenn Schritt 8 gemessen wurde. Wer BT5 drückt, steht an der Wand: nach dem Countdown erst warten, bis das Radar freigibt (höchstens 20 s; gibt es nicht frei, hält es die Person dahinter fest), dann 20 s: es soll niemand gemeldet werden. Sonst nur ein Hinweis (R9). |
| 15 | `FERTIG` / `BIS ETWA 2,0 M` oder `HINWEIS GRENZE` | Nachlaufzeit 30 s schreiben, Bericht abschliessen. Warten auf BT4/BT5, dann zurück. |

Ein Fehlschlag in Schritt 12 oder 13 (oder `NOCHMAL`) zählt als Anlauf; nach dem dritten
schreibt der Pi die gesicherten Werte zurück und zeigt `FEHLER - ALTE WERTE` (R10).

Der Test „Vorbeigehen“ der alten Fassung entfällt (Entscheid Claude): Die Grenze nach hinten
prüft Schritt 14. Vorbeigehen in Reichweite lässt sich mit dem Radar nicht sicher von
Stehen trennen; ein Test dafür würde nur einen Hinweis liefern. Das Ansprechen steht dafür
auf „normal“ (Abschnitt 6).

**Abbrechen:** BT4 oder BT2 jederzeit, auch im Countdown und während einer Messung. Hat der
Pi schon etwas geschrieben, schreibt er die Sicherung zurück. Ohne Taste für 5 min in
einem Warteschritt: Abbruch wie BT4.

## 6. Berechnung (Entscheid Claude, aus den Messungen vom 2026-11-03)

Verworfen werden die Meldungen der ersten **2 s** nach dem Umschalten in den Messmodus und
jede Meldung mit lauter Nullen (Abschnitt 3). Alle Werte in dB = 10·log10(max(Energie, 1)).
Je Tor g:
- **Rauschen** `N(g)` = höchster Wert der Leer-Messung; `N95(g)` = 95. Perzentil.
- **Ziel** `P(g)` = Median der Messung am Zielwert.
- **Dahinter** `O(g)` = Median der Messung dahinter (falls gemessen).

Regeln (Abstände `M_N = 1,5 dB`, `M_O = 1,0 dB`):
1. **Sichtbar** ist ein Tor, wenn die ganzzahlige Schwelle über dem Rauschen die Person
   noch erreicht: `aufrunden(N(g) + M_N) ≤ P(g)`.
2. **Fernstes Tor F** = das höchste sichtbare Tor, für das gilt: es gibt keine Messung
   dahinter, oder `P(g) ≥ O(g) + M_O`. Gibt es kein solches Tor: `NOCHMAL`.
3. **Auslöseschwelle** für g ≤ F: `T(g) = aufrunden(N(g) + M_N)`. Am Rand (g = F) mit
   Messung dahinter: `T(F) = max(aufrunden(N(F) + M_N), runden((P(F) + O(F)) / 2))`
   (runden: ab ,5 aufwärts). Gilt danach nicht `T(F) ≤ P(F)` (möglich wegen Tor 0/1,
   Regel 5), gilt das nächstniedrigere Tor aus Regel 2 als F; bleibt keines: `NOCHMAL`.
4. **Halteschwelle** für g ≤ F: `H(g) = min(T(g), max(aufrunden(N95(g) + 1), T(g) - 3))`.
   So gibt das Radar im leeren Raum sicher frei. Eine Regel „Halteschwelle über dem
   Dahinter“ gibt es nicht: Am Gerät gab das Radar mit Halteschwelle 32 frei, obwohl der
   Median dahinter 33,2 dB war; die Nachlaufzeit fängt kurze Aussetzer ab.
5. **Tor 0 und 1** (direkt vor dem Gehäuse) werden nie empfindlicher als ab Werk:
   Auslöseschwelle mindestens 48 und 42, Halteschwelle mindestens 45 und 42. Grund: Dort
   stört die Wand selbst, etwa die Lüfter, die erst ab 40 °C laufen und bei der Leer-Messung
   vielleicht still sind. Wer so nah steht, ist in Tor 2 ohnehin laut (bei 1 m 38,9 dB).
6. Tore hinter F schaltet das fernste Tor ab; ihre Schwellen bleiben, wie sie sind.
7. **Weitere Werte:** nächstes Tor 0, Nachlaufzeit 30 s (R5; während der Tests 10 s),
   Ansprechen **normal** (5) gegen kurzes Vorbeigehen (R6), Meldetakt Zustand 8 Hz,
   Entfernung 4 Hz.
8. **Angezeigte Reichweite:** der gewählte Zielwert; der Bericht hält zusätzlich F fest.
9. **Neuer Anlauf:** misst alles neu; nichts aus dem vorigen Anlauf wird mitgenommen (eine
   verdorbene Leer-Messung soll nicht nachwirken). Nach einem verpatzten Leer-Test wird
   `M_N` für die folgenden Anläufe um 1 dB grösser, damit seltene Spitzen nicht dreimal
   hintereinander scheitern. Das Radar behält beim Messen die zuletzt geschriebenen Werte;
   die Energien hängen nicht davon ab.

Prüfung gegen die Messungen vom 2026-11-03 (Zielwert 2,0 m, dahinter 2,5 m; ohne die
ersten Meldungen nach dem Umschalten): Tor 3 ist sichtbar (aufrunden(31,3 + 1,5) = 33 ≤ 35,0)
und vom Dahinter getrennt (35,0 ≥ 33,2 + 1,0); Tor 4 ist sichtbar (34 ≤ 34,1), aber nicht
getrennt (34,1 < 33,7 + 1,0). Also F = 3, wie von Hand gefunden. Am Rand ergibt sich
T(3) = max(33, runden(34,1)) = 34 und H(3) = max(32, 31) = 32: genau die Werks-Schwellen
von Tor 3, mit denen die Wand am 2026-11-03 bei 2 m erkannt hat und bei 2,5 m nicht neu.
Die Messdaten liegen als Testdaten im Repo (Abschnitt 10).

## 7. Bericht und Sicherung

- Ordner `radar` im Konfigurationsordner (`config/radar/`).
- `sicherung.json`: die alten Werte und der Status `laufend` / `fertig`, geschrieben in
  Schritt 0. Findet die Einrichtung beim Start eine Sicherung mit Status `laufend`, schreibt
  sie zuerst diese Werte zurück (ein früherer Durchgang wurde unterbrochen).
- `einrichtung-<JJJJMMTT-hhmmss>.json`: Zielwert, Ergebnis, Kennzahlen je Tor in dB (nicht
  alle Rohdaten), alte und neue Einstellungen, Testergebnisse, Anläufe.
- `zielwert.txt`: der zuletzt gewählte Zielwert (Vorgabe für Schritt 1).

## 8. Fehlerfälle

| Fall | Verhalten |
|---|---|
| Radar antwortet nicht oder bestätigt einen Befehl nicht | `FEHLER RADAR`; Sicherung zurückschreiben, falls schon etwas geschrieben wurde |
| Messmodus liefert keine Rahmen | wie oben |
| Zurückgelesene Werte stimmen nicht | einmal neu schreiben; dann `FEHLER - ALTE WERTE` |
| Niemand drückt eine Taste | nach 5 min Abbruch wie BT4 |
| Tasten nicht lesbar | Abbruch, Sicherung zurück, `FEHLER TASTEN` |
| Jeder andere Fehler (z. B. serielle Schnittstelle, Datei) | Kurzmodus und Sicherung zurück, Bericht, dann das Fehlerbild der Anwendung |
| Am Ende jedes Abbruchs oder Fehlers | Das Radar wird in den Kurzmodus geschaltet, auch wenn nichts geschrieben wurde (die Anwendung RADAR braucht ihn) |
| Stromausfall mitten drin | Sicherung mit Status `laufend` liegt seit Schritt 0; beim nächsten Start der Einrichtung zurückschreiben (Abschnitt 7). Bis dahin können halbe Werte im Radar stehen; das nimmt der Entwurf in Kauf |

## 9. Was sich am Code ändert

- **Neu** `rpi/app/driver/uart/ld2410s.py`: Befehle nach Datenblatt, Antworten, Messmodus.
- **Neu** ein Modul mit der Berechnung aus Abschnitt 6 als reine Funktionen, dazu Sicherung
  und Bericht.
- **Neu** die Anwendung `RADAR EINRICHTEN` anstelle des Platzhalters in
  `settings_apps.py`, eingehängt in `main.py` mit derselben Radar-Umschaltung wie RADAR.
- Die Anwendung RADAR bleibt, wie sie ist.

## 10. Prüfen

**Am PC:**
- Befehle und Antworten gegen die Beispiele im Datenblatt.
- Berechnung mit den Messdaten vom 2026-11-03 (leer, 1 m, 2 m, 2,5 m): Zielwert 2,0 m mit
  dahinter 2,5 m ergibt F = 3, T(3) = 34, H(3) = 32; ohne dahinter F = 4; Zielwert 2,5 m
  ohne dahinter F = 3 (Tor 4 bräuchte 34 bei Median 33,7); Zielwert 1 m mit
  den Daten von 2 m als dahinter ergibt F = 2; die verdorbene Leer-Messung ergibt
  `NOCHMAL`.
- Der ganze Ablauf mit nachgebildetem Radar, Tasten und Uhr: Erfolg, `NOCHMAL`, Leer-Test
  scheitert dreimal, Abbruch mit BT4 vor und nach dem Schreiben, BT6 überspringt Schritt 8,
  unterbrochene Sicherung wird zurückgeschrieben.

**Am Gerät** (mit Owner):
1. Ganze Einrichtung mit Zielwert 2,0 m. Danach: leer keine Meldung, bei 2 m Meldung, bei
   2,5 m neu keine Meldung.
2. Abbruch mit BT4 mitten in einer Messung: das Radar hat danach die alten Werte.
3. Nach der Einrichtung Strom aus und wieder ein: das Radar hat die neuen Werte noch und
   sendet im Kurzmodus (am 2026-11-03 nicht geprüft; der Treiber schaltet beim Start der
   Einrichtung ohnehin in den Kurzmodus).

## 11. Was der Builder festlegt

- Messdauern und Countdown-Längen innerhalb der genannten Grössenordnung.
- Die genauen Anzeigetexte im Rahmen von 4 × 24 Zeichen.
- Das Format des Berichts.
- Wie der erlaubte Bereich der Schwellen begrenzt wird (Datenblatt nennt keinen; Werte
  0–100 annehmen und beim Zurücklesen prüfen).

## 12. Anhang: Bytes am Draht

Alle Zahlen Little Endian. Geprüft am Gerät am 2026-11-03 (Werkzeug im Abstimm-Branch).

- **Befehl:** `FD FC FB FA` · Länge (2 B) = 2 + Länge des Werts · Befehl (2 B) · Wert ·
  `04 03 02 01`.
- **Antwort:** `FD FC FB FA` · Länge · Befehl | `0x0100` (2 B) · Status (2 B, `0` = ausgeführt)
  · Daten · `04 03 02 01`. Das Längenfeld stimmt im Datenblatt-Beispiel nicht; gelesen wird
  bis zum Rahmenende.
- **Einstellmodus ein** `0x00FF`, Wert `01 00`; Daten: Protokollversion (2 B), Puffer (2 B).
  Am Gerät: `FF 01 · 00 00 · 03 00 · 80 00`. **Aus** `0x00FE`, ohne Wert.
- **Allgemeine Werte schreiben** `0x0070`, Wert = je (Kennung 2 B, Wert 4 B). **Lesen**
  `0x0071`, Wert = Kennungen zu je 2 B; Daten = die Werte zu je 4 B, in derselben
  Reihenfolge. Am Gerät für `05 0A 06 02 0C 0B`: `02 0 10 80 5 10`.
- **Auslöseschwellen** schreiben `0x0072` = je (Tor 2 B, Wert 4 B), lesen `0x0073` = Tore zu
  je 2 B, Daten 16 × 4 B. **Halteschwellen** ebenso mit `0x0076` / `0x0077`.
- **Ausgabe** `0x007A`, Wert 6 B: `00 00 01 00 00 00` Messmodus, `00 00 00 00 00 00`
  Kurzmodus.
- **Kurzmodus-Meldung:** `6E` · Zustand (1 B: 0/1 niemand, 2/3 jemand) · Entfernung cm (2 B)
  · `62`.
- **Messmodus-Meldung:** `F4 F3 F2 F1` · Länge (2 B, = 70) · `01` · Zustand (1 B) ·
  Entfernung (2 B) · reserviert (2 B) · 16 × Energie (4 B) · `F8 F7 F6 F5`.

## 13. Offen und später

- **Eigene Entfernung für RADAR:** aus den Energien je Tor statt aus der Zentimeter-Angabe.
- **R48 und `RADAR_INSTALLED`:** damit INT_HLK die Wand weckt.
- Die Anzahl Anläufe und die Abstände `M_N`, `M_O` nach den ersten Einrichtungen am
  endgültigen Platz überprüfen.
