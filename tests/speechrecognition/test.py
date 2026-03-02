import sounddevice as sd
import numpy as np
from faster_whisper import WhisperModel
import threading
import time

class WhisperRecorder:
    def __init__(self, model_name="small", device="cpu", sample_rate=16000, channels=1, beam_size=7):
        self.sample_rate = sample_rate
        self.channels = channels
        self.beam_size = beam_size
        self.listening = False
        self.audio_buffer = []
        self.transcripts = []  # hier werden alle Transkripte gespeichert

        # Modell laden
        self.model = WhisperModel(model_name, device=device)

        # Warmup: 1 Sekunde Stille, damit Tokenizer & Weights geladen werden
        dummy_audio = np.zeros(self.sample_rate, dtype=np.float32)
        _ = self.model.transcribe(dummy_audio, language=None, beam_size=1)

        # Audio-Stream initialisieren
        self.stream = sd.InputStream(
            samplerate=self.sample_rate,
            channels=self.channels,
            dtype='float32',
            callback=self._audio_callback
        )
        self.stream.start()

        # Eingabe-Thread starten
        threading.Thread(target=self._input_thread, daemon=True).start()
        print("Drücke Enter, um Aufnahme ein-/auszuschalten. Ctrl+C zum Beenden.")

    def _audio_callback(self, indata, frames, time_info, status):
        if self.listening:
            self.audio_buffer.append(np.copy(indata[:, 0]))

    def _input_thread(self):
        while True:
            input()
            self.listening = not self.listening
            if self.listening:
                print("\nAufnahme gestartet...")
                self.audio_buffer = []
            else:
                print("\nAufnahme gestoppt.")
                if len(self.audio_buffer) > 0:
                    self._transcribe_buffer()

    def _transcribe_buffer(self):
        start_time = time.time()
        audio_array = np.concatenate(self.audio_buffer)
        print("Starte Transkription...")
        segments, _ = self.model.transcribe(audio_array, language=None, beam_size=self.beam_size)
        end_time = time.time()
        elapsed = end_time - start_time

        transcript = " ".join(segment.text.strip() for segment in segments)
        self.transcripts.append(transcript)

        print("\n--- Transkript ---")
        print(transcript)
        print("------------------")
        print(f"Transkription dauerte {elapsed:.2f} Sekunden (inkl. Array-Zusammenbau).")

    def get_transcripts(self):
        """Alle bisher aufgenommenen Transkripte abrufen."""
        return self.transcripts

    def stop(self):
        """Audio-Stream stoppen."""
        self.stream.stop()
        print("Recorder gestoppt.")

# Beispiel-Nutzung
if __name__ == "__main__":
    recorder = WhisperRecorder()
    try:
        while True:
            threading.Event().wait(1)
    except KeyboardInterrupt:
        print("\nBeende...")
        recorder.stop()
        print("Gesammelte Transkripte:")
        for t in recorder.get_transcripts():
            print("-", t)