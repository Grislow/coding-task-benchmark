import shutil
import subprocess
from concurrent.futures import ThreadPoolExecutor

from ctb.models import CodingAgent
from ctb.workspace import make_workspace, scratch_dir, setup_error

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
