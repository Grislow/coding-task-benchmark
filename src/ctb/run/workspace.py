import subprocess
import tempfile
from pathlib import Path

from ctb.langs import lang
from ctb.models import AgentResult

TIMED_OUT = "Timed out after"


def make_workspace(path: Path, task_text: str, tech: str = "python") -> None:
    toolchain = lang(tech)
    path.mkdir(parents=True, exist_ok=True)
    (path / "task.md").write_text(task_text)
    (path / toolchain.SOLUTION).write_text(toolchain.STUB)
    toolchain.prepare(path)
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


def setup_error(result: AgentResult, source: str, tech: str = "python") -> str | None:
    if source.strip() != lang(tech).STUB.strip():
        return None
    if result.error and TIMED_OUT in result.error:
        return None
    return (result.error or result.text.strip() or "The agent left the solution untouched.")[:4000]
