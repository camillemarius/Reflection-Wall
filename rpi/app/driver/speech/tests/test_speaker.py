"""Tests fuer die Sprachausgabe: wie piper und aplay gestartet werden."""
import sys
import unittest
from unittest import mock

from app.driver.speech.speaker import SpeechAssistant


class SpeakerTest(unittest.TestCase):
    def test_piper_runs_with_the_python_of_this_process(self):
        # Unter systemd liegt bin/ des venv nicht im PATH; piper kommt deshalb ueber dieses Python.
        with mock.patch("app.driver.speech.speaker.subprocess.run") as run:
            SpeechAssistant().speak("Hallo")
        piper_cmd = run.call_args_list[0].args[0]
        self.assertEqual(piper_cmd[:3], [sys.executable, "-m", "piper"])

    def test_empty_text_starts_nothing(self):
        with mock.patch("app.driver.speech.speaker.subprocess.run") as run:
            SpeechAssistant().speak("   ")
        run.assert_not_called()


if __name__ == "__main__":
    unittest.main()
