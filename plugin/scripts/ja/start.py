"""The getting-started section of the tools page.

Setup writes what the person needs to know on day one: what the assistant can and cannot
reach, what it recorded, what only they can sort out, and the first things to automate.
The tools page shows it at the top, open until they say "hide getting started". The
heading stays on the page, so one click opens it again.
"""

from __future__ import annotations

import os
from typing import Any

import yaml

from ja.workspace import Paths


class StartProblem(ValueError):
    """The getting-started content cannot be used. The message is plain."""


FIRST_FIELDS = ("name", "does", "say", "give")


def path(paths: Paths) -> Any:
    return paths.assistant_dir / "getting-started.yaml"


def _text(value: Any) -> bool:
    return isinstance(value, str) and bool(value.strip())


def _text_list(data: dict[str, Any], key: str) -> list[str]:
    value = data.get(key) or []
    if not isinstance(value, list) or not all(_text(v) for v in value):
        raise StartProblem(f"'{key}' must be a list of short sentences.")
    return [v.strip() for v in value]


def check(data: Any) -> dict[str, Any]:
    """Return the cleaned content, or raise StartProblem with a plain message."""
    if not isinstance(data, dict):
        raise StartProblem("The getting-started file must hold named parts: reach, recorded, gaps, first.")
    if not _text(data.get("reach")):
        raise StartProblem("'reach' must say in a sentence or two what I can and cannot reach.")
    first = data.get("first")
    if not isinstance(first, list) or not 1 <= len(first) <= 5:
        raise StartProblem("'first' must list one to five first automations.")
    for item in first:
        if not isinstance(item, dict) or not all(_text(item.get(k)) for k in FIRST_FIELDS):
            raise StartProblem("Each first automation needs a name, what it does, what to say, and what to give.")
    return {
        "reach": data["reach"].strip(),
        "recorded": _text_list(data, "recorded"),
        "gaps": _text_list(data, "gaps"),
        "first": [{k: item[k].strip() for k in FIRST_FIELDS} for item in first],
        "hidden": bool(data.get("hidden", False)),
    }


def load(paths: Paths) -> dict[str, Any] | None:
    """The saved content, or None when there is none or it cannot be read."""
    f = path(paths)
    if not f.is_file():
        return None
    try:
        return check(yaml.safe_load(f.read_text(encoding="utf-8")))
    except (OSError, UnicodeDecodeError, yaml.YAMLError, StartProblem):
        return None


def _save(paths: Paths, data: dict[str, Any]) -> None:
    f = path(paths)
    f.parent.mkdir(parents=True, exist_ok=True)
    tmp = f.with_suffix(".yaml.tmp")
    tmp.write_text(yaml.safe_dump(data, sort_keys=False, allow_unicode=True), encoding="utf-8")
    os.replace(tmp, f)


def save(paths: Paths, raw: Any) -> dict[str, Any]:
    data = check(raw)
    data["hidden"] = False
    _save(paths, data)
    return data


def set_hidden(paths: Paths, hidden: bool) -> None:
    data = load(paths)
    if data is None:
        raise StartProblem("There is no getting-started section yet. It is written at the end of setup.")
    data["hidden"] = hidden
    _save(paths, data)
