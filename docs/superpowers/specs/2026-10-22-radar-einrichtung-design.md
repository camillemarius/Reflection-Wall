# Radar-Einrichtung an der Wand – Entwurf

Stand: 2026-10-22, angepasst an Teil 4 am 2026-10-25 · Status: **Entwurf, wartet auf Freigabe durch den Owner**

Teil 4 (`2026-10-23-menue-und-anwendungen-design.md`) hat den Start und die Tasten geändert: Die Einrichtung startet im
Einstellungsmenü, BT5 bestätigt, BT4 bricht ab. Die betroffenen Stellen sind unten
nachgeführt.

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
- **Tasten:** Alle sechs Tasten laufen über Toggle-Flipflops (Owner, 2026-10-23).
  Jeder Druck kippt einen Pegel, und der bleibt stehen (F9). Wie lange eine Taste gedrückt war, kann niemand sehen.
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
    Ausschalten, Sitzung) aus dem Hauptentwurf, §16, und das Menü aus Teil 4.
  - Ein angeschlossenes Radar.
  - Die Firmware muss BT4–BT6 wie BT1–BT3 auswerten: jeder Pegelwechsel ist ein
    Druck (heute: `InputTrigger::NONE`). Das kommt mit Teil 4.

## 4. Was der Owner entschieden hat (2026-10-22)

| Nr. | Entscheid |
|---|---|
| R1 | Das Radar wird vor Ort mit einem Programm auf dem Pi eingestellt, einmal, wenn die Wand an ihrem endgültigen Platz hängt. |
| R2 | Bedient wird direkt an der Wand: Anweisungen auf der Anzeige, Bestätigung mit einer Taste. |
| R3 | *Ersetzt durch Teil 4 D14:* Start im Einstellungsmenü mit `RADAR EINRICHTEN`. ~~BT1 zehnmal hintereinander drücken~~ |
| R4 | *Entfällt:* Wer das Menü bedient, hat den Pi schon eingeschaltet. |
| R5 | Nachlaufzeit etwa **30 Sekunden**. |
| R6 | Erkannt wird nur, wer davorsteht. Vorbeigehen soll die Wand nicht einschalten. |
| R7 | Das Radar wird über seine UART eingestellt. |
| R8 | *Entfällt* mit R3. |
| R9 | Die Erkennung am gewählten Platz hat Vorrang. Die Reichweite wird nie unter diesen Platz gekürzt. Schalten Vorbeigehende die Wand trotzdem ein, zeigt die Anzeige nur `HINWEIS VORBEIGEHEN`. |
| R10 | Der Leer-Test ist streng: Eine einzige Meldung in den 30 s gilt als nicht bestanden. Höchstens drei Anläufe; danach `FEHLER – ALTE WERTE`, und das Radar behält seine bisherigen Einstellungen. |

**Tasten (Teil 4 D14, F7):**
- **BT5** bestätigt jeden Schritt.
- **BT4** bricht ab. Das Radar behält dann seine alten Werte.
- **BT2** bricht ebenso ab; danach fährt der ESP den Pi herunter.

**Vom Entwurf vorgeschlagen und vom Owner nicht widersprochen:** Ein Bericht wird abgelegt.

## 5. Ablauf

### 5.1 Start im Menü (Teil 4)

1. Im Einstellungsmenü wählt man `RADAR EINRICHTEN` mit BT5. Der Pi läuft schon.
2. Der Pi schaltet über die Radar-Umschaltung (Teil 4 F4) auf das Radar:
   `MODE|RADAR`, `OK` abwarten, GPIO23 HIGH, 115 200 Baud.
3. Ab hier liest der Pi die Tasten selbst. Setzt ein Tastendruck den ESP zurück,
   liest der ESP nur den Expander, merkt sich BT2 als `pendingShutdown` (§11) und
   fasst die Anzeige nicht an.
4. Am Ende schaltet der Pi zurück (`MODE|NORMAL`) und zeigt wieder die Einstellungen.
   Er bleibt an und schickt kein `DONE` (Teil 4 F7).

### 5.2 Schritte am Pi

Die Texte passen auf die Anzeige: 4 Zeilen zu 24 Zeichen, Umlaute umschrieben.

| Schritt | Anzeige (Beispiel) | Was passiert |
|---|---|---|
| 0 | `RADAR EINRICHTEN` / `ALTE WERTE GESICHERT` | Der Pi liest alle Einstellungen des Radars und speichert sie als Sicherung in einer Datei. |
| 1 | `RAUM VERLASSEN` / `DANN BT5` | Er wartet auf BT5. |
| 2 | `NOCH 15 S` … | Countdown, damit man den Raum verlassen kann. |
| 3 | `MESSE LEER 30 S` | Er misst den leeren Raum: die Signalstärke je Entfernungsbereich. |
| 4 | `AN DEINEN PLATZ` / `DANN BT5` | Er wartet auf BT5. |
| 5 | `NOCH 10 S` … | Countdown, damit man an die gewünschte Stelle gehen kann. |
| 6 | `MESSE MIT DIR 20 S` / `STILL STEHEN` | Er misst mit der Person an ihrem Platz. |
| 7 | `BERECHNE` | Er berechnet die Werte (Abschnitt 6). Ist die Person nicht klar vom Raum zu unterscheiden, folgt `NOCHMAL` und zurück zu Schritt 1. |
| 8 | `SPEICHERE` | Er schreibt alle Werte in einem Durchgang ins Radar und liest sie zur Kontrolle zurück. |
| 9 | `TEST LEER` / `RAUM VERLASSEN – BT5` | Countdown, dann 30 s leer. Das Radar darf niemanden melden, auch nicht einmal (R10). Sonst zurück zu Schritt 1, höchstens dreimal insgesamt. |
| 10 | `TEST MIT DIR` / `AN DEINEN PLATZ – BT5` | Countdown, dann 15 s. Das Radar muss jemanden melden. |
| 11 | `TEST VORBEIGEHEN` / `DREIMAL VORBEI – BT5` | Countdown, dann etwa 30 s, in denen man dreimal an der Wand vorbeigeht. Das Radar soll niemanden melden. |
| 12 | `FERTIG BIS 1,4 M` oder `HINWEIS VORBEIGEHEN` oder `FEHLER – ALTE WERTE` | Ergebnis. Bei einem Fehler in 8–10 schreibt er die gesicherten alten Werte zurück. |

**Abbrechen:** BT4 bricht jederzeit ab. Der Pi schreibt die gesicherten Werte
zurück, sofern er schon etwas geändert hat, und endet wie in 5.1, Schritt 4. BT2 tut
dasselbe; danach fährt der ESP den Pi herunter (Teil 4 F7).

**Tasten während der Einrichtung:**
- Die UART gehört in dieser Zeit dem Radar. `BUTTON`-Nachrichten vom ESP kommen
  deshalb nicht an.
- Der Pi erkennt BT5, BT4 und BT2 selbst: Er liest den Expander über I²C. Weil die Tasten
  Flipflops haben, bleibt jeder Druck als Pegel stehen.
- Ein Druck ist jede Änderung des Pegels gegenüber dem zuletzt gelesenen Stand.
  Beim Beginn jedes Warteschritts liest der Pi den Stand neu ein. Ein BT5-Druck
  davor oder während eines Countdowns zählt nicht.
- BT4 und BT2 brechen jederzeit ab, auch während eines Countdowns.
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
- **Nachlaufzeit:** 30 s (R5), als Parameter im Radar. Erlaubt das Radar weniger,
  verlängert der ESP die Zeit selbst um den Rest. Dafür gibt es eine Konstante in
  der Firmware.
- **Tests (Schritte 9–11):** Massgeblich ist der Ausgang INT_HLK (Pi-GPIO22), denn
  auf ihn reagiert die Wand. Während der Tests setzt der Pi die Nachlaufzeit
  vorübergehend auf den kleinsten Wert. So reicht eine Meldung nicht in den
  nächsten Test hinein. Die 30 s schreibt er ganz zum Schluss.
- **Vorbeigehen (R6):** Das Radar kann jemanden, der in derselben Entfernung
  vorbeigeht, nur über Stärke und Dauer von jemandem unterscheiden, der steht.
  Die Einstellung soll ein kurzes Vorbeigehen nicht genügen lassen. Wie, legt der
  Builder fest, je nachdem, was das Radar anbietet. Die Reichweite wird dafür nie
  unter den gewählten Platz gekürzt (R9). Gelingt es im Test (Schritt 11) nicht,
  zeigt die Anzeige `HINWEIS VORBEIGEHEN`. Die Werte bleiben trotzdem gespeichert,
  denn Leer und Person haben bestanden.
- **Anläufe:** `NOCHMAL` (Schritt 7) und ein nicht bestandener Leer- oder
  Personen-Test (Schritte 9 und 10) führen zurück zu Schritt 1. Nach dem dritten
  Anlauf ohne Erfolg schreibt der Pi die gesicherten Werte zurück und zeigt
  `FEHLER – ALTE WERTE` (R10).

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
| Niemand drückt BT5 | nach 5 min Abbruch wie BT4 |
| Radar-Debug länger als 60 min | wie §13 („Pi hängt im Radar-Debug“) |
| Stromausfall mitten drin | Der Pi schreibt alle neuen Werte in einem einzigen Einstellvorgang (Schritt 8). Halbe Werte entstehen nur, wenn der Strom genau in dieser etwa einen Sekunde ausfällt. Sicherung und Bericht mit Status „laufend“ entstehen schon in Schritt 0. Beim nächsten Start des Pi-Dienstes, in irgendeiner Sitzung, prüft er das und schreibt bei Bedarf die alten Werte zurück. Bis dahin können halbe Werte im Radar stehen; das nimmt der Entwurf in Kauf |

## 9. Was im Hauptentwurf dazukommt

Entfällt. Was der Hauptentwurf durch Teil 4 und diese Einrichtung braucht, steht im
Entwurf von Teil 4, Abschnitt 12, und ist dort eingetragen.

## 10. Prüfen

**Am PC** (ohne Hardware):
- Die Berechnung aus Abschnitt 6 mit aufgezeichneten oder erfundenen Messwerten:
  - klare Person,
  - Person kaum über dem Rauschen, das ergibt `NOCHMAL`,
  - Person im ersten oder im letzten Tor.
- Die Befehle an das Radar gegen ein nachgebildetes Radar, mit Einstellmodus, Bestätigung und
  Zurücklesen.

**Am Gerät** (mit Owner):
1. Eine ganze Einrichtung an der endgültigen Stelle, gestartet im Einstellungsmenü. Danach 10 min leerer Raum ohne
   Einschalten, Davorstehen schaltet ein, und die Wand geht etwa 30 s nach dem
   Weggehen aus.
2. Abbruch mit BT4 mitten in Schritt 6. Das Radar hat danach wieder die alten Werte.
3. Abbruch mit BT2 mitten in Schritt 6. Alte Werte zurück, danach fährt der Pi herunter.

## 11. Was der Builder festlegt

- Die Befehle an den LD2410S, nach dessen Protokoll-Datenblatt: Einstellmodus ein
  und aus, Parameter lesen und schreiben, Messmodus mit Werten je Tor, Bestätigungen.
  Der Builder darf den Treiber neu schreiben. Das 5-Byte-Format des heutigen Codes
  (`0x6E` … `0x62`) ist der Kurzmodus; für die Messung braucht es den Messmodus mit
  Werten je Tor. `rpi/app/applications/Animations/Radar.py` nutzt den alten Treiber
  und muss danach weiter laufen.
- Die Faktoren der Berechnung in Abschnitt 6 und die genauen Messdauern innerhalb der
  genannten Grössenordnung.
- Die genauen Anzeigetexte im Rahmen von 4 × 24 Zeichen.
- Das Format des Berichts und wo er liegt.
- Wie der Pi die Flipflop-Pegel von BT5, BT4 und BT2 am Expander auswertet.

## 12. Offen

- **Datenblatt LD2410S:** Es muss vorliegen. Davon hängen ab: das Befehlsformat, die
  Grösse eines Tors, die Anzahl der Tore und ob es eine eingebaute
  Schwellen-Automatik gibt.
- **Radar** noch nicht angeschlossen.
