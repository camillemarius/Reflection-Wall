"""
protocol.py

Format:

COMMAND|DATA

Beispiele:

GET|TEXT

TEXT|Hallo Welt
"""


class Protocol:


    SEPARATOR = "|"



    @staticmethod
    def encode(
        command,
        data=""
    ):

        return (
            command
            +
            Protocol.SEPARATOR
            +
            data
            +
            "\n"
        )



    @staticmethod
    def decode(
        message
    ):

        parts = message.split(
            Protocol.SEPARATOR,
            1
        )


        command = parts[0]

        data = ""


        if len(parts) > 1:

            data = parts[1]


        return command, data