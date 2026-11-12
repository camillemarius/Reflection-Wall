# applications/radar_records.py
# Radar-Einrichtung (Spec §7): Sicherung der alten Werte, zuletzt gewaehlter Zielwert, Bericht.
# Alles im Ordner radar des Konfigurationsordners; geschrieben wird ueber .tmp und replace.
import datetime
import json
import logging
from pathlib import Path
from typing import Callable, Optional

from app.driver.uart.ld2410s import RadarSettings

log = logging.getLogger(__name__)

TARGETS_M = (1.0, 1.5, 2.0, 2.5, 3.0, 3.5)
DEFAULT_TARGET_M = 2.0
RUNNING = "laufend"


def _write(path: Path, text: str) -> None:
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(text, encoding="utf-8")
    tmp.replace(path)


class RadarRecords:
    def __init__(self, config_dir, now: Callable[[], datetime.datetime] = datetime.datetime.now):
        self._dir = Path(config_dir) / "radar"
        self._now = now

    def _path(self, name: str) -> Path:
        self._dir.mkdir(parents=True, exist_ok=True)
        return self._dir / name

    def _backup(self) -> Optional[dict]:
        try:
            saved = json.loads((self._dir / "sicherung.json").read_text(encoding="utf-8"))
            return {"status": str(saved["status"]),
                    "werte": RadarSettings.from_dict(saved["werte"])}
        except FileNotFoundError:
            return None
        except (OSError, ValueError, KeyError, TypeError) as exc:
            log.warning("Radar-Sicherung unbrauchbar: %s", exc)
            return None

    def save_backup(self, settings: RadarSettings) -> None:
        self._write_backup(RUNNING, settings)

    def _write_backup(self, status: str, settings: RadarSettings) -> None:
        _write(self._path("sicherung.json"),
               json.dumps({"status": status, "werte": settings.to_dict()}, indent=1))

    def pending_backup(self) -> Optional[RadarSettings]:
        """Die Sicherung eines unterbrochenen Durchgangs, sonst None."""
        backup = self._backup()
        return backup["werte"] if backup and backup["status"] == RUNNING else None

    def close_backup(self, status: str) -> None:
        backup = self._backup()
        if backup is not None:
            self._write_backup(status, backup["werte"])

    def last_target_m(self) -> float:
        try:
            value = float((self._dir / "zielwert.txt").read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return DEFAULT_TARGET_M
        return value if value in TARGETS_M else DEFAULT_TARGET_M

    def save_target_m(self, metres: float) -> None:
        _write(self._path("zielwert.txt"), "%.1f\n" % metres)

    def write_report(self, report: dict) -> Path:
        path = self._path(self._now().strftime("einrichtung-%Y%m%d-%H%M%S.json"))
        _write(path, json.dumps(report, indent=1, ensure_ascii=False))
        return path
