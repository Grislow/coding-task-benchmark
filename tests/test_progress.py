from pathlib import Path

from test_benchmark import ScriptedAgent, _CORRECT, _TASK, _WRONG

from ctb.orchestrate import run_benchmark
from ctb.progress import ProgressBoard


def _attempt(snapshot: dict[str, object], agent: str, number: int) -> dict[str, object]:
    attempts = snapshot["attempts"]
    assert isinstance(attempts, list)
    for item in attempts:
        assert isinstance(item, dict)
        if item["agent"] == agent and item["number"] == number:
            return item
    raise AssertionError((agent, number))


class WatchingAgent(ScriptedAgent):
    def __init__(self, name: str, sources: list[str], board: ProgressBoard) -> None:
        super().__init__(name, sources, tokens=20)
        self.board = board
        self.saw_later_attempt = False
        self.saw_reviews_after_solves = False

    def complete(
        self,
        *,
        cwd: str,
        prompt: str,
        session_id: str | None,
        role: str,
    ):
        if role == "solve" and self._solves >= 1:
            snapshot = self.board.snapshot()
            previous = _attempt(snapshot, self.name, self._solves)
            current = _attempt(snapshot, self.name, self._solves + 1)
            assert previous["state"] in {"passed", "failed"}
            assert current["state"] == "running"
            self.saw_later_attempt = True
        if role == "review":
            snapshot = self.board.snapshot()
            assert snapshot["phase"] == "reviewing"
            attempts = snapshot["attempts"]
            assert isinstance(attempts, list)
            assert attempts
            assert all(item["state"] in {"passed", "failed"} for item in attempts)
            self.saw_reviews_after_solves = True
        return super().complete(cwd=cwd, prompt=prompt, session_id=session_id, role=role)


def test_attempt_and_review_progress_follow_the_run(tmp_path: Path) -> None:
    board = ProgressBoard(["fast", "slow"], attempts=3, author="author")
    fast = WatchingAgent("fast", [_CORRECT], board)
    slow = WatchingAgent("slow", [_WRONG, _CORRECT, _WRONG], board)
    report = run_benchmark(
        task_text=_TASK,
        agents=[fast, slow],
        test_author=ScriptedAgent("author", [], tokens=5),
        attempts=3,
        timeout_s=30,
        out_dir=tmp_path,
        review=True,
        progress=board,
    )
    assert fast.saw_later_attempt
    assert slow.saw_later_attempt
    assert fast.saw_reviews_after_solves
    assert slow.saw_reviews_after_solves

    snapshot = board.snapshot()
    assert snapshot["phase"] == "done"
    assert snapshot["suite_ready"] is True
    assert snapshot["agents"] == ["fast", "slow"]
    author = snapshot["author"]
    assert isinstance(author, dict)
    assert author["state"] == "done"

    assert _attempt(snapshot, "slow", 1)["state"] == "failed"
    kept = _attempt(snapshot, "slow", 2)
    assert kept["state"] == "passed"
    assert kept["chosen"] is True
    assert "while N" in str(kept["source"])
    assert _attempt(snapshot, "fast", 1)["chosen"] is True
    assert _attempt(snapshot, "slow", 1)["tests_total"] == 2

    reviews = snapshot["reviews"]
    assert isinstance(reviews, list)
    assert len(reviews) == 2
    assert {item["reviewer"] for item in reviews} == {"fast", "slow"}
    assert all(item["state"] == "done" and item["correctness"] == 90 for item in reviews)

    solutions = snapshot["solutions"]
    assert isinstance(solutions, list)
    by_name = {item["agent"]: item for item in solutions}
    assert by_name["fast"]["profile"] is not None
    assert by_name["slow"]["profile"] is not None
    assert {solution.agent for solution in report.solutions} == {"fast", "slow"}
