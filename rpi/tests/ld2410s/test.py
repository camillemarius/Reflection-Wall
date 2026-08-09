import random
import time

from display import Display
from radarGraph import RadarGraph


# ============================================================
# DISPLAY
# ============================================================

display = Display(
    modules_per_row=3,
    rows=4,
    simulation=False
)


# ============================================================
# RADAR
# ============================================================

radar = RadarGraph(
    display,
    min_distance=0.3,
    max_distance=5.7,

    # Je kleiner, desto ruhiger
    smoothing=0.15
)


# ============================================================
# SIMULATION
# ============================================================

MIN_DISTANCE = 0.3
MAX_DISTANCE = 5.7

distance = random.uniform(
    1.0,
    5.0
)

speed = random.uniform(
    0.3,
    0.8
)

direction = random.choice(
    [-1, 1]
)

target_speed = speed


# ============================================================
# EINSTELLUNGEN
# ============================================================

UPDATE_TIME = 0.05

ACCELERATION = 0.015

SPEED_CHANGE_PROBABILITY = 0.01


# ============================================================
# LOOP
# ============================================================

try:

    while True:

        # ----------------------------------------------------
        # Neue Zielgeschwindigkeit
        # ----------------------------------------------------

        if random.random() < SPEED_CHANGE_PROBABILITY:

            target_speed = random.uniform(
                0.2,
                1.0
            )

        # ----------------------------------------------------
        # Geschwindigkeit weich verändern
        # ----------------------------------------------------

        if speed < target_speed:

            speed += ACCELERATION

            speed = min(
                speed,
                target_speed
            )

        elif speed > target_speed:

            speed -= ACCELERATION

            speed = max(
                speed,
                target_speed
            )

        # ----------------------------------------------------
        # Position verändern
        # ----------------------------------------------------

        distance += (
            speed
            * direction
            * UPDATE_TIME
        )

        # ----------------------------------------------------
        # Grenzen
        # ----------------------------------------------------

        if distance >= MAX_DISTANCE:

            distance = MAX_DISTANCE

            direction = -1

            target_speed = random.uniform(
                0.3,
                0.8
            )

        elif distance <= MIN_DISTANCE:

            distance = MIN_DISTANCE

            direction = 1

            target_speed = random.uniform(
                0.3,
                0.8
            )

        # ----------------------------------------------------
        # Seltene Richtungsänderung
        # ----------------------------------------------------

        if random.random() < 0.001:

            direction *= -1

            target_speed = random.uniform(
                0.3,
                0.8
            )

        # ----------------------------------------------------
        # X anzeigen
        # ----------------------------------------------------

        x = radar.distance_to_x(
            distance
        )

        print(
            f"\r"
            f"Distance: {distance:5.2f} m "
            f"| Speed: {speed:4.2f} m/s "
            f"| X: {x:2d} "
            f"| Direction: "
            f"{'→' if direction > 0 else '←'}",
            end="",
            flush=True
        )

        # ----------------------------------------------------
        # Radar
        # ----------------------------------------------------

        radar.update(
            distance
        )

        # ----------------------------------------------------
        # Simulation
        # ----------------------------------------------------

        time.sleep(
            UPDATE_TIME
        )


except KeyboardInterrupt:

    print(
        "\n\nRadar test stopped."
    )

    radar.clear()