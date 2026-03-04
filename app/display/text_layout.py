# display/text_layout.py
def word_wrap(text, cols, rows):
    words = text.split()
    lines = []
    current = ""

    for word in words:
        if not current:
            current = word
        elif len(current) + 1 + len(word) <= cols:
            current += " " + word
        else:
            lines.append(current)
            current = word
        if len(lines) == rows:
            break

    if current and len(lines) < rows:
        lines.append(current)

    while len(lines) < rows:
        lines.append("")

    return lines
