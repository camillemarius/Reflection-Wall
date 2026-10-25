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


# Fragt sudo, ob die sudoers-Regel den Befehl ohne Passwort erlaubt (R6). Fuehrt ihn nicht aus.
CHECK_CMD = ["sudo", "-n", "-l", "/usr/bin/systemctl", "poweroff"]
CHECK_TIMEOUT_S = 5.0


def can_power_off(runner=subprocess.run) -> bool:
    """True, wenn die sudoers-Regel fuer power_off da ist. Fragt nie nach einem Passwort, wirft nie."""
    try:
        result = runner(CHECK_CMD, check=False, capture_output=True, timeout=CHECK_TIMEOUT_S)
    except Exception:
        return False
    return result.returncode == 0
