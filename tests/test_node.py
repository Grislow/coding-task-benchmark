import shutil
from pathlib import Path

import pytest

from ctb.langs import node
from ctb.models import AgentResult, TokenUsage
from ctb.run.orchestrate import run_benchmark

pytestmark = pytest.mark.skipif(
    shutil.which("node") is None or not (Path(node.__file__).parent / "node_modules").exists(),
    reason="needs node and make setup",
)

_GAP = """function solution(N) {
  let best = 0;
  let gap = 0;
  for (const bit of N.toString(2).replace(/0+$/, "")) {
    if (bit === "0") {
      gap += 1;
    } else {
      best = Math.max(best, gap);
      gap = 0;
    }
  }
  return best;
}
"""

_HIDDEN = """const test = require("node:test");
const assert = require("node:assert/strict");
const { solution } = require("./solution");

test("examples", () => {
  assert.equal(solution(9), 2);
  assert.equal(solution(529), 4);
});

test("no gap", () => assert.equal(solution(15), 0));
"""

_TASK = """# BinaryGap

Write `function solution(N)` that returns the longest binary gap of N.

```js
assert.equal(solution(1041), 5);
assert.equal(solution(32), 0);
```
"""

_TODO = """const express = require("express");

function solution() {
  const app = express();
  const todos = new Map();
  app.use(express.json());
  app.post("/todos", (req, res) => {
    if (typeof req.body?.title !== "string") return res.status(422).json({ detail: "title is required" });
    const todo = { id: todos.size + 1, title: req.body.title };
    todos.set(todo.id, todo);
    return res.status(201).json(todo);
  });
  app.get("/todos/:id", (req, res) => {
    const todo = todos.get(Number(req.params.id));
    if (!todo) return res.status(404).json({ detail: "Todo not found" });
    return res.json(todo);
  });
  return app;
}

module.exports = { solution };
"""


def test_a_paste_without_exports_is_graded_and_timed() -> None:
    public = node.extract_public_tests(_TASK)
    result = node.evaluate_solution(_GAP, public, _HIDDEN, "module.exports = [[9], [2 ** 20]];", 30)
    assert result.passed
    assert (result.tests_passed, result.tests_total) == (3, 3)
    assert result.performance_ms is not None


def test_a_wrong_answer_fails_the_public_examples() -> None:
    result = node.evaluate_solution("function solution() { return 0; }\n", node.extract_public_tests(_TASK), _HIDDEN, None, 30)
    assert not result.passed
    assert result.public_failed
    assert result.tests_passed == 1
    assert "public 0" in result.failure_excerpt


def test_lint_scores_structure_and_eslint_findings() -> None:
    clean, clean_note = node.readability_report(_GAP)
    sloppy, sloppy_note = node.readability_report("var best = 0\nfunction solution(N) { if (N == 1) { return best } else { return 2 } }\n")
    assert clean == 100
    assert "eslint clean" in clean_note
    assert sloppy < clean
    assert "eqeqeq" in sloppy_note and "no-var" in sloppy_note
    assert node.readability_report("function solution( {")[0] == 0
    assert node.compile_error("function ( {") is not None
    assert node.compile_error(_HIDDEN) is None


def test_the_express_probe_rewards_routes_that_survive_bad_input() -> None:
    tidy, tidy_note = node.contract_report(_TODO, None, 30)
    crashing = _TODO.replace('if (typeof req.body?.title !== "string") return res.status(422).json({ detail: "title is required" });\n', "")
    crashing = crashing.replace("title: req.body.title", "title: req.body.title.trim()")
    sloppy, sloppy_note = node.contract_report(crashing, None, 30)
    assert tidy == 100, tidy_note
    assert sloppy is not None and sloppy < tidy
    assert "POST /todos with no body returned 500" in sloppy_note


class JsAgent:
    name = "js"

    def __init__(self) -> None:
        self.solves = 0

    def complete(self, *, cwd: str, prompt: str, session_id: str | None, role: str) -> AgentResult:
        root = Path(cwd)
        text = "done"
        if role == "author":
            assert "hidden.test.js" in prompt
            (root / "hidden.test.js").write_text(_HIDDEN)
            (root / "perf_cases.js").write_text("module.exports = [[9], [529]];\n")
        elif role == "solve":
            assert "solution.js" in prompt
            assert (root / "node_modules").is_symlink()
            self.solves += 1
            if self.solves == 2:
                assert "function solution() { return 0; }" in prompt
                assert not list(root.glob("attempt-*"))
            source = "function solution() { return 0; }\nmodule.exports = { solution };\n" if self.solves == 1 else _GAP + "\nmodule.exports = { solution };\n"
            (root / "solution.js").write_text(source)
        return AgentResult(True, text, "s", TokenUsage(input_tokens=10), 5, None, None, {})


def test_a_javascript_run_writes_tests_solves_and_ranks(tmp_path: Path) -> None:
    agent = JsAgent()
    report = run_benchmark(_TASK, [agent], JsAgent(), 2, 30, tmp_path, False, tech="javascript")
    solution = report.solutions[0]
    assert [record.passed for record in solution.attempts] == [False, True]
    assert solution.attempts[1].tests_total == 3
    assert (tmp_path / "hidden" / "hidden.test.js").exists()
    assert (tmp_path / "work" / "js" / "attempt-2.js").exists()
    assert (tmp_path / "work" / "js" / "node_modules").is_symlink()
