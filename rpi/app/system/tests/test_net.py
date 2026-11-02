# system/tests/test_net.py
import unittest

from app.system.net import wait_for_host


class FakeClock:
    def __init__(self):
        self.now = 0.0

    def __call__(self):
        return self.now

    def sleep(self, seconds):
        self.now += seconds


class FakeSocket:
    def __init__(self):
        self.closed = False

    def close(self):
        self.closed = True


class FakeConnect:
    """Scheitert die ersten failures Male mit OSError, danach gelingt die Verbindung."""

    def __init__(self, failures):
        self.failures = failures
        self.calls = []
        self.sockets = []

    def __call__(self, address, timeout):
        self.calls.append((address, timeout))
        if len(self.calls) <= self.failures:
            raise OSError("Network is unreachable")
        sock = FakeSocket()
        self.sockets.append(sock)
        return sock


class WaitForHostTest(unittest.TestCase):
    def wait(self, connect, clock, timeout_s=45):
        return wait_for_host("api.groq.com", 443, timeout_s, connect=connect,
                             clock=clock, sleep=clock.sleep)

    def test_true_at_once_when_the_host_answers(self):
        clock, connect = FakeClock(), FakeConnect(failures=0)
        self.assertTrue(self.wait(connect, clock))
        self.assertEqual([address for address, _ in connect.calls], [("api.groq.com", 443)])
        self.assertEqual(clock.now, 0.0)

    def test_closes_the_probe_connection(self):
        clock, connect = FakeClock(), FakeConnect(failures=0)
        self.wait(connect, clock)
        self.assertTrue(connect.sockets[0].closed)

    def test_tries_again_until_the_host_answers(self):
        # Abnahme 2026-11-02: das Netz kam erst rund 50 s nach dem Start des Pi
        clock, connect = FakeClock(), FakeConnect(failures=3)
        self.assertTrue(self.wait(connect, clock))
        self.assertEqual(len(connect.calls), 4)
        self.assertLess(clock.now, 45)

    def test_false_once_the_time_is_up(self):
        clock, connect = FakeClock(), FakeConnect(failures=10 ** 6)
        self.assertFalse(self.wait(connect, clock))
        self.assertEqual(clock.now, 45)
        self.assertGreater(len(connect.calls), 1)

    def test_no_try_waits_longer_than_the_time_left(self):
        clock, connect = FakeClock(), FakeConnect(failures=10 ** 6)
        self.wait(connect, clock, timeout_s=1)
        self.assertTrue(all(0 < timeout <= 1 for _, timeout in connect.calls))


if __name__ == "__main__":
    unittest.main()
