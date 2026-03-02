from ui.display import Display
from chatbot.chatbot_groq import write_to_ai
from speech.SpeechToText import record_and_transcribe
from speechRecognition.fastWhisper import FastWhisper
import time
import sys

def main():
    display = Display(simulation=True)  # später False für echtes I2C
    # time.sleep(2)

    recorder = FastWhisper()
    # Prüfen, ob Mikrofon verfügbar ist
    if not recorder.mic_available:
        display.set_text("\n" + "Kein Mikrofon gefunden")
        sys.exit(1)
    
    # Aufnahme mit Enter steuern
    recorder.start_recording()
    display.set_text("\n" + "Aufnahme läuft...")
    input()
    transcript = recorder.stop_recording()
    recorder.stop()

    # Frage auf Display anzeigen
    display.set_text("\n" + transcript)

    # Transkription AI übergeben und Antwort erhalten
    answer = write_to_ai(transcript)

    display.set_text("\n" + answer)

if __name__ == "__main__":
    main()
