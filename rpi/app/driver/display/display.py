from driver.display.driver.segment_chain import SegmentChain
from driver.display.driver.display_grid import DisplayGrid

from driver.display.driver.ht16k33_driver import (
    TestModule,
    I2CModule,
    CHARS_PER_MODULE,
    init_ht16k33,
    clear_all,
    write_buffer,
)

import pyphen
import re


# ============================================================
# SILBENTRENNUNG
# ============================================================

dic = pyphen.Pyphen(
    lang="de_DE"
)


# ============================================================
# TEXT NORMALISIEREN
# ============================================================

def normalize_text(text):
    """
    Normalisiert Text für das 16-Segment-Display.

    Umlaute werden auf ASCII-Zeichen abgebildet.
    """

    replacements = {
        "Ä": "AE",
        "Ö": "OE",
        "Ü": "UE",
        "ß": "SS",
    }

    text = text.upper()

    for key, value in replacements.items():
        text = text.replace(key, value)

    return text


# ============================================================
# WORT NACH SILBEN TRENNEN
# ============================================================

def split_word_syllables(
    word,
    max_len
):
    """
    Trennt ein langes Wort möglichst sinnvoll
    nach deutschen Silben.
    """

    hyphenated = dic.inserted(
        word
    )

    parts = hyphenated.split(
        "-"
    )

    result = []
    current = ""

    for part in parts:

        # Platz für eventuellen Bindestrich
        if len(current + part) <= max_len - 1:

            current += part

        else:

            if current:

                result.append(
                    current + "-"
                )

            current = part

    if current:

        result.append(
            current
        )

    return result


# ============================================================
# DISPLAY
# ============================================================

class Display:

    WIDTH = 24
    HEIGHT = 4

    def __init__(
        self,
        modules_per_row=3,
        rows=4,
        chars_per_module=CHARS_PER_MODULE,
        simulation=False
    ):
        """
        Erstellt das komplette Display.

        modules_per_row:
            Anzahl Module pro Zeile.

        rows:
            Anzahl Zeilen.

        chars_per_module:
            Anzahl 16-Segment-Zeichen pro Modul.

        simulation:
            True  -> Terminal-Simulation
            False -> echtes I2C-Display
        """

        self.modules_per_row = (
            modules_per_row
        )

        self.rows_count = rows

        self.chars_per_module = (
            chars_per_module
        )

        self.simulation = simulation

        # ----------------------------------------------------
        # Abmessungen
        # ----------------------------------------------------

        self.WIDTH = (
            modules_per_row
            * chars_per_module
        )

        self.HEIGHT = rows

        self.total_modules = (
            modules_per_row
            * rows
        )

        # ----------------------------------------------------
        # Module erzeugen
        # ----------------------------------------------------

        if simulation:

            self.modules = [
                TestModule(
                    i,
                    chars_per_module
                )
                for i in range(
                    self.total_modules
                )
            ]

        else:

            # Alle HT16K33-Module initialisieren
            init_ht16k33(
                self.total_modules
            )

            self.modules = [
                I2CModule(
                    i,
                    chars_per_module
                )
                for i in range(
                    self.total_modules
                )
            ]

            clear_all(
                self.modules
            )

        # ----------------------------------------------------
        # Reihen erzeugen
        # ----------------------------------------------------

        self.rows = []

        for y in range(rows):

            start = (
                y
                * modules_per_row
            )

            end = (
                start
                + modules_per_row
            )

            row_modules = self.modules[
                start:end
            ]

            self.rows.append(
                SegmentChain(
                    row_modules
                )
            )

        # ----------------------------------------------------
        # Grid
        # ----------------------------------------------------

        self.grid = DisplayGrid(
            self.rows
        )

        # ----------------------------------------------------
        # Anfangszustand
        # ----------------------------------------------------

        self.clear()


    # ========================================================
    # TEXT
    # ========================================================

    def set_text(
        self,
        text
    ):
        """
        Löscht das Display und schreibt neuen Text.
        """

        self.clear()

        text = normalize_text(
            text
        )

        lines = split_text_for_grid(
            text,
            self.chars_per_module,
            self.modules_per_row,
            self.rows_count
        )

        self.grid.set_text(
            lines
        )

        if self.simulation:

            print_grid_matrix_horizontal(
                self.rows
            )


    # ========================================================
    # PIXEL SETZEN
    # ========================================================

    def set_pixel(
        self,
        x,
        y,
        state=True
    ):
        """
        Schaltet ein komplettes 16-Segment-Zeichen.

        Koordinatensystem:

            x = 0                 links
            x = WIDTH-1           rechts

            y = 0                 unten
            y = HEIGHT-1          oben

        Das ist wichtig für den RadarGraph.
        """

        # ----------------------------------------------------
        # Grenzen
        # ----------------------------------------------------

        if not (
            0 <= x < self.WIDTH
        ):
            return

        if not (
            0 <= y < self.HEIGHT
        ):
            return

        # ----------------------------------------------------
        # Display-Zeile
        #
        # Intern ist die erste Reihe oben.
        # Für das logische Koordinatensystem ist y=0 unten.
        # ----------------------------------------------------

        row = self.rows[
            self.rows_count - 1 - y
        ]

        # ----------------------------------------------------
        # Modul bestimmen
        # ----------------------------------------------------

        module_index = (
            x
            // self.chars_per_module
        )

        if module_index >= len(
            row.modules
        ):
            return

        module = row.modules[
            module_index
        ]

        # ----------------------------------------------------
        # Zeichenposition innerhalb des Moduls
        # ----------------------------------------------------

        digit_index = (
            x
            % self.chars_per_module
        )

        # ====================================================
        # SIMULATION
        # ====================================================

        if self.simulation:

            module.buffer[
                digit_index
            ] = (
                "█"
                if state
                else " "
            )

            return

        # ====================================================
        # ECHTES MODUL
        # ====================================================

        offset = (
            digit_index
            * 2
        )

        # ----------------------------------------------------
        # Alle 16 Segmente
        # ----------------------------------------------------

        if state:

            value = 0xFFFF

        else:

            value = 0x0000

        # ----------------------------------------------------
        # Buffer schreiben
        # ----------------------------------------------------

        module.buffer[
            offset
        ] = value & 0xFF

        module.buffer[
            offset + 1
        ] = (
            value >> 8
        ) & 0xFF


    # ========================================================
    # KOMPLETTE SPALTE
    # ========================================================

    def set_column(
        self,
        x,
        state=True
    ):
        """
        Schaltet eine komplette vertikale Spalte.
        """

        if not (
            0 <= x < self.WIDTH
        ):
            return

        for y in range(
            self.HEIGHT
        ):

            self.set_pixel(
                x,
                y,
                state
            )


    # ========================================================
    # ALLES LÖSCHEN
    # ========================================================

    def clear(self):
        """
        Löscht den kompletten Buffer.

        Wichtig:
        Diese Funktion schreibt bei echtem I2C
        direkt den leeren Buffer auf die Hardware.
        """

        # ----------------------------------------------------
        # Buffer löschen
        # ----------------------------------------------------

        for module in self.modules:

            if self.simulation:

                module.clear()

            else:

                module.buffer = [
                    0x00
                ] * (
                    CHARS_PER_MODULE * 2
                )

        # ----------------------------------------------------
        # Hardware löschen
        # ----------------------------------------------------

        if not self.simulation:

            for module in self.modules:

                write_buffer(
                    module.index,
                    module.buffer
                )

        # ----------------------------------------------------
        # Simulation
        # ----------------------------------------------------

        if self.simulation:

            print_grid_matrix_horizontal(
                self.rows
            )


    # ========================================================
    # REFRESH
    # ========================================================

    def refresh(self):
        """
        Schreibt den aktuellen Buffer auf das Display.
        """

        # ----------------------------------------------------
        # Simulation
        # ----------------------------------------------------

        if self.simulation:

            print_grid_matrix_horizontal(
                self.rows
            )

            return

        # ----------------------------------------------------
        # Echtes Display
        # ----------------------------------------------------

        for module in self.modules:

            write_buffer(
                module.index,
                module.buffer
            )

    # ============================================================
    # 16 SEGMENTE SETZEN
    # ============================================================
    def set_segments(self,x,y,value):
        """
        Setzt eine 16-Bit-Segmentmaske
        über das DisplayGrid.
        """

        self.grid.set_segment(
            x,
            y,
            value
        )

# ============================================================
# TEXT AUF GRID AUFTEILEN
# ============================================================

def split_text_for_grid(
    text,
    chars_per_module,
    modules_per_row,
    max_rows
):
    """
    Teilt einen Text automatisch auf das 4x24-Display auf.

    Lange Wörter werden nach Silben getrennt.
    """

    max_line_len = (
        chars_per_module
        * modules_per_row
    )

    # --------------------------------------------------------
    # Absätze
    # --------------------------------------------------------

    paragraphs = text.split(
        "\n"
    )

    lines = []

    # --------------------------------------------------------
    # Jeden Absatz bearbeiten
    # --------------------------------------------------------

    for paragraph in paragraphs:

        tokens = re.findall(
            r"\w+|[.,!?;:]",
            paragraph
        )

        # ----------------------------------------------------
        # Satzzeichen an vorheriges Wort anhängen
        # ----------------------------------------------------

        words = []

        for token in tokens:

            if (
                token in ".,!?;:"
                and words
            ):

                words[-1] += token

            else:

                words.append(
                    token
                )

        current_line = ""

        # ----------------------------------------------------
        # Leerer Absatz
        # ----------------------------------------------------

        if not words:

            lines.append(
                " " * max_line_len
            )

            if len(lines) >= max_rows:

                return lines

            continue

        # ----------------------------------------------------
        # Wörter
        # ----------------------------------------------------

        for word in words:

            # ------------------------------------------------
            # Zu langes Wort
            # ------------------------------------------------

            if len(word) > max_line_len:

                parts = split_word_syllables(
                    word,
                    max_line_len
                )

                for i, part in enumerate(parts):

                    if i == 0:

                        word = part

                    else:

                        lines.append(
                            part.ljust(
                                max_line_len
                            )
                        )

                        if (
                            len(lines)
                            >= max_rows
                        ):

                            return lines

                continue

            # ------------------------------------------------
            # Erste Wort der Zeile
            # ------------------------------------------------

            if not current_line:

                current_line = word

            # ------------------------------------------------
            # Wort passt noch
            # ------------------------------------------------

            elif (
                len(current_line)
                + 1
                + len(word)
                <= max_line_len
            ):

                current_line += (
                    " "
                    + word
                )

            # ------------------------------------------------
            # Wort passt nicht mehr
            # ------------------------------------------------

            else:

                remaining_space = (
                    max_line_len
                    - len(current_line)
                    - 1
                )

                # --------------------------------------------
                # Wort teilweise in aktuelle Zeile setzen
                # --------------------------------------------

                if remaining_space > 1:

                    part = (
                        word[
                            :remaining_space - 1
                        ]
                        + "-"
                    )

                    current_line += (
                        " "
                        + part
                    )

                    lines.append(
                        current_line.ljust(
                            max_line_len
                        )
                    )

                    word = word[
                        remaining_space - 1:
                    ]

                    current_line = word

                # --------------------------------------------
                # Kein sinnvoller Platz
                # --------------------------------------------

                else:

                    lines.append(
                        current_line.ljust(
                            max_line_len
                        )
                    )

                    current_line = word

            # ------------------------------------------------
            # Maximalzahl Zeilen erreicht
            # ------------------------------------------------

            if len(lines) >= max_rows:

                return lines

        # ----------------------------------------------------
        # Zeile abschließen
        # ----------------------------------------------------

        if current_line:

            lines.append(
                current_line.ljust(
                    max_line_len
                )
            )

            if len(lines) >= max_rows:

                return lines

    # --------------------------------------------------------
    # Restliche Zeilen auffüllen
    # --------------------------------------------------------

    while len(lines) < max_rows:

        lines.append(
            " " * max_line_len
        )

    return lines





    if not (0 <= module_index <len(row.modules)):
        return

    module = row.modules[module_index]

    # --------------------------------------------------------
    # Zeichenposition
    # --------------------------------------------------------
    digit_index = (x % self.chars_per_module)

    # ========================================================
    # SIMULATION
    # ========================================================
    if self.simulation:

        # In der Simulation können wir nur darstellen,
        # ob das Zeichen überhaupt aktiv ist.

        module.buffer[digit_index] = ("█"if value else " ")
        return

    # ========================================================
    # ECHTES HT16K33
    # ========================================================
    offset = (digit_index * 2)

    # --------------------------------------------------------
    # Low Byte
    # --------------------------------------------------------
    module.buffer[offset] = (value & 0xFF)

    # --------------------------------------------------------
    # High Byte
    # --------------------------------------------------------
    module.buffer[offset + 1] = ((value >> 8) & 0xFF)



# ============================================================
# SIMULATION
# ============================================================

def print_grid_matrix_horizontal(
    rows
):
    """
    Gibt die vier Displayzeilen horizontal aus.

    Beispiel:

    ABCDEFGH;IJKLMNOP;QRSTUVWX
    ...
    ---------------------------
    """

    if not rows:
        return

    # --------------------------------------------------------
    # Zeichenanzahl pro Modul
    # --------------------------------------------------------

    if not rows[0].modules:

        return

    chars_per_module = (
        rows[0]
        .modules[0]
        .chars_per_module
    )

    # --------------------------------------------------------
    # Reihen ausgeben
    # --------------------------------------------------------

    for row in rows:

        row_str = ""

        for module in row.modules:

            row_str += (
                "".join(
                    module.buffer
                )
                + ";"
            )

        print(
            row_str.rstrip(";")
        )

    # --------------------------------------------------------
    # Trennlinie
    # --------------------------------------------------------

    total_cols = (
        len(rows[0].modules)
        * (chars_per_module + 1)
        - 1
    )

    print(
        "-" * total_cols
    )


# ============================================================
# TEST
# ============================================================

if __name__ == "__main__":

    display = Display(
        modules_per_row=3,
        rows=4,
        simulation=True
    )

    display.set_text(
        "Hallo James, das ist ein langer "
        "Text, der automatisch auf die "
        "vier Zeilen des Grids aufgeteilt "
        "wird. Viel Spaß beim Testen!"
    )
