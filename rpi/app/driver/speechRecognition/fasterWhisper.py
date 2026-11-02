import sounddevice as sd
import numpy as np
from faster_whisper import WhisperModel
import time


class fasterWhsiper:
    # Entscheid A (2026-11-02): int8, 3 Kandidaten, fest Deutsch. An 15 s Sprache auf dem Pi 5
    # 11 s statt 34 s (float32, Beam 7, Sprache suchen), derselbe Text.
    # Modell base (Owner 2026-11-02: kurze Fragen, so schnell wie moeglich): 2 s je kurze Frage
    # statt 5.6 s mit small; an zwei Fragen derselbe Inhalt, einmal ein anderer Artikel.
    def __init__(self, model_name="base", device="cpu", sample_rate=16000, channels=1, beam_size=3,
                 compute_type="int8", language="de"):
        self.sample_rate = sample_rate
        self.channels = channels
        self.beam_size = beam_size
        self.language = language

        self.listening = False
        self.audio_buffer = []
        self.transcripts = []

        self.stream = None
        self.mic_available = True

        # Whisper Modell laden
        print("DEBUG: Lade Whisper Modell...")
        self.model = WhisperModel(model_name, device=device, compute_type=compute_type)
        print("DEBUG: Modell geladen")

        # Mikrofon check
        try:
            sd.query_devices()
        except Exception:
            self.mic_available = False
            print("Kein Mikrofon verfügbar.")

    # --------------------------
    # AUDIO STREAM MANAGEMENT
    # --------------------------

    def start_stream(self):
        """Stream sauber starten"""
        if self.stream is None:
            try:
                self.stream = sd.InputStream(
                    samplerate=self.sample_rate,
                    channels=self.channels,
                    dtype='float32',
                    callback=self._audio_callback
                )
                self.stream.start()
            except sd.PortAudioError as e:
                self.mic_available = False
                print("Fehler beim Starten des Audio-Streams:", e)

    def stop_stream(self):
        """Stream sauber stoppen + freigeben"""
        if self.stream is not None:
            try:
                self.stream.stop()
                self.stream.close()
            except Exception as e:
                print("Fehler beim Stoppen des Streams:", e)

            self.stream = None

    # --------------------------
    # CALLBACK
    # --------------------------

    def _audio_callback(self, indata, frames, time_info, status):
        if self.listening:
            self.audio_buffer.append(indata[:, 0].copy())

    # --------------------------
    # RECORD CONTROL
    # --------------------------

    def start_recording(self):
        """Startet Aufnahme"""
        if not self.mic_available:
            print("Kein Mikrofon verfügbar.")
            return

        self.audio_buffer = []
        self.listening = True

        # Stream sicherstellen
        self.start_stream()

    def stop_recording(self):
        """Stoppt Aufnahme + Transkription"""
        self.listening = False

        if len(self.audio_buffer) == 0:
            return ""

        print("Aufnahme gestoppt.")

        transcript = self._transcribe_buffer()

        # 🔥 WICHTIG: Buffer reset
        self.audio_buffer = []

        return transcript

    # --------------------------
    # TRANSKRIPTION
    # --------------------------

    def _transcribe_buffer(self):
        audio_array = np.concatenate(self.audio_buffer).astype(np.float32)

        segments, _ = self.model.transcribe(
            audio_array,
            language=self.language,
            beam_size=self.beam_size
        )

        transcript = " ".join(segment.text.strip() for segment in segments)

        self.transcripts.append(transcript)

        print("Transkription abgeschlossen.")
        return transcript

    # --------------------------
    # UTILS
    # --------------------------

    def get_transcripts(self):
        return self.transcripts

    def close(self):
        """Komplett sauber beenden"""
        self.stop_stream()