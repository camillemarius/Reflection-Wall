"""
uart.py

Basis UART Klasse
"""

import serial
import time



class UART:


    def __init__(
        self,
        port="/dev/serial0",
        baudrate=115200,
        timeout=1
    ):


        self.serial = serial.Serial(
            port,
            baudrate,
            timeout=timeout
        )


        time.sleep(0.2)



    def write(
        self,
        data
    ):

        if isinstance(
            data,
            str
        ):

            data = data.encode(
                "utf-8"
            )


        self.serial.write(
            data
        )

        self.serial.flush()



    def readline(self):

        data = self.serial.readline()


        return data.decode(
            "utf-8",
            errors="ignore"
        ).strip()



    def available(self):

        return (
            self.serial.in_waiting > 0
        )



    def close(self):

        self.serial.close()