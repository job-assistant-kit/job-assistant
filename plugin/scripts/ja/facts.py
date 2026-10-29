"""Run a tool's facts step and check what it prints.

The facts step is the part of a tool that counts, matches, and computes, so that numbers
come from code and never from the written result. It runs as its own small program on
the files it is given, with a time limit, and must print one object in the agreed shape.
"""

from __future__ import annotations

import hashlib
import json
import math
import os
import shutil
import signal
import subprocess
import sys
from dataclasses import dataclass, field
from datetime import date, datetime
from pathlib import Path
from typing import Any

from ja import inputs, safety
from ja.workspace import Paths

TIMEOUT_SECONDS = 120
SCRIPT_NAME = "facts.py"
NO_STEP = "This tool has no facts step."


class FactsProblem(Exception):
    """The facts step could not run or gave results that cannot be used. The message is plain."""


@dataclass
class Result:
    data: dict[str, Any]
    # (input name, file) in the order of the tool's input list; empty when it names no inputs
    assigned: list[tuple[str, Path]] = field(default_factory=list)

    @property
    def facts(self) -> list[dict[str, Any]]:
        return self.data["facts"]


def script_for(paths: Paths, tool_id: str) -> Path:
    return paths.skills_dir / tool_id / SCRIPT_NAME


def has_step(paths: Paths, tool_id: str) -> bool:
    return script_for(paths, tool_id).is_file()


RUNNER = Path(__file__).with_name("runner.py")
BLOCKED_EXIT = 3
BLOCKED_MARKER = "JA-BLOCKED: "


def _arguments(script: Path, files: list[Path], named) -> tuple[list[str], list[tuple[str, Path]]]:
    """The step's arguments: each input as --input "<name>=<path>" when the tool lists its inputs."""
    try:
        spec = inputs.load_spec(script.parent)
    except inputs.SpecProblem as exc:
        raise FactsProblem(str(exc)) from None
    if spec is None:
        if named:
            raise FactsProblem("This tool does not name its inputs, so give the files without names.")
        return [str(f) for f in files], []
    try:
        assigned = inputs.assign(spec, list(files), named=list(named))
    except inputs.MatchProblem as exc:
        raise FactsProblem(str(exc)) from None
    args = [part for name, path in assigned for part in ("--input", f"{name}={path}")]
    return args, assigned


def _command(root: Path, script: Path, args: list[str]) -> list[str]:
    """Run the step under the runner, with only the approved libraries available."""
    uv = shutil.which("uv")
    with_libs = [arg for lib in safety.ALLOWED_LIBRARIES for arg in ("--with", lib)]
    head = [uv, "run", "--quiet", "--no-project", *with_libs, "python"] if uv else [sys.executable]
    return [*head, str(RUNNER), str(root), str(script), *args]


def _stop_group(proc: subprocess.Popen) -> None:
    try:
        os.killpg(proc.pid, signal.SIGKILL)
    except (ProcessLookupError, PermissionError):
        pass
    try:
        proc.wait(timeout=10)
    except subprocess.TimeoutExpired:
        pass


def _last_line(text: str) -> str:
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    return lines[-1] if lines else "it stopped without saying why"


def _is_value(v: Any) -> bool:
    if isinstance(v, bool) or v is None or isinstance(v, str):
        return True
    return isinstance(v, (int, float)) and math.isfinite(v)


def validate(data: Any) -> dict[str, Any]:
    """The facts step's output in the agreed shape, with defaults filled. Raises ValueError."""
    if not isinstance(data, dict) or not isinstance(data.get("facts"), list):
        raise ValueError("there is no list of facts")
    seen: set[str] = set()
    facts = []
    for item in data["facts"]:
        if not isinstance(item, dict):
            raise ValueError("a fact is not in the expected shape")
        fid, label = item.get("id"), item.get("label")
        if not isinstance(fid, str) or not fid.strip() or not isinstance(label, str) or not label.strip():
            raise ValueError("every fact needs an id and a label")
        if fid in seen:
            raise ValueError(f"two facts have the id {fid}")
        seen.add(fid)
        if "value" not in item or not _is_value(item["value"]):
            raise ValueError(f"the fact {label} has no usable value")
        for key in ("unit", "source", "notes"):
            if not isinstance(item.get(key, ""), str):
                raise ValueError(f"the {key} of the fact {label} must be text")
        facts.append({"id": fid, "label": label, "value": item["value"], "unit": item.get("unit", ""),
                      "source": item.get("source", ""), "notes": item.get("notes", "")})
    counts = data.get("counts") or {}
    if not isinstance(counts, dict) or not all(
            isinstance(k, str) and isinstance(v, int) and not isinstance(v, bool) for k, v in counts.items()):
        raise ValueError("the counts must be whole numbers with names")
    problems = data.get("problems") or []
    if not isinstance(problems, list) or not all(isinstance(p, str) for p in problems):
        raise ValueError("the problems must be a list of sentences")
    return {"facts": facts, "counts": counts, "problems": problems}


def _parse(stdout: str) -> Any:
    try:
        return json.loads(stdout)
    except json.JSONDecodeError:
        return json.loads(_last_line(stdout))


def run(paths: Paths, tool_id: str, name: str, files: list[Path], timeout: float = TIMEOUT_SECONDS,
        script: Path | None = None, named: list[tuple[str, Path]] | tuple = ()) -> Result:
    """Run the facts step on the files. Raises FactsProblem with a plain message."""
    script = script or script_for(paths, tool_id)
    refused = safety.problem(script)
    if refused:
        raise FactsProblem(refused)
    args, assigned = _arguments(script, files, named)
    env = {**os.environ, "JA_WORKSPACE": str(paths.root), "PYTHONDONTWRITEBYTECODE": "1"}
    try:
        proc = subprocess.Popen(_command(paths.root, script, args), cwd=paths.root, env=env, text=True,
                                stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                start_new_session=True)
    except OSError:
        raise FactsProblem(f"The facts step for {name} could not start.") from None
    try:
        stdout, stderr = proc.communicate(timeout=timeout)
    except subprocess.TimeoutExpired:
        _stop_group(proc)
        raise FactsProblem(f"The facts step for {name} took too long and was stopped.") from None
    done = subprocess.CompletedProcess(proc.args, proc.returncode, stdout, stderr)
    if done.returncode == BLOCKED_EXIT and BLOCKED_MARKER in done.stderr:
        what = done.stderr.split(BLOCKED_MARKER, 1)[1].splitlines()[0].strip()
        raise FactsProblem(f"The facts step for {name} tried to {what}, which tools here are not allowed to do.")
    if done.returncode != 0:
        raise FactsProblem(f"The facts step for {name} failed: {_last_line(done.stderr)}")
    try:
        data = validate(_parse(done.stdout))
    except (json.JSONDecodeError, ValueError) as exc:
        reason = "it did not print results" if isinstance(exc, json.JSONDecodeError) else str(exc)
        raise FactsProblem(f"The facts step for {name} gave results I could not use: {reason}.") from None
    return Result(data, assigned)


def received(file: Path) -> str:
    """The date the file was last saved on this computer (YYYY-MM-DD)."""
    return datetime.fromtimestamp(Path(file).stat().st_mtime).date().isoformat()


def fingerprint(files: list[Path], roles: list[str] | None = None) -> list[dict[str, str]]:
    out = []
    for i, f in enumerate(files):
        digest = hashlib.sha256(Path(f).read_bytes()).hexdigest()
        entry = {"name": Path(f).name, "sha256": digest, "received": received(f)}
        if roles:
            entry["role"] = roles[i]
        out.append(entry)
    return out


def day_text(day: str) -> str:
    d = date.fromisoformat(day)
    return f"{d:%b} {d.day}, {d.year}"


RECEIVED_HEAD = "Received (saved on this computer): "
EXPORT_UNKNOWN = "Export date: unknown unless the person says it."


def received_lines(dates: dict[str, str]) -> list[str]:
    """Plain lines naming when each input file arrived, for results that must say how old the data is."""
    if not dates:
        return []
    listed = "; ".join(f"{name} on {day_text(day)}" for name, day in dates.items())
    return [RECEIVED_HEAD + listed + ".", EXPORT_UNKNOWN]


def last_paths(paths: Paths, tool_id: str) -> tuple[Path, Path]:
    return paths.last_dir / f"{tool_id}.json", paths.last_dir / f"{tool_id}.inputs.json"


def save_last(paths: Paths, tool_id: str, result: Result, files: list[Path]) -> Path:
    """Keep the latest facts and which files they came from, for saving an example later."""
    out, used = last_paths(paths, tool_id)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(result.data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    if result.assigned:
        files, roles = [p for _, p in result.assigned], [n for n, _ in result.assigned]
    else:
        roles = None
    used.write_text(json.dumps(fingerprint(files, roles), indent=2) + "\n", encoding="utf-8")
    return out


def value_text(v: Any) -> str:
    if v is None:
        return "unknown"
    if isinstance(v, bool):
        return "yes" if v else "no"
    return str(v)


def fact_line(fact: dict[str, Any]) -> str:
    unit = f" {fact['unit']}" if fact.get("unit") else ""
    source = fact.get("source") or "unknown"
    return f"{fact['label']}: {value_text(fact['value'])}{unit} (source: {source})"


def describe(result: Result) -> list[str]:
    lines = [fact_line(f) for f in result.facts] or ["The facts step found no facts."]
    if result.data["problems"]:
        lines += ["", "Problems it found:", *[f"  {p}" for p in result.data["problems"]]]
    if result.data["counts"]:
        lines += ["", "Counts:", *[f"  {k}: {v}" for k, v in result.data["counts"].items()]]
    return lines
