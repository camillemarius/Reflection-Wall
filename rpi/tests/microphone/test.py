# Einfaches Mikrofon-Recording auf dem Raspberry Pi
# Aufnahme startet mit ENTER
# Aufnahme stoppt mit ENTER
# Danach wird die Datei gespeichert UND abgespielt

# Installation:
# pip install sounddevice numpy scipy

import sounddevice as sd
import numpy as np
from scipy.io.wavfile import write
from pathlib import Path
from datetime import datetime

samplerate = 44100
audio_buffer = []

print("Drücke ENTER zum Starten der Aufnahme...")
input()

def callback(indata, frames, time, status):
    if status:
        print(status)
    audio_buffer.append(indata.copy())

print("Aufnahme läuft... Drücke ENTER zum Stoppen.")

stream = sd.InputStream(
    samplerate=samplerate,
    channels=1,
    callback=callback
)

stream.start()
input()
stream.stop()
stream.close()

print("Aufnahme beendet.")

# Alles zu einem Array zusammenfügen
audio = np.concatenate(audio_buffer, axis=0)

# In 16-bit konvertieren
audio_int16 = (audio * 32767).astype(np.int16)

# Unterordner "recordings" neben dem Script erstellen
project_dir = Path(__file__).parent
recordings_dir = project_dir / "recordings"
recordings_dir.mkdir(exist_ok=True)

# Dateiname mit Zeitstempel
filename = datetime.now().strftime("aufnahme_%Y%m%d_%H%M%S.wav")
filepath = recordings_dir / filename

# WAV speichern
write(filepath, samplerate, audio_int16)

print(f"Datei gespeichert: {filepath}")


print("Fertig.")