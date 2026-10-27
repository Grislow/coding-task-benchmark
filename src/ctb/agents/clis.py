import os
import shutil
import signal
import subprocess
import time
from collections.abc import Callable
from pathlib import Path

from ctb.agents.usage import (
    result_from_codex_jsonl,
    result_from_gemini_json,
    result_from_stdout,
)
from ctb.models import AgentResult, TokenUsage
from ctb.run.prompts import RUBRIC_SCHEMA, deadline_note, wrap_up_s

# --bare skips keychain and OAuth. --safe-mode keeps the signed-in subscription
# and drops skills, hooks, plugins, and CLAUDE.md so the user's setup does not solve the task.
_CLAUDE_SOLVE_TOOLS = "Bash,Read,Edit,Write"
_GROK_SOLVE_TOOLS = "read_file,grep,list_dir,search_replace,write,run_terminal_cmd"
_GROK_ALL_TOOLS = (
    "run_terminal_command,read_file,search_replace,list_dir,grep,write,kill_command_or_subagent,todo_write,"
    "get_command_or_subagent_output,scheduler_create,scheduler_delete,scheduler_list,monitor,search_tool,use_tool,"
    "workflow,enter_plan_mode,exit_plan_mode,ask_user_question,send_feedback,image_gen,image_edit,image_to_video,"
    "reference_to_video"
)

# Levels each CLI documents. A model can still reject a level its own menu omits.
EFFORTS = {
    "claude": frozenset({"low", "medium", "high", "xhigh", "max"}),
    "grok": frozenset({"low", "medium", "high", "xhigh"}),
    "codex": frozenset({"low", "medium", "high", "xhigh", "max", "ultra"}),
}


class ClaudeAgent:
    def __init__(
        self,
        timeout_s: int,
        budget_usd: float,
        model: str | None = None,
        effort: str | None = None,
    ) -> None:
        self.name = agent_name("claude", model, effort)
        self.model = model
        self.effort = effort
        self.timeout_s = timeout_s
        self.budget_usd = budget_usd

    def complete(
        self,
        *,
        cwd: str,
        prompt: str,
        session_id: str | None,
        role: str,
    ) -> AgentResult:
        if shutil.which("claude") is None:
            return _missing(self.name)
        limit = _role_timeout(self, role)
        del session_id
        command = claude_command(deadline_note(limit, role) + prompt, role, self.budget_usd, self.model, _role_effort(self, role))
        return _invoke(command, Path(cwd), os.environ.copy(), limit, result_from_stdout)


class GrokAgent:
    def __init__(self, timeout_s: int, model: str | None = None, effort: str | None = None) -> None:
        self.name = agent_name("grok", model, effort)
        self.model = model
        self.effort = effort
        self.timeout_s = timeout_s

    def complete(
        self,
        *,
        cwd: str,
        prompt: str,
        session_id: str | None,
        role: str,
    ) -> AgentResult:
        if shutil.which("grok") is None:
            return _missing(self.name)
        limit = _role_timeout(self, role)
        del session_id
        command = grok_command(deadline_note(limit, role) + prompt, Path(cwd), role, self.model, _role_effort(self, role))
        env = os.environ.copy()
        env["GROK_CLAUDE_SKILLS_ENABLED"] = "false"
        env["GROK_CURSOR_SKILLS_ENABLED"] = "false"
        return _invoke(command, Path(cwd), env, limit, result_from_stdout)


class CodexAgent:
    def __init__(self, timeout_s: int, model: str | None = None, effort: str | None = None) -> None:
        self.name = agent_name("codex", model, effort)
        self.model = model
        self.effort = effort
        self.timeout_s = timeout_s

    def complete(
        self,
        *,
        cwd: str,
        prompt: str,
        session_id: str | None,
        role: str,
    ) -> AgentResult:
        if shutil.which("codex") is None:
            return _missing(self.name)
        limit = _role_timeout(self, role)
        schema_path = None
        if role == "review":
            schema_path = Path(cwd) / "rubric.schema.json"
            schema_path.write_text(RUBRIC_SCHEMA)
        del session_id
        command = codex_command(deadline_note(limit, role) + prompt, Path(cwd), role, self.model, schema_path, _role_effort(self, role))
        return _invoke(command, Path(cwd), os.environ.copy(), limit, result_from_codex_jsonl)


class GeminiAgent:
    def __init__(self, timeout_s: int, model: str | None = None) -> None:
        self.name = agent_name("gemini", model)
        self.model = model
        self.effort = None
        self.timeout_s = timeout_s

    def complete(
        self,
        *,
        cwd: str,
        prompt: str,
        session_id: str | None,
        role: str,
    ) -> AgentResult:
        if shutil.which("gemini") is None:
            return _missing(self.name)
        limit = _role_timeout(self, role)
        del session_id
        command = gemini_command(deadline_note(limit, role) + prompt, role, self.model)
        return _invoke(command, Path(cwd), os.environ.copy(), limit, result_from_gemini_json)


def _role_effort(agent: object, role: str) -> str | None:
    if role == "review" and getattr(agent, "review_effort", None):
        return agent.review_effort
    return getattr(agent, "effort", None)


def _role_timeout(agent: object, role: str) -> int:
    if role == "review":
        review = getattr(agent, "review_timeout_s", None)
        if isinstance(review, int) and not isinstance(review, bool):
            return review
    return int(agent.timeout_s)


def agent_name(cli: str, model: str | None, effort: str | None = None) -> str:
    parts = [cli]
    if model is not None:
        parts.append(_model_slug(model))
    if effort:
        parts.append(effort)
    return "-".join(parts)


def claude_command(
    prompt: str,
    role: str,
    budget_usd: float,
    model: str | None = None,
    effort: str | None = None,
) -> list[str]:
    command = [
        "claude",
        "-p",
        prompt,
        "--output-format",
        "json",
        "--permission-prompts",
        "none",
        "--safe-mode",
        "--disable-slash-commands",
        "--strict-mcp-config",
        "--max-budget-usd",
        f"{budget_usd:g}",
    ]
    if role == "review":
        command.extend(["--tools", "", "--json-schema", RUBRIC_SCHEMA])
    else:
        command.extend(
            ["--permission-mode", "bypassPermissions", "--tools", _CLAUDE_SOLVE_TOOLS]
        )
    _append_model(command, "--model", model)
    _append_effort(command, effort)
    return command


def grok_command(
    prompt: str,
    cwd: Path,
    role: str,
    model: str | None = None,
    effort: str | None = None,
) -> list[str]:
    command = [
        "grok",
        "-p",
        prompt,
        "--output-format",
        "json",
        "--cwd",
        str(cwd.resolve()),
        "--no-subagents",
        "--disable-web-search",
    ]
    if role == "review":
        command.extend(
            [
                "--max-turns",
                "2",
                "--sandbox",
                "read-only",
                "--json-schema",
                RUBRIC_SCHEMA,
                "--disallowed-tools",
                _GROK_ALL_TOOLS,
            ]
        )
    else:
        command.extend(
            [
                "--max-turns",
                "25",
                "--sandbox",
                "strict",
                "--always-approve",
                "--tools",
                _GROK_SOLVE_TOOLS,
            ]
        )
    _append_model(command, "-m", model)
    _append_effort(command, effort)
    return command


def gemini_command(prompt: str, role: str, model: str | None = None) -> list[str]:
    command = ["gemini", "-p", prompt, "--output-format", "json", "--skip-trust", "--extensions", "none"]
    command.extend(["--approval-mode", "plan" if role == "review" else "yolo"])
    _append_model(command, "-m", model)
    return command


def codex_command(
    prompt: str,
    cwd: Path,
    role: str,
    model: str | None,
    schema_path: Path | None,
    effort: str | None = None,
) -> list[str]:
    command = [
        "codex",
        "exec",
        "--json",
        "-C",
        str(cwd.resolve()),
        "--skip-git-repo-check",
        "--ignore-user-config",
        "--ignore-rules",
    ]
    if role == "review":
        command.extend(["--sandbox", "read-only"])
    else:
        command.append("--approve-for-me")
    _append_model(command, "-m", model)
    _append_effort(command, effort, codex=True)
    if schema_path is not None:
        command.extend(["--output-schema", str(schema_path.resolve())])
    command.append(prompt)
    return command


def _append_model(command: list[str], flag: str, model: str | None) -> None:
    if model:
        command.extend([flag, model])


def _append_effort(command: list[str], effort: str | None, *, codex: bool = False) -> None:
    if not effort:
        return
    if codex:
        # --ignore-user-config drops model_reasoning_effort from the user config.
        # The value is TOML, so the level is a quoted string.
        command.extend(["-c", f'model_reasoning_effort="{effort}"'])
        return
    command.extend(["--effort", effort])


def _model_slug(model: str) -> str:
    cleaned = []
    for character in model.lower():
        if character.isalnum() or character in "._-":
            cleaned.append(character)
        else:
            cleaned.append("-")
    slug = "".join(cleaned).strip("-")
    if not slug:
        raise ValueError(f"Model '{model}' has no usable name.")
    return slug


def _invoke(
    command: list[str],
    cwd: Path,
    env: dict[str, str],
    timeout_s: int,
    parse: Callable[[str, str, int, int], AgentResult],
) -> AgentResult:
    started = time.perf_counter()
    _plant_clock(cwd, timeout_s)
    process = subprocess.Popen(
        command,
        cwd=cwd,
        env=env,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        start_new_session=True,
    )
    try:
        stdout, stderr = process.communicate(timeout=timeout_s)
    except subprocess.TimeoutExpired:
        os.killpg(process.pid, signal.SIGKILL)
        stdout, stderr = process.communicate()
        wall_ms = int((time.perf_counter() - started) * 1000)
        return parse(stdout or "", f"{stderr or ''}\nTimed out after {timeout_s}s.", 124, wall_ms)
    wall_ms = int((time.perf_counter() - started) * 1000)
    return parse(stdout, stderr, process.returncode, wall_ms)


def _plant_clock(cwd: Path, timeout_s: int) -> None:
    deadline = int(time.time()) + timeout_s
    script = cwd / "time-left"
    script.write_text(
        f"#!/bin/sh\nleft=$(( {deadline} - $(date +%s) ))\necho \"$left seconds left\"\n"
        f"if [ \"$left\" -le {wrap_up_s(timeout_s)} ]; then echo \"Wrap up now: stop exploring and leave your files in their final state.\"; fi\n"
    )
    script.chmod(0o755)


def _missing(name: str) -> AgentResult:
    return AgentResult(
        ok=False,
        text="",
        session_id=None,
        usage=TokenUsage(),
        wall_ms=0,
        cost_usd=None,
        error=f"{name} is not on PATH",
        raw={},
    )
