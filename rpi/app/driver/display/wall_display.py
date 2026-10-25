# display/wall_display.py
# Wandanzeige: 12 HT16K33-Module (je 8 Stellen), 4 Zeilen zu 3 Modulen.
import contextlib
import logging
from typing import Sequence

from app.driver.display.cells import lines_to_cells, normalize
from app.driver.display.text_layout import CHARS_PER_ROW, ROWS, wrap

log = logging.getLogger(__name__)

# Zeile fuer Zeile, je drei Module (dieselben Adressen wie beim ESP)
MODULE_ADDRESSES = (0x70, 0x71, 0x72, 0x73, 0x74, 0x75, 0x76, 0x77, 0x7F, 0x79, 0x7B, 0x7D)

CHARS_PER_MODULE = 8
MODULES_PER_ROW = CHARS_PER_ROW // CHARS_PER_MODULE
TOTAL_CELLS = CHARS_PER_ROW * ROWS

CMD_SYSTEM_SETUP = 0x20
CMD_DISPLAY_SETUP = 0x80
CMD_BRIGHTNESS = 0xE0


@contextlib.contextmanager
def _no_guard():
    yield


class WallDisplay:
    WIDTH = CHARS_PER_ROW
    HEIGHT = ROWS

    def __init__(self, bus=None, bus_guard=None):
        self._bus = bus
        self._guard = bus_guard or _no_guard
        # None = Modul noch nie geschrieben (oder letzter Versuch fehlgeschlagen)
        self._sent: list = [None] * len(MODULE_ADDRESSES)
        self._canvas = [0] * TOTAL_CELLS

    def start(self) -> None:
        if self._bus is None:
            import smbus2
            self._bus = smbus2.SMBus(1)
        # Ergebnisse der Init-Uebertragungen werden ignoriert (fehlende Module loggt _transfer)
        for addr in MODULE_ADDRESSES:
            for value in (CMD_SYSTEM_SETUP | 0x01, CMD_DISPLAY_SETUP | 0x01, CMD_BRIGHTNESS | 0x0F):
                self._transfer(lambda a=addr, v=value: self._bus.write_byte(a, v), addr)
        self._sent = [None] * len(MODULE_ADDRESSES)
        self.clear()

    def _transfer(self, action, addr) -> bool:
        """Eine Uebertragung unter bus_guard, bei OSError einmal wiederholt."""
        for attempt in (1, 2):
            try:
                with self._guard():
                    action()
                return True
            except OSError as exc:
                if attempt == 2:
                    log.warning("Schreiben an 0x%02X fehlgeschlagen: %s", addr, exc)
        return False

    @staticmethod
    def _module_cells(masks: Sequence[int], module: int) -> tuple:
        row, col = divmod(module, MODULES_PER_ROW)
        start = row * CHARS_PER_ROW + col * CHARS_PER_MODULE
        return tuple(masks[start:start + CHARS_PER_MODULE])

    def show_cells(self, masks: Sequence[int]) -> None:
        if self._bus is None:
            raise RuntimeError("WallDisplay.start() fehlt")
        for module, addr in enumerate(MODULE_ADDRESSES):
            cells = self._module_cells(masks, module)
            if cells == self._sent[module]:
                continue
            data = []
            for mask in cells:
                data.append(mask & 0xFF)
                data.append((mask >> 8) & 0xFF)
            ok = self._transfer(lambda a=addr, d=data: self._bus.write_i2c_block_data(a, 0x00, d), addr)
            self._sent[module] = cells if ok else None

    # show_lines/show_text lassen die Zeichenflaeche unberuehrt
    def show_lines(self, lines: Sequence[str], dots_own_cell: bool = False) -> None:
        self.show_cells(lines_to_cells(lines, dots_own_cell))

    def show_text(self, text: str) -> bool:
        rows, fits = wrap(normalize(text))
        self.show_lines(rows)
        return fits

    def clear(self) -> None:
        self._canvas = [0] * TOTAL_CELLS
        self.show_cells(self._canvas)

    # Zeichenflaeche (Strichmaennchen des Radars)
    def clear_canvas(self) -> None:
        """Leert nur den Puffer der Zeichenflaeche; schreibt nichts (kein Flackern)."""
        self._canvas = [0] * TOTAL_CELLS

    def set_segments(self, x: int, y: int, mask: int) -> None:
        if 0 <= x < self.WIDTH and 0 <= y < self.HEIGHT:
            self._canvas[y * self.WIDTH + x] = mask

    def refresh(self) -> None:
        self.show_cells(self._canvas)
