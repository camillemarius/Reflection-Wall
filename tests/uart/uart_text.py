"""
esp_uart_text.py

UART Treiber zum Senden von Texten an ESP-12F.

Spezialfunktion:
GPIO23 LOW aktiviert Hardware-Umschalter
für die Verbindung ESP <-> Raspberry Pi.

Benötigt:
pip install pyserial lgpio
"""

import serial
import time
import lgpio


class ESPTextUART:

    START = "<START>"
    END = "<END>"
    ACK = "OK"

    def __init__(
        self,
        port="/dev/serial0",
        baudrate=115200,
        timeout=2,
        gpio_chip=0,
        switch_gpio=23
    ):

        self.switch_gpio = switch_gpio

        self.chip = lgpio.gpiochip_open(
            gpio_chip
        )

        lgpio.gpio_claim_output(
            self.chip,
            self.switch_gpio
        )

        # UART-Verbindung aktivieren
        lgpio.gpio_write(
            self.chip,
            self.switch_gpio,
            0
        )

        time.sleep(0.05)

        self.ser = serial.Serial(
            port=port,
            baudrate=baudrate,
            timeout=timeout
        )

        time.sleep(0.2)


    def close(self):

        if self.ser:
            self.ser.close()

        if self.chip:
            # Switch wieder deaktivieren
            lgpio.gpio_write(
                self.chip,
                self.switch_gpio,
                1
            )

            lgpio.gpiochip_close(
                self.chip
            )


    def send_text(
        self,
        text,
        wait_ack=True
    ):

        if not isinstance(text, str):
            raise TypeError(
                "Text muss String sein"
            )

        message = (
            self.START +
            "\n" +
            text +
            "\n" +
            self.END +
            "\n"
        )

        self.ser.reset_input_buffer()

        self.ser.write(
            message.encode("utf-8")
        )

        self.ser.flush()

        if wait_ack:
            return self._wait_ack()

        return True


    def _wait_ack(
        self,
        timeout=3
    ):

        start = time.time()

        while time.time() - start < timeout:

            line = self.ser.readline()

            if not line:
                continue

            answer = line.decode(
                "utf-8",
                errors="ignore"
            ).strip()

            if answer == self.ACK:
                return True

        return False


    def __enter__(self):

        return self


    def __exit__(
        self,
        exc_type,
        exc,
        tb
    ):

        self.close()