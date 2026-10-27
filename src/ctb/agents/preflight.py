import json
import re
import shutil
import subprocess
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from ctb.models import CodingAgent
from ctb.run.workspace import make_workspace, scratch_dir, setup_error

TASK = "# Preflight\n\nWrite `solution()` that takes no arguments and returns 1.\n"
PROMPT = "Read task.md, then edit solution.py so it does what the task says. Reply with one word: done."
CLIS = ("claude", "codex", "grok", "gemini")


def check_agent(agent: CodingAgent) -> str | None:
    scratch = scratch_dir("check-")
    try:
        workspace = scratch / "work" / agent.name
        make_workspace(workspace, TASK)
        result = agent.complete(cwd=str(workspace), prompt=PROMPT, session_id=None, role="solve")
        source = (workspace / "solution.py").read_text()
        problem = setup_error(result, source)
        if problem is not None:
            return problem
        if not result.ok:
            return result.error or "The agent exited with an error."
        return None
    finally:
        shutil.rmtree(scratch, ignore_errors=True)


def check_all(agents: list[CodingAgent]) -> list[str | None]:
    if not agents:
        return []
    with ThreadPoolExecutor(max_workers=len(agents)) as pool:
        return list(pool.map(check_agent, agents))


def cli_versions() -> dict[str, str]:
    versions = {}
    for cli in CLIS:
        if shutil.which(cli) is None:
            versions[cli] = "not on PATH"
            continue
        completed = subprocess.run([cli, "--version"], capture_output=True, text=True, timeout=30, check=False)
        output = (completed.stdout or completed.stderr).strip()
        versions[cli] = output.splitlines()[0] if output else f"exited {completed.returncode}"
    return versions


CLAUDE_MODELS = ("fable", "opus", "sonnet", "haiku")
GEMINI_MODELS = ("gemini-3.1-pro-preview", "gemini-3-pro-preview", "gemini-3.8-flash", "gemini-3.5-flash", "gemini-2.5-pro")


def installed_clis() -> frozenset[str]:
    return frozenset(cli for cli in CLIS if shutil.which(cli) is not None)


def model_catalog() -> dict[str, dict[str, list[str]]]:
    installed = installed_clis()
    catalog: dict[str, dict[str, list[str]]] = {}
    if "claude" in installed:
        catalog["claude"] = {model: [] for model in CLAUDE_MODELS}
    if "codex" in installed:
        catalog["codex"] = _codex_models()
    if "grok" in installed:
        catalog["grok"] = _grok_models()
    if "gemini" in installed:
        catalog["gemini"] = {model: [] for model in GEMINI_MODELS}
    return catalog


def _codex_models() -> dict[str, list[str]]:
    output = _output(["codex", "debug", "models"])
    try:
        models = json.loads(output).get("models", [])
    except (ValueError, AttributeError):
        return {}
    return {
        item["slug"]: [level["effort"] for level in item.get("supported_reasoning_levels") or [] if level.get("effort")]
        for item in models
        if item.get("visibility") == "list" and item.get("slug")
    }


def _grok_models() -> dict[str, list[str]]:
    try:
        cached = json.loads((Path.home() / ".grok" / "models_cache.json").read_text()).get("models", {})
    except (OSError, ValueError, AttributeError):
        cached = {}
    names = re.findall(r"^\s*[-*]\s+(\S+)", _output(["grok", "models"]), flags=re.MULTILINE)
    return {name: _grok_efforts(cached.get(name)) for name in names}


def _grok_efforts(entry: object) -> list[str]:
    info = entry.get("info", {}) if isinstance(entry, dict) else {}
    return [item["value"] for item in info.get("reasoning_efforts") or [] if isinstance(item, dict) and item.get("value")]


def _output(command: list[str]) -> str:
    if shutil.which(command[0]) is None:
        return ""
    try:
        completed = subprocess.run(command, capture_output=True, text=True, timeout=30, check=False)
    except subprocess.TimeoutExpired:
        return ""
    return completed.stdout
