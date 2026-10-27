import ast
import json
import re
import shutil
import sys
import tempfile
import textwrap
from pathlib import Path

from ctb.langs.shared import read_junit, run
from ctb.models import EvalResult

_PERF_RUNNER = """
import cProfile
import json
import pstats
import statistics
import time
from perf_cases import CASES
from solution import solution

cases = list(CASES)[:20]
totals = []
for _ in range(5):
    started = time.perf_counter()
    for args, kwargs in cases:
        solution(*args, **kwargs)
    totals.append((time.perf_counter() - started) * 1000)
profiler = cProfile.Profile()
profiler.enable()
for args, kwargs in cases:
    solution(*args, **kwargs)
profiler.disable()
ranked = sorted(pstats.Stats(profiler).stats.items(), key=lambda item: item[1][3], reverse=True)
parts = []
for func, values in ranked:
    filename, _line, name = func
    if "lsprof" in filename or name in {"disable", "enable"} or name.startswith("<"):
        continue
    parts.append(f"{name} {values[3] * 1000:.3f} ms")
    if len(parts) == 4:
        break
note = "One profiled pass. " + ("; ".join(parts) if parts else "no functions recorded") + "."
print(json.dumps({"median_ms": statistics.median(totals) if totals else None, "note": note}))
"""


def extract_public_tests(task_text: str) -> str | None:
    blocks = re.findall(r"```python\n(.*?)```", task_text, flags=re.DOTALL)
    selected = [block.strip() for block in blocks if "assert" in block]
    if not selected:
        return None
    parts = ["from solution import solution", ""]
    for index, block in enumerate(selected):
        if re.search(r"^def test_", block, flags=re.MULTILINE):
            parts.append(block)
            parts.append("")
            continue
        indented = textwrap.indent(block, "    ")
        parts.append(f"def test_public_{index}():")
        parts.append(indented)
        parts.append("")
    return "\n".join(parts)


def compile_source(source: str) -> str | None:
    try:
        ast.parse(source)
    except SyntaxError as exc:
        return exc.msg
    return None


def evaluate_solution(
    source: str,
    public_tests: str | None,
    hidden_tests: str | None,
    perf_cases: str | None,
    timeout_s: int,
) -> EvalResult:
    if not public_tests and not hidden_tests:
        return EvalResult(False, 0, 0, False, "No tests were available.", None)
    with tempfile.TemporaryDirectory(prefix="ctb-eval-") as directory:
        root = Path(directory)
        (root / "solution.py").write_text(source)
        if public_tests:
            (root / "test_public.py").write_text(public_tests)
        if hidden_tests:
            (root / "test_hidden.py").write_text(hidden_tests)
        combined = _run_pytest(root, timeout_s)
        public_failed = False
        if public_tests:
            public = _run_pytest(root, timeout_s, "test_public.py")
            public_failed = not public.passed
        performance_ms = None
        performance_note = ""
        if combined.passed and perf_cases and compile_source(perf_cases) is None:
            performance_ms, performance_note = _run_perf(root, perf_cases, timeout_s)
        return EvalResult(
            passed=combined.passed and not public_failed,
            tests_passed=combined.tests_passed,
            tests_total=combined.tests_total,
            public_failed=public_failed,
            failure_excerpt=combined.failure_excerpt,
            performance_ms=performance_ms,
            performance_note=performance_note,
        )


def _run_pytest(root: Path, timeout_s: int, target: str | None = None) -> EvalResult:
    if shutil.which("pytest") is None and _module_missing("pytest"):
        return EvalResult(False, 0, 0, False, "pytest is not installed.", None)
    report_path = root / "junit.xml"
    if report_path.exists():
        report_path.unlink()
    command = [
        sys.executable,
        "-m",
        "pytest",
        "-q",
        "--tb=line",
        "--noconftest",
        f"--rootdir={root}",
        f"--junitxml={report_path.name}",
    ]
    if target:
        command.append(target)
    completed = run(command, root, timeout_s)
    if completed is None:
        return EvalResult(False, 0, 0, False, "pytest timed out.", None)
    passed, total, excerpt = read_junit(report_path, completed.stdout, completed.stderr)
    ok = completed.returncode == 0 and total > 0 and passed == total
    failure = "" if ok else (excerpt or completed.stdout or completed.stderr or "pytest failed")
    return EvalResult(ok, passed, total, False, failure[:4000], None)


def _run_perf(root: Path, perf_cases: str, timeout_s: int) -> tuple[float | None, str]:
    (root / "perf_cases.py").write_text(perf_cases)
    (root / "run_perf.py").write_text(_PERF_RUNNER)
    completed = run([sys.executable, "run_perf.py"], root, min(timeout_s, 30))
    if completed is None or completed.returncode != 0:
        return None, "The profiler did not finish."
    try:
        payload = json.loads(completed.stdout.strip().splitlines()[-1])
    except (json.JSONDecodeError, IndexError):
        return None, "The profiler did not finish."
    if not isinstance(payload, dict):
        return None, "The profiler did not finish."
    value = payload.get("median_ms")
    note = payload.get("note")
    text = note if isinstance(note, str) else ""
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None, text or "The profiler did not finish."
    return float(value), text


def _module_missing(name: str) -> bool:
    completed = run([sys.executable, "-c", f"import {name}"], Path.cwd(), 30)
    return completed is None or completed.returncode != 0
