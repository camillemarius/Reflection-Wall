import contextlib
import io
import logging
import unittest
from unittest import mock

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


class _DeadPort:
    def read_available(self) -> bytes:
        raise OSError("Port weg")

    def write(self, data: bytes) -> None:
        pass

    def close(self) -> None:
        pass


class ProbeFailureTest(unittest.TestCase):
    def test_dead_link_stops_with_message(self):
        out = io.StringIO()
        with mock.patch("app.link.probe.open_esp_port", return_value=_DeadPort()):
            with contextlib.redirect_stdout(out):
                code = main(["--no-gpio", "--seconds", "5"])
        self.assertEqual(code, 1)
        self.assertIn("Verbindung abgebrochen", out.getvalue())

    def _failing_open(self, exc):
        log = logging.getLogger("link")
        handlers, level = list(log.handlers), log.level
        out = io.StringIO()
        with mock.patch("app.link.probe.open_esp_port", side_effect=exc):
            with contextlib.redirect_stdout(out):
                code = main(["--no-gpio", "--seconds", "1"])
        self.assertEqual(code, 1)
        self.assertEqual(list(log.handlers), handlers)
        self.assertEqual(log.level, level)
        return out.getvalue()

    def test_missing_lgpio_prints_hint_and_restores_logger(self):
        text = self._failing_open(ModuleNotFoundError("lgpio"))
        self.assertIn("lgpio fehlt", text)
        self.assertIn("--no-gpio", text)

    def test_port_error_prints_hint_and_restores_logger(self):
        text = self._failing_open(OSError("no such port"))
        self.assertIn("Port nicht gefunden oder keine Rechte", text)
        self.assertIn("dialout", text)
