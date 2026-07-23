from groq import Groq
import os
import time
import logging
from dotenv import load_dotenv

load_dotenv()

GROQ_API_KEY = os.getenv("GROQ_API_KEY")
if not GROQ_API_KEY:
    raise ValueError("GROQ_API_KEY fehlt")

logging.basicConfig(level=logging.INFO)

client = Groq(api_key=GROQ_API_KEY)

# Global Rate Limit Schutz
LAST_REQUEST_TIME = 0
MIN_DELAY = 2  # Sekunden


def rate_limit():
    global LAST_REQUEST_TIME
    now = time.time()
    diff = now - LAST_REQUEST_TIME

    if diff < MIN_DELAY:
        time.sleep(MIN_DELAY - diff)

    LAST_REQUEST_TIME = time.time()


def write_to_ai(user_message: str, retries: int = 4) -> str:
    print("Frage an AI:", user_message)

    for attempt in range(retries):
        try:
            rate_limit()

            completion = client.chat.completions.create(
                #model="openai/gpt-oss-120b",
                model="llama-3.3-70b-versatile",
                #model="mixtral-8x7b-32768",

                messages=[
                    {"role": "user", "content": user_message}
                ],

                temperature=0.7,
                max_completion_tokens=512,  
                top_p=1,
                stream=True
            )

            full_answer = ""

            for chunk in completion:
                if not chunk or not chunk.choices:
                    continue

                delta = chunk.choices[0].delta
                if not delta:
                    continue

                text = getattr(delta, "content", None)
                if text:
                    full_answer += text

            if not full_answer.strip():
                raise ValueError("Leere Antwort")

            return full_answer

        except Exception as e:
            wait_time = min(2 ** attempt, 30)

            logging.error(f"Versuch {attempt+1}: {e}")
            logging.info(f"Retry in {wait_time}s")

            time.sleep(wait_time)

    return fallback_non_stream(user_message)


def fallback_non_stream(user_message: str) -> str:
    try:
        logging.info("Fallback ohne Streaming")

        rate_limit()

        completion = client.chat.completions.create(
            model="openai/gpt-oss-120b",
            messages=[{"role": "user", "content": user_message}],
            max_completion_tokens=512,
            stream=False
        )

        content = completion.choices[0].message.content
        return content if content else "Leere Antwort"

    except Exception as e:
        logging.error(f"Fallback fehlgeschlagen: {e}")
        return "Fehler: Keine Antwort"