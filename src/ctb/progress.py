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
        self._attempts = [
            {
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
            }
            for agent in agents
            for number in range(1, attempts + 1)
        ]
        self._reviews: list[dict[str, object]] = []
        self._solutions: list[dict[str, object]] = []

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
            item["state"] = "passed" if record.passed else "failed"
            item["tests_passed"] = record.tests_passed
            item["tests_total"] = record.tests_total
            item["wall_ms"] = record.wall_ms
            item["tokens"] = record.usage.total
            item["failure_excerpt"] = record.failure_excerpt
            item["source"] = source

    def mark_chosen(self, agent: str, number: int) -> None:
        with self._lock:
            for item in self._attempts:
                if item["agent"] == agent:
                    item["chosen"] = item["number"] == number

    def review_started(self, reviewer: str, author: str) -> None:
        with self._lock:
            item = self._review(reviewer, author)
            if item is None:
                self._reviews.append(
                    {
                        "reviewer": reviewer,
                        "author": author,
                        "state": "running",
                        "correctness": None,
                        "readability": None,
                        "extensibility": None,
                        "summary": "",
                    }
                )
                return
            item["state"] = "running"

    def review_finished(self, reviewer: str, author: str, note: ReviewNote | None) -> None:
        with self._lock:
            item = self._review(reviewer, author)
            if item is None:
                item = {
                    "reviewer": reviewer,
                    "author": author,
                    "state": "done",
                    "correctness": None,
                    "readability": None,
                    "extensibility": None,
                    "summary": "",
                }
                self._reviews.append(item)
            item["state"] = "done"
            if note is None:
                return
            item["correctness"] = note.correctness
            item["readability"] = note.readability
            item["extensibility"] = note.extensibility
            item["summary"] = note.summary

    def set_solutions(self, solutions: list[SolutionRun]) -> None:
        with self._lock:
            self._solutions = [_solution_row(solution) for solution in solutions]

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

    def _review(self, reviewer: str, author: str) -> dict[str, object] | None:
        for item in self._reviews:
            if item["reviewer"] == reviewer and item["author"] == author:
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
        "extensibility": solution.extensibility,
        "peer": solution.peer,
        "cost": solution.cost,
        "performance_ms": solution.performance_ms,
        "tokens": solution.tokens,
        "wall_ms": solution.wall_ms,
        "readability_notes": solution.readability_notes,
    }
