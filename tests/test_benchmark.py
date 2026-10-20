import time
from pathlib import Path

from ctb.evaluate import evaluate_solution
from ctb.models import AgentResult, TokenUsage
from ctb.orchestrate import run_benchmark
from ctb.prompts import SOLUTION_STUB
from ctb.report import write_report

_CORRECT = """
def solution(N):
    best = 0
    gap = 0
    seen_one = False
    while N:
        if N & 1:
            best = max(best, gap)
            gap = 0
            seen_one = True
        elif seen_one:
            gap += 1
        N >>= 1
    return best
"""

_WRONG = "def solution(N):\n    return 0\n"

_HIDDEN = """
from solution import solution

def test_hidden_sentinel_gap():
    assert solution(9) == 2
"""

_PERF = "CASES = [((9,), {}), ((529,), {})]\n"

_TASK = """
# BinaryGap

```python
assert solution(9) == 2
```
"""


class ScriptedAgent:
    def __init__(self, name: str, sources: list[str], tokens: int) -> None:
        self.name = name
        self.sources = sources
        self.tokens = tokens
        self.prompts: list[str] = []
        self.sessions: list[str | None] = []
        self._solves = 0

    def complete(
        self,
        *,
        cwd: str,
        prompt: str,
        session_id: str | None,
        role: str,
    ) -> AgentResult:
        root = Path(cwd)
        self.prompts.append(prompt)
        self.sessions.append(session_id)
        if role == "author":
            (root / "test_hidden.py").write_text(_HIDDEN)
            text = "tests"
        elif role == "review":
            text = (
                '{"readability": 80, "readability_reason": "Readable loop.", '
                '"extensibility": 70, "extensibility_reason": "One function can take another case."}'
            )
        else:
            source = self.sources[min(self._solves, len(self.sources) - 1)]
            self._solves += 1
            (root / "solution.py").write_text(source)
            text = "edited"
        return AgentResult(
            ok=True,
            text=text,
            session_id=f"{self.name}-session",
            usage=TokenUsage(input_tokens=self.tokens, output_tokens=10),
            wall_ms=self.tokens,
            cost_usd=0.01,
            error=None,
            raw={},
        )


def test_solution_is_graded_outside_the_solver_directory() -> None:
    result = evaluate_solution(_CORRECT, None, _HIDDEN, _PERF, timeout_s=30)
    assert result.passed
    assert result.tests_total == 1
    assert result.performance_ms is not None and result.performance_ms > 0
    assert "solution" in result.performance_note

    failed = evaluate_solution(_WRONG, None, _HIDDEN, _PERF, timeout_s=30)
    assert not failed.passed
    assert "test_hidden_sentinel_gap" in failed.failure_excerpt


def test_three_attempt_loop_repairs_and_peers_grade_the_other_solution(tmp_path: Path) -> None:
    author = ScriptedAgent("author", [], tokens=5)
    fast = ScriptedAgent("fast", [_CORRECT], tokens=100)
    slow = ScriptedAgent("slow", [_WRONG, _CORRECT, _WRONG], tokens=100)
    report = run_benchmark(
        task_text=_TASK,
        agents=[fast, slow],
        test_author=author,
        attempts=3,
        timeout_s=30,
        out_dir=tmp_path,
        review=True,
    )
    write_report(report, tmp_path)

    assert len(fast.prompts) == 4
    assert "test_hidden_sentinel_gap" not in fast.prompts[0]
    assert fast.prompts[0].startswith("Solve the coding task")
    assert "different approach" in fast.prompts[1]
    assert "passed the tests" in fast.prompts[1]
    assert len(slow.prompts) == 4
    assert slow.sessions[1] == "slow-session"
    assert "failed the tests" in slow.prompts[1]
    assert "test_hidden_sentinel_gap" in slow.prompts[1]
    assert "different approach" in slow.prompts[1]
    assert not (tmp_path / "work" / "slow" / "test_hidden.py").exists()
    assert (tmp_path / "work" / "slow" / "solution.py").read_text() != SOLUTION_STUB

    by_name = {solution.agent: solution for solution in report.solutions}
    assert len(by_name["fast"].attempts) == 3
    assert all(attempt.passed for attempt in by_name["fast"].attempts)
    assert any(attempt.chosen for attempt in by_name["fast"].attempts)
    assert len(by_name["slow"].attempts) == 3
    assert by_name["slow"].attempts[0].passed is False
    assert by_name["slow"].attempts[1].chosen
    assert "while N" in by_name["slow"].source
    assert by_name["fast"].reviews[0].reviewer == "slow"
    assert by_name["slow"].reviews[0].reviewer == "fast"
    assert by_name["fast"].profile is not None and by_name["slow"].profile is not None
    report_text = (tmp_path / "report.md").read_text()
    assert "| 1 | fail |" in report_text
    assert "| 2 | pass, kept |" in report_text


class SleepySolver(ScriptedAgent):
    def __init__(self, name: str) -> None:
        super().__init__(name, [_CORRECT], tokens=10)
        self.started = 0.0

    def complete(
        self,
        *,
        cwd: str,
        prompt: str,
        session_id: str | None,
        role: str,
    ) -> AgentResult:
        if role == "solve":
            self.started = time.monotonic()
            time.sleep(0.5)
        return super().complete(cwd=cwd, prompt=prompt, session_id=session_id, role=role)


def test_solvers_start_together(tmp_path: Path) -> None:
    first = SleepySolver("first")
    second = SleepySolver("second")
    run_benchmark(
        task_text=_TASK,
        agents=[first, second],
        test_author=ScriptedAgent("author", [], tokens=1),
        attempts=1,
        timeout_s=30,
        out_dir=tmp_path,
        review=False,
    )
    assert abs(first.started - second.started) < 0.3
