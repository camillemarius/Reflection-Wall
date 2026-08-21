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
    def encode(command, data=""):
        return f"{command}{Protocol.SEPARATOR}{data}\n"

    @staticmethod
    def decode(message):
        command, _, data = message.strip().partition(Protocol.SEPARATOR)
        return command, data