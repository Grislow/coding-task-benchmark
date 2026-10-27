import ast
import json
import subprocess
import sys
from collections import Counter

_RUFF_RULES = {
    "python": "E,F,I,UP,B,A,SIM,C4,PERF,RET,PL",
    "fastapi": "E,F,I,UP,B,A,SIM,C4,PERF,RET,PL,FAST,ASYNC",
}
_RUFF_IGNORE = {"python": "PLR2004", "fastapi": "PLR2004,PLR0913,PLR0917"}

_BRANCH_NODES = (
    ast.If,
    ast.For,
    ast.AsyncFor,
    ast.While,
    ast.ExceptHandler,
    ast.With,
    ast.AsyncWith,
    ast.Assert,
    ast.IfExp,
    ast.Match,
)


def readability_report(source: str, tech: str = "python") -> tuple[float, str]:
    structure, structure_note = _structure_score(source)
    ruff_score, ruff_note = _ruff_score(source, tech)
    if ruff_score is None:
        return structure, structure_note
    combined = (0.7 * structure) + (0.3 * ruff_score)
    return combined, f"{structure_note}; {ruff_note}"


def _structure_score(source: str) -> tuple[float, str]:
    try:
        tree = ast.parse(source)
    except SyntaxError as exc:
        return 0.0, f"syntax error: {exc.msg}"
    functions = [node for node in ast.walk(tree) if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))]
    if not functions:
        return 40.0, "no function defined"
    complexities = [_complexity(function) for function in functions]
    lengths = [_function_length(function) for function in functions]
    max_complexity = max(complexities)
    max_length = max(lengths)
    penalty = 0
    if max_complexity > 10:
        penalty += (max_complexity - 10) * 8
    if max_length > 40:
        penalty += (max_length - 40) * 2
    score = float(max(0, 100 - penalty))
    note = f"max complexity {max_complexity}, longest function {max_length} lines"
    return score, note


def _complexity(function: ast.FunctionDef | ast.AsyncFunctionDef) -> int:
    score = 1
    for node in ast.walk(function):
        if isinstance(node, _BRANCH_NODES):
            score += 1
        elif isinstance(node, ast.BoolOp):
            score += max(0, len(node.values) - 1)
        elif isinstance(node, (ast.ListComp, ast.SetComp, ast.DictComp, ast.GeneratorExp)):
            score += 1
    return score


def _function_length(function: ast.FunctionDef | ast.AsyncFunctionDef) -> int:
    end = getattr(function, "end_lineno", None)
    if not isinstance(end, int):
        return 1
    return max(1, end - function.lineno + 1)


def _ruff_score(source: str, tech: str) -> tuple[float | None, str]:
    try:
        completed = subprocess.run(
            [
                sys.executable,
                "-m",
                "ruff",
                "check",
                "--isolated",
                "--select",
                _RUFF_RULES[tech],
                "--ignore",
                _RUFF_IGNORE[tech],
                "--line-length",
                "100",
                "--output-format",
                "json",
                "--stdin-filename",
                "solution.py",
                "-",
            ],
            input=source,
            text=True,
            capture_output=True,
            check=False,
            timeout=30,
        )
    except (OSError, subprocess.TimeoutExpired):
        return None, ""
    try:
        payload = json.loads(completed.stdout or "[]")
    except json.JSONDecodeError:
        return None, ""
    if not isinstance(payload, list):
        return None, ""
    codes = Counter(str(item.get("code")) for item in payload if isinstance(item, dict))
    score = float(max(0, 100 - (10 * sum(codes.values()))))
    if not codes:
        return score, "ruff clean"
    listed = ", ".join(code if count == 1 else f"{code} x{count}" for code, count in sorted(codes.items()))
    return score, f"ruff {listed}"
