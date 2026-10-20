import threading
import time
from datetime import datetime, timezone
from pathlib import Path

from ctb.models import CodingAgent
from ctb.orchestrate import run_benchmark
from ctb.progress import ProgressBoard

_IDLE = {
    "phase": "idle",
    "notes": [],
    "suite_ready": False,
    "author": {"name": None, "state": "absent", "note": ""},
    "agents": [],
    "attempts": [],
    "reviews": [],
    "solutions": [],
}


class RunSession:
    def __init__(
        self,
        agents: list[CodingAgent],
        test_author: CodingAgent | None,
        *,
        attempts: int,
        timeout_s: int,
        review: bool,
        out_root: Path,
    ) -> None:
        self._agents = agents
        self._test_author = test_author
        self._attempts = attempts
        self._timeout_s = timeout_s
        self._review = review
        self._out_root = out_root
        self._lock = threading.Lock()
        self._board: ProgressBoard | None = None
        self._out_dir: Path | None = None

    def start(self, task_text: str) -> dict[str, object]:
        with self._lock:
            if self._board is not None and self._board.snapshot()["phase"] not in {"done", "error"}:
                raise RuntimeError("A run is already active.")
            author_name = None if self._test_author is None else self._test_author.name
            board = ProgressBoard(
                [agent.name for agent in self._agents],
                self._attempts,
                author_name,
            )
            board.set_phase("starting")
            out_dir = self._directory()
            self._board = board
            self._out_dir = out_dir
            thread = threading.Thread(
                target=self._execute,
                args=(task_text, board, out_dir),
                daemon=True,
            )
            thread.start()
        return board.snapshot()

    def snapshot(self) -> dict[str, object]:
        board = self._board
        if board is None:
            return dict(_IDLE)
        return board.snapshot()

    def out_dir(self) -> Path | None:
        return self._out_dir

    def _execute(self, task_text: str, board: ProgressBoard, out_dir: Path) -> None:
        try:
            run_benchmark(
                task_text=task_text,
                agents=self._agents,
                test_author=self._test_author,
                attempts=self._attempts,
                timeout_s=self._timeout_s,
                out_dir=out_dir,
                review=self._review,
                progress=board,
            )
        except Exception as exc:
            board.add_note(str(exc))
            board.set_phase("error")

    def _directory(self) -> Path:
        self._out_root.mkdir(parents=True, exist_ok=True)
        stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        out_dir = self._out_root / stamp
        if out_dir.exists():
            out_dir = self._out_root / f"{stamp}-{time.time_ns()}"
        return out_dir
