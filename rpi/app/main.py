from applications.VoiseAssistant.VoiceAssistant import VoiceAssistant
from applications.Quiz.QuizGame import QuizGame
from applications.ReflectionAI.Reflection import ReflectionAI
from driver.display.display import Display
from applications.Animations.Radar import Radar
from applications.Animations.Stickman import Stickman
from driver.speech.speaker import SpeechAssistant

def main():
    display = Display(simulation=False)
    speech_assistant  = SpeechAssistant()

    while True:
        display.set_text("1=Chat \n2=Quiz \n3=Reflection AI \n4=Radar")
        choice = input("Modus wählen: ")

        if choice == "1":
            assistant = VoiceAssistant(simulation=False, display=display, speaker=speech_assistant )
            assistant.run_once()

        elif choice == "2":
            game = QuizGame(display=display, db_key="quiz")
            game.play()

        elif choice == "3":  # Reflection AI starten
            reflection = ReflectionAI(display=display, db_key="reflection")
            antwort = reflection.start(save_to_db=True)

            # 🔹 Ausgabe zusätzlich im Assistant (optional)
            print("\n📌 Reflexions-Antwort:", antwort)
            display.set_text(f"Reflection AI:\n{antwort}")


        elif choice == "4":
            radar = Radar(display=display)
            radar.run()

        elif choice == "5":
            print("\nAnimation")
            stickman = Stickman(display=display)
            stickman.run()

        else:
            display.set_text("Ungültig")


if __name__ == "__main__":
    main()