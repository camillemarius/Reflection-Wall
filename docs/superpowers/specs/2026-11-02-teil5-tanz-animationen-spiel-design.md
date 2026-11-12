# Teil 5: Tanz, Animationen und Spiel an der Wand – Entwurf

Stand 2026-11-02. Der Owner hat am 2026-11-02 gesagt: „Setze den Code um“. Grundlage
ist die Werkstatt `docs/werkstatt/wand-werkstatt.html` (Stand 3462e7f), die der Owner
am 2026-10-23 durchgespielt hat. Dieser Entwurf hält fest, was davon auf den Pi kommt.
Die Punkte, die ich selbst entschieden habe, sind als „Entscheid Claude“ markiert.

## 1. Was kommt dazu

Drei neue Anwendungen im Hauptmenü, zwischen `STRICHMAENNCHEN` und `EINSTELLUNGEN`:

| Menüpunkt | Inhalt | Tasten |
|---|---|---|
| `TANZ 3D` | Die Tanz-Show: neun Szenen (Auftritt, Solo, Einmarsch, Welle, Spiegel, Drehung, Karussell, Bravo, Abgang), 116 Schläge pro Minute, in einer Schleife; seit 2026-11-05 ohne Klone und Stadion (Abschnitt 5) | BT5 startet die Show neu, BT4 zurück |
| `ANIMATIONEN` | Die elf Animationen der Werkstatt (Equalizer, Regen, Welle, Tunnel, Feuerwerk, Pac-Man, Laufschrift, Schlange, Pong, Matrix, Lauflicht); alle 10 s die nächste | BT6 nächste Animation, BT4 zurück |
| `SPIEL` | Das Spiel „Läufer“: Kakteen überspringen, unter Vögeln ducken; Punkte und Rekord | BT5 starten / springen, BT6 ducken, BT4 zurück |

## 2. Regeln

- **Nur feste Segmentmuster.** Alles wird aus handgezeichneten Mustern je Stelle gebaut,
  genau wie in der Werkstatt. Frei gezeichnete Linien zerfallen auf den getrennten
  16-Segment-Stellen (Owner 2026-10-23).
- **Dieselbe Kodierung wie die Schrift.** Die Bits der Werkstatt (`A = 1<<5` usw.) sind
  dieselben wie in `ascii_map`; die Muster werden unverändert übernommen.
- **Gemeinsame Bausteine** stehen in `rpi/app/driver/display/segments.py` (Bits, Spiegeln,
  Zeichenfläche zu 96 Stellen, Text ab einer Spalte, 12 Ebenen).
- **Bilder gehen über `ctx.display.show_cells`**; `WallDisplay` schreibt nur Module, die sich
  geändert haben. Höchstens 20 Bilder pro Sekunde.
- **Taktgeber und Zufall sind einsteckbar** (wie bei `StickmanApp`), damit die Tests ohne
  Warten und ohne Zufall laufen.

## 3. Was nicht kommt

- **`VIDEO`** (Entscheid Claude): Die Werkstatt rechnet Video und Bilder über eine
  Zeichenfläche auf Segmente um. Das sind keine festen Muster, und laut Owner sind solche
  Bilder auf der Wand nicht erkennbar. Bleibt draussen, bis der Owner es anders will.
- **Die Modi „frei“ und „Muster“ des Tanzes** (Entscheid Claude): „frei“ zeichnet Linien;
  „Muster“ war nur der Vorläufer der Show. Auf die Wand kommt die Show.
- **Radar als Spielsteuerung**: vom Owner abgelehnt (Werkstatt, Urteil „nein“, 2026-10-23).

## 4. Einzelheiten

- **Rekord des Spiels** (Entscheid Claude): bleibt über Neustarts erhalten, in der Datei
  `spiel_rekord.txt` im Ordner `config` (wie die Themen). Fehlt oder stört die Datei, gilt 0.
- **Ruhezeit**: wie beim Strichmännchen. Die Anwendungen laufen, bis BT4 kommt oder die
  Sitzung endet.
- **Menü**: `CHAT`, `QUIZ`, `REFLECTION`, `RADAR`, `STRICHMAENNCHEN`, `TANZ 3D`,
  `ANIMATIONEN`, `SPIEL`, `EINSTELLUNGEN`.

## 5. Neue Tanz-Show (2026-11-05)

Der Owner hat die Show auf der Wand gesehen. Sein Urteil: die Blitze und Momente, in denen
die ganze Wand leuchtet, wirken mässig; das Hinein- und Hinauslaufen wirkt am besten, «ein
bisschen 3D». Statt der vollen Wand sollen die Tänzer einzeln hereinlaufen. Das Publikum
(die kleinen Figuren) findet er lustig, er hat es aber nicht als Publikum erkannt. Aus
einer Probe an der Wand fand er «Einmarsch» und «Karussell» gut. Die Reihenfolge unten hat
er am 2026-11-05 gutgeheissen («ja passt, mach so»).

| # | Szene | Halbtakte | Inhalt |
|---|---|---|---|
| 1 | Auftritt | 22 | wie Werkstatt |
| 2 | Solo | 32 | wie Werkstatt |
| 3 | Einmarsch | 30 | ersetzt Klone: Der Solist geht auf Platz 10, die fünf anderen laufen einzeln abwechselnd von rechts und links herein (innen zuerst), drehen sich nach vorne, jubeln; dann tanzen alle sechs |
| 4–6 | Welle, Spiegel, Drehung | 24, 16, 16 | wie Werkstatt |
| 7 | Karussell | 46 | ersetzt Stadion: Die sechs schwenken aus der Reihe in einen Kreis, drehen eine Runde und kommen in die Reihe zurück; vorne gross (4 Zeilen), seitlich mittel (2 Zeilen), hinten klein (1 Stelle); dann gehen fünf einzeln ab, einer stellt sich in die Mitte |
| 8 | Bravo | 16 | «BRAVO» in Zeile 2, darunter das Publikum in den unteren zwei Reihen: erst eine La Ola von links nach rechts, dann Jubel |
| 9 | Abgang | 20 | wie Werkstatt |

- **Die ganze Wand leuchtet nie**: kein Bild hat mehr als 60 der 96 Stellen an, keine Stelle
  hat alle Segmente an.
- **Fein zwischen den Halbtakten** (Entscheid Claude): Karussell und La Ola rechnen in Vierteln
  eines Halbtakts, also etwa 15 Bilder pro Sekunde. Die anderen Szenen ändern sich nur auf
  den Halbtakt. Zwischen den Halbtakten geht nur ein Bild hinaus, wenn es sich geändert hat.
- **Helligkeit je Modul** (Entscheid Claude): `WallDisplay.set_levels` setzt die Helligkeit
  der zwölf Module (0..15) und schreibt nur Änderungen. Im Karussell bekommt jedes Modul die
  Helligkeit der vordersten Figur darin (gross 15, mittel 8, klein 3), beim Bravo ist die
  hintere Publikumsreihe dunkler (7). Beim Verlassen der Show, auch mitten im Karussell, gehen
  alle Module auf 15 zurück. Anzeigen ohne `set_levels` (Terminal) zeigen alles gleich hell.
- **Verdecken**: Im Karussell deckt eine vordere Figur die hintere zu; stehen beide in
  derselben Spalte, sieht man nur die vordere.
