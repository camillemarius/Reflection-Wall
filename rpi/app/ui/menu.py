# ui/menu.py
# Menue mit vier sichtbaren Zeilen. Der Zeiger '>' steht immer in der zweiten Zeile:
# BT6 schiebt die Liste um einen Punkt nach oben, nach dem letzten Punkt folgt der erste.
from typing import Sequence

VISIBLE = 4
POINTER_LINE = 1
# Reihenfolge, in der die Zeilen belegt werden: Auswahl, die naechsten, dann der vorige.
# Ein kurzes Menue zeigt so jeden Punkt nur einmal, und der naechste steht immer darunter.
FILL_ORDER = (1, 2, 0, 3)


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
        lines = [""] * VISIBLE
        shown = set()
        for line in FILL_ORDER:
            index = (self._selected + line - POINTER_LINE) % count
            if index in shown:
                continue
            shown.add(index)
            lines[line] = ("> " if line == POINTER_LINE else "  ") + self._items[index]
        return lines
