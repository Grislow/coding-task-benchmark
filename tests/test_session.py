import time
from pathlib import Path

import pytest
from test_benchmark import _CORRECT, _TASK, _WRONG, ScriptedAgent, SleepySolver

from ctb.models import AgentResult
from ctb.run.session import RunSession


def _wait(session: RunSession, timeout_s: float = 30) -> dict[str, object]:
    deadline = time.monotonic() + timeout_s
    snapshot = session.snapshot()
    while snapshot["phase"] not in {"done", "error"} and time.monotonic() < deadline:
        time.sleep(0.02)
        snapshot = session.snapshot()
    return snapshot


def test_one_run_reaches_done_and_writes_the_suite(tmp_path: Path) -> None:
    session = RunSession(
        [ScriptedAgent("fast", [_CORRECT], tokens=10), ScriptedAgent("slow", [_WRONG, _CORRECT], tokens=10)],
        ScriptedAgent("author", [], tokens=1),
        attempts=3,
        timeout_s=30,
        review=False,
        out_root=tmp_path,
    )
    assert session.snapshot()["phase"] == "idle"
    session.start(_TASK)
    snapshot = _wait(session)
    assert snapshot["phase"] == "done"
    assert snapshot["suite_ready"] is True
    attempts = snapshot["attempts"]
    assert isinstance(attempts, list)
    slow_first = next(item for item in attempts if item["agent"] == "slow" and item["number"] == 1)
    slow_kept = next(item for item in attempts if item["agent"] == "slow" and item["chosen"])
    assert slow_first["state"] == "failed"
    assert slow_kept["number"] == 2
    assert slow_kept["state"] == "passed"
    out_dir = session.out_dir()
    assert out_dir is not None
    assert (out_dir / "task.md").read_text() == _TASK
    assert (out_dir / "hidden" / "test_hidden.py").exists()


def test_a_second_start_is_rejected_while_the_run_is_active(tmp_path: Path) -> None:
    session = RunSession(
        [SleepySolver("first"), SleepySolver("second")],
        ScriptedAgent("author", [], tokens=1),
        attempts=1,
        timeout_s=30,
        review=False,
        out_root=tmp_path,
    )
    session.start(_TASK)
    try:
        session.start(_TASK)
    except RuntimeError as exc:
        assert "already active" in str(exc)
    else:
        raise AssertionError("second start was accepted")
    snapshot = _wait(session)
    assert snapshot["phase"] == "done"



def test_reset_is_refused_while_active_and_clears_a_finished_run(tmp_path: Path) -> None:
    session = RunSession(
        [SleepySolver("first")],
        ScriptedAgent("author", [], tokens=1),
        attempts=1,
        timeout_s=30,
        review=False,
        out_root=tmp_path,
    )
    session.start(_TASK)
    try:
        session.reset()
    except RuntimeError as exc:
        assert "already active" in str(exc)
    else:
        raise AssertionError("reset was accepted during a run")
    assert _wait(session)["phase"] == "done"
    snapshot = session.reset()
    assert snapshot["phase"] == "idle"
    assert snapshot["attempts"] == []
    assert snapshot["candidates"] == []
    assert session.out_dir() is None


class SlowAuthor(ScriptedAgent):
    def complete(
        self,
        *,
        cwd: str,
        prompt: str,
        session_id: str | None,
        role: str,
    ) -> AgentResult:
        if role == "author":
            time.sleep(0.4)
        return super().complete(cwd=cwd, prompt=prompt, session_id=session_id, role=role)


def _candidate(snapshot: dict[str, object], number: int = 1) -> dict[str, object]:
    rows = snapshot["candidates"]
    assert isinstance(rows, list)
    row = rows[number - 1]
    assert isinstance(row, dict)
    return row


def _reviewed(row: object) -> bool:
    return isinstance(row, dict) and len(row.get("reviews") or []) == 2 and row.get("profile") is not None


def _wait_for_reviews(session: RunSession, timeout_s: float = 30, count: int = 1) -> dict[str, object]:
    deadline = time.monotonic() + timeout_s
    snapshot = session.snapshot()
    while time.monotonic() < deadline:
        rows = snapshot["candidates"]
        if (
            snapshot["phase"] in {"done", "error"}
            and isinstance(rows, list)
            and len(rows) == count
            and all(_reviewed(row) for row in rows)
        ):
            return snapshot
        time.sleep(0.02)
        snapshot = session.snapshot()
    return snapshot


def test_a_paste_before_the_suite_is_rejected(tmp_path: Path) -> None:
    session = RunSession(
        [ScriptedAgent("fast", [_CORRECT], tokens=10)],
        SlowAuthor("author", [], tokens=1),
        attempts=1,
        timeout_s=30,
        review=False,
        out_root=tmp_path,
    )
    session.start(_TASK)
    try:
        session.submit_mine(_CORRECT)
    except RuntimeError as exc:
        assert "not ready" in str(exc)
    else:
        raise AssertionError("paste was accepted before the suite existed")
    assert _wait(session)["phase"] == "done"


def test_a_paste_is_scored_on_the_frozen_suite_and_reviewed(tmp_path: Path) -> None:
    fast = ScriptedAgent("fast", [_CORRECT], tokens=40)
    slow = ScriptedAgent("slow", [_WRONG, _CORRECT], tokens=80)
    session = RunSession(
        [fast, slow],
        ScriptedAgent("author", [], tokens=1),
        attempts=2,
        timeout_s=30,
        review=True,
        out_root=tmp_path,
    )
    session.start(_TASK)
    assert _wait(session)["phase"] == "done"
    session.submit_mine(_CORRECT)
    snapshot = _wait_for_reviews(session)
    mine = _candidate(snapshot)
    assert mine["passed"] is True
    assert mine["tests_passed"] == mine["tests_total"]
    reviews = mine["reviews"]
    assert isinstance(reviews, list)
    assert {item["reviewer"] for item in reviews} == {"fast", "slow"}
    assert mine["profile"] is not None
    assert mine["cost"] is None
    solutions = snapshot["solutions"]
    assert isinstance(solutions, list)
    assert all(item["profile"] is not None for item in solutions)


def test_skip_review_scores_the_paste_without_grades(tmp_path: Path) -> None:
    session = RunSession(
        [ScriptedAgent("fast", [_CORRECT], tokens=10), ScriptedAgent("slow", [_CORRECT], tokens=10)],
        ScriptedAgent("author", [], tokens=1),
        attempts=1,
        timeout_s=30,
        review=False,
        out_root=tmp_path,
    )
    session.start(_TASK)
    assert _wait(session)["phase"] == "done"
    session.submit_mine(_CORRECT)
    deadline = time.monotonic() + 10
    while _candidate(session.snapshot())["state"] == "running" and time.monotonic() < deadline:
        time.sleep(0.05)
    mine = _candidate(session.snapshot())
    assert mine["passed"] is True
    assert mine["reviews"] == []
    assert mine["profile"] is not None


def test_each_paste_is_its_own_attempt(tmp_path: Path) -> None:
    session = RunSession(
        [ScriptedAgent("fast", [_CORRECT], tokens=40), ScriptedAgent("slow", [_CORRECT], tokens=80)],
        ScriptedAgent("author", [], tokens=1),
        attempts=1,
        timeout_s=30,
        review=True,
        out_root=tmp_path,
    )
    session.start(_TASK)
    assert _wait(session)["phase"] == "done"
    try:
        session.submit_mine("  ")
    except RuntimeError as exc:
        assert "Paste" in str(exc)
    else:
        raise AssertionError("an empty paste was accepted")
    first = session.submit_mine(_CORRECT)
    assert _candidate(first)["state"] == "running"
    session.submit_mine(_WRONG)
    session.submit_mine(_CORRECT)
    snapshot = session.snapshot()
    deadline = time.monotonic() + 30
    while len(snapshot["candidates"]) < 3 or not all(_reviewed(row) or row.get("state") == "failed" for row in snapshot["candidates"]):
        assert time.monotonic() < deadline
        time.sleep(0.02)
        snapshot = session.snapshot()
    assert [row["number"] for row in snapshot["candidates"]] == [1, 2, 3]
    assert [row["state"] for row in snapshot["candidates"]] == ["passed", "failed", "passed"]
    assert {review["attempt"] for review in _candidate(snapshot, 3)["reviews"]} == {3}
    assert {(review["author"], review["attempt"]) for review in snapshot["reviews"] if review["author"] == "you"} == {("you", 1), ("you", 3)}


def test_a_paste_during_solving_is_reviewed_with_the_agents(tmp_path: Path) -> None:
    session = RunSession(
        [SleepySolver("fast"), SleepySolver("slow")],
        ScriptedAgent("author", [], tokens=1),
        attempts=1,
        timeout_s=30,
        review=True,
        out_root=tmp_path,
    )
    session.start(_TASK)
    deadline = time.monotonic() + 10
    while session.snapshot()["suite_ready"] is not True:
        if time.monotonic() > deadline:
            raise AssertionError("suite was not ready")
        time.sleep(0.02)
    session.submit_mine(_CORRECT)
    snapshot = _wait_for_reviews(session)
    mine = _candidate(snapshot)
    assert mine["passed"] is True
    reviews = mine["reviews"]
    assert isinstance(reviews, list)
    assert {item["reviewer"] for item in reviews} == {"fast", "slow"}
    solutions = snapshot["solutions"]
    assert isinstance(solutions, list)
    assert all(item["profile"] is not None for item in solutions)


def test_config_switches_models_and_sets_the_time_limit(tmp_path: Path) -> None:
    built: list[str] = []

    def build(spec: str) -> ScriptedAgent:
        built.append(spec)
        cli, model, effort = spec.split(":")
        agent = ScriptedAgent(f"{cli}-{model}-{effort}", [_CORRECT], tokens=1)
        agent.timeout_s = 1
        return agent

    opus = ScriptedAgent("claude-opus", [_CORRECT], tokens=1)
    opus.model = "opus"
    opus.timeout_s = 300
    author = ScriptedAgent("author", [], tokens=1)
    author.timeout_s = 1
    session = RunSession(
        [opus],
        author,
        attempts=1,
        timeout_s=300,
        author_timeout_s=900,
        review_timeout_s=300,
        review=False,
        out_root=tmp_path,
        catalog={"claude": ["opus", "haiku"]},
        build=build,
    )
    config = session.config()
    assert [(row["model"], row["enabled"], row["lineup"]) for row in config["models"]] == [
        ("opus", True, True),
        ("haiku", False, False),
    ]
    assert {prompt["id"] for prompt in config["prompts"]} == {"solver", "retry", "author", "review"}
    assert config["timeout_s"] == 300
    assert config["author_timeout_s"] == 900
    assert config["review_timeout_s"] == 300
    assert author.timeout_s == 900
    assert opus.timeout_s == 300
    assert opus.review_timeout_s == 300
    session.configure(
        {
            "timeout_s": 120,
            "author_timeout_s": 600,
            "review_timeout_s": 180,
            "models": [
                {"cli": "claude", "model": "opus", "enabled": False},
                {"cli": "claude", "model": "haiku", "enabled": True, "effort": "low", "review_effort": "medium"},
            ],
        }
    )
    assert built == ["claude:haiku:low"]
    snapshot = session.snapshot()
    assert snapshot["lineup"] == ["claude-haiku-low"]
    assert snapshot["timeout_s"] == 120
    assert snapshot["author_timeout_s"] == 600
    assert snapshot["review_timeout_s"] == 180
    assert author.timeout_s == 600
    haiku = session._agents[0]
    assert haiku.timeout_s == 120
    assert haiku.review_timeout_s == 180
    assert haiku.review_effort == "medium"
    assert next(row for row in session.config()["models"] if row["model"] == "haiku")["review_effort"] == "medium"
    for bad in (
        {"timeout_s": 5},
        {"author_timeout_s": 5},
        {"review_timeout_s": 4000},
        {"models": [{"cli": "claude", "model": "haiku", "enabled": False}]},
    ):
        try:
            session.configure(bad)
        except ValueError:
            pass
        else:
            raise AssertionError(bad)
    session.start(_TASK)
    done = _wait(session)
    assert [item["agent"] for item in done["attempts"]] == ["claude-haiku-low"]
    assert done["attempts"][0]["finished_at"] >= done["attempts"][0]["started_at"]
    assert done["timings"]["solving"]["end"] >= done["timings"]["solving"]["start"]


def _author_check(session: RunSession) -> dict[str, object] | None:
    rows = [row for row in session.snapshot()["preflight"] if row["role"] == "test author"]
    assert len(rows) <= 1
    return rows[0] if rows else None


def _wait_author(session: RunSession, name: str) -> dict[str, object]:
    deadline = time.monotonic() + 10
    while time.monotonic() < deadline:
        row = _author_check(session)
        if row is not None and row["agent"] == name and row["state"] == "ready":
            return row
        time.sleep(0.02)
    raise AssertionError(_author_check(session))


def test_config_can_switch_the_test_author(tmp_path: Path) -> None:
    built: list[str] = []

    def build(spec: str) -> ScriptedAgent:
        built.append(spec)
        cli, model, effort = spec.split(":")
        agent = ScriptedAgent(f"{cli}-{model}-{effort}", [_CORRECT], tokens=1)
        agent.model = model
        agent.effort = effort
        agent.timeout_s = 1
        return agent

    author = ScriptedAgent("claude-opus-high", [_CORRECT], tokens=1)
    author.model = "opus"
    author.effort = "high"
    author.timeout_s = 900
    opus = ScriptedAgent("claude-opus-medium", [_CORRECT], tokens=1)
    opus.model = "opus"
    opus.timeout_s = 300
    session = RunSession(
        [opus],
        author,
        attempts=1,
        timeout_s=300,
        author_timeout_s=900,
        review_timeout_s=300,
        review=False,
        out_root=tmp_path,
        catalog={"claude": ["opus", "sonnet"], "codex": ["gpt-6.1-sol"], "grok": ["grok-4.7"]},
        build=build,
    )
    view = session.config()["author"]
    assert isinstance(view, dict)
    assert (view["cli"], view["model"], view["effort"]) == ("claude", "opus", "high")
    session.check()
    _wait_author(session, "claude-opus-high")
    session.configure(
        {
            "models": [{"cli": "claude", "model": "opus", "enabled": True}],
            "author": {"cli": "codex", "model": "gpt-6.1-sol", "effort": "xhigh"},
        }
    )
    assert built == ["codex:gpt-6.1-sol:xhigh"]
    chosen = session._test_author
    assert chosen is not None
    assert chosen.name == "codex-gpt-6.1-sol-xhigh"
    assert chosen.timeout_s == 900
    assert opus.timeout_s == 300
    _wait_author(session, "codex-gpt-6.1-sol-xhigh")
    session.configure({"author": {"cli": "codex", "model": "gpt-6.1-sol", "effort": "xhigh"}})
    assert built == ["codex:gpt-6.1-sol:xhigh"]
    for bad in (
        {"author": {"cli": "codex", "model": "gpt-6.1-sol", "effort": "turbo"}},
        {"author": {"cli": "codex", "model": "missing", "effort": "high"}},
        {"author": {"cli": "grok", "model": "grok-4.7"}},
        {"author": "codex"},
    ):
        with pytest.raises(ValueError):
            session.configure(bad)
    assert session._test_author is chosen
    session.configure({"author": None})
    assert session._test_author is None
    assert _author_check(session) is None


class FlakyReviewer(ScriptedAgent):
    def __init__(self, name: str, sources: list[str], tokens: int) -> None:
        super().__init__(name, sources, tokens)
        self.reviews = 0

    def complete(self, *, cwd: str, prompt: str, session_id: str | None, role: str) -> AgentResult:
        result = super().complete(cwd=cwd, prompt=prompt, session_id=session_id, role=role)
        if role != "review":
            return result
        self.reviews += 1
        return result if self.reviews > 1 else AgentResult(True, "not a review", None, result.usage, 1, None, None, {})


def test_a_failed_review_can_be_retried_once_the_run_is_done(tmp_path: Path) -> None:
    flaky = FlakyReviewer("flaky", [_CORRECT], tokens=10)
    session = RunSession(
        [ScriptedAgent("solid", [_CORRECT], tokens=10), flaky],
        ScriptedAgent("author", [], tokens=1),
        attempts=1,
        timeout_s=30,
        review=True,
        out_root=tmp_path,
    )
    session.start(_TASK)
    assert _wait(session)["phase"] == "done"
    failed = next(item for item in session.snapshot()["reviews"] if item["reviewer"] == "flaky")
    assert failed["state"] == "failed"
    assert failed["summary"] == "The reply did not match the review format."
    done = next(item for item in session.snapshot()["reviews"] if item["reviewer"] == "solid")
    with pytest.raises(RuntimeError, match="Only a failed review"):
        session.retry_review("solid", done["author"], 1)
    session.retry_review("flaky", "solid", 1)
    deadline = time.monotonic() + 10
    while True:
        review = next(item for item in session.snapshot()["reviews"] if item["reviewer"] == "flaky")
        if review["state"] == "done" or time.monotonic() > deadline:
            break
        time.sleep(0.02)
    assert review["state"] == "done"
    assert review["score"] is not None
    solid = next(item for item in session.snapshot()["solutions"] if item["agent"] == "solid")
    assert solid["review"] is not None
