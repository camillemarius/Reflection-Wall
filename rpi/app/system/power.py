# system/power.py
# Faehrt den Pi herunter (SHUTDOWN vom ESP). Ueber sudo -n, damit nie nach einem Passwort gefragt wird.
import logging
import subprocess

log = logging.getLogger(__name__)

POWER_OFF_CMD = ["sudo", "-n", "/usr/bin/systemctl", "poweroff"]


def power_off(runner=subprocess.run) -> bool:
    """Startet das Herunterfahren. True nur bei Rueckgabecode 0, sonst False. Wirft nie."""
    try:
        result = runner(POWER_OFF_CMD, check=False)
    except Exception:
        log.exception("Herunterfahren fehlgeschlagen: Befehl konnte nicht gestartet werden")
        return False
    if result.returncode != 0:
        log.error("Herunterfahren fehlgeschlagen: Rueckgabecode %s", result.returncode)
        return False
    return True
