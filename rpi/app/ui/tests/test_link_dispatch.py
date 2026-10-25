import concurrent.futures
import queue
import threading
import time
import unittest

from app.link.codec import Message
from app.link.pi_link import LinkBusy
from app.ui.activity import Activity
from app.ui.app_host import StopSignal
from app.ui.buttons import QueueButtons
from app.ui.link_dispatch import LinkDispatcher


class FakeLink:
    def __init__(self):
        self.incoming = queue.Queue()
        self.replies = []
        self.requests = []
        self.script = []  # je Aufruf: "busy", None oder Message

    def reply(self, request, command, data=""):
        self.replies.append((request.seq, command, data))
        return True

    def request(self, command, data=""):
        self.requests.append((command, data))
        step = self.script.pop(0) if self.script else Message(1, "OK", "")
        if step == "busy":
            raise LinkBusy()
        fut = concurrent.futures.Future()
        fut.set_result(step)
        return fut


def wait_for(cond, timeout=2.0):
    end = time.monotonic() + timeout
    while time.monotonic() < end:
        if cond():
            return True
        time.sleep(0.005)
    return False


class DispatchTest(unittest.TestCase):
    def setUp(self):
        self.link = FakeLink()
        self.buttons = QueueButtons()
        self.activity = Activity()
        self.stop = StopSignal()
        self.released = threading.Event()
        self.shutdowns = []
        self.d = LinkDispatcher(self.link, self.buttons, self.activity, self.stop,
                                self.released, on_shutdown=lambda: self.shutdowns.append(1))
        self.d.start()
        self.addCleanup(self.d.stop)

    def test_button_forwarded_and_acked(self):
        self.link.incoming.put(Message(7, "BUTTON", "5"))
        self.assertEqual(self.buttons.get(1.0), 5)
        self.assertTrue(wait_for(lambda: self.link.replies))
        self.assertEqual(self.link.replies, [(7, "OK", "")])

    def test_bad_button(self):
        for data in ("0", "7", "x", ""):
            self.link.incoming.put(Message(3, "BUTTON", data))
        self.assertTrue(wait_for(lambda: len(self.link.replies) == 4))
        self.assertTrue(all(r[1:] == ("ERROR", "BAD_BUTTON") for r in self.link.replies))
        self.assertIsNone(self.buttons.get(0))

    def test_shutdown_stops_shell_then_ok(self):
        self.link.incoming.put(Message(9, "SHUTDOWN", ""))
        self.assertTrue(wait_for(self.stop.is_set))
        self.assertEqual(self.stop.reason, "shutdown")
        time.sleep(0.05)
        self.assertEqual(self.link.replies, [])  # erst nach Freigabe
        self.released.set()
        self.assertTrue(wait_for(lambda: self.shutdowns))
        self.assertEqual(self.link.replies, [(9, "OK", "")])

    def test_shutdown_answers_after_wait_limit(self):
        d = LinkDispatcher(self.link, self.buttons, self.activity, self.stop,
                           self.released, release_wait_s=0.05)
        d.start()
        self.addCleanup(d.stop)
        self.d.stop()
        self.link.incoming.put(Message(2, "SHUTDOWN", ""))
        self.assertTrue(wait_for(lambda: self.link.replies))
        self.assertEqual(self.link.replies[0][1], "OK")

    def test_shutdown_busy_while_radar_writing(self):
        self.d.radar_writing.set()
        self.link.incoming.put(Message(4, "SHUTDOWN", ""))
        self.assertTrue(wait_for(lambda: self.link.replies))
        self.assertEqual(self.link.replies, [(4, "BUSY", "")])
        self.assertFalse(self.stop.is_set())
        self.assertEqual(self.shutdowns, [])

    def test_session_hand_sets_reason_and_event(self):
        self.assertIsNone(self.d.session_reason)
        self.link.incoming.put(Message(11, "SESSION", "HAND"))
        self.assertTrue(self.d.session_event.wait(1.0))
        self.assertEqual(self.d.session_reason, "HAND")
        self.assertTrue(wait_for(lambda: self.link.replies))
        self.assertEqual(self.link.replies, [(11, "OK", "")])

    def test_second_session_is_answered_and_ignored(self):
        self.link.incoming.put(Message(11, "SESSION", "HAND"))
        self.link.incoming.put(Message(12, "SESSION", "NACHT"))
        self.assertTrue(wait_for(lambda: len(self.link.replies) == 2))
        self.assertEqual(self.link.replies, [(11, "OK", ""), (12, "OK", "")])
        self.assertEqual(self.d.session_reason, "HAND")

    def test_session_bad_data_is_error(self):
        self.link.incoming.put(Message(13, "SESSION", "X"))
        self.assertTrue(wait_for(lambda: self.link.replies))
        self.assertEqual(self.link.replies, [(13, "ERROR", "BAD_SESSION")])
        self.assertIsNone(self.d.session_reason)
        self.assertFalse(self.d.session_event.is_set())

    def test_shutdown_sets_shutdown_done_after_reply(self):
        self.assertFalse(self.d.shutdown_done.is_set())
        self.link.incoming.put(Message(9, "SHUTDOWN", ""))
        self.assertTrue(wait_for(self.stop.is_set))
        self.assertFalse(self.d.shutdown_done.is_set())
        self.released.set()
        self.assertTrue(self.d.shutdown_done.wait(1.0))
        self.assertEqual(self.link.replies, [(9, "OK", "")])
        self.assertEqual(self.shutdowns, [1])

    def test_shutdown_busy_does_not_set_shutdown_done(self):
        self.d.radar_writing.set()
        self.link.incoming.put(Message(4, "SHUTDOWN", ""))
        self.assertTrue(wait_for(lambda: self.link.replies))
        self.assertFalse(self.d.shutdown_done.is_set())

    def test_other_requests_kept(self):
        m = Message(5, "GET", "X")
        self.link.incoming.put(m)
        self.assertTrue(wait_for(lambda: not self.d.other.empty()))
        self.assertIs(self.d.other.get_nowait(), m)
        self.assertEqual(self.link.replies, [])

    def test_stop_ends_thread_quickly(self):
        t0 = time.monotonic()
        self.d.stop()
        self.assertLess(time.monotonic() - t0, 0.5)


class SendDoneTest(unittest.TestCase):
    def make(self, script):
        link = FakeLink()
        link.script = list(script)
        self.now = 0.0
        self.sleeps = []

        def sleep(s):
            self.sleeps.append(s)
            self.now += s
        d = LinkDispatcher(link, QueueButtons(), Activity(), StopSignal(), threading.Event(),
                           clock=lambda: self.now, sleep=sleep)
        return d, link

    def test_ok_first_try(self):
        d, link = self.make([Message(1, "OK", "")])
        self.assertTrue(d.send_done())
        self.assertEqual(link.requests, [("DONE", "")])

    def test_retries_when_busy(self):
        d, link = self.make(["busy", "busy", Message(1, "OK", "")])
        self.assertTrue(d.send_done())
        self.assertEqual(self.sleeps, [0.25, 0.25])

    def test_resends_after_10s_when_no_answer(self):
        d, link = self.make([None, Message(1, "OK", "")])
        self.assertTrue(d.send_done())
        self.assertEqual(self.sleeps, [10.0])
        self.assertEqual(len(link.requests), 2)

    def test_gives_up_after_timeout(self):
        d, link = self.make(["busy"] * 1000)
        self.assertFalse(d.send_done(timeout_s=1.0))
        self.assertLessEqual(len(link.requests), 5)

    def test_gives_up_when_never_answered(self):
        d, link = self.make([None] * 10)
        self.assertFalse(d.send_done(timeout_s=30.0))
        self.assertEqual(len(link.requests), 3)


if __name__ == "__main__":
    unittest.main()
