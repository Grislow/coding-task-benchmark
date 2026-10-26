import json
import re
import shutil
import subprocess
from concurrent.futures import ThreadPoolExecutor

from ctb.models import CodingAgent
from ctb.run.workspace import make_workspace, scratch_dir, setup_error

TASK = "# Preflight\n\nWrite `solution()` that takes no arguments and returns 1.\n"
PROMPT = "Read task.md, then edit solution.py so it does what the task says. Reply with one word: done."
CLIS = ("claude", "codex", "grok")


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


def installed_clis() -> frozenset[str]:
    return frozenset(cli for cli in CLIS if shutil.which(cli) is not None)


def model_catalog() -> dict[str, list[str]]:
    installed = installed_clis()
    catalog: dict[str, list[str]] = {}
    if "claude" in installed:
        catalog["claude"] = list(CLAUDE_MODELS)
    if "codex" in installed:
        catalog["codex"] = _codex_models()
    if "grok" in installed:
        catalog["grok"] = _grok_models()
    return catalog


def _codex_models() -> list[str]:
    output = _output(["codex", "debug", "models"])
    try:
        models = json.loads(output).get("models", [])
    except (ValueError, AttributeError):
        return []
    return [item["slug"] for item in models if item.get("visibility") == "list" and item.get("slug")]


def _grok_models() -> list[str]:
    return re.findall(r"^\s*[-*]\s+(\S+)", _output(["grok", "models"]), flags=re.MULTILINE)


def _output(command: list[str]) -> str:
    if shutil.which(command[0]) is None:
        return ""
    try:
        completed = subprocess.run(command, capture_output=True, text=True, timeout=30, check=False)
    except subprocess.TimeoutExpired:
        return ""
    return completed.stdout
