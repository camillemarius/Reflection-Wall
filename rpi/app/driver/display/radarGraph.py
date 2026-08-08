"""
radar_graph.py

24-Spalten-Verlauf für den LD2410S.
Jede X-Spalte entspricht einer Messung.
Y = 0..3 entspricht der Distanzhöhe.
"""

from collections import deque


class RadarGraph:
    def __init__(self, display, max_distance=6.0):
        self.display = display
        self.max_distance = max_distance
        self.values = deque(
            [0.0] * display.WIDTH,
            maxlen=display.WIDTH
        )

    def update(self, distance):
        if distance is None:
            return

        distance = max(
            0.0,
            min(float(distance), self.max_distance)
        )

        self.values.append(distance)
        self._draw()

    def clear(self):
        self.values.clear()
        self.values.extend(
            [0.0] * self.display.WIDTH
        )
        self.display.clear()
        self.display.refresh()

    def _draw(self):
        self.display.clear()

        for x, distance in enumerate(self.values):
            height = round(
                distance / self.max_distance
                * self.display.HEIGHT
            )

            self.display.set_column(
                x,
                height
            )

        self.display.refresh()
