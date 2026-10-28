"""The synthetic samples have the shape the tests and acceptance runs rely on."""

import csv
import json
import re
from pathlib import Path

SYN = Path(__file__).parent / "fixtures" / "synthetic"


def rows(name):
    with open(SYN / name, newline="", encoding="utf-8") as fh:
        return list(csv.DictReader(fh))


def test_readme_says_synthetic():
    assert (SYN / "README.md").read_text(encoding="utf-8").startswith("Synthetic data for tests. Not real.")


def test_export_shape():
    export = rows("servicenow-export.csv")
    assert list(export[0]) == ["Number", "Offering", "Stage", "Opened", "Governance Completed"]
    assert len(export) == 40
    assert sum(1 for r in export if not r["Governance Completed"].strip()) == 6


def test_inventory_shape_and_matching():
    inventory = rows("inventory.csv")
    assert list(inventory[0]) == ["Offering", "Owner", "Awareness Date", "Target GA"]
    assert len(inventory) == 42
    assert sum(1 for r in inventory if not r["Awareness Date"].strip()) == 5
    exact = {r["Offering"] for r in inventory}
    loose = {r["Offering"].strip().lower() for r in inventory}
    names = [r["Offering"] for r in rows("servicenow-export.csv")]
    near = [n for n in names if n not in exact and n.strip().lower() in loose]
    missing = [n for n in names if n.strip().lower() not in loose]
    assert len(near) == 3 and any(n != n.strip() for n in near)
    assert len(missing) == 2


def test_metrics():
    data = json.loads((SYN / "metrics-latest.json").read_text(encoding="utf-8"))
    assert len(data["quarters"]) == 2
    for q in data["quarters"].values():
        assert sorted(q) == [f"BR-{n}" for n in range(1, 7)]
    assert {"median_days", "count", "excluded_count"} <= set(data["ttm"])


def test_text_samples():
    brief = (SYN / "brief-incomplete.md").read_text(encoding="utf-8")
    sections = re.split(r"^## ", brief, flags=re.M)[1:]
    empty = [s.splitlines()[0] for s in sections if not "\n".join(s.splitlines()[1:]).strip()]
    assert len(empty) == 2 and "TBD per finance" in brief
    faq = (SYN / "faq.md").read_text(encoding="utf-8")
    assert len(re.findall(r"^## \d+\. .+\?$", faq, flags=re.M)) == 12
    questions = re.findall(r"^\d+\. ", (SYN / "slack-questions.txt").read_text(encoding="utf-8"), flags=re.M)
    assert len(questions) == 6
