import os
import tempfile
import sounddevice as sd
#import soundfile as sf
import numpy as np
from groq import Groq
from dotenv import load_dotenv

# Lade Umgebungsvariablen
load_dotenv()
GROQ_API_KEY = os.getenv("GROQ_API_KEY")
client = Groq(api_key=GROQ_API_KEY)

def record_and_transcribe():
    """
    Nimmt Audio über das Mikrofon auf (Start/Stop per Enter) 
    und transkribiert es mit Groq API.
    Rückgabe: transkribierter Text (str)
    """

    samplerate = 16000  # Funktioniert meist auf Linux
    channels = 1

    print("Aufnahme mit 'Enter' starten")
    input()

    print("Aufnahme mit 'Enter' stoppen")

    recording = []

    # Callback für Aufnahme
    def callback(indata, frames, time, status):
        recording.append(indata.copy())

    # Stream starten
    stream = sd.InputStream(samplerate=samplerate, channels=channels, callback=callback)
    stream.start()
    input()  # Stoppen per Enter
    stream.stop()
    stream.close()

    print("Aufnahme beendet, verarbeite Transkription...")

    # In temporäre WAV-Datei speichern
    with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmpfile:
        tmp_audio_path = tmpfile.name
        audio_array = np.concatenate(recording, axis=0)
        sf.write(tmp_audio_path, audio_array, samplerate)

    # Transkription mit Groq
    with open(tmp_audio_path, "rb") as file:
        transcription = client.audio.transcriptions.create(
            file=file,
            model="whisper-large-v3-turbo",
            response_format="verbose_json",
            timestamp_granularities=["word", "segment"],
        )

    # Temporäre Datei löschen
    os.remove(tmp_audio_path)

    # Text zurückgeben
    return transcription.text
