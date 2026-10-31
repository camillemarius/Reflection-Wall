# night_quote.py
# Zitat der Nacht: bereinigen und pruefen (dieselbe Pruefung wie QuoteCheck auf dem ESP,
# gemeinsame Testfaelle in tests/quote_vectors.json).
import re

from app import topics
from app.driver.display import text_layout

MAX_CHARS = 96

_UMLAUTS = {
    "ä": "ae", "Ä": "Ae",
    "ö": "oe", "Ö": "Oe",
    "ü": "ue", "Ü": "Ue",
    "ß": "ss",
}
# Die erlaubten Zeichen stehen nur hier; beide Muster leiten sich davon ab.
_ALLOWED_CHARS = r"A-Za-z0-9\-./:+* "
_NOT_ALLOWED = re.compile(r"[^" + _ALLOWED_CHARS + r"\t\r\n]")
_ALLOWED_ONLY = re.compile(r"[" + _ALLOWED_CHARS + r"]+")


def clean_quote(text: str) -> str:
    """Umlaute ersetzen, Unerlaubtes entfernen, Leerraum zu einem Leerzeichen. Kuerzt nicht."""
    for char, replacement in _UMLAUTS.items():
        text = text.replace(char, replacement)
    text = _NOT_ALLOWED.sub("", text)
    return " ".join(text.split())


def quote_fits(text: str) -> bool:
    """1 bis 96 erlaubte Zeichen, und der Text passt in die vier Zeilen. Bereinigt nicht."""
    if not text or len(text) > MAX_CHARS:
        return False
    if not _ALLOWED_ONLY.fullmatch(text):
        return False
    return text_layout.wrap(text)[1]


MAX_ASKS = 3
SYSTEM_PROMPT = (
    "Entwickle daraus den nächsten Gedanken. Höchstens 96 Zeichen, auf keinen Fall länger. "
    "Nur Buchstaben, Ziffern, Leerzeichen und Punkt, keine Umlaute."
)


def build_night_messages(topic: str, yesterday: str) -> list:
    user = "Thema: " + topic
    if yesterday:
        user += "\nGedanke von gestern: " + yesterday
    return [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": user},
    ]


def make_night_quote(yesterday: str, ask, config_dir=topics.CONFIG_DIR) -> tuple:
    """Fragt die KI nach dem Zitat der Nacht (hoechstens 3 Antworten).

    Gibt ("QUOTE", Text), ("ERROR", "ZU_LANG") oder ("ERROR", "KI") zurueck.
    .thema_zuletzt wird nur nach einem gelungenen Zitat geschrieben.
    """
    topic = topics.read_daily(config_dir)
    if topic != topics.read_last_daily(config_dir):
        yesterday = ""
    messages = build_night_messages(topic, yesterday)
    for _ in range(MAX_ASKS):
        try:
            answer = ask(messages)
        except Exception:
            return ("ERROR", "KI")
        if not isinstance(answer, str) or answer.startswith("Fehler"):
            return ("ERROR", "KI")
        text = clean_quote(answer)
        if quote_fits(text):
            topics.save_last_daily(config_dir, topic)
            return ("QUOTE", text)
    return ("ERROR", "ZU_LANG")
