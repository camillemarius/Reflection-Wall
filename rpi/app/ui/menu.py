# ui/menu.py
# Menue mit vier sichtbaren Zeilen und Zeiger '>' (rollt mit, springt am Ende nach oben).
from typing import Sequence

VISIBLE = 4


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
        top = max(0, self._selected - (VISIBLE - 1))
        lines = []
        for index in range(top, top + VISIBLE):
            if index >= len(self._items):
                lines.append("")
            else:
                lines.append(("> " if index == self._selected else "  ") + self._items[index])
        return lines
