"""
uart.py

Basis UART Klasse.
"""

from __future__ import annotations

import serial


class UART:

    def __init__(self, port="/dev/serial0", baudrate=115200, timeout=1):
        self.serial = serial.Serial(
            port=port,
            baudrate=baudrate,
            timeout=timeout
        )

    @property
    def available(self) -> int:
        return self.serial.in_waiting

    def clear(self):
        self.serial.reset_input_buffer()
        self.serial.reset_output_buffer()

    def write(self, data):
        if isinstance(data, str):
            data = data.encode()

        self.serial.write(data)
        self.serial.flush()

    def read(self, size=1):
        return self.serial.read(size)

    def readline(self):
        return self.serial.readline()

    def read_all(self):
        return self.serial.read_all()

    def close(self):
        self.serial.close()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        self.close()