# main.py
# Start: "python -m app.main --pc" am PC, "python -m app.main" an der Wand.
import argparse
import logging
import threading
import time

from dotenv import load_dotenv

from app.applications.chat_app import ChatApp
from app.applications.quiz_app import QuizApp
from app.applications.radar_app import RadarApp
from app.applications.reflection_app import ReflectionApp
from app.applications.settings_apps import RadarSetupPlaceholder, ThemaApp, default_server_factory
from app.applications.stickman_app import StickmanApp
from app.driver.bus_rule import BusGuard
from app.driver.display.terminal_display import TerminalDisplay
from app.driver.display.wall_display import WallDisplay
from app.link.pi_link import LinkBusy, PiLink
from app.link.radar_switch import RadarSwitch
from app.link.ready import announce_ready
from app.link.serial_port import open_esp_port
from app.system.power import can_power_off, power_off
from app.ui.activity import Activity, idle_minutes_from_env
from app.ui.app_host import DEFAULT_CONFIG_DIR, StopSignal
from app.ui.buttons import ExpanderButtons, KeyboardButtons, QueueButtons, _SmbusReader
from app.ui.link_dispatch import LinkDispatcher
from app.ui.shell import Shell

log = logging.getLogger(__name__)

EXPIRY_POLL_S = 1.0
SHELL_STOP_WAIT_S = 40.0  # leave() der Radar-Umschaltung wartet bis zu 30 s auf MODE|NORMAL
SESSION_POLL_S = 0.1      # so oft schaut der Wand-Modus nach stop, solange er wartet
READY_REPEAT_S = 10.0     # so oft geht READY noch einmal raus, solange SESSION fehlt (L3)
SHUTDOWN_WAIT_S = 10.0    # nach SHUTDOWN: power_off laeuft schon im Dispatcher
DONE_WAIT_S = 120.0       # nach DONE: so lange darf das SHUTDOWN des ESP brauchen
# So lange wartet das OK auf SHUTDOWN auf die freigegebene Anzeige. Unter der Frist des ESP
# fuer SHUTDOWN (T_shutdown, 60 s); deckt ein ganzes Bild bei haengendem INT_GPIO_EXP
# (Regel B wartet vor jedem der 12 Module bis zu 1 s).
RELEASE_WAIT_S = 45.0
SERVE_POLL_S = 1.0        # Takt des Wartens auf das Prozessende (Ctrl+C bricht es ab)


class RadarPcPlaceholder:
    """Am PC gibt es kein Radar; der Menuepunkt bleibt, damit die Reihenfolge stimmt."""

    name = "RADAR"

    def run(self, ctx) -> None:
        ctx.display.show_lines(["RADAR NUR AN DER WAND", "BT4 ZURUECK"])
        while True:
            ctx.wait_button()


def build_apps(config_dir, radar_app=None):
    """Hauptmenue und Einstellungen in der Reihenfolge der Spezifikation."""
    apps = [
        ChatApp(),
        QuizApp(),
        ReflectionApp(config_dir=config_dir),
        radar_app if radar_app is not None else RadarPcPlaceholder(),
        StickmanApp(),
    ]
    settings = [ThemaApp(server_factory=default_server_factory(config_dir)),
                RadarSetupPlaceholder()]
    return apps, settings


def _log_shutdown() -> None:
    log.info("Ausschalten angefordert (herunterfahren nur im Wand-Modus von main)")


def run_wall(display, buttons, activity, stop_event, link=None, radar_factory=None,
             config_dir=DEFAULT_CONFIG_DIR, on_shutdown=_log_shutdown,
             dispatcher=None, display_released=None) -> str:
    """Startet die Bildschirmfolge und gibt deren Stoppgrund zurueck.

    Mit link und ohne dispatcher: Tasten und SHUTDOWN des ESP gehen durch einen eigenen
    LinkDispatcher; laeuft die Frist fuer das automatische Aus ab, wird erst die Anwendung
    beendet und dann DONE gesendet.
    Mit dispatcher (Wand-Modus): main() hat ihn gestartet und stoppt ihn auch, display_released
    ist sein Event. DONE sendet dann nur main(), genau einmal.
    """
    apps, settings = build_apps(config_dir, radar_factory() if radar_factory else None)
    shell = Shell(display, buttons, apps, settings, activity, stop_event,
                  display_released=display_released)
    own = None  # eigener Dispatcher, nur ohne den von main()
    if dispatcher is None and link is not None:
        own = LinkDispatcher(link, buttons, activity, stop_event, shell.display_released,
                             on_shutdown=on_shutdown)
        own.start()

    result = []

    def run_shell() -> None:
        try:
            result.append(shell.run())
        except Exception:
            log.exception("Bildschirmfolge abgestuerzt")
            result.append("error")

    worker = threading.Thread(target=run_shell, name="shell", daemon=True)
    worker.start()
    try:
        expired = False
        while worker.is_alive():
            worker.join(EXPIRY_POLL_S)
            if worker.is_alive() and activity.expired():
                expired = True
                stop_event.set("idle")  # erst die Anwendung beenden (Radar gibt die Leitung frei)
                worker.join()
        if expired and result and result[0] == "idle" and own is not None:
            if not own.send_done():
                log.warning("DONE wurde nicht bestaetigt")
    finally:
        if worker.is_alive():
            # Ctrl+C oder Prozessende: die Anwendung beenden und auf sie warten, damit sie
            # aufraeumt (das Radar schaltet die Leitung mit leave() zurueck).
            stop_event.set("shutdown")
            worker.join(SHELL_STOP_WAIT_S)
            if worker.is_alive():
                log.warning("Bildschirmfolge nach %.0f s nicht beendet", SHELL_STOP_WAIT_S)
        if own is not None:
            own.stop()
    return result[0] if result else "error"


def _await_session(dispatcher, stop, link, clock=time.monotonic):
    """Grund der Sitzung ("HAND" oder "NACHT"); None, wenn vorher stop kam (R9).

    Fehlt SESSION, geht alle READY_REPEAT_S ein neues READY raus. Hatte der ESP nach seinem OK
    auf READY einen Reset, bevor er gesichert hat, steht er noch in EINSCHALTEN. Das neue READY
    bringt ihn in BETRIEB, und er sendet SESSION (L3)."""
    last = clock()
    while not dispatcher.session_event.wait(SESSION_POLL_S):
        if stop.is_set():
            return None
        if clock() - last >= READY_REPEAT_S:
            last = clock()
            _repeat_ready(link)
    return dispatcher.session_reason


def _repeat_ready(link) -> None:
    """Ein READY, ohne auf die Antwort zu warten; die braucht hier niemand."""
    try:
        link.request("READY")
    except LinkBusy:
        return  # eine Anfrage ist noch offen: beim naechsten Mal
    log.info("Kein SESSION nach READY, READY noch einmal")


def _hand_session(start_menu, stop, released) -> str:
    """SESSION|HAND: erst jetzt gehoert die Anzeige dem Pi (R5)."""
    released.clear()  # vor dem Blick auf stop: ab hier wartet ein SHUTDOWN auf die Freigabe
    try:
        if stop.is_set():  # SHUTDOWN kam schon mit: die Anzeige nicht mehr anfassen
            return stop.reason or "shutdown"
        return start_menu()
    finally:
        released.set()


def _night_session(stop) -> str:
    """SESSION|NACHT: die Anzeige bleibt beim ESP (V1). Teil 3b holt hier GET|QUOTE."""
    while not stop.wait(SESSION_POLL_S):
        pass
    return stop.reason or "shutdown"


def _await_power_off(dispatcher, result) -> None:
    """Nach der Sitzung: bei "idle" und "error" bittet der Pi mit DONE ums Ausschalten (nur
    hier, genau einmal); dann wartet er, bis der Dispatcher das SHUTDOWN erledigt hat.
    Kommt nach einem bestaetigten DONE kein SHUTDOWN, faehrt der Pi selbst herunter: er
    wollte ohnehin aus (M-4)."""
    wait_s = SHUTDOWN_WAIT_S
    done = False
    if result in ("idle", "error"):
        done = dispatcher.send_done()
        if not done:
            log.warning("DONE wurde nicht bestaetigt")
        wait_s = DONE_WAIT_S
    if dispatcher.shutdown_done.wait(wait_s):
        return
    if done:
        log.warning("Nach DONE %.0f s kein SHUTDOWN; der Pi faehrt selbst herunter", wait_s)
        dispatcher.shut_down_once()
    else:
        log.warning("Nach %.0f s nicht heruntergefahren; der ESP schaltet trotzdem ab", wait_s)


def _wait_for_process_end(sleep=time.sleep) -> None:
    """Nach der Sitzung: Leitung und Dispatcher bleiben an, bis systemd den Prozess beim
    Herunterfahren beendet. Sendet der ESP nach einem Reset SHUTDOWN noch einmal (R8), bekommt
    es so sein OK. Kehrt nie zurueck; Ctrl+C bricht mit KeyboardInterrupt ab."""
    while True:
        sleep(SERVE_POLL_S)


def _stop_quietly(name, action) -> None:
    try:
        action()
    except Exception:
        log.exception("%s nicht sauber beendet", name)


def _serve_wall(stop, activity_minutes) -> None:
    """Wand-Modus: READY, auf SESSION warten, Sitzung bedienen, auf das Herunterfahren warten.
    Danach weiter bedienen, bis der Prozess endet (I-1)."""
    if not can_power_off():  # R6, M-4
        log.error("sudoers-Regel fuer 'systemctl poweroff' fehlt: der Pi kann sich nicht selbst "
                  "herunterfahren, jedes Ende einer Sitzung trennt ihn hart (rpi/README.md)")
    import smbus2  # erst hier: auf dem PC nicht installierbar

    bus = smbus2.SMBus(1)  # ein Bus fuer Anzeige und Radar-Tasten
    guard = BusGuard()  # Regel B; belegt auch GPIO22 und liefert die Anwesenheit (R13)
    port = link = dispatcher = None
    try:
        guard.start()
        port = open_esp_port()
        link = PiLink(port)
        link.start()
        buttons = QueueButtons()
        activity = Activity(idle_minutes=activity_minutes, person_present=guard.radar_high)
        released = threading.Event()
        released.set()  # noch laeuft keine Bildschirmfolge: SHUTDOWN bekommt sofort OK
        dispatcher = LinkDispatcher(link, buttons, activity, stop, released,
                                    on_shutdown=power_off, release_wait_s=RELEASE_WAIT_S)
        dispatcher.start()

        def radar_factory():
            return RadarApp(
                switch_factory=lambda: RadarSwitch(link, port),
                buttons_factory=lambda: ExpanderButtons(bus=_SmbusReader(bus), bus_guard=guard))

        def start_menu() -> str:
            display = WallDisplay(bus=bus, bus_guard=guard)
            display.start()  # schreibt schon: darum erst nach SESSION|HAND
            activity.touch()  # das automatische Aus zaehlt ab dem Menue, nicht ab READY
            return run_wall(display, buttons, activity, stop, link=link,
                            radar_factory=radar_factory, dispatcher=dispatcher,
                            display_released=released)

        # announce_ready gibt False, wenn stop vor dem OK auf READY kam: ein SHUTDOWN, das der
        # Dispatcher schon bearbeitet. Dann gibt es keine Sitzung, bedient wird trotzdem.
        if announce_ready(link, stop):  # L1
            reason = _await_session(dispatcher, stop, link)
            if reason == "HAND":
                result = _hand_session(start_menu, stop, released)
            elif reason == "NACHT":
                result = _night_session(stop)
            else:  # SHUTDOWN vor SESSION (R9): die Anzeige bleibt beim ESP
                result = stop.reason or "shutdown"
            _await_power_off(dispatcher, result)
        _wait_for_process_end()
    except KeyboardInterrupt:
        stop.set("shutdown")
    finally:
        if dispatcher is not None:
            _stop_quietly("Dispatcher", dispatcher.stop)
        if link is not None:
            _stop_quietly("Leitung zum ESP", link.stop)
        if port is not None:
            _stop_quietly("Port", port.close)
        _stop_quietly("BusGuard", guard.stop)


def main(argv=None) -> None:
    parser = argparse.ArgumentParser(prog="python -m app.main")
    parser.add_argument("--pc", action="store_true",
                        help="PC-Modus: Textanzeige im Terminal, Tasten 1-6 mit Enter")
    args = parser.parse_args(argv)

    load_dotenv()
    logging.basicConfig(level=logging.INFO)
    stop = StopSignal()
    activity_minutes = idle_minutes_from_env()

    if args.pc:
        display = TerminalDisplay()
        display.start()
        buttons = KeyboardButtons()
        buttons.start()
        activity = Activity(idle_minutes=activity_minutes)
        try:
            run_wall(display, buttons, activity, stop)
        except KeyboardInterrupt:
            stop.set("shutdown")
        return

    _serve_wall(stop, activity_minutes)


if __name__ == "__main__":
    main()
