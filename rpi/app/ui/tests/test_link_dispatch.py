import concurrent.futures
import queue
import threading
import time
import unittest
from unittest import mock

from app.link.codec import Message, decode, encode
from app.link.pi_link import LinkBusy, PiLink
from app.link.tests.fakes import FakePort
from app.ui import link_dispatch
from app.ui.activity import Activity
from app.ui.app_host import StopSignal
from app.ui.buttons import QueueButtons
from app.ui.link_dispatch import LinkDispatcher


class FakeLink:
    def __init__(self):
        self.incoming = queue.Queue()
        self.replies = []
        self.requests = []
        self.script = []  # je Aufruf: "busy", None oder Message
        self.stale_seqs = set()  # Nummern, die eine neuere Anfrage ersetzt hat: reply gibt False

    def reply(self, request, command, data=""):
        self.replies.append((request.seq, command, data))
        return request.seq not in self.stale_seqs

    def request(self, command, data=""):
        self.requests.append((command, data))
        step = self.script.pop(0) if self.script else Message(1, "OK", "")
        if step == "busy":
            raise LinkBusy()
        fut = concurrent.futures.Future()
        fut.set_result(step)
        return fut


def wait_for(cond, timeout=2.0):
    end = time.monotonic() + timeout
    while time.monotonic() < end:
        if cond():
            return True
        time.sleep(0.005)
    return False


class FakeTimer:
    def __init__(self):
        self.cancelled = False

    def cancel(self):
        self.cancelled = True


class FakeTimers:
    """Statt threading.Timer: merkt sich jeden Zeitgeber; der Test loest ihn selbst aus."""

    def __init__(self):
        self.started = []  # (Frist in s, Aktion, Zeitgeber)

    def __call__(self, delay_s, action):
        timer = FakeTimer()
        self.started.append((delay_s, action, timer))
        return timer


class RecordingPort(FakePort):
    """FakePort, der jede gesendete Zeile als ("tx", Nummer, Befehl) in events eintraegt."""

    def __init__(self, events):
        super().__init__()
        self.events = events

    def write(self, data):
        super().write(data)
        for line in data.split(b"\n"):
            if line:
                msg = decode(line)
                self.events.append(("tx", msg.seq, msg.command))


class DispatchTest(unittest.TestCase):
    def setUp(self):
        self.link = FakeLink()
        self.buttons = QueueButtons()
        self.activity = Activity()
        self.stop = StopSignal()
        self.released = threading.Event()
        self.shutdowns = []
        self.d = LinkDispatcher(self.link, self.buttons, self.activity, self.stop,
                                self.released, on_shutdown=lambda: self.shutdowns.append(1))
        self.d.start()
        self.addCleanup(self.d.stop)

    def test_button_forwarded_and_acked(self):
        self.link.incoming.put(Message(7, "BUTTON", "5"))
        self.assertEqual(self.buttons.get(1.0), 5)
        self.assertTrue(wait_for(lambda: self.link.replies))
        self.assertEqual(self.link.replies, [(7, "OK", "")])

    def test_bad_button(self):
        for data in ("0", "7", "x", ""):
            self.link.incoming.put(Message(3, "BUTTON", data))
        self.assertTrue(wait_for(lambda: len(self.link.replies) == 4))
        self.assertTrue(all(r[1:] == ("ERROR", "BAD_BUTTON") for r in self.link.replies))
        self.assertIsNone(self.buttons.get(0))

    def test_shutdown_stops_shell_then_ok(self):
        self.link.incoming.put(Message(9, "SHUTDOWN", ""))
        self.assertTrue(wait_for(self.stop.is_set))
        self.assertEqual(self.stop.reason, "shutdown")
        time.sleep(0.05)
        self.assertEqual(self.link.replies, [])  # erst nach Freigabe
        self.released.set()
        self.assertTrue(wait_for(lambda: self.shutdowns))
        self.assertEqual(self.link.replies, [(9, "OK", "")])

    def test_shutdown_answers_after_wait_limit(self):
        d = LinkDispatcher(self.link, self.buttons, self.activity, self.stop,
                           self.released, release_wait_s=0.05)
        d.start()
        self.addCleanup(d.stop)
        self.d.stop()
        self.link.incoming.put(Message(2, "SHUTDOWN", ""))
        self.assertTrue(wait_for(lambda: self.link.replies))
        self.assertEqual(self.link.replies[0][1], "OK")

    def test_shutdown_busy_while_radar_writing(self):
        self.d.radar_writing.set()
        self.link.incoming.put(Message(4, "SHUTDOWN", ""))
        self.assertTrue(wait_for(lambda: self.link.replies))
        self.assertEqual(self.link.replies, [(4, "BUSY", "")])
        self.assertFalse(self.stop.is_set())
        self.assertEqual(self.shutdowns, [])

    def test_session_hand_sets_reason_and_event(self):
        self.assertIsNone(self.d.session_reason)
        self.link.incoming.put(Message(11, "SESSION", "HAND"))
        self.assertTrue(self.d.session_event.wait(1.0))
        self.assertEqual(self.d.session_reason, "HAND")
        self.assertTrue(wait_for(lambda: self.link.replies))
        self.assertEqual(self.link.replies, [(11, "OK", "")])

    def test_second_session_is_answered_and_ignored(self):
        self.link.incoming.put(Message(11, "SESSION", "HAND"))
        self.link.incoming.put(Message(12, "SESSION", "NACHT"))
        self.assertTrue(wait_for(lambda: len(self.link.replies) == 2))
        self.assertEqual(self.link.replies, [(11, "OK", ""), (12, "OK", "")])
        self.assertEqual(self.d.session_reason, "HAND")
        self.assertFalse(self.d.hand_requested.is_set())

    def test_session_bad_data_is_error(self):
        self.link.incoming.put(Message(13, "SESSION", "X"))
        self.assertTrue(wait_for(lambda: self.link.replies))
        self.assertEqual(self.link.replies, [(13, "ERROR", "BAD_SESSION")])
        self.assertIsNone(self.d.session_reason)
        self.assertFalse(self.d.session_event.is_set())

    def test_shutdown_sets_shutdown_done_after_reply(self):
        self.assertFalse(self.d.shutdown_done.is_set())
        self.link.incoming.put(Message(9, "SHUTDOWN", ""))
        self.assertTrue(wait_for(self.stop.is_set))
        self.assertFalse(self.d.shutdown_done.is_set())
        self.released.set()
        self.assertTrue(self.d.shutdown_done.wait(1.0))
        self.assertEqual(self.link.replies, [(9, "OK", "")])
        self.assertEqual(self.shutdowns, [1])

    def test_second_shutdown_gets_ok_and_on_shutdown_runs_once(self):
        # I-1: der ESP sendet SHUTDOWN nach einem Reset noch einmal, mit neuer Nummer (R8)
        self.released.set()
        self.link.incoming.put(Message(9, "SHUTDOWN", ""))
        self.assertTrue(self.d.shutdown_done.wait(1.0))
        self.link.incoming.put(Message(10, "SHUTDOWN", ""))
        self.assertTrue(wait_for(lambda: len(self.link.replies) == 2))
        self.assertEqual(self.link.replies, [(9, "OK", ""), (10, "OK", "")])
        self.assertEqual(self.shutdowns, [1])

    def test_shut_down_once_calls_on_shutdown_only_the_first_time(self):
        self.assertTrue(self.d.shut_down_once())
        self.assertTrue(self.d.shutdown_done.is_set())
        self.assertFalse(self.d.shut_down_once())
        self.released.set()
        self.link.incoming.put(Message(9, "SHUTDOWN", ""))
        self.assertTrue(wait_for(lambda: self.link.replies))
        self.assertEqual(self.link.replies, [(9, "OK", "")])
        self.assertEqual(self.shutdowns, [1])

    def test_shut_down_once_sets_done_even_if_on_shutdown_raises(self):
        def failing():
            self.shutdowns.append(1)
            raise OSError("sudo fehlt")

        d = LinkDispatcher(self.link, self.buttons, self.activity, self.stop, self.released,
                           on_shutdown=failing)
        with self.assertLogs("app.ui.link_dispatch", "ERROR"):
            self.assertTrue(d.shut_down_once())
        self.assertTrue(d.shutdown_done.is_set())
        self.assertFalse(d.shut_down_once())
        self.assertEqual(self.shutdowns, [1])

    def test_shutdown_busy_does_not_set_shutdown_done(self):
        self.d.radar_writing.set()
        self.link.incoming.put(Message(4, "SHUTDOWN", ""))
        self.assertTrue(wait_for(lambda: self.link.replies))
        self.assertFalse(self.d.shutdown_done.is_set())

    def test_other_requests_kept(self):
        m = Message(5, "PING", "")  # beantwortet sonst PiLink selbst
        self.link.incoming.put(m)
        self.assertTrue(wait_for(lambda: not self.d.other.empty()))
        self.assertIs(self.d.other.get_nowait(), m)
        self.assertEqual(self.link.replies, [])

    def test_session_hand_after_nacht_sets_hand_requested(self):
        # N3: BT2 in der Nacht. Aus NACHT wird HAND, main() startet dann das Menue.
        self.link.incoming.put(Message(11, "SESSION", "NACHT"))
        self.assertTrue(self.d.session_event.wait(1.0))
        self.assertTrue(wait_for(lambda: self.link.replies))
        self.assertFalse(self.d.hand_requested.is_set())
        self.link.incoming.put(Message(12, "SESSION", "HAND"))
        self.assertTrue(self.d.hand_requested.wait(1.0))
        self.assertEqual(self.d.session_reason, "HAND")
        self.assertEqual(self.link.replies, [(11, "OK", ""), (12, "OK", "")])

    def test_second_nacht_or_hand_after_hand_keeps_the_old_rule(self):
        for seq in (11, 12):
            self.link.incoming.put(Message(seq, "SESSION", "NACHT"))
        self.assertTrue(wait_for(lambda: len(self.link.replies) == 2))
        self.assertFalse(self.d.hand_requested.is_set())  # ein zweites NACHT startet kein Menue
        self.assertEqual(self.d.session_reason, "NACHT")
        for seq, data in ((13, "HAND"), (14, "HAND"), (15, "NACHT")):
            self.link.incoming.put(Message(seq, "SESSION", data))
        self.assertTrue(wait_for(lambda: len(self.link.replies) == 5))
        self.assertTrue(all(r[1] == "OK" for r in self.link.replies))
        self.assertEqual(self.d.session_reason, "HAND")  # nur das erste HAND nach NACHT zaehlt
        self.assertTrue(self.d.hand_requested.is_set())

    def test_stop_ends_thread_quickly(self):
        t0 = time.monotonic()
        self.d.stop()
        self.assertLess(time.monotonic() - t0, 0.5)


class SlowQuote:
    """quote_maker des Tests: meldet den Aufruf und rechnet, bis der Test release() ruft."""

    def __init__(self, result=("QUOTE", "DER WEG IST DAS ZIEL.")):
        self.result = result
        self.calls = []  # (yesterday, Name des Threads)
        self.entered = threading.Event()
        self._release = threading.Event()

    def __call__(self, yesterday):
        self.calls.append((yesterday, threading.current_thread().name))
        self.entered.set()
        self._release.wait(5)
        return self.result

    def release(self):
        self._release.set()


class GetTest(unittest.TestCase):
    """GET|QUOTE|<Text vom Vortag>: das Zitat der Nacht rechnet ein Arbeits-Thread (R10)."""

    def setUp(self):
        self.link = FakeLink()
        self.buttons = QueueButtons()

    def make(self, quote_maker):
        d = LinkDispatcher(self.link, self.buttons, Activity(), StopSignal(), threading.Event(),
                           quote_maker=quote_maker)
        d.start()
        self.addCleanup(d.stop)
        return d

    def put(self, seq, command, data=""):
        self.link.incoming.put(Message(seq, command, data))

    def test_get_answers_quote_from_worker(self):
        maker = SlowQuote()
        maker.release()
        self.make(maker)
        self.put(20, "GET", "QUOTE|GESTERN WAR ES SO.")
        self.assertTrue(wait_for(lambda: self.link.replies))
        self.assertEqual(self.link.replies, [(20, "QUOTE", "DER WEG IST DAS ZIEL.")])
        self.put(21, "GET", "QUOTE|")  # leer: eine neue Kette; nach der Antwort ein neuer Thread
        self.assertTrue(wait_for(lambda: len(self.link.replies) == 2))
        self.assertEqual(self.link.replies[1], (21, "QUOTE", "DER WEG IST DAS ZIEL."))
        self.assertEqual([y for y, _ in maker.calls], ["GESTERN WAR ES SO.", ""])
        self.assertNotIn("link-dispatch", [name for _, name in maker.calls])

    def test_get_answers_error_from_worker(self):
        for seq, code in ((22, "ZU_LANG"), (23, "KI")):
            maker = SlowQuote(("ERROR", code))
            maker.release()
            d = self.make(maker)
            self.put(seq, "GET", "QUOTE|")
            self.assertTrue(wait_for(lambda: (seq, "ERROR", code) in self.link.replies))
            d.stop()

    def test_undelivered_quote_answers_a_get_with_the_same_yesterday(self):
        # Fall C: PiLink nimmt die Antwort auf GET 20 nicht an, eine neuere Anfrage kam zuerst.
        # Das Zitat bleibt gemerkt; das GET danach mit demselben Text vom Vortag bekommt es ohne
        # zweite KI-Runde. Damit ist es zugestellt und verfaellt: GET 22 rechnet neu.
        maker = SlowQuote()
        maker.release()
        self.link.stale_seqs = {20}
        self.make(maker)
        self.put(20, "GET", "QUOTE|GESTERN")
        self.assertTrue(wait_for(lambda: len(self.link.replies) == 1))
        self.put(21, "GET", "QUOTE|GESTERN")
        self.assertTrue(wait_for(lambda: len(self.link.replies) == 2))
        self.assertEqual(self.link.replies[1], (21, "QUOTE", "DER WEG IST DAS ZIEL."))
        self.assertEqual(len(maker.calls), 1)
        self.put(22, "GET", "QUOTE|GESTERN")
        self.assertTrue(wait_for(lambda: len(self.link.replies) == 3))
        self.assertEqual(len(maker.calls), 2)

    def test_delivered_quote_is_not_reused(self):
        # Ist die Antwort zugestellt (der ESP lehnt das Zitat ab, oder ein Reset kam, waehrend
        # sie auf der Leitung war), rechnet ein spaeteres GET mit demselben Text vom Vortag neu.
        maker = SlowQuote()
        maker.release()
        self.make(maker)
        self.put(20, "GET", "QUOTE|GESTERN")
        self.assertTrue(wait_for(lambda: len(self.link.replies) == 1))
        self.put(21, "GET", "QUOTE|GESTERN")
        self.assertTrue(wait_for(lambda: len(self.link.replies) == 2))
        self.assertEqual(self.link.replies[1], (21, "QUOTE", "DER WEG IST DAS ZIEL."))
        self.assertEqual(len(maker.calls), 2)

    def test_session_end_clears_the_finished_result(self):
        maker = SlowQuote()
        maker.release()
        released = threading.Event()
        released.set()
        d = LinkDispatcher(self.link, self.buttons, Activity(), StopSignal(), released,
                           quote_maker=maker)
        d.start()
        self.addCleanup(d.stop)
        self.link.stale_seqs = {20}  # nicht zugestellt: das Zitat bliebe gemerkt
        self.put(20, "GET", "QUOTE|GESTERN")
        self.assertTrue(wait_for(lambda: len(self.link.replies) == 1))
        self.put(21, "SHUTDOWN")
        self.assertTrue(wait_for(lambda: (21, "OK", "") in self.link.replies))
        self.put(22, "GET", "QUOTE|GESTERN")
        self.assertTrue(wait_for(lambda: len(self.link.replies) == 3))
        self.assertEqual(len(maker.calls), 2)

    def test_base_exception_in_worker_does_not_block_later_gets(self):
        calls = []

        def leaving(yesterday):
            calls.append(yesterday)
            if len(calls) == 1:
                raise SystemExit  # eine BaseException; threading meldet sie nicht
            return ("QUOTE", "WIEDER DA.")

        self.make(leaving)
        self.put(40, "GET", "QUOTE|")
        self.assertTrue(wait_for(lambda: calls))
        time.sleep(0.05)  # der erste Arbeits-Thread ist zu Ende
        self.put(41, "GET", "QUOTE|")
        self.assertTrue(wait_for(lambda: self.link.replies))
        self.assertEqual(self.link.replies, [(41, "QUOTE", "WIEDER DA.")])

    def test_refused_reply_log_names_every_cause(self):
        # PiLink.reply gibt nur False: die Anfrage ist nicht mehr offen, die Leitung ist an das
        # Radar abgegeben, oder die Antwort laesst sich nicht kodieren. Das Log sagt nur das.
        maker = SlowQuote()
        maker.release()
        self.link.stale_seqs = {42}
        self.make(maker)
        with self.assertLogs("app.ui.link_dispatch", "INFO") as logs:
            self.put(42, "GET", "QUOTE|")
            self.assertTrue(wait_for(lambda: any("nicht gesendet" in line for line in logs.output)))
        line = next(line for line in logs.output if "nicht gesendet" in line)
        for cause in ("#2A", "nicht mehr offen", "Radar", "kodier"):
            self.assertIn(cause, line)

    def test_get_bad_data(self):
        maker = SlowQuote()
        maker.release()
        self.make(maker)
        for seq, data in ((30, "X"), (31, ""), (32, "QUOTE"), (33, "quote|A")):
            self.put(seq, "GET", data)
        self.assertTrue(wait_for(lambda: len(self.link.replies) == 4))
        self.assertEqual(self.link.replies, [(seq, "ERROR", "BAD_GET") for seq in (30, 31, 32, 33)])
        self.assertEqual(maker.calls, [])

    def test_get_without_maker_is_ki_error(self):
        self.make(None)
        self.put(34, "GET", "QUOTE|")
        self.assertTrue(wait_for(lambda: self.link.replies))
        self.assertEqual(self.link.replies, [(34, "ERROR", "KI")])

    def test_get_maker_raises_is_ki_error(self):
        # Wirft quote_maker (auch OSError beim Schreiben von .thema_zuletzt), bleibt GET nicht
        # offen: ERROR|KI. Danach startet das naechste GET einen neuen Thread.
        calls = []

        def failing(yesterday):
            calls.append(yesterday)
            if len(calls) == 1:
                raise OSError("Platte voll")
            return ("QUOTE", "WIEDER DA.")

        self.make(failing)
        with self.assertLogs("app.ui.link_dispatch", "ERROR"):
            self.put(35, "GET", "QUOTE|")
            self.assertTrue(wait_for(lambda: self.link.replies))
        self.assertEqual(self.link.replies, [(35, "ERROR", "KI")])
        self.put(36, "GET", "QUOTE|")
        self.assertTrue(wait_for(lambda: len(self.link.replies) == 2))
        self.assertEqual(self.link.replies[1], (36, "QUOTE", "WIEDER DA."))

    def test_worker_that_cannot_start_is_ki_error(self):
        maker = SlowQuote()
        maker.release()
        self.make(maker)  # der Dispatcher laeuft schon; nur der Arbeits-Thread scheitert
        with mock.patch.object(link_dispatch.threading, "Thread") as thread, \
                self.assertLogs("app.ui.link_dispatch", "ERROR"):
            thread.return_value.start.side_effect = RuntimeError("can't start new thread")
            self.put(38, "GET", "QUOTE|")
            self.assertTrue(wait_for(lambda: self.link.replies))
        self.assertEqual(self.link.replies, [(38, "ERROR", "KI")])
        self.put(39, "GET", "QUOTE|")  # kein GET gilt mehr als offen: ein neuer Thread
        self.assertTrue(wait_for(lambda: len(self.link.replies) == 2))
        self.assertEqual(self.link.replies[1], (39, "QUOTE", "DER WEG IST DAS ZIEL."))

    def test_bad_result_from_maker_is_ki_error(self):
        self.make(lambda yesterday: None)
        with self.assertLogs("app.ui.link_dispatch", "ERROR"):
            self.put(37, "GET", "QUOTE|")
            self.assertTrue(wait_for(lambda: self.link.replies))
        self.assertEqual(self.link.replies, [(37, "ERROR", "KI")])


class RealLinkGetTest(unittest.TestCase):
    """GET mit dem echten PiLink: Er nimmt nur eine Antwort auf die neueste Anfrage an. Jede
    Taste setzt den ESP zurueck; ein offenes GET verfaellt, und der ESP sendet es nach seiner
    eigenen Anfrage noch einmal, mit neuer Nummer."""

    def setUp(self):
        self.events = []
        self.port = RecordingPort(self.events)
        self.link = PiLink(self.port)
        self.link.start()
        self.addCleanup(self.link.stop)
        self.buttons = QueueButtons()
        self.maker = SlowQuote()
        self.addCleanup(self.maker.release)  # vor link.stop: der Arbeits-Thread endet
        self.d = LinkDispatcher(self.link, self.buttons, Activity(), StopSignal(),
                                threading.Event(), quote_maker=self.maker)
        self.d.start()
        self.addCleanup(self.d.stop)

    def feed(self, seq, command, data=""):
        self.port.feed(encode(Message(seq, command, data)) + b"\n")

    def feed_get_while_running(self, seq, data):
        """Ein GET, waehrend der Arbeits-Thread rechnet; kehrt zurueck, wenn der Dispatcher es
        als neuestes GET vermerkt hat."""
        with self.assertLogs("app.ui.link_dispatch", "INFO") as logs:
            self.feed(seq, "GET", data)
            self.assertTrue(wait_for(lambda: any("GET #%02X, waehrend" % seq in line
                                                 for line in logs.output)))

    def test_get_does_not_block_buttons(self):
        self.feed(0x20, "GET", "QUOTE|")
        self.assertTrue(self.maker.entered.wait(1.0))
        self.feed(0x21, "BUTTON", "3")  # Taste: Reset des ESP, das GET verfaellt
        self.assertEqual(self.buttons.get(1.0), 3)
        self.assertTrue(wait_for(lambda: ("tx", 0x21, "OK") in self.events))
        self.feed_get_while_running(0x22, "QUOTE|")
        self.assertNotIn("QUOTE", [e[2] for e in self.events if e[0] == "tx"])  # rechnet noch
        self.maker.release()
        self.assertTrue(wait_for(lambda: ("tx", 0x22, "QUOTE") in self.events))
        self.assertNotIn(("tx", 0x20, "QUOTE"), self.events)
        self.assertEqual(len(self.maker.calls), 1)

    def test_repeated_get_one_worker_answer_to_newest(self):
        # Review Focus 4: ein Reset des ESP, waehrend GET offen ist, sendet GET noch einmal mit
        # neuer Nummer (R8). Kein zweiter Thread; die Antwort geht an das neueste GET.
        self.feed(0x20, "GET", "QUOTE|GESTERN")
        self.assertTrue(self.maker.entered.wait(1.0))
        self.feed_get_while_running(0x21, "QUOTE|GESTERN")
        self.maker.release()
        self.assertTrue(wait_for(lambda: ("tx", 0x21, "QUOTE") in self.events))
        self.assertNotIn(("tx", 0x20, "QUOTE"), self.events)
        self.assertEqual(len(self.maker.calls), 1)

    def test_worker_done_before_the_resent_get_answers_from_its_result(self):
        # Fall C: BT2 in der Nacht. SESSION|HAND kommt, und der Arbeits-Thread wird fertig,
        # bevor das GET noch einmal kommt. Seine Antwort auf das alte GET nimmt PiLink nicht an;
        # das neue GET bekommt dasselbe Ergebnis, ohne zweite KI-Runde.
        self.feed(0x1F, "SESSION", "NACHT")
        self.assertTrue(wait_for(lambda: ("tx", 0x1F, "OK") in self.events))
        self.feed(0x20, "GET", "QUOTE|GESTERN")
        self.assertTrue(self.maker.entered.wait(1.0))
        self.feed(0x21, "SESSION", "HAND")
        self.assertTrue(self.d.hand_requested.wait(1.0))
        with self.assertLogs("app.ui.link_dispatch", "INFO") as logs:
            self.maker.release()
            self.assertTrue(wait_for(lambda: any("GET #20 nicht gesendet" in line
                                                 for line in logs.output)))
        self.feed(0x22, "GET", "QUOTE|GESTERN")
        self.assertTrue(wait_for(lambda: ("tx", 0x22, "QUOTE") in self.events))
        self.assertNotIn(("tx", 0x20, "QUOTE"), self.events)
        self.assertEqual(len(self.maker.calls), 1)


class RealLinkShutdownTest(unittest.TestCase):
    """Mit dem echten PiLink: Nummern und offene Anfragen wie auf der Leitung."""

    def setUp(self):
        self.events = []
        self.port = RecordingPort(self.events)
        self.link = PiLink(self.port)
        self.link.start()
        self.addCleanup(self.link.stop)
        self.stop, self.released, self.timers = StopSignal(), threading.Event(), FakeTimers()
        self.d = LinkDispatcher(self.link, QueueButtons(), Activity(), self.stop, self.released,
                                on_shutdown=lambda: self.events.append(("power_off",)),
                                release_wait_s=2.0, start_timer=self.timers)
        self.d.start()
        self.addCleanup(self.d.stop)

    def feed(self, seq, command):
        self.port.feed(encode(Message(seq, command, "")) + b"\n")

    def test_second_shutdown_while_the_first_waits_gets_ok_before_power_off(self):
        # Waehrend das erste SHUTDOWN auf die Anzeige wartet, kommt ein neues (Reset des ESP).
        # PiLink kennt nur noch die neue Nummer: das OK auf das erste geht nicht raus (mit
        # Log). Das neue bekommt sein OK, und erst danach laeuft on_shutdown, genau einmal.
        # Andersherum beendete systemd den Dienst, bevor dieses OK rausgeht.
        self.feed(0x20, "SHUTDOWN")
        self.assertTrue(wait_for(self.stop.is_set))
        self.feed(0x21, "SHUTDOWN")
        self.assertTrue(wait_for(lambda: self.port.unread() == 0))
        time.sleep(0.05)  # PiLink hat die Zeile gelesen und gemeldet
        with self.assertLogs("app.ui.link_dispatch", "INFO") as logs:
            self.released.set()
            self.assertTrue(wait_for(lambda: ("tx", 0x21, "OK") in self.events
                                     and self.d.shutdown_done.is_set()))
        self.assertNotIn(("tx", 0x20, "OK"), self.events)
        self.assertLess(self.events.index(("tx", 0x21, "OK")), self.events.index(("power_off",)))
        self.assertEqual(self.events.count(("power_off",)), 1)
        self.assertIn("#20", "\n".join(logs.output))
        for _, fire, _ in self.timers.started:  # der Rueckfall kommt danach und tut nichts
            fire()
        self.assertEqual(self.events.count(("power_off",)), 1)


class ReplacedShutdownFallbackTest(unittest.TestCase):
    """Das OK auf ein SHUTDOWN geht nicht raus, weil eine neuere Anfrage es ersetzt hat. Dann
    faehrt das neuere SHUTDOWN herunter. Kommt keins, faehrt der Pi nach der Frist trotzdem
    herunter."""

    def setUp(self):
        self.link = FakeLink()
        self.link.stale_seqs = {9}
        self.released = threading.Event()
        self.released.set()
        self.shutdowns = []
        self.timers = FakeTimers()
        self.d = LinkDispatcher(self.link, QueueButtons(), Activity(), StopSignal(), self.released,
                                on_shutdown=lambda: self.shutdowns.append(1),
                                start_timer=self.timers)
        self.d.start()
        self.addCleanup(self.d.stop)

    def handle(self, *messages):
        """Gibt die Anfragen dem Dispatcher und wartet, bis er alle bearbeitet hat: Er arbeitet
        der Reihe nach, das OK auf ein BUTTON am Schluss kommt also zuletzt."""
        for msg in messages:
            self.link.incoming.put(msg)
        self.link.incoming.put(Message(0x7F, "BUTTON", "1"))
        self.assertTrue(wait_for(lambda: (0x7F, "OK", "") in self.link.replies))

    def test_powers_off_after_the_fallback_time_without_a_newer_shutdown(self):
        self.handle(Message(9, "SHUTDOWN", ""))
        self.assertEqual(self.shutdowns, [])  # nicht sofort: ein neueres SHUTDOWN soll es tun
        self.assertFalse(self.d.shutdown_done.is_set())
        self.assertEqual(len(self.timers.started), 1)
        delay_s, fire, _ = self.timers.started[0]
        self.assertEqual(link_dispatch.REPLACED_SHUTDOWN_FALLBACK_S, 3.0)
        self.assertEqual(delay_s, link_dispatch.REPLACED_SHUTDOWN_FALLBACK_S)
        with self.assertLogs("app.ui.link_dispatch", "WARNING"):
            fire()  # die Frist ist um
        self.assertEqual(self.shutdowns, [1])
        self.assertTrue(self.d.shutdown_done.is_set())

    def test_newer_shutdown_powers_off_and_the_fallback_does_nothing(self):
        self.handle(Message(9, "SHUTDOWN", ""), Message(10, "SHUTDOWN", ""))
        self.assertEqual(self.link.replies[:2], [(9, "OK", ""), (10, "OK", "")])
        self.assertEqual(self.shutdowns, [1])
        self.assertTrue(self.d.shutdown_done.is_set())
        _, fire, _ = self.timers.started[0]
        with self.assertNoLogs("app.ui.link_dispatch", "WARNING"):
            fire()
        self.assertEqual(self.shutdowns, [1])

    def test_fallback_fires_only_once(self):
        self.link.stale_seqs = {9, 10}  # auch das zweite OK geht nicht raus
        self.handle(Message(9, "SHUTDOWN", ""), Message(10, "SHUTDOWN", ""))
        self.assertEqual(len(self.timers.started), 1)
        _, fire, _ = self.timers.started[0]
        with self.assertLogs("app.ui.link_dispatch", "WARNING"):
            fire()
        fire()
        self.assertEqual(self.shutdowns, [1])

    def test_fallback_does_nothing_after_stop(self):
        self.handle(Message(9, "SHUTDOWN", ""))
        _, fire, timer = self.timers.started[0]
        self.d.stop()
        self.assertTrue(timer.cancelled)
        fire()  # als haette der Zeitgeber trotz cancel() schon ausgeloest
        self.assertEqual(self.shutdowns, [])
        self.assertFalse(self.d.shutdown_done.is_set())

    def test_default_timer_powers_off_after_the_fallback_time(self):
        # Ohne eingespeisten Zeitgeber laeuft threading.Timer mit der Frist aus der Konstante
        self.d.stop()
        d = LinkDispatcher(self.link, QueueButtons(), Activity(), StopSignal(), self.released,
                           on_shutdown=lambda: self.shutdowns.append(1))
        d.start()
        self.addCleanup(d.stop)
        with mock.patch.object(link_dispatch, "REPLACED_SHUTDOWN_FALLBACK_S", 0.05), \
                self.assertLogs("app.ui.link_dispatch", "WARNING"):
            self.link.incoming.put(Message(9, "SHUTDOWN", ""))
            self.assertTrue(wait_for(lambda: self.shutdowns == [1]))
        self.assertTrue(d.shutdown_done.is_set())


class SendDoneTest(unittest.TestCase):
    def make(self, script):
        link = FakeLink()
        link.script = list(script)
        self.now = 0.0
        self.sleeps = []

        def sleep(s):
            self.sleeps.append(s)
            self.now += s
        d = LinkDispatcher(link, QueueButtons(), Activity(), StopSignal(), threading.Event(),
                           clock=lambda: self.now, sleep=sleep)
        return d, link

    def test_ok_first_try(self):
        d, link = self.make([Message(1, "OK", "")])
        self.assertTrue(d.send_done())
        self.assertEqual(link.requests, [("DONE", "")])

    def test_retries_when_busy(self):
        d, link = self.make(["busy", "busy", Message(1, "OK", "")])
        self.assertTrue(d.send_done())
        self.assertEqual(self.sleeps, [0.25, 0.25])

    def test_resends_after_10s_when_no_answer(self):
        d, link = self.make([None, Message(1, "OK", "")])
        self.assertTrue(d.send_done())
        self.assertEqual(self.sleeps, [10.0])
        self.assertEqual(len(link.requests), 2)

    def test_gives_up_after_timeout(self):
        d, link = self.make(["busy"] * 1000)
        self.assertFalse(d.send_done(timeout_s=1.0))
        self.assertLessEqual(len(link.requests), 5)

    def test_gives_up_when_never_answered(self):
        d, link = self.make([None] * 10)
        self.assertFalse(d.send_done(timeout_s=30.0))
        self.assertEqual(len(link.requests), 3)


if __name__ == "__main__":
    unittest.main()
