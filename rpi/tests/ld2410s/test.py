import random
import time

from rpi.tests.ld2410s.displayGraph import DisplayGraph
from rpi.tests.ld2410s.radarGraph import RadarGraph


display = DisplayGraph(simulation=True)
radar = RadarGraph(display, max_distance=6.0)

try:
    while True:
        distance = random.uniform(0.0, 6.0)
        print(f"Distance: {distance:.2f} m")
        radar.update(distance)
        time.sleep(0.1)

except KeyboardInterrupt:
    radar.clear()
