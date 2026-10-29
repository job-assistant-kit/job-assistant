# /// script
# requires-python = ">=3.11"
# dependencies = []
# ///
"""Test facts step: match the synthetic export to the synthetic inventory by offering name."""

import csv
import json
import sys


def rows(path):
    with open(path, newline="", encoding="utf-8-sig") as fh:
        return list(csv.DictReader(fh))


def key(name):
    return " ".join(name.split()).lower()


export, inventory = rows(sys.argv[1]), rows(sys.argv[2])
known = {key(r["Offering"]) for r in inventory}
unmatched = sorted({r["Offering"] for r in export if key(r["Offering"]) not in known})
blank = sum(1 for r in export if not r["Governance Completed"].strip())
facts = [
    {"id": "export-rows", "label": "Rows in the export", "value": len(export), "unit": "rows",
     "source": "servicenow-export.csv", "notes": ""},
    {"id": "unmatched", "label": "Offerings not in the inventory", "value": len(unmatched), "unit": "offerings",
     "source": "servicenow-export.csv and inventory.csv", "notes": "; ".join(unmatched)},
    {"id": "blank-governance", "label": "Rows with no governance date", "value": blank, "unit": "rows",
     "source": "servicenow-export.csv", "notes": ""},
]
print(json.dumps({"facts": facts, "counts": {"blank_governance": blank}, "problems": []}))
