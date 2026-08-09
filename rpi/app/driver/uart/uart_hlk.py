"""
uart_hlk.py

UART Interface für HLK LD2410S Radar Sensor.

Der LD2410S liefert im normalen Ausgabemodus
5-Byte-Datenframes:

    6E STATUS DIST_LOW DIST_HIGH 62

Beispiele:

    6E 00 00 00 62
    -> keine Person

    6E 01 00 00 62
    -> keine Person

    6E 02 23 00 62
    -> Person erkannt, 35 cm

    6E 03 23 00 62
    -> Person erkannt, 35 cm
"""

from __future__ import annotations

import time

from dataclasses import dataclass

from .uart_switch import UARTSwitch
from .uart_device import UARTDevice


@dataclass
class HLKData:

    # --------------------------------------------------------
    # Anwesenheit
    # --------------------------------------------------------

    presence: bool = False

    # --------------------------------------------------------
    # Bewegung
    #
    # Im 5-Byte-Modus liefert der Sensor keine getrennten
    # Moving/Stationary-Werte.
    # --------------------------------------------------------

    moving: bool = False
    stationary: bool = False

    # --------------------------------------------------------
    # Distanz in cm
    # --------------------------------------------------------

    distance: int = 0

    # --------------------------------------------------------
    # Energie
    #
    # Im 5-Byte-Modus nicht vorhanden.
    # --------------------------------------------------------

    energy: int = 0

    # --------------------------------------------------------
    # Separate Distanzen
    #
    # Im 5-Byte-Modus nicht vorhanden.
    # --------------------------------------------------------

    moving_distance: int = 0
    stationary_distance: int = 0

    # --------------------------------------------------------
    # Zeitpunkt des letzten gültigen Frames
    # --------------------------------------------------------

    timestamp: float = 0.0


class UARTHLK(UARTDevice):

    # ========================================================
    # LD2410S 5-BYTE PROTOKOLL
    # ========================================================

    DATA_HEADER = 0x6E
    DATA_TAIL = 0x62

    FRAME_LENGTH = 5

    # ========================================================
    # STATUSWERTE
    # ========================================================

    STATUS_NO_TARGET_0 = 0x00
    STATUS_NO_TARGET_1 = 0x01

    STATUS_TARGET_2 = 0x02
    STATUS_TARGET_3 = 0x03

    # ========================================================
    # INIT
    # ========================================================

    def __init__(
        self,
        uart,
        buffer_size=2048
    ):

        super().__init__(uart)

        # ----------------------------------------------------
        # Empfangspuffer
        # ----------------------------------------------------

        self.buffer = bytearray()

        self.buffer_size = max(
            self.FRAME_LENGTH,
            int(buffer_size)
        )

        # ----------------------------------------------------
        # Letzte Sensordaten
        # ----------------------------------------------------

        self.data = HLKData()

    # ========================================================
    # DEVICE
    # ========================================================

    @property
    def device(self):

        return UARTSwitch.Device.HLK

    # ========================================================
    # UPDATE
    # ========================================================

    def update(self):

        # ----------------------------------------------------
        # LD2410S auswählen
        # ----------------------------------------------------

        self.select()

        # ----------------------------------------------------
        # Prüfen ob Daten vorhanden sind
        # ----------------------------------------------------

        if not self.uart.available:

            return

        # ----------------------------------------------------
        # Alle verfügbaren Daten lesen
        # ----------------------------------------------------

        raw_data = self.uart.read_all()

        if not raw_data:

            return

        # ----------------------------------------------------
        # Daten an Buffer anhängen
        # ----------------------------------------------------

        self.buffer.extend(
            raw_data
        )

        # ----------------------------------------------------
        # Buffer begrenzen
        #
        # Falls aus irgendeinem Grund sehr viel Müll
        # empfangen wird, wächst der Buffer nicht unendlich.
        # ----------------------------------------------------

        if len(self.buffer) > self.buffer_size:

            del self.buffer[
                :len(self.buffer) - self.buffer_size
            ]

        # ----------------------------------------------------
        # Frames aus Buffer extrahieren
        # ----------------------------------------------------

        while True:

            frame = self.extract_frame()

            if frame is None:

                break

            self.parse_frame(
                frame
            )

    # ========================================================
    # FRAME EXTRAHIEREN
    # ========================================================

    def extract_frame(self):

        # ----------------------------------------------------
        # Header suchen
        # ----------------------------------------------------

        try:

            start = self.buffer.index(
                self.DATA_HEADER
            )

        except ValueError:

            # Kein Header vorhanden.
            #
            # Alles löschen, da kein gültiger Frame
            # daraus entstehen kann.

            self.buffer.clear()

            return None

        # ----------------------------------------------------
        # Müll vor Header entfernen
        # ----------------------------------------------------

        if start > 0:

            del self.buffer[
                :start
            ]

        # ----------------------------------------------------
        # Prüfen ob kompletter Frame vorhanden
        # ----------------------------------------------------

        if len(self.buffer) < self.FRAME_LENGTH:

            return None

        # ----------------------------------------------------
        # Kandidaten lesen
        # ----------------------------------------------------

        frame = bytes(
            self.buffer[
                :self.FRAME_LENGTH
            ]
        )

        # ----------------------------------------------------
        # Tail prüfen
        # ----------------------------------------------------

        if frame[4] != self.DATA_TAIL:

            print(
                "[HLK] Ungültiges Frame:",
                frame.hex(" ")
            )

            # Nur ein Byte verwerfen.
            #
            # Danach kann erneut nach einem Header
            # gesucht werden.

            del self.buffer[0]

            return None

        # ----------------------------------------------------
        # Frame aus Buffer entfernen
        # ----------------------------------------------------

        del self.buffer[
            :self.FRAME_LENGTH
        ]

        return frame

    # ========================================================
    # FRAME PARSEN
    # ========================================================

    def parse_frame(
        self,
        frame
    ):

        # ----------------------------------------------------
        # Länge prüfen
        # ----------------------------------------------------

        if len(frame) != self.FRAME_LENGTH:

            return

        # ----------------------------------------------------
        # Header prüfen
        # ----------------------------------------------------

        if frame[0] != self.DATA_HEADER:

            return

        # ----------------------------------------------------
        # Tail prüfen
        # ----------------------------------------------------

        if frame[4] != self.DATA_TAIL:

            return

        # ====================================================
        # STATUS
        # ====================================================

        status = frame[1]

        # ====================================================
        # DISTANZ
        # ====================================================

        distance = int.from_bytes(
            frame[2:4],
            byteorder="little"
        )

        # ====================================================
        # TIMESTAMP
        # ====================================================

        self.data.timestamp = time.time()

        # ====================================================
        # PRESENCE
        # ====================================================

        self.data.presence = (
            status == self.STATUS_TARGET_2
            or
            status == self.STATUS_TARGET_3
        )

        # ====================================================
        # DISTANCE
        # ====================================================

        self.data.distance = distance

        # ====================================================
        # MOVING / STATIONARY
        #
        # Im 5-Byte-Modus gibt es diese Information
        # nicht getrennt.
        # ====================================================

        self.data.moving = False

        self.data.stationary = False

        # ====================================================
        # ENERGY
        #
        # Im 5-Byte-Modus nicht vorhanden.
        # ====================================================

        self.data.energy = 0

        # ====================================================
        # MOVING DISTANCE
        # ====================================================

        self.data.moving_distance = distance

        # ====================================================
        # STATIONARY DISTANCE
        # ====================================================

        self.data.stationary_distance = distance

    # ========================================================
    # DATEN API
    # ========================================================

    def get_data(self):

        return self.data

    # ========================================================
    # PRESENCE
    # ========================================================

    @property
    def present(self):

        return self.data.presence

    # ========================================================
    # DISTANCE
    # ========================================================

    @property
    def distance(self):

        return self.data.distance

    # ========================================================
    # MOVING
    # ========================================================

    @property
    def moving(self):

        return self.data.moving

    # ========================================================
    # STATIONARY
    # ========================================================

    @property
    def stationary(self):

        return self.data.stationary

    # ========================================================
    # ENERGY
    # ========================================================

    @property
    def energy(self):

        return self.data.energy

    # ========================================================
    # MOVING DISTANCE
    # ========================================================

    def get_moving_distance(self):

        return self.data.moving_distance

    # ========================================================
    # STATIONARY DISTANCE
    # ========================================================

    def get_stationary_distance(self):

        return self.data.stationary_distance

    # ========================================================
    # COMMANDS
    # ========================================================

    def send_command(
        self,
        payload: bytes
    ):

        # ----------------------------------------------------
        # HLK auswählen
        # ----------------------------------------------------

        self.select()

        # ----------------------------------------------------
        # Kommando-Header
        # ----------------------------------------------------

        CMD_HEADER = (
            b"\xFD\xFC\xFB\xFA"
        )

        CMD_TAIL = (
            b"\x04\x03\x02\x01"
        )

        # ----------------------------------------------------
        # Kommando zusammenbauen
        # ----------------------------------------------------

        frame = (
            CMD_HEADER
            +
            len(payload).to_bytes(
                2,
                "little"
            )
            +
            payload
            +
            CMD_TAIL
        )

        # ----------------------------------------------------
        # Senden
        # ----------------------------------------------------

        self.uart.write(
            frame
        )

    # ========================================================
    # ENGINEERING MODE
    # ========================================================

    def enable_engineering_mode(self):

        self.send_command(
            b"\x62\x00"
        )

    # ========================================================

    def disable_engineering_mode(self):

        self.send_command(
            b"\x63\x00"
        )

    # ========================================================
    # MAX DISTANCE
    # ========================================================

    def set_max_distance(
        self,
        meters
    ):

        gate = int(
            meters / 0.75
        )

        # Byte auf gültigen Bereich begrenzen

        gate = max(
            0,
            min(
                255,
                gate
            )
        )

        self.send_command(
            bytes([
                0x01,
                gate
            ])
        )

    # ========================================================
    # MOVING THRESHOLD
    # ========================================================

    def set_moving_threshold(
        self,
        threshold
    ):

        threshold = max(
            0,
            min(
                255,
                int(threshold)
            )
        )

        self.send_command(
            bytes([
                0x02,
                threshold
            ])
        )

    # ========================================================
    # STATIONARY THRESHOLD
    # ========================================================

    def set_stationary_threshold(
        self,
        threshold
    ):

        threshold = max(
            0,
            min(
                255,
                int(threshold)
            )
        )

        self.send_command(
            bytes([
                0x03,
                threshold
            ])
        )

    # ========================================================
    # RESTART
    # ========================================================

    def restart(self):

        self.send_command(
            b"\xA3"
        )