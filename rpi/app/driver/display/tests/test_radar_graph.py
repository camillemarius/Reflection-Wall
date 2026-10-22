import contextlib
import io
import unittest

from app.driver.display.displayGraph import DisplayGraph
from app.driver.display.radarGraph import RadarGraph


class RadarGraphTest(unittest.TestCase):
    def setUp(self):
        self.display = DisplayGraph(modules_per_row=3, simulation=True)
        self.radar = RadarGraph(self.display, max_distance=6.0)

    def update(self, distance):
        with contextlib.redirect_stdout(io.StringIO()):
            self.radar.update(distance)

    def test_full_distance_fills_newest_column(self):
        self.update(6.0)
        self.assertEqual(self.display.modules[2].buffer[7], "█")
        self.assertEqual(self.display.modules[0].buffer[0], " ")

    def test_columns_move_left(self):
        self.update(6.0)
        self.update(0.0)
        self.assertEqual(self.display.modules[2].buffer[6], "█")
        self.assertEqual(self.display.modules[2].buffer[7], " ")


if __name__ == "__main__":
    unittest.main()
