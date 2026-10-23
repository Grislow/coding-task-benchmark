import subprocess
import tempfile
from pathlib import Path

from ctb.models import AgentResult
from ctb.prompts import SOLUTION_STUB

TIMED_OUT = "Timed out after"


def make_workspace(path: Path, task_text: str) -> None:
    path.mkdir(parents=True, exist_ok=True)
    (path / "task.md").write_text(task_text)
    (path / "solution.py").write_text(SOLUTION_STUB)
    subprocess.run(
        ["git", "init", "-q"],
        cwd=path,
        check=True,
        capture_output=True,
        text=True,
    )


def scratch_dir(prefix: str) -> Path:
    root = Path.home() / ".cache" / "ctb"
    root.mkdir(parents=True, exist_ok=True)
    return Path(tempfile.mkdtemp(prefix=prefix, dir=root))


def setup_error(result: AgentResult, source: str) -> str | None:
    if source.strip() != SOLUTION_STUB.strip():
        return None
    if result.error and TIMED_OUT in result.error:
        return None
    return (result.error or result.text.strip() or "The agent left solution.py untouched.")[:4000]
