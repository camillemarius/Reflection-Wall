"""
uart_switch.py

GPIO23:
HIGH -> HLK LD2410S
LOW  -> ESP8266
"""

from __future__ import annotations

from enum import Enum, auto
import time

import lgpio


class UARTSwitch:

    class Device(Enum):
        HLK = auto()
        ESP = auto()

    SWITCH_DELAY = 0.05

    def __init__(self, gpio=23, chip=0):
        self.gpio = gpio
        self.handle = lgpio.gpiochip_open(chip)

        lgpio.gpio_claim_output(self.handle, self.gpio)

        self._device = None
        self.select(self.Device.HLK)

    @property
    def device(self):
        return self._device

    def select(self, device: Device):
        if device == self._device:
            return

        value = 1 if device is self.Device.HLK else 0

        lgpio.gpio_write(self.handle, self.gpio, value)
        time.sleep(self.SWITCH_DELAY)

        self._device = device

    def select_hlk(self):
        self.select(self.Device.HLK)

    def select_esp(self):
        self.select(self.Device.ESP)

    def close(self):
        lgpio.gpiochip_close(self.handle)

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        self.close()