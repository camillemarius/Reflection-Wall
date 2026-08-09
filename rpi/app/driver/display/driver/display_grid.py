class DisplayGrid:
    """
    Mehrere SegmentChains untereinander.

    Beispiel:

        Chain 0  -> Zeile 0
        Chain 1  -> Zeile 1
        Chain 2  -> Zeile 2
        Chain 3  -> Zeile 3
    """

    def __init__(self, rows, simulation=False):
        self.rows = rows

        self.simulation = simulation

        self.total_cols = (
            self.rows[0].chars_per_chain
            if rows
            else 0
        )

        self.total_rows = len(rows)

    # =========================================================
    # CLEAR
    # =========================================================

    def clear(self):
        """Löscht das komplette Display."""

        for row in self.rows:
            row.clear()

    # =========================================================
    # TEXT
    # =========================================================

    def set_text(self, lines):
        for i, row in enumerate(self.rows):

            text = (
                lines[i]
                if i < len(lines)
                else ""
            )

            row.set_text(text)

    # =========================================================
    # SEGMENT SETZEN
    # =========================================================

    def set_segment(self, x, y, value):

        if not (0 <= x < self.total_cols):
            return

        if not (0 <= y < self.total_rows):
            return

        row = self.rows[y]

        module_index = (
            x // row.modules[0].chars_per_module
        )

        if not (
            0 <= module_index < len(row.modules)
        ):
            return

        module = row.modules[module_index]

        digit_index = (
            x % module.chars_per_module
        )

        offset = digit_index * 2

        module.buffer[offset] = (
            value & 0xFF
        )

        module.buffer[offset + 1] = (
            (value >> 8) & 0xFF
        )