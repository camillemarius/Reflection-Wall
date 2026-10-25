# night_quote.py
# Zitat der Nacht: bereinigen und pruefen (dieselbe Pruefung wie QuoteCheck auf dem ESP,
# gemeinsame Testfaelle in tests/quote_vectors.json).
import re

from app.driver.display import text_layout

MAX_CHARS = 96

_UMLAUTS = {
    "ä": "ae", "Ä": "Ae",
    "ö": "oe", "Ö": "Oe",
    "ü": "ue", "Ü": "Ue",
    "ß": "ss",
}
_NOT_ALLOWED = re.compile(r"[^A-Za-z0-9\-./:+* \t\r\n]")
_ALLOWED_ONLY = re.compile(r"[A-Za-z0-9\-./:+* ]+")


def clean_quote(text: str) -> str:
    """Umlaute ersetzen, Unerlaubtes entfernen, Leerraum zu einem Leerzeichen, kuerzen."""
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
