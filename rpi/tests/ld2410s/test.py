"""Radar-Test: simuliert Distanzen des LD2410S und zeigt sie als Graph.

Start im Ordner rpi/:
    python -m tests.ld2410s.test [--simulation] [--seconds N]

Nutzt den App-Treiber (app.driver.display). Auf dem PC mit --simulation
(Ausgabe auf der Konsole). N = 0: laeuft bis Ctrl+C.
Unter Windows die Konsole auf UTF-8 stellen, sonst scheitern die Zeichen
fuer Balken und Pfeile: python -X utf8 -m tests.ld2410s.test --simulation
"""

import argparse
import random
import time

from app.driver.display.displayGraph import DisplayGraph
from app.driver.display.radarGraph import RadarGraph

MIN_DISTANCE = 0.3
MAX_DISTANCE = 5.7

UPDATE_TIME = 0.05
ACCELERATION = 0.015
SPEED_CHANGE_PROBABILITY = 0.01


def run(display, seconds):
    radar = RadarGraph(display, max_distance=MAX_DISTANCE)

    distance = random.uniform(1.0, 5.0)
    speed = random.uniform(0.3, 0.8)
    direction = random.choice([-1, 1])
    target_speed = speed
    end = time.monotonic() + seconds if seconds > 0 else None

    try:
        while end is None or time.monotonic() < end:
            # Neue Zielgeschwindigkeit
            if random.random() < SPEED_CHANGE_PROBABILITY:
                target_speed = random.uniform(0.2, 1.0)

            # Geschwindigkeit weich verändern
            if speed < target_speed:
                speed = min(speed + ACCELERATION, target_speed)
            elif speed > target_speed:
                speed = max(speed - ACCELERATION, target_speed)

            # Position verändern
            distance += speed * direction * UPDATE_TIME

            # Grenzen
            if distance >= MAX_DISTANCE:
                distance = MAX_DISTANCE
                direction = -1
                target_speed = random.uniform(0.3, 0.8)
            elif distance <= MIN_DISTANCE:
                distance = MIN_DISTANCE
                direction = 1
                target_speed = random.uniform(0.3, 0.8)

            # Seltene Richtungsänderung
            if random.random() < 0.001:
                direction *= -1
                target_speed = random.uniform(0.3, 0.8)

            radar.update(distance)
            print(
                f"\rDistance: {distance:5.2f} m "
                f"| Speed: {speed:4.2f} m/s "
                f"| Direction: {'→' if direction > 0 else '←'}",
                end="",
                flush=True,
            )
            time.sleep(UPDATE_TIME)
    except KeyboardInterrupt:
        print("\n\nRadar test stopped.")
    finally:
        radar.clear()


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--simulation", action="store_true",
                        help="Display auf der Konsole statt über I2C")
    parser.add_argument("--seconds", type=float, default=0,
                        help="Laufzeit in Sekunden (0 = bis Ctrl+C)")
    args = parser.parse_args(argv)

    display = DisplayGraph(modules_per_row=3, simulation=args.simulation)
    run(display, args.seconds)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
