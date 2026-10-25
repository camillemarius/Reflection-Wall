# main.py
# Start: "python -m app.main --pc" am PC, "python -m app.main" an der Wand.
import argparse
import logging
import threading

from dotenv import load_dotenv

from app.applications.chat_app import ChatApp
from app.applications.quiz_app import QuizApp
from app.applications.radar_app import RadarApp
from app.applications.reflection_app import ReflectionApp
from app.applications.settings_apps import RadarSetupPlaceholder, ThemaApp
from app.applications.stickman_app import StickmanApp
from app.driver.display.terminal_display import TerminalDisplay
from app.driver.display.wall_display import WallDisplay
from app.link.pi_link import PiLink
from app.link.radar_switch import RadarSwitch
from app.link.serial_port import open_esp_port
from app.ui.activity import Activity, RadarPresence, idle_minutes_from_env
from app.ui.app_host import DEFAULT_CONFIG_DIR, StopSignal
from app.ui.buttons import ExpanderButtons, KeyboardButtons, QueueButtons, _SmbusReader
from app.ui.link_dispatch import LinkDispatcher
from app.ui.shell import Shell

log = logging.getLogger(__name__)

EXPIRY_POLL_S = 1.0


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
    settings = [ThemaApp(), RadarSetupPlaceholder()]
    return apps, settings


def _log_shutdown() -> None:
    log.info("Ausschalten angefordert (das Herunterfahren kommt mit Teil 2)")


def run_wall(display, buttons, activity, stop_event, link=None, radar_factory=None,
             config_dir=DEFAULT_CONFIG_DIR, on_shutdown=_log_shutdown) -> str:
    """Startet die Bildschirmfolge und gibt deren Stoppgrund zurueck.

    Mit link: Tasten und SHUTDOWN des ESP gehen durch den LinkDispatcher; laeuft die Frist
    fuer das automatische Aus ab, wird erst die Anwendung beendet und dann DONE gesendet.
    """
    apps, settings = build_apps(config_dir, radar_factory() if radar_factory else None)
    shell = Shell(display, buttons, apps, settings, activity, stop_event)
    dispatcher = None
    if link is not None:
        dispatcher = LinkDispatcher(link, buttons, activity, stop_event, shell.display_released,
                                    on_shutdown=on_shutdown)
        dispatcher.start()

    result = []
    worker = threading.Thread(target=lambda: result.append(shell.run()), name="shell", daemon=True)
    worker.start()
    try:
        expired = False
        while worker.is_alive():
            worker.join(EXPIRY_POLL_S)
            if worker.is_alive() and activity.expired():
                expired = True
                stop_event.set("idle")  # erst die Anwendung beenden (Radar gibt die Leitung frei)
                worker.join()
        if expired and result and result[0] == "idle" and dispatcher is not None:
            if not dispatcher.send_done():
                log.warning("DONE wurde nicht bestaetigt")
    finally:
        if dispatcher is not None:
            dispatcher.stop()
    return result[0] if result else "shutdown"


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

    import smbus2  # erst hier: auf dem PC nicht installierbar

    bus = smbus2.SMBus(1)  # ein Bus fuer Anzeige und Radar-Tasten
    display = WallDisplay(bus=bus)
    display.start()
    port = open_esp_port()
    link = PiLink(port)
    link.start()
    buttons = QueueButtons()
    activity = Activity(idle_minutes=activity_minutes, person_present=RadarPresence().present)

    def radar_factory():
        return RadarApp(switch_factory=lambda: RadarSwitch(link, port),
                        buttons_factory=lambda: ExpanderButtons(bus=_SmbusReader(bus)))

    try:
        run_wall(display, buttons, activity, stop, link=link, radar_factory=radar_factory)
    except KeyboardInterrupt:
        stop.set("shutdown")
    finally:
        link.stop()
        port.close()


if __name__ == "__main__":
    main()
