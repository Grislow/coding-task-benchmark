import shutil
import tempfile
from pathlib import Path

from ctb.langs.node.contract import contract_report
from ctb.langs.node.grade import evaluate_solution, extract_public_tests
from ctb.langs.node.grade import link_modules as prepare
from ctb.langs.node.lint import readability_report
from ctb.langs.shared import run

RUNTIME = "Node"
SOLVER_NOTE = "Keep `module.exports = { solution };` so the grader can load it. Express is installed. Do not run npm install.\n"
FENCE = "javascript"
SOLUTION = "solution.js"
PUBLIC = "public.test.js"
HIDDEN = "hidden.test.js"
PERF = "perf_cases.js"
STUB = '''function solution(...args) {
  throw new Error("replace this with the task's solution function");
}

module.exports = { solution };
'''

__all__ = [
    "compile_error",
    "contract_report",
    "evaluate_solution",
    "extract_public_tests",
    "prepare",
    "readability_report",
    "test_instructions",
]


def compile_error(source: str) -> str | None:
    if shutil.which("node") is None:
        return None
    with tempfile.TemporaryDirectory(prefix="ctb-check-") as directory:
        path = Path(directory) / "check.js"
        path.write_text(source)
        completed = run(["node", "--check", str(path)], Path(directory), 30)
    if completed is None or completed.returncode == 0:
        return None
    lines = [line for line in completed.stderr.splitlines() if "Error" in line]
    return (lines or ["syntax error"])[0]


def test_instructions() -> str:
    return (
        f"Create {HIDDEN}. It must load the entry point with "
        '`const { solution } = require("./solution");` and use `node:test` with `node:assert/strict`.\n'
        "Cover the examples in the task and the edge cases the statement implies.\n"
        "Express is installed. To call an Express app, start it with `app.listen(0)`, use the built-in `fetch`, "
        "and close the server when the test ends. Do not run npm install.\n"
        f"Create {PERF} that sets `module.exports` to an array. Each item is "
        "the array of arguments for one call to solution.\n"
    )
