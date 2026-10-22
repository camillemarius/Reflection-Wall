import contextlib
import io
import unittest

from app.link.codec import Message
from app.link.probe import answer_for, main


class ProbeTest(unittest.TestCase):
    def test_button_is_ok(self):
        self.assertEqual(answer_for(Message(9, "BUTTON", "1")), ("OK", ""))

    def test_shutdown_is_busy(self):
        self.assertEqual(answer_for(Message(10, "SHUTDOWN")), ("BUSY", ""))

    def test_get_is_error_probe(self):
        self.assertEqual(answer_for(Message(11, "GET", "QUOTE|")), ("ERROR", "PROBE"))

    def test_main_runs_on_loop_port(self):
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            code = main(["--port", "loop://", "--no-gpio", "--seconds", "0.5"])
        self.assertEqual(code, 0)
        # loop:// gibt READY zurueck; der Link beantwortet es mit ERROR|UNKNOWN
        self.assertIn("READY -> ERROR|UNKNOWN (#00)", out.getvalue())
        self.assertIn("verworfen: {}", out.getvalue())
