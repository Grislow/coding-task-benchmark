import threading
import time
from datetime import datetime, timezone
from pathlib import Path

from ctb.checks import readability_report
from ctb.contract import contract_report
from ctb.evaluate import evaluate_solution
from ctb.models import AttemptRecord, CodingAgent, SolutionRun, TokenUsage
from ctb.orchestrate import _grade, rerun_agent, run_benchmark
from ctb.preflight import check_agent
from ctb.progress import ProgressBoard, review_row
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
        tech: str = "python",
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
        self._default_tech = tech
        self._tech = tech
        self._task_text = ""
        self._checks: list[dict[str, object]] = []

    def check(self) -> dict[str, object]:
        with self._lock:
            if self._active():
                raise RuntimeError("Wait for the run to finish.")
            if any(row["state"] == "checking" for row in self._checks):
                raise RuntimeError("A check is already running.")
            roles = [(agent, "solver") for agent in self._agents]
            if self._test_author is not None:
                roles.append((self._test_author, "test author"))
            self._checks = [{"agent": agent.name, "role": role, "state": "checking", "note": ""} for agent, role in roles]
            jobs = list(zip([agent for agent, _ in roles], self._checks, strict=True))
        for agent, row in jobs:
            threading.Thread(target=self._check_one, args=(agent, row), daemon=True).start()
        return self.snapshot()

    def _check_one(self, agent: CodingAgent, row: dict[str, object]) -> None:
        try:
            problem = check_agent(agent)
        except Exception as exc:
            problem = str(exc)
        with self._lock:
            row["state"] = "ready" if problem is None else "failed"
            row["note"] = problem or ""

    def rerun(self, name: str) -> dict[str, object]:
        with self._lock:
            board = self._board
            solutions = self._report_solutions
            out_dir = self._out_dir
            if board is None or self._active():
                raise RuntimeError("Wait for the run to finish.")
            if solutions is None or out_dir is None:
                raise RuntimeError("This run has no results to re-run against.")
            agent = next((item for item in self._agents if item.name == name), None)
            if agent is None:
                raise RuntimeError(f"Unknown agent {name}.")
            board.set_phase("solving")
            threading.Thread(target=self._rerun, args=(agent, board, solutions, out_dir), daemon=True).start()
        return self.snapshot()

    def _rerun(self, agent: CodingAgent, board: ProgressBoard, solutions: list[SolutionRun], out_dir: Path) -> None:
        try:
            rerun_agent(
                solutions,
                agent,
                self._agents,
                self._task_text,
                self._attempts,
                self._timeout_s,
                out_dir,
                self._review,
                board,
                self._tech,
            )
            self._publish()
        except Exception as exc:
            board.add_note(str(exc))
            board.set_phase("error")

    def _active(self) -> bool:
        return self._board is not None and self._board.snapshot()["phase"] not in {"done", "error"}

    def start(self, task_text: str, tech: str | None = None) -> dict[str, object]:
        with self._lock:
            if self._active():
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
            self._tech = tech or self._default_tech
            self._task_text = task_text
            thread = threading.Thread(
                target=self._execute,
                args=(task_text, board, out_dir),
                daemon=True,
            )
            thread.start()
        return self.snapshot()

    def reset(self) -> dict[str, object]:
        with self._lock:
            if self._active():
                raise RuntimeError("A run is already active.")
            self._board = None
            self._task_text = ""
            self._tech = self._default_tech
            self._out_dir = None
            self._report_solutions = None
            self._you = None
            self._mine_claimed = False
            self._candidate_view = None
        return self.snapshot()

    def submit_mine(self, source: str) -> dict[str, object]:
        if self._out_dir is None or self.snapshot()["suite_ready"] is not True:
            raise RuntimeError("The suite is not ready.")
        with self._lock:
            if self._candidate_view is not None:
                raise RuntimeError("A solution was already submitted.")
            self._candidate_view = {"agent": "you", "state": "running", "source": source}
        try:
            you = self._build_you(source)
        except Exception:
            with self._lock:
                self._candidate_view = None
            raise
        with self._lock:
            if self._you is not None:
                raise RuntimeError("A solution was already submitted.")
            self._you = you
            phase = "idle" if self._board is None else self._board.snapshot()["phase"]
            start_reviews = (
                self._review
                and you.passed
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
            metadata = {
                "tech": self._tech,
                "task_text": self._task_text,
                "review_enabled": self._review,
                "preflight": [dict(row) for row in self._checks],
            }
        if board is None:
            return {**_IDLE, **metadata}
        snap = {**board.snapshot(), **metadata}
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
                tech=self._tech,
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
            if self._you is not None and self._you.passed and not self._mine_claimed:
                self._mine_claimed = True
                return self._you
            return None

    def _grade_you(self, you: SolutionRun) -> None:
        out_dir = self._out_dir
        if out_dir is None:
            return
        task_text = (out_dir / "task.md").read_text()
        board = self._board
        if board is not None:
            for agent in self._agents:
                board.review_started(agent.name, "you")
        for agent in self._agents:
            graded = _grade((you, agent), task_text, out_dir, board, self._tech)
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
                            "static": you.readability,
                            "review": you.review,
                            "contract": you.contract,
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
        readability, notes = readability_report(source, self._tech)
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
            performance_note=evaluation.performance_note,
            readability_notes=notes,
        )
        you = SolutionRun(
            agent="you",
            source=source,
            attempts=[attempt],
            performance_ms=evaluation.performance_ms,
            readability=readability,
            readability_notes=notes,
        )
        if self._tech == "fastapi":
            you.contract, you.contract_notes = contract_report(source, perf, self._timeout_s)
        return you

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
        "public_failed": False if attempt is None else attempt.public_failed,
        "tests_passed": None if attempt is None else attempt.tests_passed,
        "tests_total": None if attempt is None else attempt.tests_total,
        "performance_ms": you.performance_ms,
        "performance_note": "" if attempt is None else attempt.performance_note,
        "failure_excerpt": "" if attempt is None else attempt.failure_excerpt,
        "readability": you.readability,
        "readability_notes": you.readability_notes,
        "correctness": you.correctness,
        "performance": you.performance,
        "review": you.review,
        "contract": you.contract,
        "contract_notes": you.contract_notes,
        "cost": you.cost,
        "profile": you.profile,
        "reviews": [{**review_row(review), "author": "you", "attempt": 1, "state": "done"} for review in you.reviews],
    }


def _read(path: Path) -> str | None:
    if not path.exists():
        return None
    return path.read_text()
