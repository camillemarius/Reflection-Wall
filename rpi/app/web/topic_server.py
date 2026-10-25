# web/topic_server.py
# Kleine Webseite fuer die beiden Themen (taeglich, von Hand). Nur Standardbibliothek, kein Passwort.
import html
import socket
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Callable, Tuple
from urllib.parse import parse_qs

from app import topics

MAX_BODY = 4096
_DRAIN_LIMIT = 65536
NO_NETWORK = "KEIN NETZ"
CHAIN_NOTE = "Ein neues Thema beginnt ab der nächsten Nacht eine neue Kette."

_PAGE = """<!DOCTYPE html>
<html lang="de"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Reflection Wall</title>
<style>body{{font-family:sans-serif;max-width:32rem;margin:2rem auto;padding:0 1rem}}
input[type=text]{{width:100%;box-sizing:border-box;padding:.5rem;font-size:1rem}}
small{{color:#555}} button{{margin-top:1rem;padding:.6rem 1.2rem;font-size:1rem}}</style>
</head><body>
<h1>Themen</h1>
{message}<form method="post" action="/" accept-charset="utf-8">
<p><label>Tägliches Thema<br>
<input type="text" name="daily" maxlength="{max}" value="{daily}"></label><br>
<small>{note}</small></p>
<p><label>Thema für Reflection von Hand<br>
<input type="text" name="hand" maxlength="{max}" value="{hand}"></label></p>
<button type="submit">Speichern</button>
</form></body></html>
"""


def wall_address() -> Tuple[str, str]:
    """(<hostname>.local, IPv4 im eigenen Netz oder "KEIN NETZ")."""
    host = socket.gethostname().split(".")[0]
    ip = NO_NETWORK
    probe = None
    try:
        probe = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        probe.connect(("10.255.255.255", 9))  # UDP: es wird nichts gesendet
        ip = probe.getsockname()[0]
    except OSError:
        pass
    finally:
        if probe is not None:
            probe.close()
    return host + ".local", ip


def _noop() -> None:
    pass


class TopicServer:
    def __init__(self, config_dir, port: int = 80, host: str = "",
                 on_save: Callable[[], None] = _noop) -> None:
        self._config_dir = config_dir
        self._host = host
        self._requested_port = port
        self._on_save = on_save
        self._httpd = None
        self._thread = None
        self.port = port

    def _render(self, daily: str, hand: str, saved: bool = False) -> bytes:
        message = "<p><strong>Gespeichert.</strong></p>\n" if saved else ""
        return _PAGE.format(message=message, max=topics.MAX_LENGTH, note=html.escape(CHAIN_NOTE),
                            daily=html.escape(daily, quote=True),
                            hand=html.escape(hand, quote=True)).encode("utf-8")

    def _make_handler(self):
        server = self

        class Handler(BaseHTTPRequestHandler):
            def log_message(self, format, *args):  # keine Zugriffsprotokolle
                pass

            def _send(self, code: int, body: bytes) -> None:
                self.send_response(code)
                self.send_header("Content-Type", "text/html; charset=utf-8")
                self.send_header("Content-Length", str(len(body)))
                self.send_header("Connection", "close")
                self.end_headers()
                self.wfile.write(body)

            def do_GET(self):
                if self.path.split("?")[0] != "/":
                    self._send(404, b"Nicht gefunden.")
                    return
                self._send(200, server._render(topics.read_daily(server._config_dir),
                                               topics.read_hand(server._config_dir)))

            def do_POST(self):
                if self.path.split("?")[0] != "/":
                    self._send(404, b"Nicht gefunden.")
                    return
                try:
                    length = int(self.headers.get("Content-Length", "0"))
                except ValueError:
                    length = -1
                if length < 0 or length > MAX_BODY:
                    if 0 < length <= _DRAIN_LIMIT:
                        self.rfile.read(length)
                    self._send(413, "Eingabe zu gross.".encode("utf-8"))
                    return
                form = parse_qs(self.rfile.read(length).decode("utf-8", errors="replace"),
                                keep_blank_values=True)
                daily = form.get("daily", [topics.read_daily(server._config_dir)])[0]
                hand = form.get("hand", [topics.read_hand(server._config_dir)])[0]
                try:
                    topics.save(server._config_dir, daily, hand)
                except OSError:
                    self._send(500, "Speichern fehlgeschlagen.".encode("utf-8"))
                    return
                server._on_save()
                self._send(200, server._render(topics.clean(daily), topics.clean(hand), saved=True))

        return Handler

    def start(self) -> None:
        httpd = ThreadingHTTPServer((self._host, self._requested_port), self._make_handler())
        httpd.daemon_threads = True
        self._httpd = httpd
        self.port = httpd.server_address[1]
        self._thread = threading.Thread(target=httpd.serve_forever, kwargs={"poll_interval": 0.05}, name="topic-server", daemon=True)
        self._thread.start()

    def stop(self) -> None:
        httpd, thread = self._httpd, self._thread
        self._httpd = self._thread = None
        if httpd is None:
            return
        httpd.shutdown()
        httpd.server_close()
        if thread is not None:
            thread.join(timeout=5)
