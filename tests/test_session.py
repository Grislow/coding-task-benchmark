import time
from pathlib import Path

from test_benchmark import ScriptedAgent, SleepySolver, _CORRECT, _TASK, _WRONG

from ctb.models import AgentResult
from ctb.session import RunSession


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
    assert snapshot["candidate"] is None
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


def _candidate(snapshot: dict[str, object]) -> dict[str, object]:
    row = snapshot["candidate"]
    assert isinstance(row, dict)
    return row


def _wait_for_reviews(session: RunSession, timeout_s: float = 30) -> dict[str, object]:
    deadline = time.monotonic() + timeout_s
    snapshot = session.snapshot()
    while time.monotonic() < deadline:
        row = snapshot["candidate"]
        reviews = row["reviews"] if isinstance(row, dict) else None
        profile = row.get("profile") if isinstance(row, dict) else None
        if (
            snapshot["phase"] in {"done", "error"}
            and isinstance(reviews, list)
            and len(reviews) == 2
            and profile is not None
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
    deadline = time.monotonic() + 0.4
    while time.monotonic() < deadline:
        time.sleep(0.05)
    mine = _candidate(session.snapshot())
    assert mine["passed"] is True
    assert mine["reviews"] == []
    assert mine["profile"] is not None


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
                {"cli": "claude", "model": "haiku", "enabled": True, "effort": "low"},
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
