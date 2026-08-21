import os
import time


class Stickman:
    """Animation class for 16-segment stickman frames."""

    FRAME_TIME = 0.400
    FRAMES_DIR_NAME = "videoframes"

    def __init__(
        self,
        display,
        frames_dir=None
    ):

        self.display = display

        self.frames_dir = (
            frames_dir
            or os.path.join(
                os.path.dirname(__file__),
                self.FRAMES_DIR_NAME
            )
        )

        self.frames = []

        # Positionen des zuletzt angezeigten Frames.
        #
        # Diese werden benötigt, damit wir beim Wechsel
        # zum nächsten Frame die alten Zellen gezielt
        # mit 0x0000 löschen können.
        self.previous_frame_positions = set()

        self._load_frames()

    # ========================================================
    # FRAMES LADEN
    # ========================================================

    def _load_frames(self):

        print("========================================")
        print("Stickman: Frames laden")
        print("========================================")

        print(
            "Frames-Verzeichnis:",
            self.frames_dir
        )

        if not os.path.isdir(
            self.frames_dir
        ):

            print(
                "FEHLER: Frames-Verzeichnis "
                "existiert nicht!"
            )

            return

        frame_files = sorted(
            f
            for f in os.listdir(
                self.frames_dir
            )
            if f.endswith(".py")
        )

        print(
            f"{len(frame_files)} Python-Datei(en) gefunden."
        )

        for filename in frame_files:

            path = os.path.join(
                self.frames_dir,
                filename
            )

            print(
                f"Lade: {filename}"
            )

            namespace = {
                "__file__": path,
                "__name__": "__videoframe__"
            }

            try:

                with open(
                    path,
                    "r",
                    encoding="utf-8"
                ) as frame_file:

                    code = frame_file.read()

                exec(
                    code,
                    namespace
                )

            except Exception as error:

                print(
                    f"FEHLER beim Laden von {filename}:"
                )

                print(error)

                continue

            video_frames = namespace.get(
                "VIDEO_FRAMES"
            )

            frame_time = namespace.get(
                "FRAME_TIME",
                self.FRAME_TIME
            )

            if not isinstance(
                video_frames,
                list
            ):

                print(
                    f"WARNUNG: {filename} "
                    "enthält kein VIDEO_FRAMES."
                )

                continue

            for frame in video_frames:

                if not isinstance(
                    frame,
                    dict
                ):

                    print(
                        "WARNUNG: Frame ist kein Dictionary."
                    )

                    continue

                self.frames.append(
                    (
                        frame,
                        float(frame_time)
                    )
                )

                print(
                    f"  Frame geladen: "
                    f"{len(frame)} Zellen"
                )

        print("----------------------------------------")

        print(
            f"Insgesamt {len(self.frames)} "
            "Frame(s) geladen."
        )

        print("========================================")

    # ========================================================
    # FRAME ZEICHNEN
    # ========================================================

    def _draw_frame(
        self,
        frame
    ):

        # ----------------------------------------------------
        # Positionen des aktuellen Frames
        # ----------------------------------------------------

        current_positions = set(
            frame.keys()
        )

        # ----------------------------------------------------
        # Alte Zellen ermitteln
        #
        # Alles was im vorherigen Frame vorhanden war,
        # aber im aktuellen Frame nicht mehr vorhanden ist,
        # muss explizit gelöscht werden.
        # ----------------------------------------------------

        positions_to_clear = (
            self.previous_frame_positions
            - current_positions
        )

        # ----------------------------------------------------
        # Alte Zellen löschen
        #
        # WICHTIG:
        # Kein display.clear() verwenden!
        #
        # Dadurch bleibt der Display-Buffer erhalten
        # und es entsteht kein sichtbares Flackern.
        # ----------------------------------------------------

        for (
            x,
            y
        ) in positions_to_clear:

            self.display.set_segments(
                x,
                y,
                0x0000
            )

        # ----------------------------------------------------
        # Aktuellen Frame schreiben
        # ----------------------------------------------------

        for (
            position,
            value
        ) in frame.items():

            x, y = position

            value = int(value) & 0xFFFF

            self.display.set_segments(
                x,
                y,
                value
            )

        # ----------------------------------------------------
        # GANZ WICHTIG:
        #
        # Erst nachdem ALLE Änderungen im Buffer stehen,
        # wird EINMAL die Hardware aktualisiert.
        # ----------------------------------------------------

        self.display.refresh()

        # ----------------------------------------------------
        # Aktuelle Positionen für nächsten Frame merken
        # ----------------------------------------------------

        self.previous_frame_positions = (
            current_positions
        )

    # ========================================================
    # ANIMATION
    # ========================================================

    def run(
        self
    ):

        if not self.frames:

            print(
                "FEHLER: Keine Frames geladen!"
            )

            return

        print(
            f"Starte Endlos-Animation mit "
            f"{len(self.frames)} Frame(s)."
        )

        # ----------------------------------------------------
        # Nur einmal am Anfang löschen.
        #
        # NICHT innerhalb der Frame-Schleife!
        # ----------------------------------------------------

        self.display.clear()

        self.previous_frame_positions = set()

        try:

            while True:

                for index, (
                    frame,
                    delay
                ) in enumerate(
                    self.frames
                ):

                    print(
                        f"\nFrame "
                        f"{index + 1}/"
                        f"{len(self.frames)}"
                    )

                    self._draw_frame(
                        frame
                    )

                    time.sleep(
                        delay
                    )

        except KeyboardInterrupt:

            print()

            print(
                "Animation durch "
                "KeyboardInterrupt beendet."
            )
