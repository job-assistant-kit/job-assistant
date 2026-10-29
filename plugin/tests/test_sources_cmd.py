"""Adding and updating sources."""

import json
from datetime import date

import pytest
import yaml

from ja import sources, workspace

T = date(2026, 10, 28)


def entry(**k):
    base = dict(id="faq", name="OLM FAQ", kind="living", where="Shared drive", access="file")
    base.update(k)
    return base


def test_add_and_sorted(ws):
    p = workspace.Paths(ws)
    sources.add(p, entry(id="zeta", name="Zeta"), today=T)
    sources.add(p, entry(id="alpha", name="Alpha", exported="2026-10-20", fresh_days=14), today=T)
    raw = yaml.safe_load(p.sources.read_text(encoding="utf-8"))
    assert isinstance(raw, list) and [e["id"] for e in raw] == ["alpha", "zeta"]
    by_id, problems = sources.load(p)
    assert problems == [] and by_id["alpha"].fresh_days == 14 and by_id["alpha"].exported == "2026-10-20"


def test_add_refuses_duplicate_and_bad_values(ws):
    p = workspace.Paths(ws)
    sources.add(p, entry(), today=T)
    with pytest.raises(sources.SourceProblem) as err:
        sources.add(p, entry(), today=T)
    assert str(err.value) == "There is already a source called faq."
    for bad in (entry(id="Bad Id"), entry(id="x", kind="soft"), entry(id="y", exported="soon"),
                entry(id="z", exported="2026-11-30"), entry(id="w", name=" ")):
        with pytest.raises(sources.SourceProblem):
            sources.add(p, bad, today=T)
    assert [e["id"] for e in yaml.safe_load(p.sources.read_text(encoding="utf-8"))] == ["faq"]


def test_add_keeps_entries_it_cannot_read(ws):
    p = workspace.Paths(ws)
    p.sources.write_text("- id: odd\n  name: Odd\n  kind: soft\n  where: x\n  access: file\n  note: keep\n",
                         encoding="utf-8")
    sources.add(p, entry(), today=T)
    raw = yaml.safe_load(p.sources.read_text(encoding="utf-8"))
    assert [e["id"] for e in raw] == ["faq", "odd"] and raw[1]["note"] == "keep"


def test_exported_updates_date(ws):
    p = workspace.Paths(ws)
    sources.add(p, entry(exported="2026-10-01"), today=T)
    sources.set_exported(p, "faq", "2026-10-27", today=T)
    assert sources.load(p)[0]["faq"].exported == "2026-10-27"
    with pytest.raises(sources.SourceProblem):
        sources.set_exported(p, "nope", "2026-10-27", today=T)
    with pytest.raises(sources.SourceProblem):
        sources.set_exported(p, "faq", "2026-12-01", today=T)
    with pytest.raises(sources.SourceProblem):
        sources.set_exported(p, "faq", "27 Oct", today=T)


def test_describe(ws):
    p = workspace.Paths(ws)
    sources.add(p, entry(exported="2026-10-20"), today=T)
    sources.add(p, entry(id="drive-plan", name="Plan", access="connector"), today=T)
    sources.add(p, entry(id="old", name="Old export"), today=T)
    rows = {r["id"]: r for r in sources.describe(p, T)}
    assert rows["faq"]["age"] == "Copy from Oct 20, 8 days old, past its 7-day limit"
    assert rows["drive-plan"]["age"] == "live" and rows["drive-plan"]["reached"] == "read live through a connector"
    assert rows["old"]["age"] == "No export date yet"
    assert rows["faq"]["reached"] == "a copy you drop in"


def test_sources_list_names_confidential_tools(ws, write_tool):
    import json, subprocess, sys
    from pathlib import Path
    ja = Path(__file__).parents[1] / "scripts" / "ja.py"
    run = lambda *a: subprocess.run([sys.executable, str(ja), "--workspace", str(ws), *a, "--today", "2026-10-28"],
                                    capture_output=True, text=True)
    assert run("sources", "add", "--id", "inv", "--name", "Inventory", "--kind", "living", "--where", "Drive",
               "--access", "file", "--exported", "2026-10-27").returncode == 0
    write_tool(ws, id="brief", name="Brief", confidential=True, sources=["inv"])
    write_tool(ws, id="faq", name="FAQ", confidential=False, sources=["inv"])
    rows = json.loads(run("sources", "list", "--json").stdout)
    assert rows[0]["confidential_tools"] == ["brief"]
