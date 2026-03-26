from driver.chatbot.groqAPI import write_to_ai
from driver.database.mysql import get_previous_answers, save_answer

import re

class AIQuizGenerator:
    def __init__(self, db_key="quiz"):
        self.db_key = db_key 

    def generate_quiz(self):
        # 1. Alte Fragen holen
        previous_questions = get_previous_answers(self.db_key)

        # 2. Als String formatieren
        if previous_questions:
            previous_text = "\n".join(previous_questions)
        else:
            previous_text = "Keine bisherigen Fragen."

        # 3. Prompt erweitern
        prompt = f"""
        Erstelle ein Quiz. Nicht schwere Fragen. Schweizer sollte die Antwort wissen.
        Alle Antworten und Hinweise müssen zu 100% korrekt sein.

        WICHTIG:
        Wiederhole KEINE dieser Fragen:
        {previous_text}

        Gib mir:
        1. Eine Schätzfrage
        2. Die richtige Antwort
        3. Zwei Hinweise von schwer bis mittelleicht

        Der letzte Hinweis darf die Antwort NICHT direkt verraten.

        Format:
        FRAGE: ...
        LÖSUNG: ...
        HINWEIS1: ...
        HINWEIS2: ...
        """

        response = write_to_ai(prompt)
        
        print(f"response: {response}\n")

        parsed = self.parse_response(response)

        # 4. Neue Frage speichern
        if parsed["frage"] != "Keine Frage erhalten":
            save_answer(parsed["frage"], self.db_key)
        return parsed

    import re

    def parse_response(self, text):
        data = {
            "frage": "Keine Frage erhalten",
            "lösung": "Keine Lösung erhalten",
            "hinweis1": "Kein Hinweis 1",
            "hinweis2": "Kein Hinweis 2",
            "hinweis3": "Kein Hinweis 3",
        }

        # 🔹 Markdown (** **) entfernen
        text = text.replace("**", "")

        # 🔹 Patterns (flexibel!)
        patterns = {
            "frage": r"FRAGE:\s*(.+)",
            "lösung": r"L[ÖO]SUNG:\s*(.+)",
            "hinweis1": r"HINWEIS\s*1.*?:\s*(.+)",
            "hinweis2": r"HINWEIS\s*2.*?:\s*(.+)",
            "hinweis3": r"HINWEIS\s*3.*?:\s*(.+)",
        }

        for key, pattern in patterns.items():
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                data[key] = match.group(1).strip()

        return data