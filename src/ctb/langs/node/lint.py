import json
import re
from collections import Counter
from pathlib import Path

from ctb.langs.node.grade import EXPORT
from ctb.langs.shared import run

_HERE = Path(__file__).parent
_ESLINT = _HERE / "node_modules" / ".bin" / "eslint"
_METRICS = {"complexity", "max-lines-per-function"}


def readability_report(source: str, tech: str = "javascript") -> tuple[float, str]:
    del tech
    messages = _eslint(source)
    if messages is None:
        return 0.0, "eslint is not installed; run make setup"
    fatal = next((item for item in messages if item.get("fatal")), None)
    if fatal is not None:
        return 0.0, f"syntax error: {fatal.get('message', '')}"
    structure, structure_note = _structure(messages)
    codes = Counter(str(item.get("ruleId")) for item in messages if item.get("ruleId") not in _METRICS)
    lint = float(max(0, 100 - (10 * sum(codes.values()))))
    if codes:
        listed = ", ".join(code if count == 1 else f"{code} x{count}" for code, count in sorted(codes.items()))
        lint_note = f"eslint {listed}"
    else:
        lint_note = "eslint clean"
    return (0.7 * structure) + (0.3 * lint), f"{structure_note}; {lint_note}"


def _eslint(source: str) -> list[dict[str, object]] | None:
    if not _ESLINT.exists():
        return None
    command = [
        str(_ESLINT),
        "--config",
        str(_HERE / "eslint.config.mjs"),
        "--format",
        "json",
        "--stdin",
        "--stdin-filename",
        "solution.js",
    ]
    completed = run(command, _HERE, 60, stdin=source + EXPORT)
    if completed is None:
        return None
    try:
        payload = json.loads(completed.stdout or "[]")
    except json.JSONDecodeError:
        return None
    if not payload or not isinstance(payload[0], dict):
        return []
    lines = source.count("\n") + 1
    return [item for item in payload[0].get("messages", []) if isinstance(item, dict) and (item.get("fatal") or int(item.get("line") or 0) <= lines)]


def _structure(messages: list[dict[str, object]]) -> tuple[float, str]:
    complexities = _numbers(messages, "complexity", r"complexity of (\d+)")
    lengths = _numbers(messages, "max-lines-per-function", r"too many lines \((\d+)\)")
    if not complexities:
        return 40.0, "no function defined"
    max_complexity = max(complexities)
    max_length = max(lengths or [1])
    penalty = 0
    if max_complexity > 10:
        penalty += (max_complexity - 10) * 8
    if max_length > 40:
        penalty += (max_length - 40) * 2
    note = f"max complexity {max_complexity}, longest function {max_length} lines"
    return float(max(0, 100 - penalty)), note


def _numbers(messages: list[dict[str, object]], rule: str, pattern: str) -> list[int]:
    found = (re.search(pattern, str(item.get("message", ""))) for item in messages if item.get("ruleId") == rule)
    return [int(match.group(1)) for match in found if match]
