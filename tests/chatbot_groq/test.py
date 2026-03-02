import os
from dotenv import load_dotenv
from groq import Groq

# Lade alle Variablen aus .env
load_dotenv()  

# Lese den API-Key
api_key = os.getenv("GROQ_API_KEY")
if not api_key:
    raise ValueError("Keine GROQ_API_KEY gefunden in .env")

# Initialisiere den Client mit API-Key
client = Groq(api_key=api_key)

# Beispiel-Chat
completion = client.chat.completions.create(
    model="openai/gpt-oss-120b",
    messages=[{"role": "user", "content": "Wie viele Ecken hat mein Hut?"}],
    temperature=1,
    max_completion_tokens=8192,
    top_p=1,
    reasoning_effort="medium",
    stream=True,
    stop=None
)

for chunk in completion:
    print(chunk.choices[0].delta.content or "", end="")