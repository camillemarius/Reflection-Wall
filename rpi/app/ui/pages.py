# ui/pages.py
# Seiten fuer lange Texte (D17): vier volle Zeilen je Seite, auf jeder Seite
# ausser der letzten steht ein '>' an Stelle 24 der Zeile 4.
from app.driver.display.cells import used_cells
from app.driver.display.text_layout import CHARS_PER_ROW, ROWS, wrap

POINTER = ">"


def _take_row(text: str, index: int, width: int) -> tuple[str, int]:
    """Eine Zeile ab index, hoechstens width Zeichen, Umbruch wie wrap()."""
    length = len(text)
    while index < length and text[index] == " ":
        index += 1
    take = min(length - index, width)
    if take == width and index + take < length and text[index + take] != " ":
        break_at = take
        while break_at > 0 and text[index + break_at - 1] != " ":
            break_at -= 1
        if break_at > 0:
            take = break_at
    return text[index:index + take], index + take


def paginate(text: str) -> list[list[str]]:
    """Seiten zu 4 Zeilen a 24 Zeichen."""
    rows, fits = wrap(text)
    if fits:
        return [rows]

    pages = []
    index = 0
    while True:
        rows, fits = wrap(text[index:])
        if fits:
            pages.append(rows)
            return pages
        page = []
        for row in range(ROWS):
            last = row == ROWS - 1
            width = CHARS_PER_ROW - 1 if last else CHARS_PER_ROW
            piece, index = _take_row(text, index, width)
            if last:
                # Nach Stellen auffuellen, nicht nach Zeichen: ein Punkt teilt die Stelle mit
                # dem Zeichen davor, der Zeiger muss trotzdem in die letzte Stelle.
                page.append(piece + " " * (width - used_cells(piece)) + POINTER)
            else:
                page.append(piece.ljust(width))
        pages.append(page)
