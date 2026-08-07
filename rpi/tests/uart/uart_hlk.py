"""
uart_hlk.py

UART Interface für HLK LD2410S Radar Sensor.
"""

from __future__ import annotations

import struct
import time

from dataclasses import dataclass

from uart_switch import UARTSwitch
from uart_device import UARTDevice


@dataclass
class HLKData:
    presence: bool = False
    moving: bool = False
    stationary: bool = False
    distance: int = 0
    energy: int = 0
    moving_distance: int = 0
    stationary_distance: int = 0
    timestamp: float = 0


class UARTHLK(UARTDevice):

    DATA_HEADER = b"\xF4\xF3\xF2\xF1"
    DATA_TAIL = b"\xF8\xF7\xF6\xF5"

    CMD_HEADER = b"\xFD\xFC\xFB\xFA"
    CMD_TAIL = b"\x04\x03\x02\x01"

    def __init__(self, uart, buffer_size=2048):
        super().__init__(uart)

        self.buffer = bytearray(max(0, buffer_size))
        self.data = HLKData()

    @property
    def device(self):
        return UARTSwitch.Device.HLK

    # ---------------------
    # Empfang
    # ---------------------

    def update(self):
        self.select()

        if self.uart.available:
            self.buffer.extend(
                self.uart.read_all()
            )

        while True:
            frame = self.extract_frame()

            if frame is None:
                break

            self.parse_frame(frame)


    def extract_frame(self):

        start = self.buffer.find(
            self.DATA_HEADER
        )

        if start < 0:
            self.buffer.clear()
            return None

        end = self.buffer.find(
            self.DATA_TAIL,
            start
        )

        if end < 0:
            return None

        end += len(self.DATA_TAIL)

        frame = self.buffer[start:end]

        del self.buffer[:end]

        return bytes(frame)


    # ---------------------
    # Daten Parsing
    # ---------------------

    def parse_frame(self, frame):

        if len(frame) < 14:
            return

        self.data.timestamp = time.time()

        self.data.presence = frame[6] != 0

        self.data.moving_distance = int.from_bytes(
            frame[8:10],
            "little"
        )

        self.data.moving = frame[10] > 0

        self.data.stationary_distance = int.from_bytes(
            frame[11:13],
            "little"
        )

        self.data.stationary = frame[13] > 0


        if self.data.moving:
            self.data.distance = self.data.moving_distance
            self.data.energy = frame[10]

        elif self.data.stationary:
            self.data.distance = self.data.stationary_distance
            self.data.energy = frame[13]


    # ---------------------
    # Daten API
    # ---------------------

    def get_data(self):
        return self.data

    @property
    def present(self):
        return self.data.presence

    @property
    def distance(self):
        return self.data.distance

    @property
    def moving(self):
        return self.data.moving

    @property
    def stationary(self):
        return self.data.stationary

    @property
    def energy(self):
        return self.data.energy


    def get_moving_distance(self):
        return self.data.moving_distance


    def get_stationary_distance(self):
        return self.data.stationary_distance


    # ---------------------
    # Commands
    # ---------------------

    def send_command(self, payload: bytes):

        self.select()

        frame = (
            self.CMD_HEADER +
            struct.pack(
                "<H",
                len(payload)
            ) +
            payload +
            self.CMD_TAIL
        )

        self.uart.write(frame)


    def enable_engineering_mode(self):
        self.send_command(
            b"\x62\x00"
        )


    def disable_engineering_mode(self):
        self.send_command(
            b"\x63\x00"
        )


    def set_max_distance(self, meters):

        gate = int(
            meters / 0.75
        )

        self.send_command(
            bytes([
                0x01,
                gate
            ])
        )


    def set_moving_threshold(self, threshold):

        self.send_command(
            bytes([
                0x02,
                threshold
            ])
        )


    def set_stationary_threshold(self, threshold):

        self.send_command(
            bytes([
                0x03,
                threshold
            ])
        )


    def restart(self):

        self.send_command(
            b"\xA3"
        )