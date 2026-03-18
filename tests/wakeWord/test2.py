from pocketsphinx import LiveSpeech

speech = LiveSpeech(
    kws='wake.txt',
    verbose=False,
    # Deutsches Modell
)

print("Listening...")

for phrase in speech:
    print("Wake word detected!")
    break