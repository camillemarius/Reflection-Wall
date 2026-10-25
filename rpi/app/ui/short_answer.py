# ui/short_answer.py
# Kurze Antworten fuer die Wand (D17): hoechstens drei Anfragen, bis der Text in vier Zeilen passt.
from typing import Callable

from app.driver.display.cells import normalize
from app.driver.display.text_layout import wrap

SHORT_RULE = "Antworte in hoechstens 96 Zeichen. Nur Buchstaben, Ziffern, Leerzeichen und Punkt."


def ask_short(ask: Callable[[], str], attempts: int = 3) -> str:
    """Fragt, bis wrap(normalize(antwort)) passt, hoechstens attempts Mal; gibt die letzte Antwort zurueck."""
    answer = ""
    for _ in range(max(1, attempts)):
        answer = ask()
        if wrap(normalize(answer))[1]:
            break
    return answer
