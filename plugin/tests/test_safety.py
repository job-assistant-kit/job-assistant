"""Facts steps and code parts may not reach other systems or run programs."""

import pytest

from ja import safety

OK = """
import csv, json, sys
from pathlib import Path
import os.path
print(json.dumps({"facts": [], "counts": {}, "problems": []}))
os.path.exists("x")
"""


@pytest.mark.parametrize("code", [
    "import socket",
    "import http.client",
    "from urllib.request import urlopen",
    "import requests",
    "import httpx as h",
    "import smtplib",
    "from ftplib import FTP",
    "import subprocess",
    "import os\nos.system('ls')",
    "import os\nos.popen('ls')",
    "from os import system",
    "import os\nos.execv('/bin/ls', [])",
    "__import__('socket')",
    "import importlib\nimportlib.import_module('subprocess')",
    "import os\ngetattr(os, 'system')('ls')",
])
def test_refused(tmp_path, code):
    f = tmp_path / "facts.py"
    f.write_text(code, encoding="utf-8")
    assert safety.problem(f) == safety.REFUSED


def test_allowed(tmp_path):
    f = tmp_path / "facts.py"
    f.write_text(OK, encoding="utf-8")
    assert safety.problem(f) is None


def test_unreadable_code(tmp_path):
    f = tmp_path / "facts.py"
    f.write_text("def broken(:\n", encoding="utf-8")
    assert "line 1" in safety.problem(f)
