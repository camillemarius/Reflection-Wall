import time
import unittest

from app.link.codec import EncodeError, Message
from app.link.pi_link import LinkBusy, PiLink
from app.link.tests.fakes import FakeClock, FakePort

READY0 = b"$00:READY*71\n"


class PiLinkTest(unittest.TestCase):
    def setUp(self):
        self.clock = FakeClock()
        self.port = FakePort()
        self.link = PiLink(self.port, clock=self.clock)

    def feed_poll(self, data):
        self.port.feed(data)
        self.link.poll()

    def test_request_writes_one_frame(self):
        self.link.request("READY")
        self.assertEqual(self.port.take_tx(), READY0)

    def test_request_repeats_every_250ms_until_answer(self):
        fut = self.link.request("READY")
        self.port.take_tx()
        self.clock.now = 0.249
        self.link.poll()
        self.assertEqual(self.port.take_tx(), b"")
        self.clock.now = 0.25
        self.link.poll()
        self.assertEqual(self.port.take_tx(), READY0)
        self.feed_poll(b"$00:OK*3E\n")
        self.assertTrue(fut.done())
        self.assertEqual(fut.result(), Message(0, "OK"))
        self.clock.now = 0.75
        self.link.poll()
        self.assertEqual(self.port.take_tx(), b"")

    def test_request_expires_after_3s_with_12_frames(self):
        fut = self.link.request("READY")
        for i in range(1, 12):
            self.clock.now = i * 0.25
            self.link.poll()
        self.assertEqual(self.port.take_tx(), READY0 * 12)
        self.assertFalse(fut.done())
        self.clock.now = 3.0
        self.link.poll()
        self.assertTrue(fut.done())
        self.assertIsNone(fut.result())
        self.assertEqual(self.port.take_tx(), b"")

    def test_numbers_count_per_request_not_per_repeat(self):
        self.link.request("READY")
        self.clock.now = 0.25
        self.link.poll()
        self.port.take_tx()
        self.feed_poll(b"$00:OK*3E\n")
        self.link.request("READY")
        self.assertEqual(self.port.take_tx(), b"$01:READY*70\n")

    def test_second_request_while_open_raises_link_busy(self):
        self.link.request("READY")
        with self.assertRaises(LinkBusy):
            self.link.request("READY")

    def test_unencodable_request_raises_and_keeps_number(self):
        with self.assertRaises(EncodeError):
            self.link.request("GET", "QUOTE|Ä")
        self.assertEqual(self.port.take_tx(), b"")
        self.link.request("READY")
        self.assertEqual(self.port.take_tx(), READY0)

    def test_late_answer_for_previous_number_is_ignored(self):
        self.link.request("READY")
        self.feed_poll(b"$00:OK*3E\n")
        fut2 = self.link.request("READY")
        self.port.take_tx()
        self.feed_poll(b"$00:OK*3E\n")
        self.assertFalse(fut2.done())
        self.assertEqual(sum(self.link.discarded.values()), 0)

    def test_ping_is_answered_by_the_link(self):
        self.feed_poll(b"$03:PING*29\n")
        self.assertEqual(self.port.take_tx(), b"$03:PONG*2F\n")
        self.assertTrue(self.link.incoming.empty())

    def test_button_goes_to_incoming_and_reply_is_sent(self):
        self.feed_poll(b"$09:BUTTON|1*68\n")
        msg = self.link.incoming.get_nowait()
        self.assertEqual(msg, Message(9, "BUTTON", "1"))
        self.assertTrue(self.link.reply(msg, "OK"))
        self.assertEqual(self.port.take_tx(), b"$09:OK*37\n")

    def test_duplicate_gets_previous_answer_again(self):
        self.feed_poll(b"$09:BUTTON|1*68\n")
        msg = self.link.incoming.get_nowait()
        self.link.reply(msg, "OK")
        self.port.take_tx()
        self.feed_poll(b"$09:BUTTON|1*68\n")
        self.assertEqual(self.port.take_tx(), b"$09:OK*37\n")
        self.assertTrue(self.link.incoming.empty())

    def test_repeated_get_quote_before_reply_is_delivered_once(self):
        line = b"$11:GET|QUOTE|DER WEG IST DAS ZIEL.*1C\n"
        for _ in range(4):
            self.feed_poll(line)
        self.assertEqual(self.link.incoming.qsize(), 1)
        self.assertEqual(self.port.take_tx(), b"")
        msg = self.link.incoming.get_nowait()
        self.link.reply(msg, "QUOTE", "WAS BLEIBT IST DIE FRAGE.")
        self.assertEqual(self.port.take_tx(), b"$11:QUOTE|WAS BLEIBT IST DIE FRAGE.*32\n")

    def test_second_reply_is_refused(self):
        self.feed_poll(b"$09:BUTTON|1*68\n")
        msg = self.link.incoming.get_nowait()
        self.assertTrue(self.link.reply(msg, "OK"))
        self.port.take_tx()
        self.assertFalse(self.link.reply(msg, "OK"))
        self.assertEqual(self.port.take_tx(), b"")

    def test_unknown_command_is_answered_with_error_unknown(self):
        self.feed_poll(b"$05:READY*74\n")
        self.assertEqual(self.port.take_tx(), b"$05:ERROR|UNKNOWN*53\n")
        self.assertTrue(self.link.incoming.empty())

    def test_bad_line_is_counted_logged_and_not_answered(self):
        with self.assertLogs("link", "WARNING"):
            self.feed_poll(b"$00:PING*2B\n")
        self.assertEqual(self.link.discarded["BAD_CHECKSUM"], 1)
        self.assertEqual(self.port.take_tx(), b"")

    def test_lowercase_command_is_counted_not_answered(self):
        body = b"05:ping"
        x = 0
        for b in body:
            x ^= b
        line = b"$" + body + b"*" + ("%02X" % x).encode() + b"\n"
        with self.assertLogs("link", "WARNING"):
            self.feed_poll(line)
        self.assertEqual(self.link.discarded["BAD_COMMAND"], 1)
        self.assertEqual(self.port.take_tx(), b"")

    def test_esp_debug_line_is_logged(self):
        with self.assertLogs("link", "INFO") as cm:
            self.feed_poll(b"[WALL] aus\r\n")
        self.assertIn("ESP| [WALL] aus", "\n".join(cm.output))
        self.assertEqual(self.link.discarded["NO_START"], 1)

    def test_empty_lines_are_not_counted(self):
        self.feed_poll(b"\n\r\n$03:PING*29\n\n")
        self.assertEqual(self.port.take_tx(), b"$03:PONG*2F\n")
        self.assertEqual(sum(self.link.discarded.values()), 0)

    def test_too_long_line_is_dropped_and_next_line_is_read(self):
        with self.assertLogs("link", "WARNING"):
            self.feed_poll(b"A" * 300 + b"\n$03:PING*29\n")
        self.assertEqual(self.link.discarded["TOO_LONG"], 1)
        self.assertEqual(self.port.take_tx(), b"$03:PONG*2F\n")

    def test_partial_line_waits_for_newline(self):
        self.feed_poll(b"$03:PI")
        self.assertEqual(self.port.take_tx(), b"")
        self.feed_poll(b"NG*29\n")
        self.assertEqual(self.port.take_tx(), b"$03:PONG*2F\n")

    def test_garbage_bytes_do_not_raise(self):
        self.feed_poll(b"\xff\xfe\x00\n$03:PING*29\n")
        self.assertEqual(self.port.take_tx(), b"$03:PONG*2F\n")


class PiLinkThreadTest(unittest.TestCase):
    def setUp(self):
        self.port = FakePort()
        self.link = PiLink(self.port)
        self.addCleanup(self.link.stop)

    def wait_for(self, cond, timeout=1.0):
        end = time.monotonic() + timeout
        while time.monotonic() < end:
            if cond():
                return True
            time.sleep(0.005)
        return cond()

    def test_thread_round_trip(self):
        self.link.start()
        self.assertTrue(self.link.alive)
        self.port.feed(b"$03:PING*29\n")
        got = bytearray()

        def seen():
            got.extend(self.port.take_tx())
            return b"$03:PONG*2F\n" in got
        self.assertTrue(self.wait_for(seen))
        fut = self.link.request("READY")
        self.port.feed(b"$00:OK*3E\n")
        self.assertEqual(fut.result(timeout=1), Message(0, "OK"))
        self.link.stop()
        self.assertFalse(self.link.alive)

    def test_port_error_ends_thread_and_open_request(self):
        with self.assertLogs("link", "ERROR"):
            self.link.start()
            fut = self.link.request("READY")
            self.port.fail = OSError("Port weg")
            self.assertIsNone(fut.result(timeout=1))
            self.assertTrue(self.wait_for(lambda: not self.link.alive))
        self.assertIsNone(self.link.request("READY").result(timeout=0))


if __name__ == "__main__":
    unittest.main()
