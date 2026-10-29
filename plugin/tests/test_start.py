"""The getting-started section at the top of the tools page."""

import re
import subprocess
import sys
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
