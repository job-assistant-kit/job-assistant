"""Fill page templates safely: one pass, one line per value, quoted frontmatter."""

from __future__ import annotations

import re
from typing import Any, Mapping

import yaml

PLACEHOLDER = re.compile(r"\{\{(\w+)\}\}")


def one_line(value: Any) -> str:
    return " ".join(str(value).split())


def no_comments(text: str) -> str:
    """Remove HTML comment delimiters so text cannot open or close a marked block."""
    return text.replace("<!--", "").replace("-->", "")


def yaml_scalar(value: Any) -> str:
    """A double-quoted YAML scalar on one line."""
    return yaml.safe_dump(one_line(value), default_style='"', width=10**9, allow_unicode=True).strip()


def yaml_list(values: list[str]) -> str:
    """A YAML flow list of double-quoted items on one line."""
    return "[" + ", ".join(yaml_scalar(v) for v in values) + "]"


def fill(template: str, values: Mapping[str, str]) -> str:
    """Replace each {{key}} once. Text inside the values is never expanded again."""
    def swap(match: re.Match[str]) -> str:
        key = match.group(1)
        if key not in values:
            raise KeyError(f"the template needs a value for {key}")
        return values[key]

    return PLACEHOLDER.sub(swap, template)
