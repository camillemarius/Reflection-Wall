import time
from driver.database.mysql import setup_db
from applications.Quiz.AIQuizGenerator import AIQuizGenerator
from driver.display.display import Display

setup_db("quiz")

class QuizGame:
    def __init__(self, display: Display = None, db_key="quiz"):
        self.db_key = db_key
        self.generator = AIQuizGenerator(db_key="quiz")
        # 🔹 Display setzen, sonst Simulation
        self.display = display if display else Display(simulation=True)

    def play(self):
        
        self.display.set_text("Frage wird generiert...")
        quiz = self.generator.generate_quiz()

        frage = quiz["frage"]
        antwort = quiz["lösung"]
        hinweise = [
            quiz["hinweis1"],
            quiz["hinweis2"]
        ]

        print("\n=== QUIZ STARTET ===\n")
        self.display.set_text("Quiz startet")
        time.sleep(2)

        # Frage anzeigen
        print(f"FRAGE: {frage}\n")
        self.display.set_text(frage)

        for runde in range(2):
            input(f"\nDrücke ENTER für Hinweis {runde+1}...")

            print(f"\n--- Runde {runde+1} ---")
            print(f"Hinweis: {hinweise[runde]}\n")

            self.display.set_text(f"Runde {runde+1}")
            time.sleep(1)

            self.display.set_text(hinweise[runde])
        
        input(f"\nDrücke ENTER für die Lösung {runde+1}...")
        print(f"\nLÖSUNG: {antwort}\n")
        self.display.set_text(f"Lösung: {antwort}")
        input(f"\nDrücke ENTER für die Lösung {runde+1}...")

        return False