"""
uart_master.py

UART Master mit Umschaltung zwischen
HLK LD2410S und ESP8266.
"""

from __future__ import annotations

import time

from uart import UART
from uart_switch import UARTSwitch


class UARTMaster:

    SWITCH_DELAY = 0.1

    def __init__(self, port="/dev/serial0", baudrate=115200, timeout=1):
        self.switch = UARTSwitch()
        self.uart = UART(port, baudrate, timeout)

        self._device = None
        self.select(UARTSwitch.Device.ESP)

    @property
    def device(self):
        return self.switch.device

    def select(self, device: UARTSwitch.Device):
        if device == self.device:
            return

        self.switch.select(device)
        self.uart.clear()

        time.sleep(self.SWITCH_DELAY)

    def select_hlk(self):
        self.select(UARTSwitch.Device.HLK)

    def select_esp(self):
        self.select(UARTSwitch.Device.ESP)

    @property
    def available(self):
        return self.uart.available

    def clear(self):
        self.uart.clear()

    def write(self, data):
        self.uart.write(data)

    def read(self, size=1):
        return self.uart.read(size)

    def readline(self):
        return self.uart.readline()

    def read_all(self):
        return self.uart.read_all()

    def close(self):
        self.uart.close()
        self.switch.close()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        self.close()