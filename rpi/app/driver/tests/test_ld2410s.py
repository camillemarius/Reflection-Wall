"""Tests fuer den LD2410S-Treiber mit nachgebildetem Radar und Fake-Uhr (Spec §12)."""
import struct
import unittest

from app.driver.uart.ld2410s import (GENERAL_IDS, LD2410S, LD2410SError, RadarSettings,
                                     command_frame, parse_acks, parse_energies, parse_states)

HEAD, TAIL = b"\xfd\xfc\xfb\xfa", b"\x04\x03\x02\x01"
WERK_GENERAL = {"farthest": 2, "nearest": 0, "delay_s": 10, "status_hz10": 80,
                "distance_hz10": 5, "speed": 10}
WERK_TRIGGER = [48, 42, 36, 34, 32] + [31] * 11
WERK_HOLD = [45, 42, 33, 32] + [28] * 12


class Clock:
    def __init__(self):
        self.now = 0.0

    def __call__(self):
        return self.now

    def advance(self, seconds):
        self.now += seconds


def ack(cmd, data=b"", status=0, length=None):
    body = struct.pack("<HH", cmd | 0x0100, status) + data
    return HEAD + struct.pack("<H", len(body) if length is None else length) + body + TAIL


def energy_frame(energies, state=0):
    body = bytes([0x01, state]) + struct.pack("<HH", 0, 0) + b"".join(
        struct.pack("<I", e) for e in energies)
    return b"\xf4\xf3\xf2\xf1" + struct.pack("<H", len(body)) + body + b"\xf8\xf7\xf6\xf5"


def state_frame(state):
    return bytes([0x6E, state]) + struct.pack("<H", 100) + b"\x62"


class FakeRadar:
    """Antwortet auf Befehlsrahmen wie der LD2410S und sendet je nach Ausgabe Meldungen."""

    FRAME_S = 0.25
    STATE_S = 0.125

    def __init__(self, clock):
        self.clock = clock
        self.general = dict(WERK_GENERAL)
        self.trigger = list(WERK_TRIGGER)
        self.hold = list(WERK_HOLD)
        self.output = "minimal"
        self.commands = []
        self.status = {}
        self.silent = set()
        self.silent_once = set()  # Befehle, deren naechste Antwort verloren geht
        self.broken = set()  # Befehle, bei denen die UART selbst einen Fehler wirft
        self.energies = lambda k: [1000] * 16  # k-te Meldung seit dem Umschalten
        self.present = lambda t: False
        self._pending = b""
        self._mode_since = 0.0
        self._emitted = 0
        self._ids = {v: k for k, v in GENERAL_IDS.items()}

    def write(self, data):
        while data:
            assert data[:4] == HEAD, data.hex()
            n = struct.unpack("<H", data[4:6])[0]
            cmd = struct.unpack("<H", data[6:8])[0]
            value = data[8:6 + n]
            assert data[6 + n:10 + n] == TAIL
            data = data[10 + n:]
            self.commands.append(cmd)
            if cmd in self.broken:
                raise OSError("serieller Fehler")
            answer = self._answer(cmd, value)
            if cmd in self.silent or cmd in self.silent_once:
                self.silent_once.discard(cmd)
                continue
            self._pending += ack(cmd, answer, self.status.get(cmd, 0))

    def _answer(self, cmd, value):
        words = [struct.unpack("<H", value[i:i + 2])[0] for i in range(0, len(value) - 1, 2)]
        pairs = [struct.unpack("<HI", value[i:i + 6]) for i in range(0, len(value) - 5, 6)]
        if cmd == 0x00FF:
            return bytes.fromhex("03008000")
        if cmd == 0x0071:
            return b"".join(struct.pack("<I", self.general[self._ids[w]]) for w in words)
        if cmd in (0x0073, 0x0077):
            table = self.trigger if cmd == 0x0073 else self.hold
            return b"".join(struct.pack("<I", table[w]) for w in words)
        if cmd == 0x0070:
            for key, val in pairs:
                self.general[self._ids[key]] = val
        if cmd in (0x0072, 0x0076):
            table = self.trigger if cmd == 0x0072 else self.hold
            for gate, val in pairs:
                table[gate] = val
        if cmd == 0x007A:
            self.output = "standard" if value == bytes.fromhex("000001000000") else "minimal"
            self._mode_since, self._emitted = self.clock(), 0
        return b""

    def read_all(self):
        out, self._pending = self._pending, b""
        step = self.FRAME_S if self.output == "standard" else self.STATE_S
        while self._mode_since + (self._emitted + 1) * step <= self.clock() + 1e-9:
            t = self._mode_since + (self._emitted + 1) * step
            if self.output == "standard":
                out += energy_frame(self.energies(self._emitted))
            else:
                out += state_frame(2 if self.present(t) else 0)
            self._emitted += 1
        return out


class FramesTest(unittest.TestCase):
    def test_command_frame_enable(self):
        self.assertEqual(command_frame(0x00FF, b"\x01\x00"),
                         bytes.fromhex("fdfcfbfa0400ff00010004030201"))

    def test_parse_acks_reads_to_tail_despite_wrong_length(self):
        data = b"\x6e\x00\x00\x00\x62" + ack(0x00FF, bytes.fromhex("03008000"), length=0x1A)
        self.assertEqual(parse_acks(data), {0x01FF: bytes.fromhex("000003008000")})

    def test_parse_energies_and_states(self):
        energies = list(range(100, 116))
        data = b"\x00" + energy_frame(energies, state=2) + energy_frame([0] * 16)[:20]
        self.assertEqual(parse_energies(data), [energies])
        self.assertEqual(parse_states(state_frame(1) + state_frame(2) + b"\x6e\x03"),
                         [False, True])


class DriverTest(unittest.TestCase):
    def setUp(self):
        self.clock = Clock()
        self.fake = FakeRadar(self.clock)
        self.radar = LD2410S(self.fake, clock=self.clock, sleep=self.clock.advance)

    def wait(self, seconds):
        self.clock.advance(seconds)

    def test_read_settings_factory_values(self):
        self.assertEqual(self.radar.read_settings(),
                         RadarSettings(WERK_GENERAL, WERK_TRIGGER, WERK_HOLD))

    def test_write_then_read_back_equal(self):
        wanted = RadarSettings({"farthest": 3, "nearest": 0, "delay_s": 30, "status_hz10": 80,
                                "distance_hz10": 40, "speed": 5},
                               [48, 42, 35, 34] + [31] * 12, [45, 42, 34, 32] + [28] * 12)
        self.radar.write_settings(wanted)
        self.assertEqual(self.radar.read_settings(), wanted)

    def test_write_sends_one_config_session(self):
        self.radar.write_settings(RadarSettings(WERK_GENERAL, WERK_TRIGGER, WERK_HOLD))
        self.assertEqual(self.fake.commands, [0x00FF, 0x0070, 0x0072, 0x0076, 0x00FE])

    def test_nonzero_status_raises(self):
        self.fake.status[0x0072] = 1
        with self.assertRaises(LD2410SError):
            self.radar.write_settings(RadarSettings(WERK_GENERAL, WERK_TRIGGER, WERK_HOLD))
        self.assertEqual(self.fake.commands[-1], 0x00FE)  # Einstellmodus wieder verlassen

    def test_missing_ack_raises_after_timeout(self):
        self.fake.silent.add(0x0071)
        with self.assertRaises(LD2410SError):
            self.radar.read_settings()
        self.assertLess(self.clock.now, 5.0)

    def test_measure_drops_settle_and_zero_frames(self):
        # Meldung k traegt k als Energie; jede fuenfte ist leer
        self.fake.energies = lambda k: [0] * 16 if k % 5 == 4 else [k + 1] * 16
        frames = self.radar.measure(5.0, self.wait)
        firsts = [f[0] for f in frames]
        self.assertTrue(firsts)
        # Meldung k kommt nach (k + 1) * 0,25 s: vor 2 s sind es die Meldungen 0..6
        self.assertGreaterEqual(min(firsts), 8)
        self.assertNotIn(0, [e for f in frames for e in f])
        self.assertEqual(self.fake.output, "minimal")

    def test_measure_restores_minimal_mode_when_wait_raises(self):
        def wait(seconds):
            self.clock.advance(seconds)
            if self.clock.now > 1.0:
                raise KeyboardInterrupt

        with self.assertRaises(KeyboardInterrupt):
            self.radar.measure(30.0, wait)
        self.assertEqual(self.fake.output, "minimal")

    def test_watch_returns_times_and_states(self):
        self.fake.present = lambda t: t >= 1.0
        seen = self.radar.watch(2.0, self.wait)
        self.assertTrue(seen)
        self.assertFalse(seen[0][1])
        self.assertTrue(seen[-1][1])
        self.assertTrue(all(t <= 2.0 + 1e-6 for t, _ in seen))

    def test_end_is_sent_even_if_enable_ack_is_lost(self):
        self.fake.silent_once.add(0x00FF)
        with self.assertRaises(LD2410SError):
            self.radar.read_settings()
        self.assertEqual(self.fake.commands[-1], 0x00FE)

    def test_end_is_sent_after_a_serial_error(self):
        self.fake.broken.add(0x0072)
        with self.assertRaises(OSError):
            self.radar.write_settings(RadarSettings(WERK_GENERAL, WERK_TRIGGER, WERK_HOLD))
        self.assertEqual(self.fake.commands[-1], 0x00FE)

    def test_measure_back_to_minimal_when_switching_fails(self):
        self.fake.silent_once.add(0x00FE)  # Ausgabe umgeschaltet, Antwort auf END verloren
        with self.assertRaises(LD2410SError):
            self.radar.measure(5.0, self.wait)
        self.assertEqual(self.fake.output, "minimal")

    def test_measure_abort_is_not_masked_by_failing_minimal_mode(self):
        class Abort(Exception):
            pass

        def wait(seconds):
            self.clock.advance(seconds)
            if self.clock.now > 1.0:
                self.fake.silent.add(0x007A)
                raise Abort()

        with self.assertRaises(Abort):
            self.radar.measure(30.0, wait)

    def test_watch_ignores_input_from_before(self):
        self.fake.present = lambda t: t < 5.0
        self.clock.advance(10.0)  # zehn Sekunden niemand gelesen: alte Meldungen im Puffer
        seen = self.radar.watch(1.0, self.wait)
        self.assertTrue(seen)
        self.assertFalse(any(present for _, present in seen))

    def test_settings_dict_roundtrip_and_bad_form(self):
        settings = RadarSettings(WERK_GENERAL, WERK_TRIGGER, WERK_HOLD)
        self.assertEqual(RadarSettings.from_dict(settings.to_dict()), settings)
        for bad in ({}, {"general": {}, "trigger": [1] * 16, "hold": [1] * 16},
                    {"general": WERK_GENERAL, "trigger": [1] * 15, "hold": [1] * 16}):
            with self.assertRaises(ValueError):
                RadarSettings.from_dict(bad)


if __name__ == "__main__":
    unittest.main()
