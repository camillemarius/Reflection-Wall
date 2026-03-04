import pvporcupine
import pyaudio

porcupine = pvporcupine.create(keywords=["Apache"])  # z.B. wake word
pa = pyaudio.PyAudio()

stream = pa.open(
    rate=porcupine.sample_rate,
    channels=1,
    format=pyaudio.paInt16,
    input=True,
)

print("Listening for wake word…")
while True:
    pcm = stream.read(porcupine.frame_length)
    pcm = np.frombuffer(pcm, dtype=np.int16)

    keyword_index = porcupine.process(pcm)
    if keyword_index >= 0:
        print("Wake word detected!")
        break