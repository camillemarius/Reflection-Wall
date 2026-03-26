import sys
from driver.display.display import Display
from driver.speechRecognition.fasterWhisper import fasterWhsiper
from driver.chatbot.groqAPI import write_to_ai

class VoiceAssistant:
    def __init__(self, simulation=False):
        self.display = Display(simulation=simulation)
        self.recorder = fasterWhsiper()

        # 🔹 Mikrofon prüfen
        if not self.recorder.mic_available:
            self.mic_available = False
            self.display.set_text("Kein Mikrofon angeschlossen.")
            print("Kein Mikrofon angeschlossen.")
        else:
            self.mic_available = True
            self.display.set_text("System bereit.")

    def record_and_transcribe(self):
        if not self.mic_available:
            self.display.set_text("Aufnahme übersprungen: Kein Mikrofon.")
            return ""  # frühzeitig zurückkehren

        input("Enter drücken zum Starten...")
        self.display.set_text("Aufnahme läuft...")

        self.recorder.start_recording()

        input("Enter drücken zum Stoppen...")
        self.display.set_text("Verarbeite Aufnahme...")

        transcript = self.recorder.stop_recording()
        return transcript

    def ask_ai(self, text):
        if not text.strip():
            return "Keine Eingabe für die AI."
        return write_to_ai(text)

    def display_text(self, text):
        self.display.set_text(text)

    def run_once(self):
        transcript = self.record_and_transcribe()
        if not transcript:
            self.display.set_text("Keine Aufnahme verfügbar, Funktion beendet.")
            return "", ""

        self.display_text(transcript)

        answer = self.ask_ai(transcript)
        self.display_text(answer)
        print("\n", answer)

        input("\nDrücke ENTER, um fortzufahren...")
        return transcript, answer