# driver/uart/ld2410s.py
# HLK-LD2410S ueber die UART: Einstellungen lesen und schreiben, Energien je Tor, Anwesenheit.
# Bytes nach "HLK-LD2410S Serial Communication Protocol V1.00", am Geraet geprueft (Radar-Spec §12).
import struct
import time
from dataclasses import dataclass, field
from typing import Callable

GATES = 16
# Reihenfolge fest: so gehen die Kennungen raus und so kommen die Werte zurueck
GENERAL_IDS = {"farthest": 0x05, "nearest": 0x0A, "delay_s": 0x06, "status_hz10": 0x02,
               "distance_hz10": 0x0C, "speed": 0x0B}

CMD_HEAD, CMD_TAIL = b"\xfd\xfc\xfb\xfa", b"\x04\x03\x02\x01"
ENERGY_HEAD, ENERGY_TAIL = b"\xf4\xf3\xf2\xf1", b"\xf8\xf7\xf6\xf5"

ENABLE, END = 0x00FF, 0x00FE
WRITE_GENERAL, READ_GENERAL = 0x0070, 0x0071
WRITE_TRIGGER, READ_TRIGGER = 0x0072, 0x0073
WRITE_HOLD, READ_HOLD = 0x0076, 0x0077
OUTPUT = 0x007A
OUTPUT_STANDARD = bytes.fromhex("000001000000")
OUTPUT_MINIMAL = bytes.fromhex("000000000000")

READ_STEP_S = 0.02


class LD2410SError(RuntimeError):
    pass


@dataclass
class RadarSettings:
    general: dict = field(default_factory=dict)
    trigger: list = field(default_factory=list)
    hold: list = field(default_factory=list)

    def to_dict(self) -> dict:
        return {"general": dict(self.general), "trigger": list(self.trigger),
                "hold": list(self.hold)}

    @classmethod
    def from_dict(cls, d) -> "RadarSettings":
        try:
            general = {key: int(d["general"][key]) for key in GENERAL_IDS}
            trigger = [int(v) for v in d["trigger"]]
            hold = [int(v) for v in d["hold"]]
        except (KeyError, TypeError, ValueError) as exc:
            raise ValueError("keine Radar-Einstellungen: %s" % exc) from exc
        if len(trigger) != GATES or len(hold) != GATES:
            raise ValueError("Schwellen brauchen %d Tore" % GATES)
        return cls(general, trigger, hold)


def command_frame(cmd: int, value: bytes = b"") -> bytes:
    body = struct.pack("<H", cmd) + value
    return CMD_HEAD + struct.pack("<H", len(body)) + body + CMD_TAIL


def parse_acks(data: bytes) -> dict:
    """Antworten -> {Befehl | 0x0100: Status + Daten}. Gelesen bis zum Rahmenende, denn das
    Laengenfeld stimmt im Datenblatt-Beispiel nicht."""
    out, i = {}, 0
    while True:
        i = data.find(CMD_HEAD, i)
        if i < 0:
            return out
        tail = data.find(CMD_TAIL, i + 6)
        if tail < 0:
            return out
        body = data[i + 6:tail]
        if len(body) >= 4:
            out[struct.unpack("<H", body[:2])[0]] = body[2:]
        i = tail + 4


def parse_energies(data: bytes) -> list:
    """Messmodus-Meldungen -> je 16 Energiewerte."""
    out, i = [], 0
    while True:
        i = data.find(ENERGY_HEAD, i)
        if i < 0 or i + 6 > len(data):
            return out
        n = struct.unpack("<H", data[i + 4:i + 6])[0]
        body = data[i + 6:i + 6 + n]
        if (len(body) == n == 6 + 4 * GATES and body[0] == 0x01
                and data[i + 6 + n:i + 10 + n] == ENERGY_TAIL):
            out.append(list(struct.unpack("<%dI" % GATES, body[6:])))
            i += 10 + n
        else:
            i += 4


def parse_states(data: bytes) -> list:
    """Kurzmodus-Meldungen 6E Zustand Entfernung(2) 62 -> jemand da (Zustand 2 oder 3)."""
    out, i = [], 0
    while True:
        i = data.find(b"\x6e", i)
        if i < 0 or i + 5 > len(data):
            return out
        if data[i + 4] == 0x62 and data[i + 1] <= 3:
            out.append(data[i + 1] >= 2)
            i += 5
        else:
            i += 1


def _pairs(items) -> bytes:
    return b"".join(struct.pack("<HI", key, int(value)) for key, value in items)


def _words(ids) -> bytes:
    return b"".join(struct.pack("<H", i) for i in ids)


def _values(data: bytes, count: int) -> list:
    if len(data) < 4 * count:
        raise LD2410SError("Antwort zu kurz: %s" % data.hex())
    return list(struct.unpack("<%dI" % count, data[:4 * count]))


class LD2410S:
    def __init__(self, uart, clock: Callable[[], float] = time.monotonic,
                 sleep: Callable[[float], None] = time.sleep, ack_timeout_s: float = 1.0) -> None:
        self._uart = uart
        self._clock = clock
        self._sleep = sleep
        self._ack_timeout_s = ack_timeout_s

    def _transact(self, cmd: int, value: bytes = b"") -> bytes:
        """Befehl senden, auf die Antwort warten; gibt die Daten nach dem Status zurueck."""
        self._uart.read_all()  # Meldungen von vorher sind keine Antwort
        self._uart.write(command_frame(cmd, value))
        deadline = self._clock() + self._ack_timeout_s
        buffer = b""
        while True:
            buffer += self._uart.read_all() or b""
            payload = parse_acks(buffer).get(cmd | 0x0100)
            if payload is not None:
                status = struct.unpack("<H", payload[:2])[0]
                if status != 0:
                    raise LD2410SError("Befehl 0x%04X: Status %d" % (cmd, status))
                return payload[2:]
            if self._clock() >= deadline:
                raise LD2410SError("Befehl 0x%04X: keine Antwort" % cmd)
            self._sleep(READ_STEP_S)

    def _session(self, steps) -> list:
        """steps im Einstellmodus ausfuehren; der Einstellmodus wird immer verlassen."""
        self._transact(ENABLE, b"\x01\x00")
        try:
            answers = [self._transact(cmd, value) for cmd, value in steps]
        except LD2410SError:
            try:
                self._transact(END)
            except LD2410SError:
                pass
            raise
        self._transact(END)
        return answers

    def read_settings(self) -> RadarSettings:
        general, trigger, hold = self._session([
            (READ_GENERAL, _words(GENERAL_IDS.values())),
            (READ_TRIGGER, _words(range(GATES))),
            (READ_HOLD, _words(range(GATES)))])
        return RadarSettings(dict(zip(GENERAL_IDS, _values(general, len(GENERAL_IDS)))),
                             _values(trigger, GATES), _values(hold, GATES))

    def write_settings(self, settings: RadarSettings) -> None:
        self._session([
            (WRITE_GENERAL, _pairs((GENERAL_IDS[k], settings.general[k]) for k in GENERAL_IDS)),
            (WRITE_TRIGGER, _pairs(enumerate(settings.trigger))),
            (WRITE_HOLD, _pairs(enumerate(settings.hold)))])

    def minimal_mode(self) -> None:
        self._session([(OUTPUT, OUTPUT_MINIMAL)])

    def measure(self, seconds: float, wait: Callable[[float], None],
                settle_s: float = 2.0) -> list:
        """seconds lang Energien je Tor; ohne die ersten settle_s und ohne leere Meldungen.
        wait(s) wartet und darf werfen (Abbruch); der Kurzmodus kommt in jedem Fall zurueck."""
        self._session([(OUTPUT, OUTPUT_STANDARD)])
        try:
            timed = self._collect(seconds, wait, parse_energies)
        finally:
            self.minimal_mode()
        return [e for t, e in timed if t >= settle_s and any(e)]

    def watch(self, seconds: float, wait: Callable[[float], None]) -> list:
        """seconds lang Kurzmodus-Meldungen -> [(Sekunden seit Start, jemand da)]."""
        return self._collect(seconds, wait, parse_states)

    def _collect(self, seconds, wait, parse) -> list:
        start = self._clock()
        buffer, timed = b"", []
        while self._clock() - start < seconds:
            wait(0.1)
            data = self._uart.read_all()
            if not data:
                continue
            buffer += data
            items = parse(buffer)
            now = self._clock() - start
            timed.extend((now, item) for item in items[len(timed):])
        return timed
