from applications.VoiseAssistant.VoiceAssistant import VoiceAssistant
from applications.Quiz.QuizGame import QuizGame
from applications.ReflectionAI.Reflection import ReflectionAI
from driver.display.display import Display

def main():
    display = Display(simulation=False)

    while True:
        display.set_text("1=Chat \n2=Quiz \n3=Reflection AI")
        choice = input("Modus wählen: ")

        if choice == "1":
            assistant = VoiceAssistant(simulation=False)
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

        else:
            display.set_text("Ungültig")


if __name__ == "__main__":
    main()