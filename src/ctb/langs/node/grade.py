import json
import re
import shutil
import tempfile
from pathlib import Path

from ctb.langs.shared import read_junit, run
from ctb.models import EvalResult

NODE_MODULES = Path(__file__).parent / "node_modules"
EXPORT = '\nif (typeof solution === "function") module.exports = { ...module.exports, solution };\n'

_PERF_RUNNER = """
const { performance } = require("node:perf_hooks");
const { solution } = require("./solution");
const cases = require("./perf_cases").slice(0, 20);
const totals = [];
for (let pass = 0; pass < 5; pass += 1) {
  const started = performance.now();
  for (const args of cases) solution(...args);
  totals.push(performance.now() - started);
}
totals.sort((left, right) => left - right);
console.log(JSON.stringify({ median_ms: totals[2], note: `Median of 5 passes over ${cases.length} cases.` }));
"""


def extract_public_tests(task_text: str) -> str | None:
    blocks = re.findall(r"```(?:javascript|js)\n(.*?)```", task_text, flags=re.DOTALL)
    selected = [block.strip() for block in blocks if "assert" in block]
    if not selected:
        return None
    parts = [
        'const test = require("node:test");',
        'const assert = require("node:assert/strict");',
        'const { solution } = require("./solution");',
        "",
    ]
    for index, block in enumerate(selected):
        parts.extend([f'test("public {index}", async () => {{', block, "});", ""])
    return "\n".join(parts)


def evaluate_solution(
    source: str,
    public_tests: str | None,
    hidden_tests: str | None,
    perf_cases: str | None,
    timeout_s: int,
) -> EvalResult:
    if not public_tests and not hidden_tests:
        return EvalResult(False, 0, 0, False, "No tests were available.", None)
    if shutil.which("node") is None:
        return EvalResult(False, 0, 0, False, "node is not installed.", None)
    with tempfile.TemporaryDirectory(prefix="ctb-eval-") as directory:
        root = Path(directory)
        stage(root, source)
        files = []
        if public_tests:
            (root / "public.test.js").write_text(public_tests)
            files.append("public.test.js")
        if hidden_tests:
            (root / "hidden.test.js").write_text(hidden_tests)
            files.append("hidden.test.js")
        combined = _run_tests(root, timeout_s, files)
        public_failed = bool(public_tests) and not _run_tests(root, timeout_s, ["public.test.js"]).passed
        performance_ms = None
        performance_note = ""
        if combined.passed and perf_cases:
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


def stage(root: Path, source: str) -> None:
    (root / "solution.js").write_text(source + EXPORT)
    link_modules(root)


def link_modules(directory: Path) -> None:
    link = directory / "node_modules"
    if NODE_MODULES.exists() and not link.exists():
        link.symlink_to(NODE_MODULES, target_is_directory=True)


def _run_tests(root: Path, timeout_s: int, files: list[str]) -> EvalResult:
    report_path = root / "junit.xml"
    if report_path.exists():
        report_path.unlink()
    command = [
        "node",
        "--test",
        "--test-force-exit",
        "--test-reporter=junit",
        f"--test-reporter-destination={report_path.name}",
        *files,
    ]
    completed = run(command, root, timeout_s)
    if completed is None:
        return EvalResult(False, 0, 0, False, "node --test timed out.", None)
    passed, total, excerpt = read_junit(report_path, completed.stdout, completed.stderr)
    ok = completed.returncode == 0 and total > 0 and passed == total
    failure = "" if ok else (excerpt or completed.stdout or completed.stderr or "node --test failed")
    return EvalResult(ok, passed, total, False, failure[:4000], None)


def _run_perf(root: Path, perf_cases: str, timeout_s: int) -> tuple[float | None, str]:
    (root / "perf_cases.js").write_text(perf_cases)
    (root / "run_perf.js").write_text(_PERF_RUNNER)
    completed = run(["node", "run_perf.js"], root, min(timeout_s, 30))
    if completed is None or completed.returncode != 0:
        return None, "The timer did not finish."
    try:
        payload = json.loads(completed.stdout.strip().splitlines()[-1])
    except (json.JSONDecodeError, IndexError):
        return None, "The timer did not finish."
    value = payload.get("median_ms") if isinstance(payload, dict) else None
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None, "The timer did not finish."
    return float(value), str(payload.get("note") or "")
