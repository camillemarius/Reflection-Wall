from display.display import Display
from chatbot.chatbot_groq import write_to_ai
from app.speechRecognition.fasterWhisper import fasterWhsiper
import time
import sys

def main():
    display = Display(simulation=True)  # später False für echtes I2C
    # time.sleep(2)

    recorder = fasterWhsiper()
    # Prüfen, ob Mikrofon verfügbar ist
    if not recorder.mic_available:
        display.set_text("\n" + "Kein Mikrofon gefunden")
        sys.exit(1)
    
    # Aufnahme mit Enter steuern
    print("\nAufnahme mit Enter starten")
    input()
    recorder.start_recording()
    display.set_text("\n" + "Aufnahme läuft...")
    input()
    transcript = recorder.stop_recording()
    recorder.stop()

    # Frage auf Display anzeigen
    print("\n" + transcript + "\n")
    display.set_text("\n" + transcript)

    # Transkription AI übergeben und Antwort erhalten
    answer = write_to_ai(transcript)
    
    print("\n" + answer + "\n")
    display.set_text("\n" + answer)

if __name__ == "__main__":
    main()
