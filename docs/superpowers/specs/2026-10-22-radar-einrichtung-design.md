# Radar-Einrichtung an der Wand – Entwurf

Stand: 2026-10-22 · Status: **Entwurf, wartet auf Freigabe durch den Owner**

Baut auf `docs/superpowers/specs/2026-10-19-esp-pi-steuerung-design.md` auf (im
Folgenden „Hauptentwurf“). Abschnittsnummern wie §8 beziehen sich auf ihn.

---

## 1. Zweck

Die Wand soll nur angehen, wenn jemand vor ihr steht. Leute, die vorbeigehen,
Bewegung im Hintergrund oder Dinge im Raum sollen sie nicht einschalten.

Wie der Raum aussieht, ist erst bekannt, wenn die Wand an ihrem endgültigen Platz
hängt. Deshalb wird das Radar nicht vorher eingestellt, sondern dort, von einem
Programm auf dem Pi. Bedient wird es direkt an der Wand: Die Anzeige zeigt die
Schritte, die Tasten bestätigen sie. Ein Laptop ist nicht nötig.

## 2. Ziele, Nicht-Ziele, Anti-Ziele

**Ziele**
- Jemand, der an der gewählten Stelle steht, wird erkannt.
- Bei leerem Raum bleibt die Wand dunkel.
- Wer in Reichweite vorbeigeht, schaltet die Wand nicht ein, soweit das Radar das
  unterscheiden kann (Abschnitt 7).
- Nach dem Weggehen bleibt die Wand noch etwa **30 Sekunden** an.
- Die Einstellungen bleiben im Radar gespeichert, auch nach einem Stromausfall.
- Ein Bericht hält fest, was gemessen und eingestellt wurde.

**Nicht-Ziele**
- Richtung oder Winkel erkennen. Das Radar misst nur Entfernung und Signalstärke.
- Personen unterscheiden.
- Die Firmware des Radars ändern.
- Laufend nachstellen. Eingestellt wird nur, wenn jemand die Einrichtung startet.

**Anti-Ziele** (wäre ein Misserfolg, auch wenn es technisch läuft)
- Die Wand geht nach der Einrichtung von selbst an.
- Die Einrichtung startet aus Versehen.
- Nach einem Abbruch oder Fehler hat das Radar halbe oder unsinnige Werte.
- Für die Einrichtung braucht es einen Laptop.

## 3. Rahmen

- **Radar:** HLK-LD2410S. Sein Ausgang INT_HLK geht an ESP-GPIO13 und Pi-GPIO22.
  Er ist HIGH, solange jemand erkannt wird, und danach noch die Nachlaufzeit lang
  (F8). Seine UART geht über den Umschalter CD4053 an die UART des Pi; GPIO23 HIGH
  schaltet auf das Radar (F1). Steckt der Flasher, ist die Verbindung zum ESP
  getrennt (F2).
- **Radar-Debug** (Entscheid S3-a, §6.3, §7): Der Pi meldet ihn mit `MODE|RADAR` an.
  Der ESP pausiert, die UART läuft mit 115 200 Baud auf das Radar. Höchstens 60 min.
- **Tasten:** BT1, BT2, BT3, BT4 und BT6 laufen über Toggle-Flipflops. Jeder Druck
  kippt einen Pegel, und der bleibt stehen (F9). BT4 und BT6 hat der Owner am
  2026-10-22 umgelötet. Wie lange eine Taste gedrückt war, kann niemand sehen.
- **Jeder Tastendruck setzt den ESP zurück** (F4). Seine Uhr fängt dann neu an.
  Was einen Neustart überstehen muss, steht im RTC-Speicher.
- **Der vorhandene Radar-Treiber** (`rpi/app/driver/uart/uart_hlk.py`):
  - Er liest die kurzen 5-Byte-Meldungen (Kopf `0x6E`, Ende `0x62`).
  - Er hat erste Befehle: Messmodus an/aus, Reichweite, Schwellen, Neustart.
  - Er schaltet das Radar aber nicht in den Einstellmodus.
  - Er wertet keine Bestätigung aus.
  - Das Format der Befehle ist nicht geprüft.
  - Er ist ein Ausgangspunkt, kein fertiger Baustein.
- **Voraussetzungen:**
  - Teil 0 (Pi eingerichtet), Teil 1 (Verbindung ESP–Pi) und Teil 2 (Ein- und
    Ausschalten, Sitzung) aus dem Hauptentwurf, §16.
  - Ein angeschlossenes Radar.
  - Die Firmware muss BT4 und BT6 wie BT1–BT3 auswerten: jeder Pegelwechsel ist ein
    Druck (heute: fallende Flanke).

## 4. Was der Owner entschieden hat (2026-10-22)

| Nr. | Entscheid |
|---|---|
| R1 | Das Radar wird vor Ort mit einem Programm auf dem Pi eingestellt, einmal, wenn die Wand an ihrem endgültigen Platz hängt. |
| R2 | Bedient wird direkt an der Wand: Anweisungen auf der Anzeige, Bestätigung mit einer Taste. |
| R3 | **Start: BT1 zehnmal hintereinander drücken**, ruhig, etwa einmal pro Sekunde. Die Wand darf dazwischen nicht ausgehen. |
| R4 | Ist der Pi aus, schaltet der ESP zuerst seine Speisung ein. |
| R5 | Nachlaufzeit etwa **30 Sekunden**. |
| R6 | Erkannt wird nur, wer davorsteht. Vorbeigehen soll die Wand nicht einschalten. |
| R7 | Das Radar wird über seine UART eingestellt. |
| R8 | Der Start mit zehn Drücken wird am Gerät auf Zuverlässigkeit geprüft (Abschnitt 10). |

**Vom Entwurf vorgeschlagen und vom Owner nicht widersprochen** (bitte beim Lesen
prüfen):
- **BT3** bestätigt jeden Schritt.
- **BT2** bricht ab. Das Radar behält dann seine alten Werte.
- Ein Bericht wird abgelegt.

## 5. Ablauf

### 5.1 Start am ESP

1. Der ESP zählt BT1-Drücke in Folge in einem RTC-Feld `button1Streak`.
   - Jeder BT1-Druck erhöht es um eins.
   - Geht die Wand aus, steht es wieder auf 0.
   - Ein anderer Tastendruck oder eine laufende Sitzung setzt es ebenfalls auf 0.
2. Bis zum neunten Druck schaltet BT1 wie gewohnt durch die Zitate (T2-a).
3. Beim **zehnten** Druck zeigt die Anzeige `RADAR EINRICHTEN`, und `button1Streak`
   steht wieder auf 0.
4. Ist der Pi aus, schaltet der ESP ihn ein und wartet auf `READY` (wie in §7).
5. Der ESP schickt dem Pi den Auftrag, die Einrichtung zu starten. Dafür braucht es
   eine neue Nachricht im Protokoll (§6.3), zum Beispiel `SETUP|RADAR`; der Pi
   antwortet `OK`.
6. Der Pi meldet `MODE|RADAR` und schaltet auf das Radar um, wie im Radar-Debug.
7. Am Ende meldet der Pi `MODE|NORMAL` und `DONE`. Hat der ESP den Pi für die
   Einrichtung eingeschaltet, fährt er ihn danach wieder herunter (wie in §7).

### 5.2 Schritte am Pi

Die Texte passen auf die Anzeige: 4 Zeilen zu 24 Zeichen, Umlaute umschrieben.

| Schritt | Anzeige (Beispiel) | Was passiert |
|---|---|---|
| 0 | `RADAR EINRICHTEN` / `ALTE WERTE GESICHERT` | Der Pi liest alle Einstellungen des Radars und speichert sie als Sicherung in einer Datei. |
| 1 | `RAUM VERLASSEN` / `DANN BT3` | Er wartet auf BT3. |
| 2 | `NOCH 15 S` … | Countdown, damit man den Raum verlassen kann. |
| 3 | `MESSE LEER 30 S` | Er misst den leeren Raum: die Signalstärke je Entfernungsbereich. |
| 4 | `AN DEINEN PLATZ` / `DANN BT3` | Er wartet auf BT3. |
| 5 | `NOCH 10 S` … | Countdown, damit man an die gewünschte Stelle gehen kann. |
| 6 | `MESSE MIT DIR 20 S` / `STILL STEHEN` | Er misst mit der Person an ihrem Platz. |
| 7 | `BERECHNE` | Er berechnet die Werte (Abschnitt 6). Ist die Person nicht klar vom Raum zu unterscheiden, folgt `NOCHMAL` und zurück zu Schritt 1. |
| 8 | `SPEICHERE` | Er schreibt alle Werte in einem Durchgang ins Radar und liest sie zur Kontrolle zurück. |
| 9 | `TEST LEER` / `RAUM VERLASSEN – BT3` | Countdown, dann 30 s leer. Das Radar darf niemanden melden. |
| 10 | `TEST MIT DIR` / `AN DEINEN PLATZ – BT3` | Countdown, dann 15 s. Das Radar muss jemanden melden. |
| 11 | `TEST VORBEIGEHEN` / `DREIMAL VORBEI – BT3` | Countdown, dann etwa 30 s, in denen man dreimal an der Wand vorbeigeht. Das Radar soll niemanden melden. |
| 12 | `FERTIG BIS 1,4 M` oder `HINWEIS VORBEIGEHEN` oder `FEHLER – ALTE WERTE` | Ergebnis. Bei einem Fehler in 8–10 schreibt er die gesicherten alten Werte zurück. |

**Abbrechen:** BT2 bricht jederzeit ab. Der Pi schreibt die gesicherten Werte
zurück, sofern er schon etwas geändert hat, und beendet sich wie in 5.1, Schritte 7.

**Tasten während der Einrichtung:**
- Die UART gehört in dieser Zeit dem Radar. `BUTTON`-Nachrichten vom ESP kommen
  deshalb nicht an.
- Der Pi erkennt BT3 und BT2 selbst: Er liest den Expander über I²C. Weil die Tasten
  Flipflops haben, bleibt jeder Druck als Pegel stehen.
- Er hält sich dabei an die I²C-Regel B (§10): Er liest erst, wenn der ESP den
  Expander gelesen und den Bus zurückgegeben hat.
- Der ESP setzt bei BT2 im Radar-Debug wie bisher `pendingShutdown` (§11).

## 6. Berechnung

Das Radar teilt die Entfernung in Bereiche („Tore“) ein. Je Tor gibt es eine
Schwelle, ab der es jemanden meldet, und eine, ab der es ihn weiter festhält. Für
jedes Tor gilt:

- **Leer-Messung:** Daraus ergibt sich das Grundrauschen je Tor, nämlich der höchste
  Wert oder ein hoher Perzentilwert über 30 s.
- **Personen-Messung:** Daraus ergibt sich, in welchen Toren die Person sichtbar ist
  und wie stark.
- **Reichweite:** Das letzte Tor, in dem die Person deutlich sichtbar ist. Tore
  dahinter werden abgeschaltet, über die maximale Reichweite oder sehr hohe
  Schwellen.
- **Schwellen:** Für die Tore bis zur Reichweite liegen sie zwischen dem Grundrauschen
  und dem Signal der Person. Sie liegen mit Abstand über dem Rauschen und mit Abstand
  unter der Person.
- **Nicht unterscheidbar:** Liegt das Signal der Person nicht klar über dem Rauschen,
  wird nichts gespeichert, und es folgt `NOCHMAL`.
- **Nachlaufzeit:** 30 s (R5).
- **Vorbeigehen (R6):** Das Radar kann jemanden, der in derselben Entfernung
  vorbeigeht, nur über Stärke und Dauer von jemandem unterscheiden, der steht.
  Die Einstellung soll ein kurzes Vorbeigehen nicht genügen lassen. Wie, legt der
  Builder fest, je nachdem, was das Radar anbietet. Gelingt das im Test (Schritt 11)
  nicht, zeigt die Anzeige `HINWEIS VORBEIGEHEN`. Die Werte bleiben trotzdem
  gespeichert, denn Leer und Person haben bestanden.

Falls der LD2410S eine eigene automatische Schwellen-Messung anbietet, darf der
Builder sie für die Leer-Messung nutzen. Reichweite, Prüfung und Bericht bleiben
wie beschrieben.

## 7. Bericht

Nach jedem Durchgang, auch nach einem Abbruch, legt der Pi einen Bericht ab, zum
Beispiel in `rpi/data/radar/einrichtung-<Datum>.json`. Er enthält:
- Datum und Ergebnis.
- Die Messwerte je Tor, leer und mit Person.
- Die alten und die neuen Einstellungen.
- Das Ergebnis der drei Tests.

Der letzte Bericht erklärt später, warum die Wand reagiert, wie sie reagiert.

## 8. Fehlerfälle

| Fall | Verhalten |
|---|---|
| Radar antwortet nicht oder bestätigt einen Befehl nicht | `FEHLER RADAR`; gesicherte Werte zurückschreiben, falls schon etwas geändert wurde; Ende wie 5.1, 7 |
| Rückgelesene Werte stimmen nicht mit den geschriebenen überein | einmal neu schreiben; dann `FEHLER – ALTE WERTE` |
| Niemand drückt BT3 | nach 5 min Abbruch wie BT2 |
| Radar-Debug länger als 60 min | wie §13 („Pi hängt im Radar-Debug“) |
| Stromausfall mitten drin | Das Radar kann halbe Werte haben. Beim nächsten Start des Pi-Dienstes wird geprüft, ob ein Bericht ohne Abschluss liegt; dann werden die gesicherten Werte zurückgeschrieben |
| Flasher steckt | Die UART zum ESP ist getrennt (F2); die Einrichtung startet nicht und der ESP zeigt `FLASHER STECKT` |

## 9. Was im Hauptentwurf dazukommt

- §6.3 Befehle: eine Nachricht ESP → Pi, um die Einrichtung zu starten.
- §10 Tasten: BT1 zehnmal in Folge startet die Einrichtung. BT4 und BT6 haben jetzt
  Flipflops.
- §11 Gespeicherter Zustand: das RTC-Feld `button1Streak`.
- §15 Offen: Nachlaufzeit des Radars → wird mit der Einrichtung auf 30 s gesetzt.
- §16 Teile: ein neuer Teil „Radar-Einrichtung“ nach Teil 2.

## 10. Prüfen

**Am PC** (ohne Hardware):
- Die Berechnung aus Abschnitt 6 mit aufgezeichneten oder erfundenen Messwerten:
  - klare Person,
  - Person kaum über dem Rauschen, das ergibt `NOCHMAL`,
  - Person im ersten oder im letzten Tor.
- Die Befehle an das Radar gegen ein nachgebildetes Radar, mit Einstellmodus, Bestätigung und
  Zurücklesen.
- Die Zählung `button1Streak` als reine Logik auf dem ESP:
  - 9 Drücke starten nichts;
  - der 10. startet;
  - wenn die Wand ausgeht, beginnt die Zählung von vorn.

**Am Gerät** (mit Owner):
1. Start: fünfmal je zehn Drücke im Sekundentakt. Die Einrichtung startet jedes Mal.
2. Neun Drücke. Es startet nichts.
3. Eine Pause von über 60 s mitten drin. Die Zählung beginnt von vorn.
4. Immer schneller drücken, bis Drücke verloren gehen. Den kürzesten sicheren Abstand
   in die Anleitung eintragen.
5. Eine ganze Einrichtung an der endgültigen Stelle. Danach 10 min leerer Raum ohne
   Einschalten, Davorstehen schaltet ein, und die Wand geht etwa 30 s nach dem
   Weggehen aus.
6. Abbruch mit BT2 mitten in Schritt 6. Das Radar hat danach wieder die alten Werte.

## 11. Was der Builder festlegt

- Die Befehle an den LD2410S, nach dessen Protokoll-Datenblatt: Einstellmodus ein
  und aus, Parameter lesen und schreiben, Messmodus mit Werten je Tor, Bestätigungen.
  Der vorhandene Treiber wird dafür überarbeitet.
- Die Faktoren der Berechnung in Abschnitt 6 und die genauen Messdauern innerhalb der
  genannten Grössenordnung.
- Die genauen Anzeigetexte im Rahmen von 4 × 24 Zeichen.
- Das Format des Berichts und wo er liegt.
- Wie der Pi die Flipflop-Pegel von BT2 und BT3 am Expander auswertet.

## 12. Offen

- **BT5:** Hängt sie noch direkt am Expander? Für die Einrichtung wird sie nicht
  gebraucht.
- **Datenblatt LD2410S:** Es muss vorliegen. Davon hängen ab: das Befehlsformat, die
  Grösse eines Tors, die Anzahl der Tore und ob es eine eingebaute
  Schwellen-Automatik gibt.
- **Radar** noch nicht angeschlossen.
