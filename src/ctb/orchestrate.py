import sys
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
from pathlib import Path

from ctb.checks import readability_report
from ctb.evaluate import compile_source, evaluate_solution, extract_public_tests
from ctb.models import AttemptRecord, BenchmarkReport, CodingAgent, ReviewNote, SolutionRun
from ctb.progress import ProgressBoard
from ctb.prompts import author_prompt, next_approach_prompt, solver_prompt
from ctb.reviews import parse_review
from ctb.score import apply_profile, chosen_index
from ctb.workspace import make_workspace


def run_benchmark(
    task_text: str,
    agents: list[CodingAgent],
    test_author: CodingAgent | None,
    attempts: int,
    timeout_s: int,
    out_dir: Path,
    review: bool,
    progress: ProgressBoard | None = None,
    candidate: Callable[[], SolutionRun | None] | None = None,
) -> BenchmarkReport:
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "task.md").write_text(task_text)
    notes: list[str] = []
    public_tests = extract_public_tests(task_text)
    hidden_tests, perf_cases, author_note = _hidden_suite(test_author, task_text, out_dir, progress)
    if author_note:
        notes.append(author_note)
        if progress is not None:
            progress.add_note(author_note)
    _store_suite(out_dir, public_tests, hidden_tests, perf_cases)
    if progress is not None:
        progress.set_suite(bool(public_tests or hidden_tests))
    if not public_tests and not hidden_tests:
        missing = "No tests were produced. Solvers get one attempt and correctness is left blank."
        notes.append(missing)
        if progress is not None:
            progress.add_note(missing)
    solutions = _solve_all(
        agents,
        task_text,
        public_tests,
        hidden_tests,
        perf_cases,
        attempts,
        timeout_s,
        out_dir,
        progress,
    )
    if review and len(agents) >= 2:
        _review(solutions, agents, task_text, out_dir, progress, candidate)
    elif review:
        skipped = "Peer review needs two agents, so that dimension was left out."
        notes.append(skipped)
        if progress is not None:
            progress.add_note(skipped)
    apply_profile(solutions)
    if progress is not None:
        progress.set_solutions(solutions)
        progress.set_phase("done")
    return BenchmarkReport(_title(task_text), str(out_dir), notes, solutions)


def _solve_all(
    agents: list[CodingAgent],
    task_text: str,
    public_tests: str | None,
    hidden_tests: str | None,
    perf_cases: str | None,
    attempts: int,
    timeout_s: int,
    out_dir: Path,
    progress: ProgressBoard | None = None,
) -> list[SolutionRun]:
    if progress is not None:
        progress.set_phase("solving")
    if not agents:
        return []
    with ThreadPoolExecutor(max_workers=len(agents)) as pool:
        futures = [
            pool.submit(
                _solve,
                agent,
                task_text,
                public_tests,
                hidden_tests,
                perf_cases,
                attempts,
                timeout_s,
                out_dir,
                progress,
            )
            for agent in agents
        ]
        return [future.result() for future in futures]


def _solve(
    agent: CodingAgent,
    task_text: str,
    public_tests: str | None,
    hidden_tests: str | None,
    perf_cases: str | None,
    attempts: int,
    timeout_s: int,
    out_dir: Path,
    progress: ProgressBoard | None = None,
) -> SolutionRun:
    print(f"solving {agent.name}", file=sys.stderr, flush=True)
    workspace = out_dir / "work" / agent.name
    make_workspace(workspace, task_text)
    session_id: str | None = None
    records: list[AttemptRecord] = []
    sources: list[str] = []
    for number in range(1, attempts + 1):
        if progress is not None:
            progress.attempt_started(agent.name, number)
        previous = records[-1] if records else None
        prompt = solver_prompt() if previous is None else next_approach_prompt(
            previous.number,
            previous.passed,
            previous.tests_passed,
            previous.tests_total,
            previous.performance_ms,
            previous.readability,
            previous.failure_excerpt,
        )
        result = agent.complete(
            cwd=str(workspace),
            prompt=prompt,
            session_id=session_id,
            role="solve",
        )
        session_id = result.session_id or session_id
        solution_path = workspace / "solution.py"
        source = solution_path.read_text() if solution_path.exists() else ""
        evaluation = evaluate_solution(source, public_tests, hidden_tests, perf_cases, timeout_s)
        readability, readability_notes = readability_report(source)
        excerpt = result.error or evaluation.failure_excerpt
        (workspace / f"attempt-{number}.py").write_text(source)
        sources.append(source)
        records.append(
            AttemptRecord(
                number=number,
                session_id=session_id,
                usage=result.usage,
                wall_ms=result.wall_ms,
                cost_usd=result.cost_usd,
                passed=evaluation.passed and result.ok,
                tests_passed=evaluation.tests_passed,
                tests_total=evaluation.tests_total,
                public_failed=evaluation.public_failed,
                failure_excerpt="" if evaluation.passed else excerpt[:4000],
                agent_error=result.error,
                performance_ms=evaluation.performance_ms,
                readability=readability,
                performance_note=evaluation.performance_note,
                readability_notes=readability_notes,
            )
        )
        if progress is not None:
            progress.attempt_finished(agent.name, records[-1], source)
        if evaluation.tests_total == 0:
            break
    best = chosen_index(records)
    records[best] = replace(records[best], chosen=True)
    if progress is not None:
        progress.mark_chosen(agent.name, records[best].number)
    source = sources[best]
    (workspace / "solution.py").write_text(source)
    readability, readability_notes = readability_report(source)
    return SolutionRun(
        agent=agent.name,
        source=source,
        attempts=records,
        performance_ms=records[best].performance_ms,
        readability=readability,
        readability_notes=readability_notes,
    )


def _hidden_suite(
    author: CodingAgent | None,
    task_text: str,
    out_dir: Path,
    progress: ProgressBoard | None = None,
) -> tuple[str | None, str | None, str | None]:
    if author is None:
        return None, None, None
    if progress is not None:
        progress.set_phase("authoring")
        progress.author_running(author.name)
    workspace = out_dir / "work" / f"{author.name}-author"
    make_workspace(workspace, task_text)
    result = author.complete(
        cwd=str(workspace),
        prompt=author_prompt(),
        session_id=None,
        role="author",
    )
    hidden = _readable(workspace / "test_hidden.py")
    perf = _readable(workspace / "perf_cases.py")
    notes: list[str] = []
    if not result.ok:
        notes.append(f"Test author {author.name} failed: {result.error}")
    if hidden is not None and compile_source(hidden) is not None:
        notes.append("Hidden tests did not parse and were discarded.")
        hidden = None
    if perf is not None and compile_source(perf) is not None:
        notes.append("Performance cases did not parse and were discarded.")
        perf = None
    if hidden is None:
        notes.append("No hidden suite. Public asserts in the task are the grader, when they exist.")
    note = " ".join(notes)
    if progress is not None:
        progress.author_finished(ok=result.ok, note=note)
    return hidden, perf, note or None


def _review(
    solutions: list[SolutionRun],
    agents: list[CodingAgent],
    task_text: str,
    out_dir: Path,
    progress: ProgressBoard | None = None,
    candidate: Callable[[], SolutionRun | None] | None = None,
) -> None:
    extra = None if candidate is None else candidate()
    jobs = [
        (solution, agent)
        for solution in solutions
        for agent in agents
        if agent.name != solution.agent
    ]
    if extra is not None:
        jobs.extend((extra, agent) for agent in agents if agent.name != extra.agent)
    if not jobs:
        return
    if progress is not None:
        progress.set_phase("reviewing")
    with ThreadPoolExecutor(max_workers=len(jobs)) as pool:
        notes = [
            future.result()
            for future in [pool.submit(_grade, job, task_text, out_dir, progress) for job in jobs]
        ]
    for solution, note in notes:
        if note is not None:
            solution.reviews.append(note)


def _grade(
    job: tuple[SolutionRun, CodingAgent],
    task_text: str,
    out_dir: Path,
    progress: ProgressBoard | None = None,
) -> tuple[SolutionRun, ReviewNote | None]:
    from ctb.prompts import review_prompt

    solution, agent = job
    if progress is not None:
        progress.review_started(agent.name, solution.agent)
    print(f"grading {solution.agent} with {agent.name}", file=sys.stderr, flush=True)
    workspace = out_dir / "work" / f"review-{agent.name}-{solution.agent}"
    make_workspace(workspace, task_text)
    (workspace / "solution.py").write_text(solution.source)
    result = agent.complete(
        cwd=str(workspace),
        prompt=review_prompt(task_text, solution.source),
        session_id=None,
        role="review",
    )
    note = parse_review(result.text, agent.name) or parse_review(_raw_text(result.raw), agent.name)
    if progress is not None:
        progress.review_finished(agent.name, solution.agent, note)
    return solution, note


def _store_suite(
    out_dir: Path,
    public_tests: str | None,
    hidden_tests: str | None,
    perf_cases: str | None,
) -> None:
    hidden_dir = out_dir / "hidden"
    hidden_dir.mkdir(exist_ok=True)
    if public_tests:
        (hidden_dir / "test_public.py").write_text(public_tests)
    if hidden_tests:
        (hidden_dir / "test_hidden.py").write_text(hidden_tests)
    if perf_cases:
        (hidden_dir / "perf_cases.py").write_text(perf_cases)


def _readable(path: Path) -> str | None:
    if not path.exists():
        return None
    return path.read_text()


def _raw_text(raw: dict[str, object]) -> str:
    import json

    return json.dumps(raw)


def _title(task_text: str) -> str:
    for line in task_text.splitlines():
        stripped = line.strip()
        if stripped.startswith("#"):
            return stripped.lstrip("#").strip() or "Coding task"
        if stripped:
            return stripped[:80]
    return "Coding task"
