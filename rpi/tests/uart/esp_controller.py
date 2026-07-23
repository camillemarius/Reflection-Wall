"""
esp_controller.py

Raspberry Pi Controller

Beantwortet Anfragen
vom ESP8266.
"""


from uart import UART
from uart_switch import UARTSwitch
from protocol import Protocol
from commands import Commands



class ESPController:


    def __init__(self, text_provider, config_provider=None, port="/dev/serial0", baudrate=115200, switch_gpio=23):

        self.text_provider = text_provider
        self.config_provider = config_provider

        self.switch = UARTSwitch(
            gpio=switch_gpio
        )

        self.uart = UART(
            port=port,
            baudrate=baudrate
        )


    def loop(self):
        self.switch.enable()
        try:
            if self.uart.available():
                message = self.uart.readline()
                command, data = Protocol.decode(
                    message
                )
                self.handle(
                    command,
                    data
                )

        finally:
            self.switch.disable()



    def handle(self, command, data):
        # ESP fordert Daten an
        if command == Commands.GET:
            # Text senden
            if data == Commands.TEXT:
                text = self.text_provider()
                self.send(Commands.TEXT,text)

            # Konfiguration senden
            elif data == Commands.CONFIG:
                if self.config_provider:
                    config = self.config_provider()
                    self.send(
                        Commands.CONFIG,
                        config
                    )


        # ESP sendet Daten
        elif command == Commands.SET:
            self.handle_set(
                data
            )



    def handle_set(self, data):
        """
        Verarbeitung von
        SET Nachrichten

        Beispiel:
        SET|CONFIG
        """

        self.send(
            Commands.OK,
            data
        )



    def send(self, command, data=""):
        message = Protocol.encode(
            command,
            data
        )
        self.switch.enable()
        try:
            self.uart.write(
                message
            )
        finally:
            self.switch.disable()



    def close(self):
        self.uart.close()
        self.switch.close()