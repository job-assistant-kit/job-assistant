"""The facts runner blocks outside actions however the code reaches them.

Each case is a real attempt run under the runner. The bypasses come from a review of the
earlier import check, which only looked at the source text.
"""

from __future__ import annotations

import subprocess
import sys
import textwrap
from pathlib import Path

import pytest

RUNNER = Path(__file__).parents[1] / "scripts" / "ja" / "runner.py"
OK = 'import json; print(json.dumps({"facts": [], "counts": {}, "problems": []}))\n'


def run_step(ws: Path, body: str, *files: Path) -> subprocess.CompletedProcess:
    script = ws / "facts.py"
    script.write_text(textwrap.dedent(body), encoding="utf-8")
    return subprocess.run([sys.executable, str(RUNNER), str(ws), str(script), *map(str, files)],
                          capture_output=True, text=True, timeout=60, cwd=ws)


@pytest.fixture
def ws(tmp_path: Path) -> Path:
    root = tmp_path / "ws"
    (root / "inbox").mkdir(parents=True)
    (root / ".claude").mkdir()
    (root / ".claude" / "settings.json").write_text('{"permissions": {"deny": ["x"]}}', encoding="utf-8")
    return root


def blocked(r: subprocess.CompletedProcess, what: str) -> bool:
    return r.returncode == 3 and f"JA-BLOCKED: {what}" in r.stderr


def test_normal_step_runs(ws: Path) -> None:
    data = ws / "inbox" / "a.csv"
    data.write_text("Offering,Stage\nA,Intake\nB,Review\n", encoding="utf-8")
    r = run_step(ws, """
        import csv, json, sys
        rows = list(csv.DictReader(open(sys.argv[1], newline="")))
        print(json.dumps({"facts": [{"id": "rows", "label": "Rows", "value": len(rows)}], "counts": {}, "problems": []}))
    """, data)
    assert r.returncode == 0, r.stderr
    assert '"value": 2' in r.stdout


def test_input_outside_the_folder_is_allowed_when_given(ws: Path, tmp_path: Path) -> None:
    data = tmp_path / "export.csv"
    data.write_text("A\n1\n", encoding="utf-8")
    r = run_step(ws, "import sys; open(sys.argv[1]).read()\n" + OK, data)
    assert r.returncode == 0, r.stderr


@pytest.mark.parametrize("body", [
    "import asyncio\nasync def m():\n    await asyncio.open_connection('127.0.0.1', 9)\nasyncio.run(m())\n",
    "import asyncio\nasync def m():\n    await asyncio.start_server(lambda r, w: None, '127.0.0.1', 0)\nasyncio.run(m())\n",
    "import socket\nsocket.create_connection(('127.0.0.1', 9))\n",
    "s = __import__('so' + 'cket')\ns.socket().connect(('127.0.0.1', 9))\n",
    "import urllib.request\nurllib.request.urlopen('http://127.0.0.1:9/')\n",
])
def test_network_is_blocked(ws: Path, body: str) -> None:
    assert blocked(run_step(ws, body), "reach another system")


# The samples below are deliberate attempts to get around the runner; they are run only
# under it, as test input.
@pytest.mark.parametrize("body", [
    "import os as o\no.system('id -un')\n",
    "from os import *\nsystem('id -un')\n",
    "import sys\nsys.modules['os'].system('id -un')\n",
    "import posix\nposix.system('id -un')\n",
    "import importlib\nname = 'sub' + 'process'\nimportlib.import_module(name).run(['id', '-un'])\n",
    "eval(\"__import__('os').popen('id -un').read()\")\n",
    "exec(\"import subprocess; subprocess.run(['id'])\")\n",
    "import os\nos.execv('/bin/true', ['true'])\n",
])
def test_running_programs_is_blocked(ws: Path, body: str) -> None:
    assert blocked(run_step(ws, body), "run a program")


@pytest.mark.parametrize("body", [
    "import pathlib\npathlib.Path('.claude/settings.json').write_text('{}')\n",
    "open('inbox/new.txt', 'w').write('x')\n",
    "import os\nfd = os.open('inbox/new.txt', os.O_WRONLY | os.O_CREAT)\n",
    "import os\nos.remove('.claude/settings.json')\n",
    "import shutil\nshutil.rmtree('inbox')\n",
    "import os\nos.rename('inbox', 'gone')\n",
])
def test_changing_files_is_blocked(ws: Path, body: str) -> None:
    r = run_step(ws, body)
    assert blocked(r, "change a file")
    assert (ws / ".claude" / "settings.json").read_text(encoding="utf-8") == '{"permissions": {"deny": ["x"]}}'
    assert not (ws / "inbox" / "new.txt").exists() and (ws / "inbox").is_dir()


def test_reading_outside_the_folder_is_blocked(ws: Path, tmp_path: Path) -> None:
    secret = tmp_path / "secret.txt"
    secret.write_text("private", encoding="utf-8")
    r = run_step(ws, f"print(open({str(secret)!r}).read())\n")
    assert blocked(r, "read a file outside the assistant folder")
    assert "private" not in r.stdout


def test_native_code_is_blocked(ws: Path) -> None:
    assert blocked(run_step(ws, "import ctypes\nctypes.CDLL(None).system(b'id')\n"),
                   "load code from outside Python")


def test_asyncio_programs_are_blocked(ws: Path) -> None:
    # asyncio opens an internal socket pair before it can start a program, so the run
    # is stopped at that first step.
    body = "import asyncio\nasync def m():\n    await asyncio.create_subprocess_exec('id')\nasyncio.run(m())\n"
    r = run_step(ws, body)
    assert r.returncode == 3 and "JA-BLOCKED: " in r.stderr


def test_a_second_hook_is_refused(ws: Path) -> None:
    assert blocked(run_step(ws, "import sys\nsys.addaudithook(lambda e, a: None)\n"), "turn off its safety checks")


def test_swallowed_refusal_still_fails_the_run(ws: Path) -> None:
    body = "import socket\ntry:\n    socket.create_connection(('127.0.0.1', 9))\nexcept Exception:\n    pass\n" + OK
    r = run_step(ws, body)
    assert blocked(r, "reach another system")


def test_part_changed_after_adding_is_still_blocked(ws: Path) -> None:
    part = ws / "parts" / "norm"
    part.mkdir(parents=True)
    (part / "part.py").write_text("import os\nos.system('id -un')\n", encoding="utf-8")
    body = """
        import importlib.util
        spec = importlib.util.spec_from_file_location("norm", "parts/norm/part.py")
        m = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(m)
    """
    assert blocked(run_step(ws, body), "run a program")
