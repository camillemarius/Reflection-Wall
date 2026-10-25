import concurrent.futures
import time
import unittest

import serial

from app.driver.uart.uart_hlk import UARTHLK
from app.link.codec import Message, decode, encode
from app.link.pi_link import LinkBusy, PiLink
from app.link.radar_switch import RadarSwitch, RadarSwitchError, RadarUart
from app.link.tests.fakes import FakeClock, FakePort

RADAR_FRAME = bytes([0x6E, 0x02, 0x23, 0x00, 0x62])  # Person, 35 cm
LEAVE = [("baud", 74880), ("gpio23", 0), "resume", ("request", "MODE|NORMAL")]


class FakeSerial:
    def __init__(self, events):
        self.events = events

    def reset_input_buffer(self):
        self.events.append("flush")


class SwitchPort:
    """Schreibt jede Umschaltung in events; einzelne Schritte koennen scheitern."""

    def __init__(self, events):
        self.events = events
        self.serial = FakeSerial(events)
        self.gpio_error = None
        self.baud_errors = {}

    def select_radar(self, on):
        self.events.append(("gpio23", 1 if on else 0))
        if on and self.gpio_error is not None:
            raise self.gpio_error

    def set_baud(self, baud):
        self.events.append(("baud", baud))
        if baud in self.baud_errors:
            raise self.baud_errors[baud]


class FakeLink:
    """Antwortet je Anfrage mit dem naechsten Eintrag aus answers (Message, None oder Ausnahme)."""

    def __init__(self, events):
        self.events = events
        self.answers = []
        self.pause_error = None

    def request(self, command, data=""):
        answer = self.answers.pop(0) if self.answers else Message(0, "OK")
        if isinstance(answer, Exception):
            self.events.append(("busy", command + "|" + data))
            raise answer
        self.events.append(("request", command + "|" + data))
        fut = concurrent.futures.Future()
        fut.set_result(answer)
        return fut

    def pause(self):
        if self.pause_error is not None:
            raise self.pause_error
        self.events.append("pause")

    def resume(self):
        self.events.append("resume")


class RadarSwitchTest(unittest.TestCase):
    def setUp(self):
        self.events = []
        self.link = FakeLink(self.events)
        self.port = SwitchPort(self.events)
        self.clock = FakeClock()
        self.sleeps = []

        def sleep(seconds):
            self.sleeps.append(seconds)
            self.clock.advance(seconds)
        self.switch = RadarSwitch(self.link, self.port, clock=self.clock, sleep=sleep)

    def test_enter_order(self):
        uart = self.switch.enter()
        self.assertEqual(self.events, [("request", "MODE|RADAR"), "pause", ("gpio23", 1),
                                       ("baud", 115200), "flush"])
        self.assertIsInstance(uart, RadarUart)

    def test_enter_without_ok_raises_and_stays_esp(self):
        self.link.answers = [None]
        with self.assertRaises(RadarSwitchError):
            self.switch.enter()
        self.assertEqual(self.events, [("request", "MODE|RADAR")])

    def test_leave_order(self):
        self.switch.enter()
        self.events.clear()
        self.assertTrue(self.switch.leave())
        self.assertEqual(self.events, LEAVE)

    def test_leave_runs_after_error(self):
        with self.assertRaises(RuntimeError):
            with self.switch as uart:
                self.assertIsInstance(uart, RadarUart)
                self.events.clear()
                raise RuntimeError("Radar kaputt")
        self.assertEqual(self.events, LEAVE)

    def test_enter_without_ok_in_with_still_sends_mode_normal(self):
        self.link.answers = [None]  # danach OK
        with self.assertRaises(RadarSwitchError):
            with self.switch:
                self.fail("Rumpf darf nicht laufen")
        self.assertEqual(self.events, [("request", "MODE|RADAR"), ("request", "MODE|NORMAL")])

    def test_refused_mode_radar_needs_no_mode_normal(self):
        self.link.answers = [Message(0, "ERROR", "UNKNOWN")]
        with self.assertRaises(RadarSwitchError):
            with self.switch:
                pass
        self.assertEqual(self.events, [("request", "MODE|RADAR")])

    def test_enter_failing_part_way_switches_back_what_was_switched(self):
        self.port.gpio_error = OSError("GPIO weg")
        with self.assertRaises(OSError):
            with self.switch:
                pass
        self.assertEqual(self.events, [("request", "MODE|RADAR"), "pause", ("gpio23", 1),
                                       ("gpio23", 0), "resume", ("request", "MODE|NORMAL")])

    def test_refused_pause_leaves_gpio_and_baud_alone(self):
        self.link.pause_error = LinkBusy("Anfrage offen")
        with self.assertRaises(LinkBusy):
            with self.switch:
                pass
        self.assertEqual(self.events, [("request", "MODE|RADAR"), "resume",
                                       ("request", "MODE|NORMAL")])

    def test_mode_normal_repeats_every_quarter_second_until_ok(self):
        self.switch.enter()
        self.events.clear()
        self.link.answers = [None, LinkBusy(), Message(1, "BUSY"), Message(2, "OK")]
        self.assertTrue(self.switch.leave())
        tries = [e for e in self.events if isinstance(e, tuple) and e[1] == "MODE|NORMAL"]
        self.assertEqual(len(tries), 4)
        self.assertEqual(self.sleeps, [0.25, 0.25, 0.25])

    def test_mode_normal_gives_up_after_30_s(self):
        self.switch.enter()
        self.link.answers = [None] * 1000
        with self.assertLogs("app.link.radar_switch", "ERROR"):
            self.assertFalse(self.switch.leave())
        self.assertGreaterEqual(self.clock.now, 30.0)
        self.assertLessEqual(self.clock.now, 30.25)

    def test_a_failing_step_in_leave_does_not_stop_the_others(self):
        self.switch.enter()
        self.events.clear()
        self.port.baud_errors[74880] = OSError("Port weg")
        with self.assertLogs("app.link.radar_switch", "ERROR"):
            self.assertFalse(self.switch.leave())
        self.assertEqual(self.events, LEAVE)

    def test_switch_can_be_used_again(self):
        for _ in range(2):
            self.events.clear()
            with self.switch:
                pass
            self.assertEqual(self.events[-4:], LEAVE)
            self.assertEqual(len(self.events), 9)


class EspPort(FakePort):
    """Port mit Umschalter; antwortet wie der ESP mit OK auf MODE|..."""

    def __init__(self, events):
        super().__init__()
        self.events = events
        self.serial = FakeSerial(events)

    def write(self, data):
        super().write(data)
        msg = decode(data.rstrip(b"\n"))
        if msg.command == "MODE":
            self.events.append(("esp", msg.data))
            self.feed(encode(Message(msg.seq, "OK")) + b"\n")

    def select_radar(self, on):
        self.events.append(("gpio23", 1 if on else 0))

    def set_baud(self, baud):
        self.events.append(("baud", baud))


class RadarSwitchWithPiLinkTest(unittest.TestCase):
    def test_round_trip_leaves_radar_bytes_out_of_the_link(self):
        events = []
        port = EspPort(events)
        link = PiLink(port)
        self.addCleanup(link.stop)
        link.start()
        switch = RadarSwitch(link, port, normal_timeout_s=2.0)
        switch.enter()
        reads = port.reads
        port.feed(RADAR_FRAME * 4)  # gehoert dem Radar, nicht dem Link
        time.sleep(0.05)
        self.assertEqual(port.reads, reads)
        self.assertTrue(switch.leave())
        self.assertEqual(events, [("esp", "RADAR"), ("gpio23", 1), ("baud", 115200), "flush",
                                  ("baud", 74880), ("gpio23", 0), ("esp", "NORMAL")])
        self.assertEqual(sum(link.discarded.values()), 0)
        self.assertTrue(link.alive)


class RadarUartTest(unittest.TestCase):
    def setUp(self):
        self.ser = serial.serial_for_url("loop://", timeout=0.05)
        self.addCleanup(self.ser.close)

    def test_hlk_reads_frames_through_the_shared_port(self):
        sensor = UARTHLK(RadarUart(self.ser))
        self.ser.write(RADAR_FRAME)
        sensor.update()
        self.assertTrue(sensor.present)
        self.assertEqual(sensor.distance, 35)
        self.assertGreater(sensor.data.timestamp, 0)

    def test_passes_reads_and_writes_to_the_serial(self):
        uart = RadarUart(self.ser)
        uart.select(object())  # Umschalten gehoert RadarSwitch
        uart.write(b"ab\ncd")
        self.assertEqual(uart.available, 5)
        self.assertEqual(uart.read(1), b"a")
        self.assertEqual(uart.readline(), b"b\n")
        self.assertEqual(uart.read_all(), b"cd")


if __name__ == "__main__":
    unittest.main()
