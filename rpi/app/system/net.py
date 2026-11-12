# system/net.py
# Warten aufs Netz: nach dem Start des Pi ist es oft noch nicht da (Abnahme 2026-11-02: erst nach
# rund 50 s; die Fragen an die KI davor endeten alle mit "Connection error").
import socket
import time

RETRY_S = 2.0            # Abstand der Versuche
CONNECT_TIMEOUT_S = 3.0  # ein einzelner Versuch hoechstens


def wait_for_host(host, port, timeout_s, connect=socket.create_connection,
                  clock=time.monotonic, sleep=time.sleep) -> bool:
    """True, sobald eine TCP-Verbindung zu host:port gelingt; False, wenn das nach timeout_s noch
    nicht so ist. Die Probeverbindung wird gleich wieder geschlossen."""
    end = clock() + timeout_s
    while True:
        left = end - clock()
        try:
            connect((host, port), timeout=max(0.1, min(CONNECT_TIMEOUT_S, left))).close()
            return True
        except OSError:
            pass
        left = end - clock()
        if left <= 0:
            return False
        sleep(min(RETRY_S, left))
