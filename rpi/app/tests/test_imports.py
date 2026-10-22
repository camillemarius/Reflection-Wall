import os
import re
import subprocess
import sys
import unittest
from pathlib import Path

RPI = Path(__file__).resolve().parents[2]

CHILD = r"""
import importlib, pkgutil, sys
from unittest import mock

import app

with mock.patch("mysql.connector.connect", side_effect=AssertionError("DB beim Import")), \
     mock.patch("groq.Groq", side_effect=AssertionError("Groq beim Import")):
    for info in pkgutil.walk_packages(app.__path__, "app."):
        if ".tests" in info.name:
            continue
        importlib.import_module(info.name)

assert "smbus2" not in sys.modules, "smbus2 beim Import geladen"
assert "lgpio" not in sys.modules, "lgpio beim Import geladen"
"""

BAD_IMPORT = re.compile(r"^\s*(from rpi\.|import rpi\.|from driver\.|from applications\.|from \.)")


class ImportTest(unittest.TestCase):
    def test_every_module_imports_without_hardware_or_network(self):
        env = {k: v for k, v in os.environ.items() if k != "GROQ_API_KEY"}
        result = subprocess.run(
            [sys.executable, "-c", CHILD],
            cwd=RPI, env=env, capture_output=True, text=True, timeout=120,
        )
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_imports_use_the_app_package(self):
        bad = []
        for path in (RPI / "app").rglob("*.py"):
            for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
                if BAD_IMPORT.match(line):
                    bad.append(f"{path.relative_to(RPI)}:{number}: {line.strip()}")
        self.assertEqual(bad, [], "\n".join(bad))
