"""Zeilenformat der Verbindung ESP-Pi: $NN:BEFEHL|DATEN*XX.

Gleiche Pruefreihenfolge und gleiche Fehlercodes wie esp/lib/core/src/LinkCodec.cpp.
"""
from dataclasses import dataclass

MAX_LINE = 256  # Bytes ohne b"\n"

_DIGITS = "0123456789ABCDEF"

_ESP_REQUESTS = frozenset({"PING", "GET", "BUTTON", "SHUTDOWN"})
_PI_REQUESTS = frozenset({"READY", "DONE", "MODE"})
_RESPONSES = frozenset({"PONG", "QUOTE", "OK", "BUSY", "ERROR"})


@dataclass(frozen=True)
class Message:
    seq: int  # 0..255
    command: str
    data: str = ""  # unmaskiert


class CodecError(ValueError):
    def __init__(self, code: str):
        super().__init__(code)
        self.code = code


class EncodeError(CodecError):
    pass


class DecodeError(CodecError):
    pass


def _printable(b: int) -> bool:
    return 0x20 <= b <= 0x7E


def _valid_command(cmd) -> bool:
    return len(cmd) > 0 and all(65 <= c <= 90 for c in cmd)


def _hex_val(b: int) -> int:
    if 0x30 <= b <= 0x39:
        return b - 0x30
    if 0x41 <= b <= 0x46:
        return b - 0x41 + 10
    if 0x61 <= b <= 0x66:
        return b - 0x61 + 10
    return -1


def _hex(v: int) -> str:
    return _DIGITS[v >> 4] + _DIGITS[v & 0x0F]


def _xor(data: bytes) -> int:
    s = 0
    for b in data:
        s ^= b
    return s


def encode(msg: Message) -> bytes:
    if not isinstance(msg.seq, int) or isinstance(msg.seq, bool) or not 0 <= msg.seq <= 255:
        raise EncodeError("BAD_FORMAT")
    if not all(ord(c) < 128 for c in msg.command) or not _valid_command(msg.command.encode("ascii")):
        raise EncodeError("BAD_COMMAND")

    escaped = []
    for c in msg.data:
        if c == "\\":
            escaped.append("\\\\")
        elif c == "\n":
            escaped.append(chr(92) + "n")
        elif c == "\r":
            escaped.append(chr(92) + "r")
        elif _printable(ord(c)):
            escaped.append(c)
        else:
            raise EncodeError("BAD_CHAR")
    payload = "".join(escaped)

    body = _hex(msg.seq) + ":" + msg.command
    if payload:
        body += "|" + payload
    body_bytes = body.encode("ascii")
    out = b"$" + body_bytes + b"*" + _hex(_xor(body_bytes)).encode("ascii")
    if len(out) > MAX_LINE:
        raise EncodeError("TOO_LONG")
    return out


def decode(line: bytes) -> Message:
    if not isinstance(line, (bytes, bytearray)):
        raise TypeError("decode erwartet bytes")
    line = bytes(line)
    if len(line) > MAX_LINE:
        raise DecodeError("TOO_LONG")
    if not line or line[0] != 0x24:  # '$'
        raise DecodeError("NO_START")
    if not all(_printable(b) for b in line):
        raise DecodeError("BAD_CHAR")

    star = line.rfind(b"*")
    if star == -1 or star + 3 != len(line):
        raise DecodeError("BAD_FORMAT")
    h1 = _hex_val(line[star + 1])
    h2 = _hex_val(line[star + 2])
    if h1 < 0 or h2 < 0:
        raise DecodeError("BAD_FORMAT")

    if _xor(line[1:star]) != h1 * 16 + h2:
        raise DecodeError("BAD_CHECKSUM")

    if star < 4:
        raise DecodeError("BAD_FORMAT")
    n1 = _hex_val(line[1])
    n2 = _hex_val(line[2])
    if n1 < 0 or n2 < 0 or line[3] != 0x3A:  # ':'
        raise DecodeError("BAD_FORMAT")

    pipe = line.find(b"|", 4)
    if pipe == -1 or pipe > star:
        pipe = star
    command = line[4:pipe]
    if not _valid_command(command):
        raise DecodeError("BAD_COMMAND")

    data = []
    if pipe < star:
        i = pipe + 1
        while i < star:
            c = line[i]
            if c != 0x5C:  # '\'
                data.append(chr(c))
                i += 1
                continue
            if i + 1 >= star:
                raise DecodeError("BAD_ESCAPE")
            e = line[i + 1]
            if e == 0x5C:
                data.append("\\")
            elif e == 0x6E:  # 'n'
                data.append("\n")
            elif e == 0x72:  # 'r'
                data.append("\r")
            else:
                raise DecodeError("BAD_ESCAPE")
            i += 2

    return Message(n1 * 16 + n2, command.decode("ascii"), "".join(data))


def role_of(command: str) -> str:
    if command in _ESP_REQUESTS:
        return "esp_request"
    if command in _PI_REQUESTS:
        return "pi_request"
    if command in _RESPONSES:
        return "response"
    return "unknown"


def deadline_ms(command: str) -> int:
    if command == "GET":
        return 120000
    if command == "SHUTDOWN":
        return 60000
    return 3000
