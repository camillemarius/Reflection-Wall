# display/text_layout.py
# Zeilenumbruch der Anzeige: dieselbe Regel wie TextLayout::wrap auf dem ESP
# (gemeinsame Testfaelle in tests/display_vectors.json).
from app.driver.display.ascii_map import ASCII_16SEG

CHARS_PER_ROW = 24
ROWS = 4


def wrap(text: str) -> tuple[list[str], bool]:
    """Vier Zeilen zu je 24 Zeichen und ob der ganze Text hineinpasst."""
    length = len(text)
    index = 0
    rows = []

    for _ in range(ROWS):
        # Leerzeichen am Zeilenanfang wuerden den Text einruecken
        while index < length and text[index] == " ":
            index += 1

        take = min(length - index, CHARS_PER_ROW)

        # Faellt der Schnitt mitten in ein Wort, bis zum letzten Leerzeichen
        # zurueckgehen. Passt ein Wort nicht in eine Zeile, wird es hart getrennt.
        if take == CHARS_PER_ROW and index + take < length and text[index + take] != " ":
            break_at = take
            while break_at > 0 and text[index + break_at - 1] != " ":
                break_at -= 1
            if break_at > 0:
                take = break_at

        rows.append(text[index:index + take].ljust(CHARS_PER_ROW))
        index += take

    while index < length and text[index] == " ":
        index += 1
    return rows, index >= length


def displayable(ch: str) -> bool:
    """Kann die Anzeige das Zeichen zeigen? Kleinbuchstaben erscheinen gross."""
    return ch.upper() in ASCII_16SEG
