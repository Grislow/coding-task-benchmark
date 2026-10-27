import json
import os
import time
from pathlib import Path

import pytest

from ctb.agents.clis import (
    agent_name,
    claude_command,
    codex_command,
    gemini_command,
    grok_command,
)
from ctb.agents.usage import (
    result_from_codex_jsonl,
    result_from_gemini_json,
    result_from_stdout,
)
from ctb.cli import (
    INTERVIEW_AGENTS,
    INTERVIEW_AUTHOR,
    _build_agent,
    _resolve_author,
    _split_agent,
    main,
)
from ctb.models import AgentResult, TokenUsage
from ctb.run.prompts import review_prompt, rubric_rules
from ctb.run.reviews import parse_review


def test_claude_and_grok_usage_json() -> None:
    claude = result_from_stdout(
        """
        {
          "type": "result",
          "is_error": false,
          "result": "done",
          "session_id": "claude-1",
          "duration_ms": 1500,
          "total_cost_usd": 0.02,
          "usage": {
            "input_tokens": 10,
            "output_tokens": 4,
            "cache_read_input_tokens": 3,
            "cache_creation_input_tokens": 1
          }
        }
        """,
        "",
        0,
        1800,
    )
    assert claude.ok
    assert claude.session_id == "claude-1"
    assert claude.text == "done"
    assert claude.usage.total == 18
    assert claude.cost_usd == 0.02
    assert claude.wall_ms == 1800

    grok = result_from_stdout(
        """
        {
          "text": "shipped",
          "sessionId": "grok-1",
          "usage": {
            "input_tokens": 8,
            "output_tokens": 2,
            "cache_read_input_tokens": 0,
            "cache_creation_input_tokens": 0,
            "reasoning_tokens": 5,
            "total_tokens": 15
          }
        }
        """,
        "",
        0,
        900,
    )
    assert grok.session_id == "grok-1"
    assert grok.usage.total == 15
    assert grok.cost_usd is None


def test_review_json_inside_a_wrapper() -> None:
    finding = {"line": 3, "rule": "PY-STDLIB", "severity": "major", "issue": "Manual count.", "fix": "Counter."}
    note = parse_review(
        json.dumps({"text": json.dumps({"findings": [finding], "summary": "Clear."})}),
        "grok",
        rubric_rules("python"),
        10,
    )
    assert note is not None
    assert note.reviewer == "grok"
    assert note.summary == "Clear."
    assert [item.rule for item in note.findings] == ["PY-STDLIB"]
    assert note.score == 90


def test_review_keeps_only_findings_it_can_check() -> None:
    def item(line: object, rule: str, severity: str = "minor") -> dict[str, object]:
        return {"line": line, "rule": rule, "severity": severity, "issue": "i", "fix": "f"}

    findings = [
        item(2, "PY-NAME"),
        item(2, "PY-NAME", "major"),
        item(0, "PY-NAME"),
        item(9, "PY-NAME"),
        item(3, "MADE-UP"),
        item(4, "API-VALID"),
        item("5", "PY-FLOW"),
        item(5, "CMT-WHAT", "blocker"),
    ]
    note = parse_review(json.dumps({"findings": findings, "summary": ""}), "codex", rubric_rules("python"), 8)
    assert note is not None
    assert [(finding.line, finding.rule) for finding in note.findings] == [(2, "PY-NAME"), (5, "CMT-WHAT")]
    assert note.score == 72


def test_fastapi_rubric_extends_python() -> None:
    assert rubric_rules("python") < rubric_rules("fastapi")
    assert "API-VALID" in rubric_rules("fastapi")
    assert "CMT-WHAT" in review_prompt("task", "def solution():\n    pass\n", "python")
    assert "   1  def solution():" in review_prompt("task", "def solution():\n    pass\n", "python")


def test_headless_commands_keep_solvers_in_bounds() -> None:
    solve = claude_command("Solve the task", "solve", 2)
    assert "--safe-mode" in solve
    assert "--bare" not in solve
    assert "bypassPermissions" in solve
    assert "--resume" not in solve
    assert "--effort" not in solve

    review = claude_command("Grade", "review", 2)
    assert review[review.index("--tools") + 1] == ""
    assert "bypassPermissions" not in review

    grok = grok_command("Solve", Path("/tmp/task"), "solve")
    assert grok[grok.index("--sandbox") + 1] == "strict"
    assert "--always-approve" in grok
    assert "--disable-web-search" in grok

    grok_review = grok_command("Grade", Path("/tmp/task"), "review")
    assert grok_review[grok_review.index("--sandbox") + 1] == "read-only"
    assert "-r" not in grok_review
    removed = grok_review[grok_review.index("--disallowed-tools") + 1].split(",")
    assert {"read_file", "list_dir", "grep", "run_terminal_command", "ask_user_question"} <= set(removed)

    claude_model = claude_command("Solve", "solve", 2, "opus")
    assert claude_model[claude_model.index("--model") + 1] == "opus"
    grok_model = grok_command("Solve", Path("/tmp/task"), "solve", "grok-4")
    assert grok_model[grok_model.index("-m") + 1] == "grok-4"


def test_interview_lineup_is_five_distinct_models() -> None:
    agents = [_build_agent(name, 30, 1) for name in INTERVIEW_AGENTS]
    assert [(agent.name, agent.model, agent.effort) for agent in agents] == [
        ("claude-opus-medium", "opus", "medium"),
        ("claude-sonnet-high", "sonnet", "high"),
        ("codex-gpt-6-astra-high", "gpt-6-astra", "high"),
        ("codex-gpt-6.1-sol-xhigh", "gpt-6.1-sol", "xhigh"),
        ("grok-grok-4.7-high", "grok-4.7", "high"),
    ]
    opus, sonnet, astra, sol, grok = agents
    opus_cmd = claude_command("Solve", "solve", 1, opus.model, opus.effort)
    assert opus_cmd[opus_cmd.index("--effort") + 1] == "medium"
    sonnet_cmd = claude_command("Solve", "solve", 1, sonnet.model, sonnet.effort)
    assert sonnet_cmd[sonnet_cmd.index("--effort") + 1] == "high"
    astra_cmd = codex_command("Solve", Path("/tmp/task"), "solve", astra.model, None, astra.effort)
    assert astra_cmd[astra_cmd.index("-c") + 1] == 'model_reasoning_effort="high"'
    sol_cmd = codex_command("Again", Path("/tmp/task"), "solve", sol.model, None, sol.effort)
    assert sol_cmd[sol_cmd.index("-c") + 1] == 'model_reasoning_effort="xhigh"'
    assert "--ignore-user-config" in sol_cmd
    grok_cmd = grok_command("Solve", Path("/tmp/task"), "solve", grok.model, grok.effort)
    assert grok_cmd[grok_cmd.index("--effort") + 1] == "high"


def test_ui_defaults_match_the_interview_lineup(monkeypatch: pytest.MonkeyPatch) -> None:
    seen: dict[str, object] = {}
    monkeypatch.setattr("ctb.cli.installed_clis", lambda: frozenset({"claude", "codex", "grok", "gemini"}))
    monkeypatch.setattr("ctb.cli.model_catalog", dict)

    def fake_serve(session: object, port: int) -> int:
        seen["agents"] = [agent.name for agent in session._agents]
        author = session._test_author
        seen["author"] = None if author is None else author.name
        seen["port"] = port
        seen["review"] = session._review
        seen["attempts"] = session._attempts
        seen["timeout"] = session._timeout_s
        seen["author_timeout"] = session._author_timeout_s
        seen["review_timeout"] = session._review_timeout_s
        seen["author_limit"] = None if author is None else author.timeout_s
        seen["solve_limits"] = [agent.timeout_s for agent in session._agents]
        seen["review_limits"] = [agent.review_timeout_s for agent in session._agents]
        return 0

    monkeypatch.setattr("ctb.cli._serve", fake_serve)
    assert main(["ui"]) == 0
    assert seen["agents"] == [_build_agent(name, 600, 3).name for name in INTERVIEW_AGENTS]
    assert seen["author"] == _build_agent(INTERVIEW_AUTHOR, 600, 3).name
    assert seen["port"] == 8765
    assert seen["review"] is True
    assert seen["attempts"] == 3
    assert seen["timeout"] == 300
    assert seen["author_timeout"] == 900
    assert seen["review_timeout"] == 300
    assert seen["author_limit"] == 900
    assert seen["solve_limits"] == [300] * 5
    assert seen["review_limits"] == [300] * 5


def test_a_missing_cli_is_left_out_of_the_page(monkeypatch: pytest.MonkeyPatch) -> None:
    seen: dict[str, object] = {}
    monkeypatch.setattr("ctb.cli.installed_clis", lambda: frozenset({"grok"}))
    monkeypatch.setattr("ctb.cli.model_catalog", lambda: {"grok": ["grok-4.7", "grok-4"]})

    def fake_serve(session: object, port: int) -> int:
        del port
        seen["agents"] = [agent.name for agent in session._agents]
        author = session._test_author
        seen["author"] = None if author is None else author.name
        seen["clis"] = {row["cli"] for row in session._models}
        return 0

    monkeypatch.setattr("ctb.cli._serve", fake_serve)
    assert main(["ui"]) == 0
    assert seen["agents"] == ["grok-grok-4.7-high"]
    assert seen["author"] == "grok-grok-4.7-high"
    assert seen["clis"] == {"grok"}


def test_the_test_author_falls_back_through_available_models(monkeypatch: pytest.MonkeyPatch) -> None:
    catalog = {
        "claude": ["opus", "sonnet"],
        "codex": ["gpt-6-astra", "gpt-6.1-sol"],
        "grok": ["grok-4.7", "grok-4"],
    }
    monkeypatch.setattr("ctb.cli.installed_clis", lambda: frozenset({"claude", "codex", "grok"}))
    assert _resolve_author(INTERVIEW_AUTHOR, catalog) == INTERVIEW_AUTHOR
    assert _resolve_author("none", catalog) == "none"
    assert _resolve_author("fake", {}) == "fake"
    assert _resolve_author("grok:grok-4:low", {"grok": ["grok-4", "grok-4.7"]}) == "grok:grok-4:low"
    monkeypatch.setattr("ctb.cli.installed_clis", lambda: frozenset({"codex", "grok"}))
    assert _resolve_author(INTERVIEW_AUTHOR, catalog) == "codex:gpt-6.1-sol:xhigh"
    monkeypatch.setattr("ctb.cli.installed_clis", lambda: frozenset({"grok"}))
    assert _resolve_author(INTERVIEW_AUTHOR, {"grok": ["grok-4.7"]}) == "grok:grok-4.7:high"
    assert _resolve_author(INTERVIEW_AUTHOR, {"grok": ["grok-4"], "codex": ["gpt-6-astra"]}) == "none"


def test_catalog_skips_a_cli_that_is_not_installed(monkeypatch: pytest.MonkeyPatch) -> None:
    from ctb.agents.preflight import model_catalog

    monkeypatch.setattr("ctb.agents.preflight.shutil.which", lambda name: "/bin/grok" if name == "grok" else None)
    monkeypatch.setattr("ctb.agents.preflight._grok_models", lambda: ["grok-4.7"])
    assert model_catalog() == {"grok": ["grok-4.7"]}


def test_agent_entries_can_name_a_model() -> None:
    assert _split_agent("claude:opus") == ("claude", "opus", None)
    assert _split_agent("claude:opus:medium") == ("claude", "opus", "medium")
    assert _split_agent("Codex") == ("codex", None, None)
    assert agent_name("claude", "opus") == "claude-opus"
    assert agent_name("claude", "opus", "medium") == "claude-opus-medium"
    assert agent_name("codex", "gpt-5.4") == "codex-gpt-5.4"
    with pytest.raises(ValueError):
        _build_agent("claude:opus:turbo", 30, 1)
    opus = _build_agent("claude:opus", 30, 1)
    sonnet = _build_agent("claude:sonnet", 30, 1)
    assert opus.name == "claude-opus"
    assert sonnet.name == "claude-sonnet"
    with pytest.raises(ValueError):
        _build_agent("fake:opus", 30, 1)


def test_codex_jsonl_reports_thread_and_split_cache() -> None:
    parsed = result_from_codex_jsonl(
        "\n".join(
            [
                '{"type":"thread.started","thread_id":"thread-1"}',
                '{"type":"error","message":"Reconnecting... 1/5"}',
                '{"type":"item.completed","item":{"id":"item_3","type":"agent_message","text":"shipped"}}',
                '{"type":"turn.completed","usage":{"input_tokens":100,"cached_input_tokens":40,"output_tokens":10}}',
                '{"type":"turn.completed","usage":{"input_tokens":20,"cached_input_tokens":0,"output_tokens":5}}',
            ]
        ),
        "",
        0,
        500,
    )
    assert parsed.ok
    assert parsed.session_id == "thread-1"
    assert parsed.text == "shipped"
    assert parsed.usage.input_tokens == 80
    assert parsed.usage.cache_read_tokens == 40
    assert parsed.usage.output_tokens == 15
    assert parsed.usage.total == 135

    failed = result_from_codex_jsonl(
        '{"type":"turn.failed","error":{"message":"stream ended"}}',
        "",
        0,
        10,
    )
    assert not failed.ok
    assert failed.error == "stream ended"


def test_codex_commands_always_run_sandboxed() -> None:
    solve = codex_command("Solve", Path("/tmp/task"), "solve", "gpt-5.4", None)
    assert solve[:2] == ["codex", "exec"]
    assert "resume" not in solve
    assert "--sandbox" not in solve
    assert "--approve-for-me" in solve
    assert solve[solve.index("-m") + 1] == "gpt-5.4"
    assert "--ignore-user-config" in solve
    assert "-c" not in solve

    review = codex_command("Grade", Path("/tmp/task"), "review", None, Path("/tmp/rubric.json"))
    assert review[review.index("--sandbox") + 1] == "read-only"
    assert "--approve-for-me" not in review
    assert review[review.index("--output-schema") + 1] == str(Path("/tmp/rubric.json").resolve())

    schema = Path("runs/x/work/codex/rubric.schema.json")
    graded = codex_command("Grade", Path("runs/x/work/codex"), "review", None, schema)
    assert graded[graded.index("--output-schema") + 1] == str(schema.resolve())

    relative = codex_command("Solve", Path("runs/x/work/codex"), "solve", None, None)
    assert relative[relative.index("-C") + 1] == str(Path("runs/x/work/codex").resolve())



def test_grok_cwd_is_absolute() -> None:
    command = grok_command("Solve", Path("runs/x/work/grok"), "solve")
    assert command[command.index("--cwd") + 1] == str(Path("runs/x/work/grok").resolve())


def test_a_review_uses_its_own_limit(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    from ctb.agents.clis import ClaudeAgent

    seen: dict[str, int] = {}
    seen_prompt: dict[str, str] = {}

    def fake_invoke(command: list[str], cwd: Path, env: dict[str, str], timeout_s: int, parse: object) -> AgentResult:
        del cwd, env, parse
        seen["timeout"] = timeout_s
        seen_prompt["text"] = command[2]
        seen_prompt["effort"] = command[command.index("--effort") + 1]
        return AgentResult(True, "", None, TokenUsage(), 1, None, None, {})

    monkeypatch.setattr("ctb.agents.clis._invoke", fake_invoke)
    monkeypatch.setattr("ctb.agents.clis.shutil.which", lambda _name: "claude")
    agent = ClaudeAgent(300, 1.0, "opus", "medium")
    agent.review_timeout_s = 180
    agent.complete(cwd=str(tmp_path), prompt="Solve", session_id=None, role="solve")
    assert seen["timeout"] == 300
    assert seen_prompt["text"].startswith("You have 5 minutes.")
    assert "sh time-left" in seen_prompt["text"]
    assert seen_prompt["text"].endswith("Solve")
    agent.complete(cwd=str(tmp_path), prompt="Grade", session_id=None, role="review")
    assert seen["timeout"] == 180
    assert seen_prompt["text"].startswith("You have 3 minutes.")
    assert "time-left" not in seen_prompt["text"]
    assert seen_prompt["effort"] == "medium"
    agent.review_effort = "low"
    agent.complete(cwd=str(tmp_path), prompt="Grade", session_id=None, role="review")
    assert seen_prompt["effort"] == "low"
    agent.complete(cwd=str(tmp_path), prompt="Solve", session_id=None, role="solve")
    assert seen_prompt["effort"] == "medium"
    author = ClaudeAgent(900, 1.0, "opus", "high")
    author.review_timeout_s = 300
    author.complete(cwd=str(tmp_path), prompt="Write tests", session_id=None, role="author")
    assert seen["timeout"] == 900
    assert seen_prompt["text"].startswith("You have 15 minutes.")


def test_time_left_reports_the_seconds_remaining(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    import subprocess
    from time import time as real_time

    from ctb.agents.clis import _plant_clock
    from ctb.run.prompts import wrap_up_s

    _plant_clock(tmp_path, 600)
    completed = subprocess.run(["sh", str(tmp_path / "time-left")], capture_output=True, text=True, check=True)
    left = int(completed.stdout.split()[0])
    assert 590 <= left <= 600
    assert "Wrap up" not in completed.stdout
    monkeypatch.setattr("ctb.agents.clis.time.time", lambda: real_time() - 550)
    _plant_clock(tmp_path, 600)
    completed = subprocess.run(["sh", str(tmp_path / "time-left")], capture_output=True, text=True, check=True)
    assert "Wrap up now" in completed.stdout
    assert [wrap_up_s(limit) for limit in (30, 90, 300, 900)] == [10, 30, 60, 180]


def test_a_timeout_stops_the_agent_and_its_children(tmp_path: Path) -> None:
    from ctb.agents.clis import _invoke

    marker = tmp_path / "child.pid"
    started = time.perf_counter()
    result = _invoke(
        ["sh", "-c", f"sleep 30 & echo $! > {marker}; wait"],
        tmp_path,
        dict(os.environ),
        1,
        lambda stdout, stderr, code, wall_ms: AgentResult(False, stdout, None, TokenUsage(), wall_ms, None, stderr, {}),
    )
    assert time.perf_counter() - started < 10
    assert "Timed out after 1s." in (result.error or "")
    child = int(marker.read_text())
    time.sleep(0.2)
    try:
        os.kill(child, 0)
    except ProcessLookupError:
        pass
    else:
        raise AssertionError("the child kept running")


def test_gemini_runs_headless_and_reads_its_json() -> None:
    solve = gemini_command("Solve", "solve", "gemini-3.1-pro-preview")
    assert solve[:3] == ["gemini", "-p", "Solve"]
    assert solve[solve.index("--approval-mode") + 1] == "yolo"
    assert solve[solve.index("-m") + 1] == "gemini-3.1-pro-preview"
    assert gemini_command("Review", "review")[gemini_command("Review", "review").index("--approval-mode") + 1] == "plan"
    done = result_from_gemini_json(
        '{"response": "done", "stats": {"models": {"gemini-3.1-pro-preview": {"tokens": {"prompt": 100, "candidates": 20, "cached": 40, "thoughts": 5}}}}}',
        "",
        0,
        9,
    )
    assert (done.ok, done.text, done.usage.input_tokens, done.usage.cache_read_tokens, done.usage.output_tokens) == (True, "done", 60, 40, 20)
    login = result_from_gemini_json("", '{"session_id": "s", "error": {"type": "Error", "message": "Please set an Auth method", "code": 41}}', 41, 9)
    assert not login.ok
    assert login.error == "Please set an Auth method"
    with pytest.raises(ValueError, match="unknown reasoning level"):
        _build_agent("gemini:gemini-3.5-flash:high", 30, 1)
