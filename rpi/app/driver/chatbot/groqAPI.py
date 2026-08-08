from groq import Groq
import os
import time
import logging
import threading
from dotenv import load_dotenv

load_dotenv()

GROQ_API_KEY = os.getenv("GROQ_API_KEY")
if not GROQ_API_KEY:
    raise ValueError("GROQ_API_KEY fehlt")

logging.basicConfig(level=logging.INFO)

client = Groq(api_key=GROQ_API_KEY)

# Global Rate Limit Schutz (thread-safe)
LAST_REQUEST_TIME = 0
MIN_DELAY = 2  # Sekunden
lock = threading.Lock()


def rate_limit():
    global LAST_REQUEST_TIME

    with lock:
        now = time.time()
        diff = now - LAST_REQUEST_TIME

        if diff < MIN_DELAY:
            time.sleep(MIN_DELAY - diff)

        LAST_REQUEST_TIME = time.time()


def write_to_ai(messages, retries: int = 4) -> str:
    """
    messages: List[dict] oder String

    Beispiel:
    [
        {"role": "system", "content": "Du bist ein Assistent."},
        {"role": "user", "content": "Hallo"}
    ]
    """

    # Input normalisieren
    if isinstance(messages, str):
        messages = [{"role": "user", "content": messages}]

    if not isinstance(messages, list):
        raise TypeError("messages must be a list of dicts or a string")

    print("Frage an AI:", messages)

    for attempt in range(retries):
        try:
            rate_limit()

            completion = client.chat.completions.create(
                model="llama-3.3-70b-versatile",
                messages=messages,
                temperature=0.7,
                max_completion_tokens=512,
                top_p=1,
                stream=True
            )

            full_answer = ""

            for chunk in completion:
                if not chunk or not chunk.choices:
                    continue

                text = chunk.choices[0].delta.content or ""
                full_answer += text

            if not full_answer.strip():
                raise ValueError("Leere Antwort")

            return full_answer

        except Exception as e:
            wait_time = min(2 ** attempt, 30)

            logging.error(f"Versuch {attempt + 1}: {e}")
            logging.info(f"Retry in {wait_time}s")

            time.sleep(wait_time)

    return fallback_non_stream(messages)


def fallback_non_stream(messages) -> str:
    try:
        logging.info("Fallback ohne Streaming")

        rate_limit()

        completion = client.chat.completions.create(
            model="llama-3.1-8b-instant",
            messages=messages,
            max_completion_tokens=512,
            stream=False
        )

        content = completion.choices[0].message.content
        return content if content else "Leere Antwort"

    except Exception as e:
        logging.error(f"Fallback fehlgeschlagen: {e}")
        return "Fehler: Keine Antwort"