"""
uart_esp.py

UART Interface für ESP8266.
Verarbeitet Kommunikation zwischen
Raspberry Pi und ESP.
"""

from __future__ import annotations

from .uart_switch import UARTSwitch
from .uart_device import UARTDevice

from .protocol import Protocol
from .commands import Commands


class UARTESP(UARTDevice):

    def __init__(
        self,
        uart,
        text_provider=None,
        config_provider=None
    ):
        super().__init__(uart)

        self.text_provider = text_provider
        self.config_provider = config_provider


    @property
    def device(self):
        return UARTSwitch.Device.ESP


    # ---------------------
    # Loop
    # ---------------------

    def update(self):

        self.select()

        if not self.uart.available:
            return

        message = self.uart.readline()

        if not message:
            return

        command, data = Protocol.decode(
            message
        )

        self.handle(
            command,
            data
        )


    # ---------------------
    # Commands
    # ---------------------

    def handle(self, command, data):

        if command == Commands.GET:
            self.handle_get(data)

        elif command == Commands.SET:
            self.handle_set(data)


    def handle_get(self, data):

        if data == Commands.TEXT:

            if self.text_provider:

                self.send(
                    Commands.TEXT,
                    self.text_provider()
                )


        elif data == Commands.CONFIG:

            if self.config_provider:

                self.send(
                    Commands.CONFIG,
                    self.config_provider()
                )


    def handle_set(self, data):

        """
        Verarbeitung von
        SET Nachrichten.

        Beispiel:
        SET|CONFIG
        """

        self.send(
            Commands.OK,
            data
        )


    # ---------------------
    # Kommunikation
    # ---------------------

    def send(
        self,
        command,
        data=""
    ):

        message = Protocol.encode(
            command,
            data
        )

        self.select()

        self.uart.write(
            message
        )


    def request(
        self,
        command,
        data=""
    ):

        self.send(
            command,
            data
        )


        if self.uart.available:

            return Protocol.decode(
                self.uart.readline()
            )

        return None