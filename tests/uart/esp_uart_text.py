"""
esp_uart_text.py

Spezialisierte UART Klasse für ESP-12F
mit Hardware-UART-Umschaltung.

Ablauf:
---------
1. GPIO23 LOW
2. UART Verbindung aktiv
3. Text senden
4. ACK vom ESP warten
5. GPIO23 HIGH


Benötigt:
---------
pip install pyserial lgpio
"""


from uart_text import ESPTextUART
from uart_switch import UARTSwitch



class SwitchedESPTextUART:



    def __init__(
        self,
        port="/dev/serial0",
        baudrate=115200,
        timeout=2,
        switch_gpio=23,
        gpio_chip=0
    ):


        self.switch = UARTSwitch(
            gpio=switch_gpio,
            gpio_chip=gpio_chip
        )


        self.uart = ESPTextUART(
            port=port,
            baudrate=baudrate,
            timeout=timeout
        )



    # ---------------------------------------------
    # Text senden
    # ---------------------------------------------

    def send_text(
        self,
        text,
        wait_ack=True
    ):


        self.switch.enable()


        try:

            result = self.uart.send_text(
                text,
                wait_ack
            )

        finally:

            self.switch.disable()



        return result



    # ---------------------------------------------
    # Dauerhafte Verbindung
    # ---------------------------------------------

    def connect(self):

        """
        UART-Switch dauerhaft aktivieren
        """

        self.switch.enable()



    def disconnect(self):

        """
        UART-Switch deaktivieren
        """

        self.switch.disable()



    # ---------------------------------------------
    # Schliessen
    # ---------------------------------------------

    def close(self):

        self.uart.close()

        self.switch.close()



    # ---------------------------------------------
    # Context Manager
    # ---------------------------------------------

    def __enter__(self):

        return self



    def __exit__(
        self,
        exc_type,
        exc,
        tb
    ):

        self.close()