# Teil 5: Tanz, Animationen und Spiel an der Wand – Entwurf

Stand 2026-11-02. Der Owner hat am 2026-11-02 gesagt: „Setze den Code um“. Grundlage
ist die Werkstatt `docs/werkstatt/wand-werkstatt.html` (Stand 3462e7f), die der Owner
am 2026-10-23 durchgespielt hat. Dieser Entwurf hält fest, was davon auf den Pi kommt.
Die Punkte, die ich selbst entschieden habe, sind als „Entscheid Claude“ markiert.

## 1. Was kommt dazu

Drei neue Anwendungen im Hauptmenü, zwischen `STRICHMAENNCHEN` und `EINSTELLUNGEN`:

| Menüpunkt | Inhalt | Tasten |
|---|---|---|
| `TANZ 3D` | Die Tanz-Show der Werkstatt: neun Szenen (Auftritt, Solo, Klone, Welle, Spiegel, Drehung, Stadion, Bravo, Abgang), 116 Schläge pro Minute, in einer Schleife | BT5 startet die Show neu, BT4 zurück |
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
