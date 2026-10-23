import threading

from ctb.models import AttemptRecord, ReviewNote, SolutionRun


class ProgressBoard:
    def __init__(self, agents: list[str], attempts: int, author: str | None = None) -> None:
        self._lock = threading.Lock()
        self._phase = "idle"
        self._notes: list[str] = []
        self._suite_ready = False
        self._author = {
            "name": author,
            "state": "waiting" if author else "absent",
            "note": "",
        }
        self._agents = list(agents)
        self._attempts = [_waiting(agent, number) for agent in agents for number in range(1, attempts + 1)]
        self._reviews: list[dict[str, object]] = []
        self._solutions: list[dict[str, object]] = []

    def reset_agent(self, agent: str) -> None:
        with self._lock:
            self._attempts = [
                _waiting(agent, item["number"]) if item["agent"] == agent else item for item in self._attempts
            ]
            self._reviews = [
                item
                for item in self._reviews
                if item["author"] != agent and (item["reviewer"] != agent or item["author"] == "you")
            ]

    def set_phase(self, phase: str) -> None:
        with self._lock:
            self._phase = phase

    def add_note(self, note: str) -> None:
        if not note:
            return
        with self._lock:
            self._notes.append(note)

    def set_suite(self, ready: bool) -> None:
        with self._lock:
            self._suite_ready = ready

    def author_running(self, name: str) -> None:
        with self._lock:
            self._author["name"] = name
            self._author["state"] = "running"

    def author_finished(self, *, ok: bool, note: str) -> None:
        with self._lock:
            self._author["state"] = "done" if ok else "failed"
            self._author["note"] = note

    def attempt_started(self, agent: str, number: int) -> None:
        with self._lock:
            item = self._attempt(agent, number)
            item["state"] = "running"

    def attempt_finished(self, agent: str, record: AttemptRecord, source: str) -> None:
        with self._lock:
            item = self._attempt(agent, record.number)
            item["state"] = "setup" if record.setup_error else "passed" if record.passed else "failed"
            item["tests_passed"] = record.tests_passed
            item["tests_total"] = record.tests_total
            item["wall_ms"] = record.wall_ms
            item["tokens"] = record.usage.total
            item["failure_excerpt"] = record.failure_excerpt
            item["source"] = source
            item["performance_ms"] = record.performance_ms
            item["performance_note"] = record.performance_note
            item["readability"] = record.readability
            item["readability_notes"] = record.readability_notes
            item["public_failed"] = record.public_failed

    def mark_chosen(self, agent: str, number: int) -> None:
        with self._lock:
            for item in self._attempts:
                if item["agent"] == agent:
                    item["chosen"] = item["number"] == number

    def review_started(self, reviewer: str, author: str, attempt: int = 1) -> None:
        with self._lock:
            item = self._review(reviewer, author, attempt)
            if item is None:
                self._reviews.append(_pending(reviewer, author, "running", attempt))
                return
            item["state"] = "running"

    def review_finished(self, reviewer: str, author: str, note: ReviewNote | None, attempt: int = 1) -> None:
        with self._lock:
            item = self._review(reviewer, author, attempt)
            if item is None:
                item = _pending(reviewer, author, "done", attempt)
                self._reviews.append(item)
            item["state"] = "done" if note is not None else "failed"
            if note is not None:
                item.update(review_row(note))

    def set_solutions(self, solutions: list[SolutionRun]) -> None:
        with self._lock:
            self._solutions = [_solution_row(solution) for solution in solutions]
            for solution in solutions:
                for run in solution.attempt_runs:
                    item = self._attempt(solution.agent, run.attempts[0].number)
                    item["contract"] = run.contract
                    item["contract_notes"] = run.contract_notes

    def snapshot(self) -> dict[str, object]:
        with self._lock:
            return {
                "phase": self._phase,
                "notes": list(self._notes),
                "suite_ready": self._suite_ready,
                "author": dict(self._author),
                "agents": list(self._agents),
                "attempts": [dict(item) for item in self._attempts],
                "reviews": [dict(item) for item in self._reviews],
                "solutions": [dict(item) for item in self._solutions],
            }

    def _attempt(self, agent: str, number: int) -> dict[str, object]:
        for item in self._attempts:
            if item["agent"] == agent and item["number"] == number:
                return item
        raise KeyError((agent, number))

    def _review(self, reviewer: str, author: str, attempt: int) -> dict[str, object] | None:
        for item in self._reviews:
            if item["reviewer"] == reviewer and item["author"] == author and item["attempt"] == attempt:
                return item
        return None


def _solution_row(solution: SolutionRun) -> dict[str, object]:
    return {
        "agent": solution.agent,
        "source": solution.source,
        "profile": solution.profile,
        "correctness": solution.correctness,
        "performance": solution.performance,
        "readability": solution.readability,
        "review": solution.review,
        "contract": solution.contract,
        "contract_notes": solution.contract_notes,
        "cost": solution.cost,
        "performance_ms": solution.performance_ms,
        "tokens": solution.tokens,
        "wall_ms": solution.wall_ms,
        "readability_notes": solution.readability_notes,
    }


def review_row(note: ReviewNote) -> dict[str, object]:
    return {
        "reviewer": note.reviewer,
        "score": note.score,
        "summary": note.summary,
        "findings": [
            {
                "line": finding.line,
                "rule": finding.rule,
                "severity": finding.severity,
                "issue": finding.issue,
                "fix": finding.fix,
            }
            for finding in note.findings
        ],
    }


def _pending(reviewer: str, author: str, state: str, attempt: int) -> dict[str, object]:
    return {
        "reviewer": reviewer,
        "author": author,
        "attempt": attempt,
        "state": state,
        "score": None,
        "summary": "",
        "findings": [],
    }


def _waiting(agent: str, number: int) -> dict[str, object]:
    return {
        "agent": agent,
        "number": number,
        "state": "waiting",
        "tests_passed": None,
        "tests_total": None,
        "wall_ms": None,
        "tokens": None,
        "failure_excerpt": "",
        "source": None,
        "chosen": False,
        "performance_ms": None,
        "performance_note": "",
        "readability": None,
        "readability_notes": "",
        "public_failed": False,
        "contract": None,
        "contract_notes": "",
    }
