import threading
import time
from collections.abc import Callable
from datetime import datetime, timezone
from pathlib import Path

from ctb.agents.clis import EFFORTS, agent_name
from ctb.agents.preflight import check_agent
from ctb.langs import WEB, lang
from ctb.models import AttemptRecord, CodingAgent, SolutionRun, TokenUsage
from ctb.run.orchestrate import (
    _grade,
    _sync_chosen,
    family,
    read_suite,
    rerun_agent,
    run_benchmark,
)
from ctb.run.progress import ProgressBoard, review_row
from ctb.run.prompts import (
    author_prompt,
    deadline_note,
    next_approach_prompt,
    review_prompt,
    solver_prompt,
)
from ctb.run.score import apply_profile, correctness_score, weighted_score

LEVELS = ("none", "minimal", "low", "medium", "high", "xhigh", "max", "ultra")

_IDLE = {
    "phase": "idle",
    "notes": [],
    "suite_ready": False,
    "author": {"name": None, "state": "absent", "note": ""},
    "agents": [],
    "attempts": [],
    "reviews": [],
    "solutions": [],
    "candidates": [],
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
        catalog: dict[str, list[str]] | dict[str, dict[str, list[str]]] | None = None,
        build: Callable[[str], CodingAgent] | None = None,
        author_timeout_s: int | None = None,
        review_timeout_s: int | None = None,
    ) -> None:
        self._agents = agents
        self._reviewers = list(agents)
        self._racers = list(agents)
        self._judges = list(agents)
        self._lineup = list(agents)
        self._build = build
        self._models = [_model_row(agent) for agent in agents]
        self._levels = {
            (cli, model): list(models[model])
            for cli, models in (catalog or {}).items()
            if isinstance(models, dict)
            for model in models
            if models[model]
        }
        taken = {(row["cli"], row["model"]) for row in self._models}
        for cli, models in (catalog or {}).items():
            for model in models:
                if (cli, model) not in taken:
                    taken.add((cli, model))
                    level = "high" if "high" in self._efforts(cli, model) else None
                    self._models.append({"cli": cli, "model": model, "effort": level, "review_effort": level, "lineup": False, "enabled": False})
        self._test_author = test_author
        self._attempts = attempts
        self._timeout_s = timeout_s
        self._author_timeout_s = timeout_s if author_timeout_s is None else author_timeout_s
        self._review_timeout_s = timeout_s if review_timeout_s is None else review_timeout_s
        self._review = review
        self._out_root = out_root
        self._lock = threading.Lock()
        self._board: ProgressBoard | None = None
        self._out_dir: Path | None = None
        self._report_solutions: list[SolutionRun] | None = None
        self._yours: list[SolutionRun] = []
        self._claimed: set[int] = set()
        self._views: list[dict[str, object]] = []
        self._default_tech = tech
        self._tech = tech
        self._task_text = ""
        self._checks: list[dict[str, object]] = []
        self._apply_timeouts()

    def check(self) -> dict[str, object]:
        with self._lock:
            if self._active():
                raise RuntimeError("Wait for the run to finish.")
            if any(row["state"] == "checking" for row in self._checks):
                raise RuntimeError("A check is already running.")
            roles = self._roles()
            self._checks = [_check_row(agent, role) for agent, role in roles]
            jobs = list(zip([agent for agent, _ in roles], self._checks, strict=True))
        self._start_checks(jobs)
        return self.snapshot()

    def _roles(self) -> list[tuple[CodingAgent, str]]:
        roles = [(agent, "solver") for agent in self._agents]
        roles.extend((agent, "reviewer") for agent in self._reviewers if agent not in self._agents)
        if self._test_author is not None:
            roles.append((self._test_author, "test author"))
        return roles

    def _start_checks(self, jobs: list[tuple[CodingAgent, dict[str, object]]]) -> None:
        for agent, row in jobs:
            threading.Thread(target=self._check_one, args=(agent, row), daemon=True).start()

    def config(self) -> dict[str, object]:
        with self._lock:
            locked = self._active()
            models = [
                {**row, "name": _row_name(row), "efforts": self._efforts(row["cli"], row["model"])}
                for row in self._models
            ]
            timeout_s = self._timeout_s
            author_timeout_s = self._author_timeout_s
            review_timeout_s = self._review_timeout_s
            tech = self._tech
        return {
            "locked": locked,
            "timeout_s": timeout_s,
            "author_timeout_s": author_timeout_s,
            "review_timeout_s": review_timeout_s,
            "attempts": self._attempts,
            "author": _author_view(self._test_author, self._efforts),
            "models": models,
            "prompts": _prompts(tech, timeout_s, author_timeout_s, review_timeout_s),
        }

    def configure(self, payload: dict[str, object]) -> dict[str, object]:
        timeout_s = _bounded_timeout(payload.get("timeout_s", self._timeout_s))
        author_timeout_s = _bounded_timeout(payload.get("author_timeout_s", self._author_timeout_s))
        review_timeout_s = _bounded_timeout(payload.get("review_timeout_s", self._review_timeout_s))
        wanted = {
            (item.get("cli"), item.get("model")): item
            for item in payload.get("models", [])
            if isinstance(item, dict)
        }
        jobs: list[tuple[CodingAgent, dict[str, object]]] = []
        with self._lock:
            if self._active():
                raise RuntimeError("Wait for the run to finish.")
            new_author = self._test_author
            replace_author = False
            if "author" in payload:
                spec = _parse_author(payload["author"], self._models, self._efforts, self._test_author)
                if not _authors_match(self._test_author, spec, self._efforts):
                    new_author = None if spec is None else self._build_author(spec)
                    replace_author = True
            rows = [dict(row) for row in self._models]
            for row in rows:
                item = wanted.get((row["cli"], row["model"]))
                if item is None:
                    continue
                row["enabled"] = item.get("enabled") is True
                effort = item.get("effort")
                levels = self._efforts(row["cli"], row["model"])
                if effort is not None:
                    effort = _chosen(effort, levels, row["cli"])
                    if effort != row["effort"]:
                        row["effort"] = effort
                        if row["lineup"]:
                            row["name"] = agent_name(str(row["cli"]), str(row["model"]), _level(effort))
                review_effort = item.get("review_effort")
                if review_effort is not None:
                    row["review_effort"] = _chosen(review_effort, levels, row["cli"])
            built = {agent.name: agent for agent in [*self._lineup, *self._agents, *self._reviewers]}
            agents = []
            reviewers = []
            for row in rows:
                if not row["enabled"]:
                    continue
                name = _row_name(row)
                solving = row["effort"] != "none"
                reviewing = row["review_effort"] != "none"
                if not solving and not reviewing:
                    raise ValueError(f"{row['model']} is set to none for both solving and reviews. Switch it off instead.")
                if name not in built:
                    if self._build is None:
                        raise ValueError(f"This page cannot start {name}.")
                    effort = _level(row["effort"])
                    built[name] = self._build(f"{row['cli']}:{row['model']}" + (f":{effort}" if effort else ""))
                built[name].review_effort = _level(row["review_effort"])
                if solving:
                    agents.append(built[name])
                if reviewing:
                    reviewers.append(built[name])
            if not agents:
                raise ValueError("Switch on at least one model for solving.")
            self._models = rows
            self._agents = agents
            self._reviewers = reviewers
            if replace_author:
                self._test_author = new_author
            self._timeout_s = timeout_s
            self._author_timeout_s = author_timeout_s
            self._review_timeout_s = review_timeout_s
            self._apply_timeouts()
            if self._checks:
                jobs = self._recheck(replace_author)
        self._start_checks(jobs)
        return self.config()

    def _recheck(self, replace_author: bool) -> list[tuple[CodingAgent, dict[str, object]]]:
        kept = {(row["agent"], row["role"]): row for row in self._checks if row["role"] != "test author"}
        jobs = []
        rows = []
        for agent, role in self._roles():
            if role == "test author":
                continue
            row = kept.get((agent.name, role))
            if row is None:
                row = _check_row(agent, role)
                jobs.append((agent, row))
            rows.append(row)
        authors = [row for row in self._checks if row["role"] == "test author"]
        if replace_author:
            authors = []
            if self._test_author is not None:
                authors = [_check_row(self._test_author, "test author")]
                jobs.append((self._test_author, authors[0]))
        self._checks = rows + authors
        return jobs

    def _efforts(self, cli: object, model: object) -> list[str]:
        known = self._levels.get((cli, model)) or EFFORTS.get(str(cli), ())
        return [level for level in LEVELS if level in known]

    def _apply_timeouts(self) -> None:
        for agent in {id(agent): agent for agent in [*self._agents, *self._reviewers]}.values():
            if hasattr(agent, "timeout_s"):
                agent.timeout_s = self._timeout_s
            agent.review_timeout_s = self._review_timeout_s
        author = self._test_author
        if author is not None and hasattr(author, "timeout_s"):
            author.timeout_s = self._author_timeout_s

    def _check_one(self, agent: CodingAgent, row: dict[str, object]) -> None:
        try:
            problem = check_agent(agent)
        except Exception as exc:
            problem = str(exc)
        with self._lock:
            if not any(existing is row for existing in self._checks):
                return
            row["state"] = "ready" if problem is None else "failed"
            row["note"] = problem or ""

    def _build_author(self, spec: tuple[str, str, str | None]) -> CodingAgent:
        cli, model, effort = spec
        text = f"{cli}:{model}" if effort is None else f"{cli}:{model}:{effort}"
        if self._build is None:
            raise ValueError(f"This page cannot start {text}.")
        return self._build(text)

    def rerun(self, name: str) -> dict[str, object]:
        with self._lock:
            board = self._board
            solutions = self._report_solutions
            out_dir = self._out_dir
            if board is None or self._active():
                raise RuntimeError("Wait for the run to finish.")
            if solutions is None or out_dir is None:
                raise RuntimeError("This run has no results to re-run against.")
            agent = next((item for item in self._racers if item.name == name), None)
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
                self._judges,
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

    def retry_review(self, reviewer: str, author: str, attempt: int) -> dict[str, object]:
        with self._lock:
            board = self._board
            if board is None or self._active():
                raise RuntimeError("Wait for the run to finish.")
            job = next(
                (item for item in board.snapshot()["reviews"] if item["reviewer"] == reviewer and item["author"] == author and item["attempt"] == attempt),
                None,
            )
            if job is None or job["state"] != "failed":
                raise RuntimeError("Only a failed review can be retried.")
            agent = next((item for item in self._judges if item.name == reviewer), None)
            target = self._review_target(author, attempt)
            if agent is None or target is None:
                raise RuntimeError("That review is not part of this run.")
            board.review_started(reviewer, author, attempt)
        threading.Thread(target=self._retry_review, args=(target, agent, board), daemon=True).start()
        return self.snapshot()

    def _review_target(self, author: str, attempt: int) -> SolutionRun | None:
        if author == "you":
            return next((you for you in self._yours if _number(you) == attempt), None)
        solution = next((item for item in self._report_solutions or [] if item.agent == author), None)
        if solution is None:
            return None
        return next((run for run in solution.attempt_runs if run.attempts[0].number == attempt), None)

    def _retry_review(self, target: SolutionRun, agent: CodingAgent, board: ProgressBoard) -> None:
        out_dir = self._out_dir
        if out_dir is None:
            return
        _, note = _grade((target, agent), (out_dir / "task.md").read_text(), out_dir, board, self._tech)
        if note is None:
            return
        with self._lock:
            target.reviews = [*(item for item in target.reviews if item.reviewer != agent.name), note]
            solutions = self._report_solutions
            if solutions is not None and target.agent != "you":
                _sync_chosen(solutions)
                apply_profile(solutions)
                board.set_solutions(solutions)
        self._publish()

    def _active(self) -> bool:
        return self._board is not None and self._board.snapshot()["phase"] not in {"done", "error"}

    def start(self, task_text: str, tech: str | None = None) -> dict[str, object]:
        with self._lock:
            if self._active():
                raise RuntimeError("A run is already active.")
            if any(row["state"] == "checking" for row in self._checks):
                raise RuntimeError("Wait for the model check to finish.")
            failed = {(row["agent"], row["role"]) for row in self._checks if row["state"] == "failed"}
            author_name = None if self._test_author is None else self._test_author.name
            if (author_name, "test author") in failed:
                raise RuntimeError(f"The test author {author_name} cannot run. Pick another one in Config.")
            broken = {name for name, role in failed if role != "test author"}
            racers = [agent for agent in self._agents if agent.name not in broken]
            if not racers:
                raise RuntimeError("None of the models can run. Switch on another one in Config.")
            self._racers = racers
            self._judges = [agent for agent in self._reviewers if agent.name not in broken]
            board = ProgressBoard(
                [agent.name for agent in racers],
                self._attempts,
                author_name,
            )
            board.set_phase("starting")
            out_dir = self._directory()
            self._board = board
            self._out_dir = out_dir
            self._report_solutions = None
            self._yours = []
            self._claimed = set()
            self._views = []
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
            self._yours = []
            self._claimed = set()
            self._views = []
        return self.snapshot()

    def submit_mine(self, source: str) -> dict[str, object]:
        if not source.strip():
            raise RuntimeError("Paste a solution first.")
        if self._out_dir is None or self.snapshot()["suite_ready"] is not True:
            raise RuntimeError("The suite is not ready.")
        with self._lock:
            number = len(self._views) + 1
            self._views.append({"agent": "you", "number": number, "state": "running", "source": source, "started_at": time.time()})
            views = self._views
        threading.Thread(target=self._score_mine, args=(views, number, source), daemon=True).start()
        return self.snapshot()

    def _score_mine(self, views: list[dict[str, object]], number: int, source: str) -> None:
        try:
            you = self._build_you(source, number)
        except Exception as exc:
            with self._lock:
                views[number - 1] = {
                    "agent": "you",
                    "number": number,
                    "state": "failed",
                    "source": source,
                    "passed": False,
                    "failure_excerpt": str(exc),
                    "reviews": [],
                }
            return
        with self._lock:
            if self._views is not views:
                return
            self._yours.append(you)
            phase = "idle" if self._board is None else self._board.snapshot()["phase"]
            start_reviews = self._review and you.passed and phase in {"reviewing", "done", "error"} and number not in self._claimed
            if start_reviews:
                self._claimed.add(number)
        self._publish()
        if start_reviews:
            self._grade_you(you)

    def snapshot(self) -> dict[str, object]:
        with self._lock:
            board = self._board
            views = [dict(view) for view in self._views]
            metadata = {
                "tech": self._tech,
                "task_text": self._task_text,
                "review_enabled": self._review,
                "preflight": [dict(row) for row in self._checks],
                "lineup": [agent.name for agent in self._agents],
                "reviewers": [agent.name for agent in self._reviewers],
                "palette": list(dict.fromkeys(agent.name for agent in [*self._lineup, *self._agents, *self._reviewers])),
                "attempts_per_agent": self._attempts,
                "timeout_s": self._timeout_s,
                "author_timeout_s": self._author_timeout_s,
                "review_timeout_s": self._review_timeout_s,
                "now": time.time(),
            }
        if board is None:
            return {**_IDLE, **metadata, "candidates": views}
        for row in views:
            reviews = row.get("reviews")
            if isinstance(reviews, list):
                row["reviews"] = [dict(item) for item in reviews]
        return {**board.snapshot(), **metadata, "candidates": views}

    def out_dir(self) -> Path | None:
        return self._out_dir

    def _execute(self, task_text: str, board: ProgressBoard, out_dir: Path) -> None:
        try:
            report = run_benchmark(
                task_text=task_text,
                agents=self._racers,
                reviewers=self._judges,
                test_author=self._test_author,
                attempts=self._attempts,
                timeout_s=self._timeout_s,
                out_dir=out_dir,
                review=self._review,
                progress=board,
                candidate=self._claim_yours,
                tech=self._tech,
            )
            with self._lock:
                self._report_solutions = report.solutions
            self._publish()
            for you in self._claim_yours() if self._review else []:
                threading.Thread(target=self._grade_you, args=(you,), daemon=True).start()
        except Exception as exc:
            board.add_note(str(exc))
            board.set_phase("error")

    def _claim_yours(self) -> list[SolutionRun]:
        with self._lock:
            fresh = [you for you in self._yours if you.passed and _number(you) not in self._claimed]
            self._claimed.update(_number(you) for you in fresh)
            return fresh

    def _grade_you(self, you: SolutionRun) -> None:
        out_dir = self._out_dir
        if out_dir is None:
            return
        task_text = (out_dir / "task.md").read_text()
        board = self._board
        if board is not None:
            for agent in self._judges:
                board.review_started(agent.name, "you", _number(you))
        for agent in self._judges:
            graded = _grade((you, agent), task_text, out_dir, board, self._tech)
            if graded[1] is not None:
                you.reviews.append(graded[1])
        self._publish()

    def _publish(self) -> None:
        with self._lock:
            if not self._yours:
                return
            others = self._report_solutions
            if others is not None:
                apply_profile([*others, *self._yours])
                for you in self._yours:
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
                for you in self._yours:
                    attempt = you.chosen_attempt()
                    if attempt is not None:
                        you.correctness = correctness_score(
                            attempt.tests_passed,
                            attempt.tests_total,
                            attempt.public_failed,
                        )
            for you in self._yours:
                self._views[_number(you) - 1] = _candidate_row(you)

    def _build_you(self, source: str, number: int) -> SolutionRun:
        out_dir = self._out_dir
        if out_dir is None:
            raise RuntimeError("The suite is not ready.")
        toolchain = lang(self._tech)
        public, tests, perf = read_suite(out_dir, self._tech)
        evaluation = toolchain.evaluate_solution(source, public, tests, perf, self._timeout_s)
        readability, notes = toolchain.readability_report(source, self._tech)
        attempt = AttemptRecord(
            number=number,
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
        if self._tech in WEB:
            you.contract, you.contract_notes = toolchain.contract_report(source, perf, self._timeout_s)
        return you

    def _directory(self) -> Path:
        self._out_root.mkdir(parents=True, exist_ok=True)
        stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        out_dir = self._out_root / stamp
        if out_dir.exists():
            out_dir = self._out_root / f"{stamp}-{time.time_ns()}"
        return out_dir


def _check_row(agent: CodingAgent, role: str) -> dict[str, object]:
    return {"agent": agent.name, "role": role, "state": "checking", "note": ""}


def _number(you: SolutionRun) -> int:
    return you.attempts[0].number


def _candidate_row(you: SolutionRun) -> dict[str, object]:
    attempt = you.chosen_attempt()
    return {
        "agent": you.agent,
        "number": _number(you),
        "state": "passed" if you.passed else "failed",
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
        "reviews": [{**review_row(review), "author": "you", "attempt": _number(you), "state": "done"} for review in you.reviews],
    }


def _bounded_timeout(value: object) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or not 30 <= value <= 3600:
        raise ValueError("The time limit must be between 30 and 3600 seconds.")
    return value


def _author_view(agent: CodingAgent | None, efforts: Callable[[object, object], list[str]]) -> dict[str, object] | None:
    if agent is None:
        return None
    cli = family(agent.name)
    model = getattr(agent, "model", None) or agent.name
    return {
        "cli": cli,
        "model": model,
        "effort": getattr(agent, "effort", None),
        "name": agent.name,
        "efforts": efforts(cli, model),
    }


def _parse_author(
    requested: object,
    models: list[dict[str, object]],
    efforts: Callable[[object, object], list[str]],
    current: CodingAgent | None = None,
) -> tuple[str, str, str | None] | None:
    if requested is None:
        return None
    if not isinstance(requested, dict):
        raise ValueError("The test author must name a model.")
    cli = requested.get("cli")
    model = requested.get("model")
    effort = requested.get("effort")
    if not isinstance(cli, str) or not isinstance(model, str) or not cli or not model:
        raise ValueError("The test author must name a model.")
    known = any(row["cli"] == cli and row["model"] == model for row in models)
    current_view = _author_view(current, efforts)
    if not known and current_view is not None:
        known = current_view["cli"] == cli and current_view["model"] == model
    if not known:
        raise ValueError(f"{cli}:{model} is not an available model.")
    allowed = efforts(cli, model)
    if allowed:
        if not isinstance(effort, str) or effort not in allowed:
            raise ValueError(f"{cli} has no reasoning level '{effort}'.")
        return cli, model, effort
    if effort not in (None, ""):
        raise ValueError(f"{cli} does not take a reasoning level.")
    return cli, model, None


def _authors_match(
    agent: CodingAgent | None,
    spec: tuple[str, str, str | None] | None,
    efforts: Callable[[object, object], list[str]],
) -> bool:
    if agent is None or spec is None:
        return agent is None and spec is None
    view = _author_view(agent, efforts)
    cli, model, effort = spec
    return view is not None and view["cli"] == cli and view["model"] == model and view["effort"] == effort


def _model_row(agent: CodingAgent) -> dict[str, object]:
    return {
        "cli": family(agent.name),
        "model": getattr(agent, "model", None) or agent.name,
        "effort": getattr(agent, "effort", None),
        "review_effort": getattr(agent, "review_effort", None) or getattr(agent, "effort", None),
        "lineup": True,
        "enabled": True,
        "name": agent.name,
    }


def _row_name(row: dict[str, object]) -> str:
    if row["lineup"]:
        return str(row["name"])
    return agent_name(str(row["cli"]), str(row["model"]), _level(row["effort"]))


def _chosen(effort: object, levels: list[str], cli: object) -> str | None:
    if effort == "default" and not levels:
        return None
    if effort != "none" and effort not in levels:
        raise ValueError(f"{cli} has no reasoning level '{effort}'.")
    return str(effort)


def _level(effort: object) -> str | None:
    return None if effort in (None, "none") else str(effort)


def _prompts(tech: str, solve_s: int, author_s: int, review_s: int) -> list[dict[str, str]]:
    return [
        {"id": "solver", "title": "Solver, attempt 1", "text": deadline_note(solve_s) + solver_prompt(tech)},
        {
            "id": "retry",
            "title": "Solver, attempts 2 and 3",
            "text": deadline_note(solve_s) + next_approach_prompt(1, False, 7, 10, 0.42, 88, "<first test failure, up to 4000 characters>", "<the previous attempt's code>", tech),
        },
        {"id": "author", "title": "Test author", "text": deadline_note(author_s, "author") + author_prompt(tech)},
        {"id": "review", "title": "Reviewer", "text": deadline_note(review_s, "review") + review_prompt("<task.md>", f"<{lang(tech).SOLUTION}>", tech)},
    ]
