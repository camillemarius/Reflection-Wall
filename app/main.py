# main.py
# main.py
from app.display.ht16k33_driver import init_ht16k33, clear_all
from app.display.display_utils import show_text
from app.chatbot.chatbot_groq import write_to_ai

import time

def main():
    # HT16K33 initialisieren
    #init_ht16k33()

    # Kurzer Testtext
    #show_text("HELLO")
    #time.sleep(2)

    # Frage an die AI
    user_question = "Was ist der Sinn des Lebens?"
    ai_answer = write_to_ai(user_question)  # Antwort von der Groq-KI

    print("\nAI-Antwort:", ai_answer)  # optional für Konsole

    # Antwort auf den Displays anzeigen (scrollt automatisch, falls nötig)
    show_text(ai_answer, delay=0.2)

    # Nach der Anzeige alles löschen
    clear_all()

if __name__ == "__main__":
    main()
