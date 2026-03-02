from ui.segment_chain import SegmentChain
from ui.display_grid import DisplayGrid
from driver.ht16k33_driver import TestModule, I2CModule, CHARS_PER_MODULE, init_ht16k33, clear_all

# ----- Display Platzhalter-Klasse -----
class Display:
    def __init__(self, modules_per_row=3, rows=4, chars_per_module=CHARS_PER_MODULE, simulation=False):
        """
        Erzeugt ein Display-Objekt.
        simulation=True  -> TestModule (Terminal)
        simulation=False -> echte Module (I2C)
        """
        self.modules_per_row = modules_per_row
        self.rows_count = rows
        self.chars_per_module = chars_per_module
        self.simulation = simulation

        self.total_modules = modules_per_row * rows

        # Module erzeugen
        if simulation:
            self.modules = [TestModule(i, chars_per_module) for i in range(self.total_modules)]
        else:
            # Init aller echten Module
            init_ht16k33(self.total_modules)
            self.modules = [I2CModule(i, chars_per_module) for i in range(self.total_modules)]
            clear_all(self.modules)

        # SegmentChains und Grid
        self.rows = [SegmentChain(self.modules[i*modules_per_row:(i+1)*modules_per_row])
                     for i in range(rows)]
        self.grid = DisplayGrid(self.rows)

    def set_text(self, text):
        """Text automatisch auf Zeilen aufteilen und auf Grid setzen"""
        line_length = self.modules_per_row * self.chars_per_module
        lines = split_text_for_grid(
            text,
            self.chars_per_module,
            self.modules_per_row,
            self.rows_count
        )
        self.grid.set_text(lines)

        if self.simulation:
            print_grid_matrix_horizontal(self.rows)

    def clear(self):
        """Alles löschen"""
        self.grid.clear()
        if self.simulation:
            print_grid_matrix_horizontal(self.rows)


# ----- Hilfsfunktionen -----
def split_text_for_grid(text, chars_per_module, modules_per_row, max_rows):
    max_line_len = chars_per_module * modules_per_row

    words = text.split()
    lines = []
    current_line = ""

    for word in words:
        # Falls ein einzelnes Wort länger als eine Zeile ist,
        # brechen wir es kontrolliert in Zeilenstücke
        while len(word) > max_line_len:
            if len(lines) < max_rows:
                lines.append(word[:max_line_len])
                word = word[max_line_len:]
            else:
                return lines

        if not current_line:
            current_line = word
        elif len(current_line) + 1 + len(word) <= max_line_len:
            current_line += " " + word
        else:
            lines.append(current_line.ljust(max_line_len))
            current_line = word

        if len(lines) >= max_rows:
            break

    if len(lines) < max_rows and current_line:
        lines.append(current_line.ljust(max_line_len))

    while len(lines) < max_rows:
        lines.append(" " * max_line_len)

    return lines




def print_grid_matrix_horizontal(rows):
    """Module horizontal nebeneinander drucken (Simulation)"""
    if not rows:
        return

    chars_per_module = rows[0].modules[0].chars_per_module

    for row in rows:
        row_str = ""
        for module in row.modules:
            row_str += "".join(module.buffer) + ";"
        print(row_str.rstrip(";"))

    # Trenner passend zur Breite
    total_cols = len(rows[0].modules) * (chars_per_module + 1) - 1
    print("-" * total_cols)


# ----- Beispiel Nutzung -----
if __name__ == "__main__":
    display = Display(simulation=True)  # True = Terminal, False = I2C
    display.set_text(
        "Hallo James, das ist ein langer Text, der automatisch auf die 4 Zeilen des Grids aufgeteilt wird. Viel Spaß beim Testen!"
    )
