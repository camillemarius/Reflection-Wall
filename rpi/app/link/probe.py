"""Pruefwerkzeug fuer die Verbindung ESP-Pi.

Aufruf auf dem Pi: cd rpi && python -m app.link.probe
Das Werkzeug faehrt den Pi nie herunter: SHUTDOWN wird mit BUSY beantwortet.
"""
import argparse
import concurrent.futures
import logging
import queue
import sys
import time

from app.link.codec import Message
from app.link.pi_link import PiLink
from app.link.serial_port import ESP_BAUD, ESP_DEVICE, open_esp_port

WAIT_S = 0.1


def answer_for(request: Message) -> tuple[str, str]:
    if request.command == "BUTTON":
        return ("OK", "")
    if request.command == "SHUTDOWN":
        return ("BUSY", "")
    return ("ERROR", "PROBE")


def _describe(msg: Message) -> str:
    return f"{msg.command}|{msg.data}" if msg.data else msg.command


def _serve(link: PiLink) -> None:
    """Leert incoming (hoechstens WAIT_S warten) und beantwortet jede Anfrage."""
    try:
        req = link.incoming.get(timeout=WAIT_S)
    except queue.Empty:
        return
    command, data = answer_for(req)
    print(f"{_describe(req)} (#{req.seq:02X}) <- {_describe(Message(req.seq, command, data))}",
          flush=True)
    link.reply(req, command, data)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Prueft die Verbindung zum ESP")
    ap.add_argument("--port", default=ESP_DEVICE)
    ap.add_argument("--baud", type=int, default=ESP_BAUD)
    ap.add_argument("--seconds", type=float, default=0, help="0 = bis Ctrl+C")
    ap.add_argument("--no-gpio", action="store_true", help="GPIO23 nicht schalten")
    args = ap.parse_args(argv)

    log = logging.getLogger("link")
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(logging.Formatter("%(asctime)s %(message)s", "%H:%M:%S"))
    old_level = log.level
    port = None
    link = None
    code = 0
    log.setLevel(logging.DEBUG)
    log.addHandler(handler)
    try:
        try:
            port = open_esp_port(args.port, args.baud, select_gpio=not args.no_gpio)
        except ModuleNotFoundError as exc:
            print(f"Fehler: {exc.name or 'lgpio'} fehlt - auf dem PC mit --no-gpio starten",
                  flush=True)
            return 1
        except Exception as exc:
            print(f"Fehler: Port nicht gefunden oder keine Rechte ({exc}) - "
                  "uart0 aktiviert, Benutzer in dialout?", flush=True)
            return 1
        link = PiLink(port)
        link.start()
        end = time.monotonic() + args.seconds if args.seconds > 0 else None
        answered = False
        fut: "concurrent.futures.Future | None" = None
        while end is None or time.monotonic() < end:
            if not link.alive:
                print("Fehler: Verbindung abgebrochen (Portfehler) - Kabel und Port pruefen",
                      flush=True)
                code = 1
                break
            if not answered:
                if fut is None:
                    fut = link.request("READY")
                if fut.done():
                    reply = fut.result()
                    fut = None  # ohne Antwort: neu senden
                    if reply is not None:
                        print(f"READY -> {_describe(reply)} (#{reply.seq:02X})", flush=True)
                        answered = True
            _serve(link)
    except KeyboardInterrupt:
        pass
    finally:
        if link is not None:
            print(f"verworfen: {dict(link.discarded)}", flush=True)
            link.stop()
        if port is not None:
            port.close()
        log.removeHandler(handler)
        log.setLevel(old_level)
    return code


if __name__ == "__main__":
    sys.exit(main())
