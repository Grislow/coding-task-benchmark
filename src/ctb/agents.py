import os
import shutil
import subprocess
import time
from collections.abc import Callable
from pathlib import Path

from ctb.models import AgentResult, TokenUsage
from ctb.prompts import RUBRIC_SCHEMA
from ctb.usage import result_from_codex_jsonl, result_from_stdout

# --bare skips keychain and OAuth. --safe-mode keeps the signed-in subscription
# and drops skills, hooks, plugins, and CLAUDE.md so the user's setup does not solve the task.
_CLAUDE_SOLVE_TOOLS = "Bash,Read,Edit,Write"
_GROK_SOLVE_TOOLS = "read_file,grep,list_dir,search_replace,write,run_terminal_cmd"


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
        command = claude_command(
            prompt, session_id, role, self.budget_usd, self.model, self.effort
        )
        return _invoke(command, Path(cwd), os.environ.copy(), self.timeout_s, result_from_stdout)


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
        command = grok_command(prompt, Path(cwd), session_id, role, self.model, self.effort)
        env = os.environ.copy()
        env["GROK_CLAUDE_SKILLS_ENABLED"] = "false"
        env["GROK_CURSOR_SKILLS_ENABLED"] = "false"
        return _invoke(command, Path(cwd), env, self.timeout_s, result_from_stdout)


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
        schema_path = None
        if role == "review":
            schema_path = Path(cwd) / "rubric.schema.json"
            schema_path.write_text(RUBRIC_SCHEMA)
        command = codex_command(
            prompt, Path(cwd), session_id, role, self.model, schema_path, self.effort
        )
        return _invoke(command, Path(cwd), os.environ.copy(), self.timeout_s, result_from_codex_jsonl)


def agent_name(cli: str, model: str | None, effort: str | None = None) -> str:
    parts = [cli]
    if model is not None:
        parts.append(_model_slug(model))
    if effort:
        parts.append(effort)
    return "-".join(parts)


def claude_command(
    prompt: str,
    session_id: str | None,
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
    if session_id:
        command.extend(["--resume", session_id])
    return command


def grok_command(
    prompt: str,
    cwd: Path,
    session_id: str | None,
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
                "write,search_replace,run_terminal_cmd",
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
    if session_id:
        command.extend(["-r", session_id])
    return command


def codex_command(
    prompt: str,
    cwd: Path,
    session_id: str | None,
    role: str,
    model: str | None,
    schema_path: Path | None,
    effort: str | None = None,
) -> list[str]:
    # `codex exec resume` has no --sandbox flag. Later attempts bypass approvals
    # so a permission prompt cannot hang the process. The first attempt uses
    # --approve-for-me, which runs in workspace-write and cannot take --sandbox.
    if session_id:
        command = [
            "codex",
            "exec",
            "resume",
            "--json",
            "--skip-git-repo-check",
            "--ignore-user-config",
            "--ignore-rules",
            "--dangerously-bypass-approvals-and-sandbox",
        ]
        _append_model(command, "-m", model)
        _append_effort(command, effort, codex=True)
        if schema_path is not None:
            command.extend(["--output-schema", str(schema_path.resolve())])
        command.extend([session_id, prompt])
        return command
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
    try:
        completed = subprocess.run(
            command,
            cwd=cwd,
            env=env,
            text=True,
            capture_output=True,
            timeout=timeout_s,
            check=False,
        )
    except subprocess.TimeoutExpired as exc:
        wall_ms = int((time.perf_counter() - started) * 1000)
        stdout = exc.stdout if isinstance(exc.stdout, str) else ""
        stderr = exc.stderr if isinstance(exc.stderr, str) else ""
        return parse(stdout, f"{stderr}\nTimed out after {timeout_s}s.", 124, wall_ms)
    wall_ms = int((time.perf_counter() - started) * 1000)
    return parse(completed.stdout, completed.stderr, completed.returncode, wall_ms)


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
