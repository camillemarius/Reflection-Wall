# link/ready.py
# Meldet dem ESP, dass der Pi-Dienst laeuft: READY, bis der ESP mit OK antwortet (L1).
import concurrent.futures
import logging
import time
from typing import Callable

from app.link.pi_link import LinkBusy

log = logging.getLogger(__name__)

BUSY_RETRY_S = 0.25
ANSWER_WAIT_S = 5.0  # Frist des ESP (3 s) plus Reserve


def announce_ready(link, stop, sleep: Callable[[float], None] = time.sleep) -> bool:
    """Sendet READY, bis OK kommt. False, wenn stop gesetzt wird."""
    while not stop.is_set():
        try:
            future = link.request("READY")
        except LinkBusy:
            sleep(BUSY_RETRY_S)
            continue
        try:
            answer = future.result(timeout=ANSWER_WAIT_S)
        except concurrent.futures.TimeoutError:
            answer = None
        if answer is not None and answer.command == "OK":
            return True
        if answer is None:
            log.info("READY ohne Antwort, neuer Versuch")
        else:
            log.warning("READY mit %s beantwortet, neuer Versuch", answer.command)
    return False
