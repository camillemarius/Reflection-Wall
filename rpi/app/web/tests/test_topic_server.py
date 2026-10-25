import tempfile
import unittest
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from unittest import mock

from app import topics
from app.web import topic_server
from app.web.topic_server import TopicServer, wall_address


class TopicServerTest(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.dir = Path(self._tmp.name)
        self.saved = 0
        self.server = TopicServer(self.dir, port=0, host="127.0.0.1",
                                  on_save=self._on_save)
        self.server.start()
        self.url = "http://127.0.0.1:%d/" % self.server.port

    def tearDown(self):
        self.server.stop()
        self._tmp.cleanup()

    def _on_save(self):
        self.saved += 1

    def _post(self, daily, hand, raw=None):
        data = raw if raw is not None else urllib.parse.urlencode(
            {"daily": daily, "hand": hand}).encode("utf-8")
        request = urllib.request.Request(self.url, data=data, method="POST")
        with urllib.request.urlopen(request, timeout=5) as response:
            return response.read().decode("utf-8")

    def _get(self):
        with urllib.request.urlopen(self.url, timeout=5) as response:
            return response.read().decode("utf-8")

    def test_get_shows_topics(self):
        topics.save(self.dir, "Mut", "Freundschaft")
        page = self._get()
        self.assertIn("Mut", page)
        self.assertIn("Freundschaft", page)
        self.assertIn("Ein neues Thema beginnt ab der nächsten Nacht eine neue Kette.", page)
        self.assertIn("Speichern", page)

    def test_get_escapes_html(self):
        topics.save(self.dir, '<b>"x"</b>', "h")
        self.assertNotIn("<b>", self._get())

    def test_save_normalizes(self):
        page = self._post("Zeile1\nZeile2", "x" * 300)
        self.assertIn("Gespeichert.", page)
        daily = (self.dir / topics.DAILY_FILE).read_text(encoding="utf-8")
        hand = (self.dir / topics.HAND_FILE).read_text(encoding="utf-8")
        self.assertEqual(daily.strip(), "Zeile1 Zeile2")
        self.assertEqual(len(daily.strip().splitlines()), 1)
        self.assertLessEqual(len(hand.strip()), 120)

    def test_umlauts_round_trip(self):
        self._post("Wärme und Größe", "Übermut")
        self.assertEqual(topics.read_daily(self.dir), "Wärme und Größe")
        page = self._get()
        self.assertIn("Wärme und Größe", page)
        self.assertIn("Übermut", page)

    def test_save_touches_activity(self):
        self._post("a", "b")
        self.assertEqual(self.saved, 1)

    def test_oversized_body_is_rejected(self):
        with self.assertRaises(urllib.error.HTTPError) as caught:
            self._post("", "", raw=b"daily=" + b"a" * 5000)
        self.assertEqual(caught.exception.code, 413)
        caught.exception.close()
        self.assertEqual(self.saved, 0)

    def test_unknown_path_is_404(self):
        with self.assertRaises(urllib.error.HTTPError) as caught:
            urllib.request.urlopen(self.url + "x", timeout=5)
        self.assertEqual(caught.exception.code, 404)
        caught.exception.close()

    def test_stop_is_repeatable(self):
        self.server.stop()
        self.server.stop()


class WallAddressTest(unittest.TestCase):
    def test_hostname_without_domain_plus_local(self):
        with mock.patch.object(topic_server.socket, "gethostname", return_value="wall.fritz.box"):
            self.assertEqual(wall_address()[0], "wall.local")

    def test_ip_from_udp_socket(self):
        fake = mock.MagicMock()
        fake.getsockname.return_value = ("192.168.1.50", 5555)
        with mock.patch.object(topic_server.socket, "socket", return_value=fake):
            self.assertEqual(wall_address()[1], "192.168.1.50")
        fake.send.assert_not_called()
        fake.sendto.assert_not_called()

    def test_no_network(self):
        with mock.patch.object(topic_server.socket, "socket", side_effect=OSError):
            self.assertEqual(wall_address()[1], "KEIN NETZ")


if __name__ == "__main__":
    unittest.main()
