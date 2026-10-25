# link/tests/test_ready.py
import concurrent.futures
import unittest

from app.link.codec import Message
from app.link.pi_link import LinkBusy
from app.link.ready import announce_ready
from app.ui.app_host import StopSignal


class ScriptLink:
    def __init__(self, script):
        self.script = list(script)  # je Aufruf: "busy", None oder Message
        self.requests = []

    def request(self, command, data=""):
        self.requests.append((command, data))
        step = self.script.pop(0) if self.script else Message(1, "OK", "")
        if step == "busy":
            raise LinkBusy()
        fut = concurrent.futures.Future()
        fut.set_result(step)
        return fut


class ReadyTest(unittest.TestCase):
    def setUp(self):
        self.sleeps = []
        self.stop = StopSignal()

    def run_ready(self, link):
        return announce_ready(link, self.stop, sleep=self.sleeps.append)

    def test_ready_returns_true_on_ok(self):
        link = ScriptLink([Message(1, "OK", "")])
        self.assertTrue(self.run_ready(link))
        self.assertEqual(link.requests, [("READY", "")])

    def test_ready_repeats_after_deadline_with_new_request(self):
        link = ScriptLink([None, Message(2, "OK", "")])
        self.assertTrue(self.run_ready(link))
        self.assertEqual(link.requests, [("READY", ""), ("READY", "")])

    def test_ready_waits_on_link_busy(self):
        link = ScriptLink(["busy", "busy", Message(1, "OK", "")])
        self.assertTrue(self.run_ready(link))
        self.assertEqual(self.sleeps, [0.25, 0.25])

    def test_ready_stops_on_stop_signal(self):
        link = ScriptLink([None] * 10)
        self.stop.set("shutdown")
        self.assertFalse(self.run_ready(link))
        self.assertEqual(link.requests, [])

    def test_ready_stops_while_busy(self):
        link = ScriptLink(["busy"] * 10)
        self.sleeps = []

        def sleep(s):
            self.stop.set("shutdown")
        self.assertFalse(announce_ready(link, self.stop, sleep=sleep))

    def test_error_answer_is_retried(self):
        link = ScriptLink([Message(1, "ERROR", "STATE"), Message(2, "OK", "")])
        self.assertTrue(self.run_ready(link))
        self.assertEqual(len(link.requests), 2)


if __name__ == "__main__":
    unittest.main()
