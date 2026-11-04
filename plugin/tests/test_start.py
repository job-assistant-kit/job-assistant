"""The getting-started section at the top of the tools page."""

import os
import re
import subprocess
import sys
import time
from datetime import date
from pathlib import Path

import pytest
import yaml

from ja import dashboard, start, workspace

JA = Path(__file__).parents[1] / "scripts" / "ja.py"
T = date(2026, 10, 29)
GOOD = {
    "reach": "I cannot read your systems directly. Export files and drop them in the inbox.",
    "recorded": ["Two tools you look after", "Six sources"],
    "gaps": ["Ask for maintainer access to the roadmap code"],
    "first": [{"name": "Inventory and ServiceNow cross-check", "does": "Shows only the mismatches.",
               "say": "automate this: the inventory and ServiceNow cross-check",
               "give": "a ServiceNow export and a copy of the inventory sheet"}],
}


def run(ws, *args):
    return subprocess.run([sys.executable, str(JA), "--workspace", str(ws), *args, "--today", "2026-10-29"],
                          capture_output=True, text=True)


@pytest.mark.parametrize("bad, words", [
    ([], "named parts"),
    ({**GOOD, "reach": ""}, "'reach'"),
    ({**GOOD, "first": []}, "one to five"),
    ({**GOOD, "first": [{"name": "x"}]}, "needs a name"),
    ({**GOOD, "gaps": "one gap"}, "'gaps'"),
])
def test_bad_content_is_refused_plainly(bad, words):
    with pytest.raises(start.StartProblem, match=words):
        start.check(bad)


def test_set_shows_it_open_then_hide_and_show(ws):
    p = workspace.Paths(ws)
    (ws / "inbox").mkdir(exist_ok=True)
    f = ws / "inbox" / "getting-started.yaml"
    f.write_text(yaml.safe_dump(GOOD), encoding="utf-8")
    r = run(ws, "start", "set", "--file", str(f))
    assert r.returncode == 0, r.stderr
    assert "file://" in r.stdout and not f.exists()
    html = (ws / "dashboard" / "index.html").read_text(encoding="utf-8")
    assert '<details class="start rise r3" open>' in html
    assert "automate this: the inventory and ServiceNow cross-check" in html
    assert "Only you can sort these out" in html
    assert run(ws, "start", "hide").returncode == 0
    html = (ws / "dashboard" / "index.html").read_text(encoding="utf-8")
    assert '<details class="start rise r3">' in html and "Getting started" in html
    assert run(ws, "start", "show").returncode == 0
    assert start.load(p)["hidden"] is False


def test_hide_without_content_is_plain(ws):
    r = run(ws, "start", "hide")
    assert r.returncode == 1 and "written at the end of setup" in r.stderr


def test_no_section_when_unreadable(ws):
    p = workspace.Paths(ws)
    start.path(p).write_text("reach: [", encoding="utf-8")
    assert "<details class=\"start" not in dashboard.render(p, T)


def test_page_has_its_fonts_and_reaches_nothing_outside(ws):
    p = workspace.Paths(ws)
    start.save(p, GOOD)
    out = dashboard.write(p, T)
    html = out.read_text(encoding="utf-8")
    for name in ("fraunces-latin-wght-normal.woff2", "fraunces-latin-wght-italic.woff2",
                 "instrument-sans-latin-wght-normal.woff2", "OFL-Fraunces.txt", "OFL-InstrumentSans.txt"):
        assert (out.parent / "fonts" / name).is_file(), name
    assert not re.search(r"(src|href)=\"?https?:", html)
    assert "url(\"http" not in html and "<script" not in html


def _fake_opener(tmp_path):
    """A stand-in for the system's browser opener that notes the page it was asked to open."""
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    seen = tmp_path / "opened.txt"
    for name in ("xdg-open", "open"):
        f = bin_dir / name
        f.write_text(f'#!/bin/sh\nprintf "%s" "$1" > "{seen}"\n', encoding="utf-8")
        f.chmod(0o755)
    return bin_dir, seen


def _set_with_open(ws, path_value):
    (ws / "inbox").mkdir(exist_ok=True)
    f = ws / "inbox" / "getting-started.yaml"
    f.write_text(yaml.safe_dump(GOOD), encoding="utf-8")
    env = {**os.environ, "PATH": path_value}
    return subprocess.run([sys.executable, str(JA), "--workspace", str(ws), "start", "set", "--file", str(f),
                           "--open", "--today", "2026-10-29"], capture_output=True, text=True, env=env)


def test_set_with_open_opens_the_tools_page(ws, tmp_path):
    bin_dir, seen = _fake_opener(tmp_path)
    r = _set_with_open(ws, str(bin_dir) + os.pathsep + os.environ.get("PATH", ""))
    assert r.returncode == 0, r.stderr
    assert "file://" in r.stdout and "opened" in r.stdout
    deadline = time.monotonic() + 5
    while not seen.exists() and time.monotonic() < deadline:
        time.sleep(0.05)
    assert seen.read_text(encoding="utf-8") == str(ws / "dashboard" / "index.html")


def test_set_with_open_and_no_browser_says_where_the_page_is(ws, tmp_path):
    empty = tmp_path / "empty"
    empty.mkdir()
    r = _set_with_open(ws, str(empty))
    assert r.returncode == 0, r.stderr
    assert "file://" in r.stdout and "could not open a browser" in r.stdout
    assert "dashboard/index.html" in r.stdout
