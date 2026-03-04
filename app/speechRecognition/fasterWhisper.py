import sounddevice as sd
import numpy as np
from faster_whisper import WhisperModel
import time

class fasterWhsiper:
    def __init__(self, model_name="small", device="cpu", sample_rate=16000, channels=1, beam_size=7):
        self.sample_rate = sample_rate
        self.channels = channels
        self.beam_size = beam_size
        self.listening = False
        self.audio_buffer = []
        self.transcripts = []

        # Modell laden
        self.model = WhisperModel(model_name, device=device)


        # Audio-Stream initialisieren
        self.mic_available = True  # Standard: Mikrofon verfügbar
        try:
            self.stream = sd.InputStream(
                samplerate=self.sample_rate,
                channels=self.channels,
                dtype='float32',
                callback=self._audio_callback
            )
            self.stream.start()
        except sd.PortAudioError:
            self.mic_available = False


    def _audio_callback(self, indata, frames, time_info, status):
        if self.listening:
            self.audio_buffer.append(np.copy(indata[:, 0]))

    def start_recording(self):
        """Startet die Aufnahme."""
        if not self.listening:
            self.listening = True
            self.audio_buffer = []

    def stop_recording(self):
        """Stoppt die Aufnahme und transkribiert den aufgenommenen Text."""
        if self.listening:
            self.listening = False
            print("Aufnahme gestoppt.")
            if len(self.audio_buffer) > 0:
                return self._transcribe_buffer()
        return ""

    def _transcribe_buffer(self):
        audio_array = np.concatenate(self.audio_buffer)
        segments, _ = self.model.transcribe(audio_array, language=None, beam_size=self.beam_size)
        transcript = " ".join(segment.text.strip() for segment in segments)
        self.transcripts.append(transcript)
        print("Transkription abgeschlossen.")
        return transcript

    def get_transcripts(self):
        """Alle bisher aufgenommenen Transkripte abrufen."""
        return self.transcripts

    def stop(self):
        """Audio-Stream stoppen."""
        self.stream.stop()
        print("Recorder gestoppt.")


# Beispiel-Nutzung
if __name__ == "__main__":
    recorder = fasterWhsiper()

    # Aufnahme manuell steuern
    recorder.start_recording()
    print("Aufnahme läuft für 5 Sekunden...")
    time.sleep(5)
    transcript = recorder.stop_recording()

    print("\nTranskript:")
    print(transcript)

    recorder.stop()