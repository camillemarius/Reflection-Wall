"""Tests fuer die Spracherkennung des Chats (fasterWhisper) mit Fake-Whisper, ohne Mikrofon."""
import importlib
import sys
import types
import unittest
from unittest import mock

import numpy as np

MODULE = "app.driver.speechRecognition.fasterWhisper"


class FakeSegment:
    def __init__(self, text):
        self.text = text


class RecorderTest(unittest.TestCase):
    def setUp(self):
        self.model = mock.Mock()
        self.model.transcribe.return_value = ([FakeSegment(" Hallo "), FakeSegment("Wand. ")], None)
        self.whisper_model = mock.Mock(return_value=self.model)
        fakes = {
            "faster_whisper": types.SimpleNamespace(WhisperModel=self.whisper_model),
            "sounddevice": types.SimpleNamespace(query_devices=mock.Mock(), InputStream=mock.Mock(),
                                                 PortAudioError=Exception),
        }
        patcher = mock.patch.dict(sys.modules, fakes)
        patcher.start()
        self.addCleanup(patcher.stop)  # nimmt auch das hier importierte Modul wieder heraus
        sys.modules.pop(MODULE, None)
        self.module = importlib.import_module(MODULE)

    def test_loads_small_as_int8_on_the_cpu(self):
        # Entscheid A (2026-11-02): an 15 s Sprache 11 s statt 34 s, derselbe Text
        self.module.fasterWhsiper()
        self.whisper_model.assert_called_once_with("small", device="cpu", compute_type="int8")

    def test_recognizes_german_with_three_candidates(self):
        recorder = self.module.fasterWhsiper()
        recorder.audio_buffer = [np.zeros(1600, dtype=np.float32)]
        self.assertEqual(recorder.stop_recording(), "Hallo Wand.")
        _, kwargs = self.model.transcribe.call_args
        self.assertEqual(kwargs, {"language": "de", "beam_size": 3})


if __name__ == "__main__":
    unittest.main()
