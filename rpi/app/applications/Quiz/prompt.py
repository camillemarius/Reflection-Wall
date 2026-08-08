PROMPT_TEMPLATE = """
Erstelle ein Quiz. Nicht schwere Fragen. Schweizer sollte die Antwort wissen.
Alle Antworten und Hinweise müssen zu 100% korrekt sein.
WICHTIG:
Wiederhole KEINE dieser Fragen:
{previous_text}
Gib mir:
1. Eine Schätzfrage
2. Die richtige Antwort
3. Zwei Hinweise von schwer bis mittelleicht
Der letzte Hinweis darf die Antwort NICHT direkt verraten.
Format:
FRAGE: ...
LÖSUNG: ...
HINWEIS1: ...
HINWEIS2: ...
"""