# chatbot/chatbot.py
from chatbot.chatbot_db import setup_db, get_previous_answers, save_answer
from chatbot.promt_template import PROMPT_TEMPLATE
from groq import Groq
import os
from dotenv import load_dotenv

# Lade Umgebungsvariablen
load_dotenv()
GROQ_API_KEY = os.getenv("GROQ_API_KEY")

# Initialisiere Groq Client
client = Groq(api_key=GROQ_API_KEY)

# Stelle sicher, dass die DB existiert
setup_db()

def write_to_ai(user_message: str) -> str:
    """
    Sendet die Benutzer-Nachricht an die Groq AI und gibt die Antwort als String zurück.
    Streaming wird unterstützt, sodass die Antwort während der Generierung angezeigt wird.
    """

    # User-Prompt aus Template füllen
    user_prompt = user_message +"Antworte kurz und bündig, in 1-2 Sätzen."

    # Anfrage an Groq (Chat Completion)
    completion = client.chat.completions.create(
        model="openai/gpt-oss-120b",
        messages=[{"role": "user", "content": user_prompt}],
        temperature=1,
        max_completion_tokens=8192,
        top_p=1,
        reasoning_effort="medium",
        stream=True,  # Streaming aktivieren
        stop=None
    )

    # Antwort sammeln
    full_answer = ""
    for chunk in completion:
        # Inhalt extrahieren (falls vorhanden)
        delta_text = chunk.choices[0].delta.content or ""
        print(delta_text, end="", flush=True)  # Echtzeit-Streaming Ausgabe
        full_answer += delta_text

    print()  # Zeilenumbruch nach Streaming-Ausgabe

    # Antwort speichern (falls save_answer definiert ist)
    save_answer(full_answer)

    return full_answer




def start_reflection_ai(user_message: str) -> str:
    """
    Schreibt eine Nachricht an die Reflexions-KI und gibt die Antwort zurück.
    """
    previous_answers = get_previous_answers()
    previous_answers_text = "\n".join(previous_answers)

    # User-Prompt aus Template füllen
    user_prompt = PROMPT_TEMPLATE.format(previous_answers=previous_answers_text)

    # Anfrage an Groq
    completion = client.chat.completions.create(
        model="openai/gpt-oss-120b",
        messages=[{"role": "user", "content": user_prompt}],
        temperature=1,
        max_completion_tokens=8192,
        top_p=1,
        reasoning_effort="medium",
        stream=True,
        stop=None
    )

    # Antwort sammeln
    today_answer = ""
    for chunk in completion:
        text = chunk.choices[0].delta.content or ""
        print(text, end="")  # optional
        today_answer += text

    # Antwort speichern
    save_answer(today_answer)

    return today_answer
