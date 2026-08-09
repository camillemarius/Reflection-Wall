from segment_chain import SegmentChain
from display_grid import DisplayGrid

from ht16k33_driver import (
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
# Silbentrennung
# ============================================================

dic = pyphen.Pyphen(
    lang="de_DE"
)


# ============================================================
# Text normalisieren
# ============================================================

def normalize_text(text):

    replacements = {
        "Ä": "AE",
        "Ö": "OE",
        "Ü": "UE",
        "ß": "SS",
    }

    text = text.upper()

    for k, v in replacements.items():

        text = text.replace(
            k,
            v
        )

    return text


# ============================================================
# Wort trennen
# ============================================================

def split_word_syllables(
    word,
    max_len
):

    hyphenated = dic.inserted(
        word
    )

    parts = hyphenated.split(
        "-"
    )

    result = []
    current = ""

    for part in parts:

        if len(
            current + part
        ) <= max_len - 1:

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
# Display
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

        self.modules_per_row = (
            modules_per_row
        )

        self.rows_count = rows

        self.chars_per_module = (
            chars_per_module
        )

        self.simulation = simulation

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
        # Module
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
        # Reihen
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

            row_modules = (
                self.modules[
                    start:end
                ]
            )

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

        self.clear()


    # ========================================================
    # Text
    # ========================================================

    def set_text(
        self,
        text
    ):

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
    # Pixel setzen
    # ========================================================

    def set_pixel(
        self,
        x,
        y,
        state=True
    ):

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
        # Reihe
        # ----------------------------------------------------

        row = self.rows[self.rows_count - 1 - y]

        # ----------------------------------------------------
        # Modul
        # ----------------------------------------------------

        module_index = (
            x
            // self.chars_per_module
        )

        # ----------------------------------------------------
        # Position im Modul
        # ----------------------------------------------------

        digit_index = (
            x
            % self.chars_per_module
        )

        module = row.modules[
            module_index
        ]

        # ====================================================
        # Simulation
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
        # Echtes Modul
        # ====================================================

        offset = (
            digit_index * 2
        )

        # ----------------------------------------------------
        # ALLE 16 SEGMENTE
        # ----------------------------------------------------

        ALL_SEGMENTS = 0xFFFF

        if state:

            value = ALL_SEGMENTS

        else:

            value = 0x0000

        # ----------------------------------------------------
        # Buffer
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
    # Komplette Spalte
    # ========================================================

    def set_column(
        self,
        x,
        state=True
    ):

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
    # Alles löschen
    # ========================================================

    def clear(self):

        # Buffer direkt löschen

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
        # Hardware sofort löschen
        # ----------------------------------------------------

        if not self.simulation:

            for module in self.modules:

                write_buffer(
                    module.index,
                    module.buffer
                )

        if self.simulation:

            print_grid_matrix_horizontal(
                self.rows
            )


    # ========================================================
    # Refresh
    # ========================================================

    def refresh(self):

        if self.simulation:

            print_grid_matrix_horizontal(
                self.rows
            )

            return

        # ----------------------------------------------------
        # ALLE 12 Module schreiben
        # ----------------------------------------------------

        for module in self.modules:

            write_buffer(
                module.index,
                module.buffer
            )


# ============================================================
# Text auf Grid aufteilen
# ============================================================

def split_text_for_grid(
    text,
    chars_per_module,
    modules_per_row,
    max_rows
):

    max_line_len = (
        chars_per_module
        * modules_per_row
    )

    paragraphs = text.split(
        "\n"
    )

    lines = []

    for paragraph in paragraphs:

        tokens = re.findall(
            r"\w+|[.,!?;:]",
            paragraph
        )

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

        if not words:

            lines.append(
                " " * max_line_len
            )

            if len(lines) >= max_rows:

                return lines

            continue

        for word in words:

            # ------------------------------------------------
            # Lange Wörter
            # ------------------------------------------------

            if len(word) > max_line_len:

                parts = (
                    split_word_syllables(
                        word,
                        max_line_len
                    )
                )

                for i, part in enumerate(
                    parts
                ):

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
            # Neues Wort
            # ------------------------------------------------

            if not current_line:

                current_line = word

            elif (
                len(current_line)
                + 1
                + len(word)
                <= max_line_len
            ):

                current_line += (
                    " " + word
                )

            else:

                remaining_space = (
                    max_line_len
                    - len(current_line)
                    - 1
                )

                if remaining_space > 1:

                    part = (
                        word[
                            :remaining_space - 1
                        ]
                        + "-"
                    )

                    current_line += (
                        " " + part
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

                else:

                    lines.append(
                        current_line.ljust(
                            max_line_len
                        )
                    )

                    current_line = word

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
    # Auffüllen
    # --------------------------------------------------------

    while len(lines) < max_rows:

        lines.append(
            " " * max_line_len
        )

    return lines


# ============================================================
# Simulation
# ============================================================

def print_grid_matrix_horizontal(
    rows
):

    if not rows:
        return

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

    print(
        "-" * 24
    )