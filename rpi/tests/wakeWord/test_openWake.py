import numpy as np
import sounddevice as sd
from openwakeword.model import Model
import time

# ----------------------------
# Modell laden
# ----------------------------
model = Model()

print("Verfügbare Wake-Words:")
print(model.models.keys())

# ----------------------------
# Audio Settings
# ----------------------------
SAMPLE_RATE = 16000
CHUNK_SIZE = 400
THRESHOLD = 0.4
COOLDOWN = 2.0

buffer = np.zeros(0, dtype=np.int16)
last_trigger = 0

# ----------------------------
# Callback
# ----------------------------
def callback(indata, frames, time_info, status):
    global buffer, last_trigger

    if status:
        print(status)

    audio = np.squeeze(indata)
    audio = (audio * 32767).astype(np.int16)

    buffer = np.concatenate((buffer, audio))

    while len(buffer) >= CHUNK_SIZE:
        chunk = buffer[:CHUNK_SIZE]
        buffer = buffer[CHUNK_SIZE:]   # ✅ FIX

        print("Max level:", np.max(np.abs(chunk)))

        prediction = model.predict(chunk)
        print(prediction)

        score = prediction.get("timer", 0)

        if score > THRESHOLD:
            now = time.time()
            if now - last_trigger > COOLDOWN:
                print("\n======================")
                print(" 20 minute timer")
                print("======================\n")
                last_trigger = now

# ----------------------------
# Stream starten
# ----------------------------
print("🎤 Starte Live-Erkennung...")

with sd.InputStream(
    channels=1,
    samplerate=SAMPLE_RATE,
    blocksize=CHUNK_SIZE,
    dtype='float32',
    callback=callback
):
    sd.sleep(60000)