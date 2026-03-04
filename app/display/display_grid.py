# core/display_grid.py
from display.segment_chain import SegmentChain

class DisplayGrid:
    def __init__(self, rows):
        """
        rows: Liste von SegmentChain-Instanzen (vertikal untereinander)
        """
        self.rows = rows
        self.total_cols = self.rows[0].chars_per_chain if rows else 0
        self.total_rows = len(rows)

    def clear(self):
        for row in self.rows:
            row.clear()

    def set_text(self, lines):
        """
        lines: Liste von Strings, eine pro Zeile
        """
        for i, row in enumerate(self.rows):
            text = lines[i] if i < len(lines) else ""
            row.set_text(text)
