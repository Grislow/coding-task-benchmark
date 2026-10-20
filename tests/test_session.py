import time
from pathlib import Path

from test_benchmark import ScriptedAgent, SleepySolver, _CORRECT, _TASK, _WRONG

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
