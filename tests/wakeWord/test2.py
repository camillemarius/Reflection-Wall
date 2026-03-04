from pocketsphinx import LiveSpeech

speech = LiveSpeech(
    keyphrase='Apache',
    kws_threshold=1e-20
)

for phrase in speech:
    print("Wake word detected!")
    break