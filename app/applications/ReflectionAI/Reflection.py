import logging
from applications.ReflectionAI.promt_template import PROMPT_TEMPLATE
from driver.database.mysql import get_previous_answers, save_answer, setup_db
from driver.chatbot.groqAPI import write_to_ai
from driver.display.display import Display  # deine Display-Klasse

setup_db("reflection")


class ReflectionAI:
    def __init__(self, display: Display = None, db_key="reflection", retries: int = 3):
        self.db_key = db_key
        self.retries = retries
        # 🔹 Display setzen, sonst Default (Simulation)
        self.display = display if display else Display(simulation=True)

    def start(self, save_to_db: bool = True) -> str:
        # 🔹 Vorherige Antworten holen
        previous_answers = get_previous_answers(self.db_key)
        previous_answers_text = "\n".join(previous_answers) if previous_answers else "Keine bisherigen Antworten."

        # 🔹 Prompt vorbereiten
        user_prompt = PROMPT_TEMPLATE.format(previous_answers=previous_answers_text)

        # 🔹 Antwort von AI holen
        try:
            today_answer = write_to_ai(user_prompt, retries=self.retries)

            if not today_answer.strip():
                raise ValueError("Leere Antwort Reflection AI")

            # 🔹 Auf Display ausgeben
            self.display.set_text(today_answer)
            print("\n", today_answer)
            input("\nDrücke ENTER um fortzufahren...")

            # 🔹 Optional in DB speichern
            if save_to_db:
                save_answer(today_answer, self.db_key)

            return today_answer

        except Exception as e:
            logging.error(f"Fehler bei der Reflexions-KI: {e}")
            self.display.set_text("Fehler bei der Reflexions-KI.")
            return "Fehler bei der Reflexions-KI."