import subprocess
from pathlib import Path

from ctb.prompts import SOLUTION_STUB


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
