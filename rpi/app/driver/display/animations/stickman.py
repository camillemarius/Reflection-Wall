class Stickman:

    # ============================================================
    # ANIMATION
    # ============================================================

    ANIMATION_INTERVAL = 0.20

    # ============================================================
    # STICKMAN SEGMENTE
    # ============================================================

    ROW1 = 0x0000

    ROW2 = (
        (1 << 9)  |
        (1 << 10) |
        (1 << 8)  |
        (1 << 0)  |
        (1 << 15) |
        (1 << 13)
    )

    ROW3 = (
        (1 << 6)  |
        (1 << 3)  |
        (1 << 12)
    )

    ROW4_NORMAL = (
        (1 << 11) |
        (1 << 14) |
        (1 << 4)
    )

    ROW4_FRAME_1 = (
        (1 << 11) |
        (1 << 4)
    )

    ROW4_FRAME_2 = (
        (1 << 4)
    )

    ROW4_FRAME_3 = (
        (1 << 14) |
        (1 << 4)
    )

    # ============================================================
    # INIT
    # ============================================================

    def __init__(
        self,
        display,
        min_distance=0.7,
        max_distance=2.0,
    ):

        self.display = display

        self.min_distance = float(
            min_distance
        )

        self.max_distance = float(
            max_distance
        )

        # --------------------------------------------------------
        # Position
        # --------------------------------------------------------

        self.current_distance = None
        self.current_x = None

        # --------------------------------------------------------
        # Animation
        # --------------------------------------------------------

        self.animation_frame = 0
        self.last_animation_time = 0.0

        self.drawn = False

    # ============================================================
    # DISTANZ -> X
    # ============================================================

    def distance_to_x(
        self,
        distance
    ):

        distance = float(
            distance
        )

        distance = max(
            self.min_distance,
            min(
                distance,
                self.max_distance
            )
        )

        distance_range = (
            self.max_distance -
            self.min_distance
        )

        if distance_range <= 0:

            return 0

        ratio = (
            distance -
            self.min_distance
        ) / distance_range

        width = self.display.WIDTH

        # --------------------------------------------------------
        # Rand
        # --------------------------------------------------------

        margin = 2

        usable_width = max(
            1,
            width - (2 * margin)
        )

        x = round(
            ratio *
            (usable_width - 1)
        )

        x += margin

        return max(
            0,
            min(
                width - 1,
                x
            )
        )

    # ============================================================
    # ANZEIGEN
    # ============================================================

    def show(
        self,
        distance
    ):

        if distance is None:

            return

        try:

            distance = float(
                distance
            )

        except (
            TypeError,
            ValueError
        ):

            return

        # --------------------------------------------------------
        # Distanz begrenzen
        # --------------------------------------------------------

        distance = max(
            self.min_distance,
            min(
                distance,
                self.max_distance
            )
        )

        # --------------------------------------------------------
        # Position berechnen
        # --------------------------------------------------------

        new_x = self.distance_to_x(
            distance
        )

        # --------------------------------------------------------
        # Position geändert?
        # --------------------------------------------------------

        position_changed = (
            new_x != self.current_x
        )

        if not position_changed:

            return

        # --------------------------------------------------------
        # Position übernehmen
        # --------------------------------------------------------

        self.current_x = new_x
        self.current_distance = distance

        # --------------------------------------------------------
        # Animation
        # --------------------------------------------------------

        self.animation_frame = (
            self.animation_frame + 1
        ) % 4

        # --------------------------------------------------------
        # Zeichnen
        # --------------------------------------------------------

        self._draw()

    # ============================================================
    # ZEICHNEN
    # ============================================================

    def _draw(self):

        if self.current_x is None:

            return

        x = self.current_x

        # --------------------------------------------------------
        # Display löschen
        # --------------------------------------------------------

        self.display.clear()

        # --------------------------------------------------------
        # Zeile 1
        # --------------------------------------------------------

        self.display.set_segments(
            x,
            0,
            self.ROW1
        )

        # --------------------------------------------------------
        # Zeile 2
        # --------------------------------------------------------

        self.display.set_segments(
            x,
            1,
            self.ROW2
        )

        # --------------------------------------------------------
        # Zeile 3
        # --------------------------------------------------------

        self.display.set_segments(
            x,
            2,
            self.ROW3
        )

        # --------------------------------------------------------
        # Zeile 4 / Laufanimation
        # --------------------------------------------------------

        if self.animation_frame == 0:

            row4 = self.ROW4_NORMAL

        elif self.animation_frame == 1:

            row4 = self.ROW4_FRAME_1

        elif self.animation_frame == 2:

            row4 = self.ROW4_FRAME_2

        else:

            row4 = self.ROW4_FRAME_3

        self.display.set_segments(
            x,
            3,
            row4
        )

        # --------------------------------------------------------
        # Display aktualisieren
        # --------------------------------------------------------

        self.display.refresh()

        self.drawn = True

    # ============================================================
    # CLEAR
    # ============================================================

    def clear(self):

        self.current_distance = None
        self.current_x = None
        self.animation_frame = 0
        self.last_animation_time = 0.0
        self.drawn = False

        self.display.clear()

