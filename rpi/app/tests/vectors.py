"""Liest die gemeinsame Testfall-Datei im Verzeichnis tests/ der Wurzel."""
import json
from pathlib import Path

REPO = Path(__file__).resolve().parents[3]


def _strings(value):
    if isinstance(value, str):
        yield value
    elif isinstance(value, dict):
        for k, v in value.items():
            yield k
            yield from _strings(v)
    elif isinstance(value, list):
        for v in value:
            yield from _strings(v)


def load_vectors(file_name: str) -> list[dict]:
    raw = (REPO / "tests" / file_name).read_bytes()
    try:
        text = raw.decode("ascii")
    except UnicodeDecodeError as exc:
        raise AssertionError(f"{file_name} ist nicht reines ASCII: {exc}") from exc

    vectors = json.loads(text)["vectors"]

    by_line = []
    for line in text.splitlines():
        line = line.strip()
        if not line.startswith('{"'):
            continue
        if line.endswith(","):
            line = line[:-1]
        by_line.append(json.loads(line))
    if by_line != vectors:
        raise AssertionError(
            f"{file_name}: die Zeilen mit einem Fall sind nicht genau die Faelle in 'vectors'"
        )

    for s in _strings(vectors):
        try:
            s.encode("latin-1")
        except UnicodeEncodeError as exc:
            raise AssertionError(f"{file_name}: Zeichenkette passt nicht in latin-1: {s!r}") from exc
    return vectors
