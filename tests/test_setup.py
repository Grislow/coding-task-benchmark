from pathlib import Path

import pytest
from test_benchmark import _CORRECT, _TASK, ScriptedAgent

from ctb import orchestrate
from ctb.models import AgentResult, TokenUsage
from ctb.orchestrate import rerun_agent, run_benchmark
from ctb.preflight import check_agent
from ctb.progress import ProgressBoard


class BrokenAgent(ScriptedAgent):
    def __init__(self, name: str, failures: int, *, ok: bool) -> None:
        super().__init__(name, [_CORRECT], tokens=10)
        self.failures = failures
        self.ok = ok
        self.calls = 0

    def complete(self, *, cwd: str, prompt: str, session_id: str | None, role: str) -> AgentResult:
        if role != "solve":
            return super().complete(cwd=cwd, prompt=prompt, session_id=session_id, role=role)
        self.calls += 1
        if self.calls > self.failures:
            return super().complete(cwd=cwd, prompt=prompt, session_id=session_id, role=role)
        return AgentResult(
            ok=self.ok,
            text="I couldn't read task.md.",
            session_id=None,
            usage=TokenUsage(),
            wall_ms=5,
            cost_usd=None,
            error=None if self.ok else "unknown model id",
            raw={},
        )


@pytest.fixture(autouse=True)
def no_delay(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(orchestrate, "RETRY_DELAY_S", 0)


def _run(tmp_path: Path, agents: list[ScriptedAgent], board: ProgressBoard):
    return run_benchmark(
        task_text=_TASK,
        agents=agents,
        test_author=ScriptedAgent("author", [], tokens=5),
        attempts=2,
        timeout_s=30,
        out_dir=tmp_path,
        review=True,
        progress=board,
    )


def test_one_failed_call_is_retried_without_using_an_attempt(tmp_path: Path) -> None:
    flaky = BrokenAgent("flaky", failures=1, ok=False)
    board = ProgressBoard(["flaky"], attempts=2, author="author")
    report = _run(tmp_path, [flaky], board)
    first = report.solutions[0].attempts[0]
    assert first.passed and first.setup_error is None
    assert flaky.calls == 3


def test_an_agent_that_never_edits_is_a_setup_error_and_can_rerun(tmp_path: Path) -> None:
    denied = BrokenAgent("claude-denied", failures=4, ok=True)
    healthy = ScriptedAgent("grok-fine", [_CORRECT], tokens=10)
    board = ProgressBoard([denied.name, healthy.name], attempts=2, author="author")
    report = _run(tmp_path, [denied, healthy], board)
    broken = next(item for item in report.solutions if item.agent == denied.name)
    assert all(attempt.setup_error == "I couldn't read task.md." for attempt in broken.attempts)
    assert not broken.passed
    states = {item["state"] for item in board.snapshot()["attempts"] if item["agent"] == denied.name}
    assert states == {"setup"}
    assert "test_hidden_sentinel_gap" not in denied.prompts[-1]

    rerun_agent(report.solutions, denied, [denied, healthy], _TASK, 2, 30, tmp_path, True, board)
    fixed = next(item for item in report.solutions if item.agent == denied.name)
    assert fixed.passed
    snapshot = board.snapshot()
    assert snapshot["phase"] == "done"
    assert {item["state"] for item in snapshot["attempts"] if item["agent"] == denied.name} == {"passed"}
    pairs = {(item["reviewer"], item["author"]) for item in snapshot["reviews"] if item["state"] == "done"}
    assert (healthy.name, denied.name) in pairs
    assert (denied.name, healthy.name) in pairs
    assert fixed.profile is not None


def test_preflight_names_the_problem(tmp_path: Path) -> None:
    assert check_agent(ScriptedAgent("fine", [_CORRECT], tokens=1)) is None
    assert check_agent(BrokenAgent("denied", failures=1, ok=True)) == "I couldn't read task.md."
    assert check_agent(BrokenAgent("model", failures=1, ok=False)) == "unknown model id"
