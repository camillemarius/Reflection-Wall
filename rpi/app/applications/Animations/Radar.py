import time

from driver.display.animations.stickman import Stickman
from driver.uart.uart_master import UARTMaster
from driver.uart.uart_hlk import UARTHLK


class Radar:

    SENSOR_TIMEOUT = 5.0

    def __init__(self, display):

        self.display = display

        # ====================================================
        # STRICHMÄNNCHEN
        # ====================================================

        self.stickman = Stickman(
            display=self.display,
            min_distance=0.7,
            max_distance=2.0,
        )

        # ====================================================
        # UART
        # ====================================================

        self.uart = UARTMaster(
            port="/dev/ttyAMA0",
            baudrate=115200,
            timeout=1
        )

        # ====================================================
        # LD2410S
        # ====================================================

        self.sensor = UARTHLK(
            self.uart
        )

        # ====================================================
        # STATUS
        # ====================================================

        self.running = False

        self.last_sensor_data = None

        # Sensorfehler-Zustand
        self.sensor_error = False

        # Merkt sich, ob aktuell eine Person erkannt wird
        self.person_present = False

    # ========================================================
    # START
    # ========================================================

    def run(self):

        print()
        print("========================================")
        print("          RADAR VISUALISIERUNG")
        print("========================================")
        print()
        print("LD2410S wird gestartet...")
        print("CTRL+C beendet den Radar-Modus.")
        print()

        self.running = True

        try:

            # ------------------------------------------------
            # LD2410S auswählen
            # ------------------------------------------------

            self.uart.select_hlk()

            print("LD2410S verbunden.")

            # ------------------------------------------------
            # Hauptloop
            # ------------------------------------------------

            while self.running:

                # ============================================
                # SENSOR AKTUALISIEREN
                # ============================================

                self.sensor.update()

                # ============================================
                # ZEITSTEMPEL DES LETZTEN FRAMES
                # ============================================

                timestamp = self.sensor.data.timestamp

                if timestamp > 0:

                    self.last_sensor_data = timestamp

                # ============================================
                # SENSOR-TIMEOUT
                # ============================================

                no_data = (
                    self.last_sensor_data is None
                    or
                    time.time() - self.last_sensor_data
                    > self.SENSOR_TIMEOUT
                )

                # =================================================
                # KEINE DATEN
                # =================================================

                if no_data:

                    # --------------------------------------------
                    # Nur beim Eintritt in den Fehlerzustand
                    # --------------------------------------------

                    if not self.sensor_error:

                        print(
                            "FEHLER: Keine Daten "
                            "vom LD2410S empfangen."
                        )

                        self.sensor_error = True

                        # Strichmännchen löschen
                        self.stickman.clear()

                    # --------------------------------------------
                    # Display nicht erneut beschreiben
                    # --------------------------------------------

                    time.sleep(0.1)

                    continue

                # =================================================
                # DATEN WIEDER VORHANDEN
                # =================================================

                if self.sensor_error:
                    
                    self.sensor_error = False

                    # Display einmal löschen.
                    # Danach zeichnet Stickman wieder.
                    self.display.clear()

                # ============================================
                # DISTANZ
                # ============================================

                distance = self.sensor.distance

                # ============================================
                # PRESENCE
                # ============================================

                if self.sensor.present:

                    # ----------------------------------------
                    # Person erkannt
                    # ----------------------------------------

                    distance_m = distance / 100.0

                    # Nur intern für Status
                    self.person_present = True

                    # Strichmännchen anzeigen
                    #
                    # Die Position wird anhand der
                    # gemessenen Distanz bestimmt.
                    #
                    self.stickman.show(
                        distance_m
                    )

                else:

                    # ----------------------------------------
                    # Keine Person
                    # ----------------------------------------

                    if self.person_present:

                        self.person_present = False

                        self.stickman.clear()

                # ============================================
                # CPU ENTLASTEN
                # ============================================

                time.sleep(0.1)

        # ====================================================
        # CTRL+C
        # ====================================================

        except KeyboardInterrupt:

            print()
            print("Radar-Modus beendet.")

        # ====================================================
        # UNERWARTETER FEHLER
        # ====================================================

        except Exception as error:

            print()
            print("RADAR FEHLER:")
            print(error)

            # ----------------------------------------------
            # Strichmännchen löschen
            # ----------------------------------------------

            self.stickman.clear()

            # ----------------------------------------------
            # Fehler nur einmal anzeigen
            # ----------------------------------------------

            if not self.sensor_error:

                self.sensor_error = True

                self.display.set_text(
                    "RADAR FEHLER\n"
                    "Sensor/UART\n"
                    "nicht verfügbar"
                )

            time.sleep(2)

        # ====================================================
        # AUFRÄUMEN
        # ====================================================

        finally:

            self.stop()

    # ========================================================
    # STOP
    # ========================================================

    def stop(self):

        if not self.running:
            return

        self.running = False

        print("Radar wird beendet...")

        # ----------------------------------------------------
        # Strichmännchen löschen
        # ----------------------------------------------------

        self.stickman.clear()

        # ----------------------------------------------------
        # Display löschen
        # ----------------------------------------------------

        self.display.clear()

        # ----------------------------------------------------
        # UART schließen
        # ----------------------------------------------------

        if self.uart is not None:

            self.uart.close()

        print("Radar gestoppt.")

