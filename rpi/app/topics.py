# topics.py
# Themendateien: thema.txt (taeglich) und thema_hand.txt (von Hand). Ein Thema ist eine Zeile, hoechstens 120 Zeichen.
import os
import tempfile
from pathlib import Path

DEFAULT_TOPIC = "Was ist der Sinn des Lebens"
CONFIG_DIR = Path(__file__).resolve().parent / "config"
MAX_LENGTH = 120
DAILY_FILE = "thema.txt"
HAND_FILE = "thema_hand.txt"
LAST_DAILY_FILE = ".thema_zuletzt"


def clean(text: str) -> str:
    """Eine Zeile, Leerraum zusammengefasst, hoechstens 120 Zeichen."""
    return " ".join(str(text).split())[:MAX_LENGTH].rstrip()


def _read(config_dir, name: str) -> str:
    try:
        return clean((Path(config_dir) / name).read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError):
        return ""


def read_daily_file(config_dir=CONFIG_DIR) -> str:
    """Inhalt von thema.txt ohne Ersatzangabe ("" wenn leer oder fehlend)."""
    return _read(config_dir, DAILY_FILE)


def read_hand_file(config_dir=CONFIG_DIR) -> str:
    """Inhalt von thema_hand.txt ohne Ersatzangabe ("" wenn leer oder fehlend)."""
    return _read(config_dir, HAND_FILE)


def read_daily(config_dir=CONFIG_DIR) -> str:
    return _read(config_dir, DAILY_FILE) or DEFAULT_TOPIC


def read_hand(config_dir=CONFIG_DIR) -> str:
    return _read(config_dir, HAND_FILE) or read_daily(config_dir)


def _write(directory: Path, name: str, text: str) -> None:
    fd, tmp = tempfile.mkstemp(dir=directory, prefix=name + ".", suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            handle.write(text + "\n" if text else "")
        os.replace(tmp, directory / name)
    except BaseException:
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise


def save(config_dir, daily: str, hand: str) -> None:
    directory = Path(config_dir)
    directory.mkdir(parents=True, exist_ok=True)
    _write(directory, DAILY_FILE, clean(daily))
    _write(directory, HAND_FILE, clean(hand))


def read_last_daily(config_dir=CONFIG_DIR) -> str:
    """Das Thema, zu dem zuletzt ein Zitat der Nacht gelang ("" wenn leer oder fehlend)."""
    return _read(config_dir, LAST_DAILY_FILE)


def save_last_daily(config_dir, topic: str) -> None:
    directory = Path(config_dir)
    directory.mkdir(parents=True, exist_ok=True)
    _write(directory, LAST_DAILY_FILE, clean(topic))
