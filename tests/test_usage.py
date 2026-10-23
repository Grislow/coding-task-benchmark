import json
from pathlib import Path

import pytest

from ctb.agents import agent_name, claude_command, codex_command, grok_command
from ctb.cli import INTERVIEW_AGENTS, INTERVIEW_AUTHOR, _build_agent, _split_agent, main
from ctb.prompts import review_prompt, rubric_rules
from ctb.reviews import parse_review
from ctb.usage import result_from_codex_jsonl, result_from_stdout


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
    solve = claude_command("Solve the task", None, "solve", 2)
    assert "--safe-mode" in solve
    assert "--bare" not in solve
    assert "bypassPermissions" in solve
    assert "--resume" not in solve
    assert "--effort" not in solve

    resumed = claude_command("Fix it", "abc", "solve", 2)
    assert resumed[resumed.index("--resume") + 1] == "abc"

    review = claude_command("Grade", None, "review", 2)
    assert review[review.index("--tools") + 1] == ""
    assert "bypassPermissions" not in review

    grok = grok_command("Solve", Path("/tmp/task"), None, "solve")
    assert grok[grok.index("--sandbox") + 1] == "strict"
    assert "--always-approve" in grok
    assert "--disable-web-search" in grok

    grok_review = grok_command("Grade", Path("/tmp/task"), "sid", "review")
    assert grok_review[grok_review.index("--sandbox") + 1] == "read-only"
    assert grok_review[grok_review.index("-r") + 1] == "sid"

    claude_model = claude_command("Solve", None, "solve", 2, "opus")
    assert claude_model[claude_model.index("--model") + 1] == "opus"
    grok_model = grok_command("Solve", Path("/tmp/task"), None, "solve", "grok-4")
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
    opus_cmd = claude_command("Solve", None, "solve", 1, opus.model, opus.effort)
    assert opus_cmd[opus_cmd.index("--effort") + 1] == "medium"
    sonnet_cmd = claude_command("Solve", None, "solve", 1, sonnet.model, sonnet.effort)
    assert sonnet_cmd[sonnet_cmd.index("--effort") + 1] == "high"
    astra_cmd = codex_command("Solve", Path("/tmp/task"), None, "solve", astra.model, None, astra.effort)
    assert astra_cmd[astra_cmd.index("-c") + 1] == 'model_reasoning_effort="high"'
    sol_cmd = codex_command("Again", Path("/tmp/task"), "thread-1", "solve", sol.model, None, sol.effort)
    assert sol_cmd[sol_cmd.index("-c") + 1] == 'model_reasoning_effort="xhigh"'
    assert "--ignore-user-config" in sol_cmd
    grok_cmd = grok_command("Solve", Path("/tmp/task"), None, "solve", grok.model, grok.effort)
    assert grok_cmd[grok_cmd.index("--effort") + 1] == "high"


def test_ui_defaults_match_the_interview_lineup(monkeypatch: pytest.MonkeyPatch) -> None:
    seen: dict[str, object] = {}

    def fake_serve(session: object, port: int) -> int:
        seen["agents"] = [agent.name for agent in session._agents]
        author = session._test_author
        seen["author"] = None if author is None else author.name
        seen["port"] = port
        seen["review"] = session._review
        seen["attempts"] = session._attempts
        seen["timeout"] = session._timeout_s
        return 0

    monkeypatch.setattr("ctb.cli._serve", fake_serve)
    assert main(["ui"]) == 0
    assert seen["agents"] == [_build_agent(name, 600, 3).name for name in INTERVIEW_AGENTS]
    assert seen["author"] == _build_agent(INTERVIEW_AUTHOR, 600, 3).name
    assert seen["port"] == 8765
    assert seen["review"] is True
    assert seen["attempts"] == 3
    assert seen["timeout"] == 600


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


def test_codex_commands_sandbox_the_first_attempt_only() -> None:
    solve = codex_command("Solve", Path("/tmp/task"), None, "solve", "gpt-5.4", None)
    assert solve[:2] == ["codex", "exec"]
    assert "resume" not in solve
    assert "--sandbox" not in solve
    assert "--approve-for-me" in solve
    assert solve[solve.index("-m") + 1] == "gpt-5.4"
    assert "--ignore-user-config" in solve
    assert "-c" not in solve

    review = codex_command("Grade", Path("/tmp/task"), None, "review", None, Path("/tmp/rubric.json"))
    assert review[review.index("--sandbox") + 1] == "read-only"
    assert "--approve-for-me" not in review
    assert review[review.index("--output-schema") + 1] == str(Path("/tmp/rubric.json").resolve())

    resume = codex_command("Fix", Path("/tmp/task"), "thread-1", "solve", "gpt-5.4", None)
    schema = Path("runs/x/work/codex/rubric.schema.json")
    graded = codex_command("Grade", Path("runs/x/work/codex"), None, "review", None, schema)
    assert graded[graded.index("--output-schema") + 1] == str(schema.resolve())

    relative = codex_command("Solve", Path("runs/x/work/codex"), None, "solve", None, None)
    assert relative[relative.index("-C") + 1] == str(Path("runs/x/work/codex").resolve())

    assert resume[2] == "resume"
    assert resume[-2] == "thread-1"
    assert "--sandbox" not in resume
    assert "--dangerously-bypass-approvals-and-sandbox" in resume


def test_grok_cwd_is_absolute() -> None:
    command = grok_command("Solve", Path("runs/x/work/grok"), None, "solve")
    assert command[command.index("--cwd") + 1] == str(Path("runs/x/work/grok").resolve())
