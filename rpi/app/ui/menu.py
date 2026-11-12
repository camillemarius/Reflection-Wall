# ui/menu.py
# Menue mit vier sichtbaren Zeilen. Der Zeiger '>' steht immer in der zweiten Zeile:
# BT6 schiebt die Liste um einen Punkt nach oben, nach dem letzten Punkt folgt der erste.
# Zwischen dem letzten und dem ersten Punkt steht eine leere Zeile, damit die Liste nicht
# endlos wirkt; der Zeiger springt ueber sie hinweg.
from typing import Sequence

VISIBLE = 4
POINTER_LINE = 1


class Menu:
    def __init__(self, items: Sequence[str]) -> None:
        if not items:
            raise ValueError("Menue ohne Punkte")
        self._items = list(items)
        self._selected = 0

    @property
    def selected(self) -> int:
        return self._selected

    def select(self, index: int) -> None:
        self._selected = index % len(self._items)

    def down(self) -> None:
        self._selected = (self._selected + 1) % len(self._items)

    def lines(self) -> list[str]:
        count = len(self._items)
        ring = count + 1  # der letzte Platz im Ring ist die leere Zeile
        lines = [""] * VISIBLE
        shown = set()
        for line in range(VISIBLE):
            index = (self._selected + line - POINTER_LINE) % ring
            if index == count or index in shown:
                continue  # Luecke, oder ein kurzes Menue wuerde den Punkt doppelt zeigen
            shown.add(index)
            lines[line] = ("> " if line == POINTER_LINE else "  ") + self._items[index]
        return lines
