"""
display_graph.py

Grafische Abstraktion für ein 4x24 16-Segment-Display.
X = 0..23, Y = 0..3
"""

from rpi.app.driver.display.ht16k33_driver import (
    TestModule, I2CModule, CHARS_PER_MODULE,
    init_ht16k33, clear_all, write_buffer
)


class DisplayGraph:
    WIDTH = 24
    HEIGHT = 4

    def __init__(self, modules_per_row=3, simulation=False):
        self.simulation = simulation
        if simulation:
            self.modules = [TestModule(i) for i in range(modules_per_row)]
        else:
            init_ht16k33(modules_per_row)
            self.modules = [I2CModule(i) for i in range(modules_per_row)]
            clear_all(self.modules)
        self.clear()

    def clear(self):
        if self.simulation:
            for module in self.modules:
                module.clear()
        else:
            clear_all(self.modules)

    def set_pixel(self, x, y, state=True):
        if not (0 <= x < self.WIDTH and 0 <= y < self.HEIGHT):
            return

        module = self.modules[x // CHARS_PER_MODULE]
        digit = x % CHARS_PER_MODULE

        if self.simulation:
            module.buffer[digit] = "█" if state else " "
            return

        offset = digit * 2
        value = module.buffer[offset] | (module.buffer[offset + 1] << 8)
        segment = self._get_vertical_segment(y)
        value = value | segment if state else value & ~segment
        module.buffer[offset] = value & 0xFF
        module.buffer[offset + 1] = (value >> 8) & 0xFF

    def _get_vertical_segment(self, y):
        return {
            0: 0x0001,
            1: 0x0002,
            2: 0x0004,
            3: 0x0008
        }[y]

    def set_column(self, x, height):
        height = max(0, min(self.HEIGHT, height))
        for y in range(self.HEIGHT):
            self.set_pixel(x, y, y < height)

    def set_graph(self, values):
        self.clear()
        if not values:
            self.refresh()
            return

        values = values[:self.WIDTH]
        maximum = max(values)

        if maximum <= 0:
            self.refresh()
            return

        for x, value in enumerate(values):
            height = round(value / maximum * self.HEIGHT)
            self.set_column(x, height)

        self.refresh()

    def refresh(self):
        if self.simulation:
            self._print()
            return

        for module in self.modules:
            write_buffer(module.index, module.buffer)

    def _print(self):
        print()
        for y in reversed(range(self.HEIGHT)):
            line = ""
            for x in range(self.WIDTH):
                module = self.modules[x // CHARS_PER_MODULE]
                digit = x % CHARS_PER_MODULE
                line += module.buffer[digit] if y == 0 else " "
            print(line)
        print("-" * self.WIDTH)

