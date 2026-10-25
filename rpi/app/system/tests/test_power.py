# system/tests/test_power.py
import unittest
from types import SimpleNamespace

from app.system.power import power_off


class FakeRunner:
    def __init__(self, returncode=0, exc=None):
        self.returncode = returncode
        self.exc = exc
        self.calls = []

    def __call__(self, args, **kwargs):
        self.calls.append((args, kwargs))
        if self.exc is not None:
            raise self.exc
        return SimpleNamespace(returncode=self.returncode)


class PowerOffTest(unittest.TestCase):
    def test_power_off_runs_systemctl_poweroff(self):
        runner = FakeRunner(returncode=0)
        self.assertTrue(power_off(runner=runner))
        self.assertEqual(len(runner.calls), 1)
        args, kwargs = runner.calls[0]
        self.assertEqual(args, ["sudo", "-n", "/usr/bin/systemctl", "poweroff"])
        self.assertEqual(kwargs, {"check": False})

    def test_power_off_logs_nonzero_return(self):
        runner = FakeRunner(returncode=1)
        with self.assertLogs("app.system.power", level="ERROR"):
            self.assertFalse(power_off(runner=runner))

    def test_power_off_logs_missing_sudo(self):
        runner = FakeRunner(exc=FileNotFoundError("sudo"))
        with self.assertLogs("app.system.power", level="ERROR"):
            self.assertFalse(power_off(runner=runner))
