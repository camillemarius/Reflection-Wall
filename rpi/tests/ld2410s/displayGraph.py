class RadarGraph:
    """
    Radar-Anzeige für ein 24x4 16-Segment-Display.

    Eine Position entspricht einem kompletten 16-Segment-Zeichen.

        y=0   [ ][ ][ ][ ][ ]...
        y=1   [ ][ ][ ][ ][ ]...
        y=2   [ ][ ][ ][ ][ ]...
        y=3   [ ][ ][ ][ ][ ]...

    Die Distanz bestimmt die X-Position.
    An dieser Position leuchten alle vier Zeichen
    übereinander.
    """

    def __init__(self, display, max_distance=6.0):
        self.display = display
        self.max_distance = max_distance

    def update(self, distance):
        if distance is None:
            return

        # Distanz begrenzen
        distance = max(
            0.0,
            min(float(distance), self.max_distance)
        )

        # -------------------------------------------------
        # Distanz -> X-Position
        # -------------------------------------------------

        x = round(
            distance / self.max_distance
            * (self.display.modules_per_row * self.display.chars_per_module - 1)
        )

        # -------------------------------------------------
        # Komplettes Display löschen
        # -------------------------------------------------

        self.display.clear()

        # -------------------------------------------------
        # Eine komplette vertikale Linie zeichnen
        # -------------------------------------------------

        for row in self.display.rows:

            # Wir setzen genau ein komplettes
            # 16-Segment-Zeichen auf dieser Zeile.
            self._set_segment(row, x)

        # -------------------------------------------------
        # Anzeige aktualisieren
        # -------------------------------------------------

        self._refresh()

    def _set_segment(self, row, x):
        """
        Schaltet ein einzelnes 16-Segment-Zeichen
        innerhalb einer SegmentChain ein.
        """

        chars_per_module = self.display.chars_per_module

        # Welches Modul?
        module_index = x // chars_per_module

        # Welches Zeichen innerhalb des Moduls?
        digit_index = x % chars_per_module

        module = row.modules[module_index]

        # Alle 16 Segmente einschalten
        value = 0xFFFF

        offset = digit_index * 2

        module.buffer[offset] = value & 0xFF
        module.buffer[offset + 1] = (value >> 8) & 0xFF

    def _refresh(self):
        """
        Schreibt alle Module auf das I2C-Display.
        """

        for row in self.display.rows:
            for module in row.modules:
                from driver.display.ht16k33_driver import write_buffer

                write_buffer(
                    module.module_index,
                    module.buffer
                )

    def clear(self):
        """
        Löscht das komplette Radar-Display.
        """

        self.display.clear()