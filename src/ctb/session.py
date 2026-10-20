import threading
import time
from datetime import datetime, timezone
from pathlib import Path

from ctb.checks import readability_report
from ctb.evaluate import evaluate_solution
from ctb.models import AttemptRecord, CodingAgent, SolutionRun, TokenUsage
from ctb.orchestrate import _grade, run_benchmark
from ctb.progress import ProgressBoard
from ctb.score import apply_profile, correctness_score, weighted_score

_IDLE = {
    "phase": "idle",
    "notes": [],
    "suite_ready": False,
    "author": {"name": None, "state": "absent", "note": ""},
    "agents": [],
    "attempts": [],
    "reviews": [],
    "solutions": [],
    "candidate": None,
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
        self._report_solutions: list[SolutionRun] | None = None
        self._you: SolutionRun | None = None
        self._mine_claimed = False
        self._candidate_view: dict[str, object] | None = None

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
            self._report_solutions = None
            self._you = None
            self._mine_claimed = False
            self._candidate_view = None
            thread = threading.Thread(
                target=self._execute,
                args=(task_text, board, out_dir),
                daemon=True,
            )
            thread.start()
        return self.snapshot()

    def submit_mine(self, source: str) -> dict[str, object]:
        if self._out_dir is None or self.snapshot()["suite_ready"] is not True:
            raise RuntimeError("The suite is not ready.")
        you = self._build_you(source)
        with self._lock:
            if self._you is not None:
                raise RuntimeError("A solution was already submitted.")
            self._you = you
            phase = "idle" if self._board is None else self._board.snapshot()["phase"]
            start_reviews = (
                self._review
                and phase in {"reviewing", "done", "error"}
                and not self._mine_claimed
            )
            if start_reviews:
                self._mine_claimed = True
        self._publish()
        if start_reviews:
            threading.Thread(target=self._grade_you, args=(you,), daemon=True).start()
        return self.snapshot()

    def snapshot(self) -> dict[str, object]:
        with self._lock:
            board = self._board
            view = self._candidate_view
        if board is None:
            return dict(_IDLE)
        snap = board.snapshot()
        if view is None:
            snap["candidate"] = None
            return snap
        row = dict(view)
        reviews = row.get("reviews")
        if isinstance(reviews, list):
            row["reviews"] = [dict(item) for item in reviews]
        snap["candidate"] = row
        return snap

    def out_dir(self) -> Path | None:
        return self._out_dir

    def _execute(self, task_text: str, board: ProgressBoard, out_dir: Path) -> None:
        try:
            report = run_benchmark(
                task_text=task_text,
                agents=self._agents,
                test_author=self._test_author,
                attempts=self._attempts,
                timeout_s=self._timeout_s,
                out_dir=out_dir,
                review=self._review,
                progress=board,
                candidate=self._claim_you,
            )
            with self._lock:
                self._report_solutions = report.solutions
            you = self._claim_you() if self._review else None
            if you is not None:
                self._grade_you(you)
            else:
                self._publish()
        except Exception as exc:
            board.add_note(str(exc))
            board.set_phase("error")

    def _claim_you(self) -> SolutionRun | None:
        with self._lock:
            if self._you is not None and not self._mine_claimed:
                self._mine_claimed = True
                return self._you
            return None

    def _grade_you(self, you: SolutionRun) -> None:
        out_dir = self._out_dir
        if out_dir is None:
            return
        task_text = (out_dir / "task.md").read_text()
        for agent in self._agents:
            graded = _grade((you, agent), task_text, out_dir, None)
            if graded[1] is not None:
                you.reviews.append(graded[1])
        self._publish()

    def _publish(self) -> None:
        with self._lock:
            you = self._you
            if you is None:
                return
            others = self._report_solutions
            if others is not None:
                apply_profile([*others, you])
                if you.tokens == 0 and you.wall_ms == 0:
                    you.cost = None
                    you.profile = weighted_score(
                        {
                            "correctness": you.correctness,
                            "performance": you.performance,
                            "readability": you.readability,
                            "extensibility": you.extensibility,
                            "peer": you.peer,
                            "cost": None,
                        }
                    )
                board = self._board
                if board is not None:
                    board.set_solutions(others)
            else:
                attempt = you.chosen_attempt()
                if attempt is not None:
                    you.correctness = correctness_score(
                        attempt.tests_passed,
                        attempt.tests_total,
                        attempt.public_failed,
                    )
            self._candidate_view = _candidate_row(you)

    def _build_you(self, source: str) -> SolutionRun:
        out_dir = self._out_dir
        if out_dir is None:
            raise RuntimeError("The suite is not ready.")
        hidden = out_dir / "hidden"
        public = _read(hidden / "test_public.py")
        tests = _read(hidden / "test_hidden.py")
        perf = _read(hidden / "perf_cases.py")
        evaluation = evaluate_solution(source, public, tests, perf, self._timeout_s)
        readability, notes = readability_report(source)
        attempt = AttemptRecord(
            number=1,
            session_id=None,
            usage=TokenUsage(),
            wall_ms=0,
            cost_usd=None,
            passed=evaluation.passed,
            tests_passed=evaluation.tests_passed,
            tests_total=evaluation.tests_total,
            public_failed=evaluation.public_failed,
            failure_excerpt="" if evaluation.passed else evaluation.failure_excerpt[:4000],
            agent_error=None,
            performance_ms=evaluation.performance_ms,
            readability=readability,
            chosen=True,
        )
        return SolutionRun(
            agent="you",
            source=source,
            attempts=[attempt],
            performance_ms=evaluation.performance_ms,
            readability=readability,
            readability_notes=notes,
        )

    def _directory(self) -> Path:
        self._out_root.mkdir(parents=True, exist_ok=True)
        stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        out_dir = self._out_root / stamp
        if out_dir.exists():
            out_dir = self._out_root / f"{stamp}-{time.time_ns()}"
        return out_dir


def _candidate_row(you: SolutionRun) -> dict[str, object]:
    attempt = you.chosen_attempt()
    return {
        "agent": you.agent,
        "source": you.source,
        "passed": you.passed,
        "tests_passed": None if attempt is None else attempt.tests_passed,
        "tests_total": None if attempt is None else attempt.tests_total,
        "performance_ms": you.performance_ms,
        "failure_excerpt": "" if attempt is None else attempt.failure_excerpt,
        "readability": you.readability,
        "readability_notes": you.readability_notes,
        "correctness": you.correctness,
        "performance": you.performance,
        "extensibility": you.extensibility,
        "peer": you.peer,
        "cost": you.cost,
        "profile": you.profile,
        "reviews": [
            {
                "reviewer": review.reviewer,
                "correctness": review.correctness,
                "readability": review.readability,
                "extensibility": review.extensibility,
                "summary": review.summary,
            }
            for review in you.reviews
        ],
    }


def _read(path: Path) -> str | None:
    if not path.exists():
        return None
    return path.read_text()
