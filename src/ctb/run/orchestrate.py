import shutil
import sys
import time
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
from functools import partial
from pathlib import Path

from ctb.langs import WEB, lang
from ctb.models import (
    AgentResult,
    AttemptRecord,
    BenchmarkReport,
    CodingAgent,
    ReviewNote,
    SolutionRun,
)
from ctb.run.progress import ProgressBoard
from ctb.run.prompts import (
    author_prompt,
    next_approach_prompt,
    rubric_rules,
    solver_prompt,
)
from ctb.run.reviews import parse_review
from ctb.run.score import apply_profile, chosen_index
from ctb.run.workspace import TIMED_OUT, make_workspace, scratch_dir, setup_error

RETRY_DELAY_S = 5.0


def run_benchmark(
    task_text: str,
    agents: list[CodingAgent],
    test_author: CodingAgent | None,
    attempts: int,
    timeout_s: int,
    out_dir: Path,
    review: bool,
    progress: ProgressBoard | None = None,
    candidate: Callable[[], list[SolutionRun]] | None = None,
    tech: str = "python",
) -> BenchmarkReport:
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "task.md").write_text(task_text)
    notes: list[str] = []
    public_tests = lang(tech).extract_public_tests(task_text)
    hidden_tests, perf_cases, author_note = _hidden_suite(test_author, task_text, out_dir, progress, tech)
    if author_note:
        notes.append(author_note)
        if progress is not None:
            progress.add_note(author_note)
    _store_suite(out_dir, public_tests, hidden_tests, perf_cases, tech)
    if progress is not None:
        progress.set_suite(bool(public_tests or hidden_tests))
    if not public_tests and not hidden_tests:
        missing = "No tests were produced. Correctness is left blank."
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
        tech,
    )
    if tech in WEB:
        for solution in solutions:
            _contract(solution, perf_cases, timeout_s, tech)
    if progress is not None:
        progress.set_solutions(solutions)
    if review and agents:
        _review(solutions, agents, task_text, out_dir, progress, candidate, tech)
    apply_profile(solutions)
    if progress is not None:
        progress.set_solutions(solutions)
        progress.set_phase("done")
    return BenchmarkReport(_title(task_text), str(out_dir), notes, solutions, tech)


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
    tech: str = "python",
) -> list[SolutionRun]:
    if progress is not None:
        progress.set_phase("solving")
    if not agents:
        return []
    with ThreadPoolExecutor(max_workers=len(agents)) as pool:
        futures = [
            pool.submit(
                _solve_apart,
                agent,
                task_text,
                public_tests,
                hidden_tests,
                perf_cases,
                attempts,
                timeout_s,
                out_dir,
                progress,
                tech,
            )
            for agent in agents
        ]
        return [future.result() for future in futures]


def _solve_apart(
    agent: CodingAgent,
    task_text: str,
    public_tests: str | None,
    hidden_tests: str | None,
    perf_cases: str | None,
    attempts: int,
    timeout_s: int,
    out_dir: Path,
    progress: ProgressBoard | None = None,
    tech: str = "python",
) -> SolutionRun:
    scratch = scratch_dir("solve-")
    try:
        return _solve(
            agent,
            task_text,
            public_tests,
            hidden_tests,
            perf_cases,
            attempts,
            timeout_s,
            scratch,
            progress,
            tech,
        )
    finally:
        produced = scratch / "work" / agent.name
        if produced.exists():
            shutil.copytree(produced, out_dir / "work" / agent.name, symlinks=True, dirs_exist_ok=True)
        shutil.rmtree(scratch, ignore_errors=True)


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
    tech: str = "python",
) -> SolutionRun:
    print(f"solving {agent.name}", file=sys.stderr, flush=True)
    toolchain = lang(tech)
    workspace = out_dir / "work" / agent.name
    make_workspace(workspace, task_text, tech)
    solution_path = workspace / toolchain.SOLUTION
    records: list[AttemptRecord] = []
    sources: list[str] = []
    for number in range(1, attempts + 1):
        if progress is not None:
            progress.attempt_started(agent.name, number)
        previous = next((index for index in reversed(range(len(records))) if records[index].setup_error is None), None)
        prompt = solver_prompt(tech) if previous is None else next_approach_prompt(
            records[previous].number,
            records[previous].passed,
            records[previous].tests_passed,
            records[previous].tests_total,
            records[previous].performance_ms,
            records[previous].readability,
            records[previous].failure_excerpt,
            sources[previous],
            tech,
        )
        result = _with_retry(
            partial(agent.complete, cwd=str(workspace), prompt=prompt, session_id=None, role="solve"),
            lambda attempt: setup_error(attempt, _source(solution_path), tech) is not None,
        )
        source = _source(solution_path)
        sources.append(source)
        problem = setup_error(result, source, tech)
        if problem is not None:
            records.append(
                AttemptRecord(
                    number=number,
                    session_id=result.session_id,
                    usage=result.usage,
                    wall_ms=result.wall_ms,
                    cost_usd=result.cost_usd,
                    passed=False,
                    tests_passed=0,
                    tests_total=0,
                    public_failed=False,
                    failure_excerpt=problem,
                    agent_error=result.error,
                    setup_error=problem,
                )
            )
            if progress is not None:
                progress.attempt_finished(agent.name, records[-1], source)
            continue
        evaluation = toolchain.evaluate_solution(source, public_tests, hidden_tests, perf_cases, timeout_s)
        readability, readability_notes = toolchain.readability_report(source, tech)
        excerpt = result.error or evaluation.failure_excerpt
        records.append(
            AttemptRecord(
                number=number,
                session_id=result.session_id,
                usage=result.usage,
                wall_ms=result.wall_ms,
                cost_usd=result.cost_usd,
                passed=evaluation.passed and result.ok,
                tests_passed=evaluation.tests_passed,
                tests_total=evaluation.tests_total,
                public_failed=evaluation.public_failed,
                failure_excerpt="" if evaluation.passed and result.ok else excerpt[:4000],
                agent_error=result.error,
                performance_ms=evaluation.performance_ms,
                readability=readability,
                performance_note=evaluation.performance_note,
                readability_notes=readability_notes,
            )
        )
        if progress is not None:
            progress.attempt_finished(agent.name, records[-1], source)
    for number, attempt_source in enumerate(sources, 1):
        (workspace / f"attempt-{number}{solution_path.suffix}").write_text(attempt_source)
    best = chosen_index(records)
    records[best] = replace(records[best], chosen=True)
    if progress is not None:
        progress.mark_chosen(agent.name, records[best].number)
    source = sources[best]
    solution_path.write_text(source)
    readability, readability_notes = toolchain.readability_report(source, tech)
    return SolutionRun(
        agent=agent.name,
        source=source,
        attempts=records,
        performance_ms=records[best].performance_ms,
        readability=readability,
        readability_notes=readability_notes,
        attempt_runs=[
            SolutionRun(
                agent=agent.name,
                source=attempt_source,
                attempts=[record],
                performance_ms=record.performance_ms,
                readability=record.readability,
                readability_notes=record.readability_notes,
            )
            for record, attempt_source in zip(records, sources, strict=True)
        ],
    )


def _hidden_suite(
    author: CodingAgent | None,
    task_text: str,
    out_dir: Path,
    progress: ProgressBoard | None = None,
    tech: str = "python",
) -> tuple[str | None, str | None, str | None]:
    if author is None:
        return None, None, None
    toolchain = lang(tech)
    if progress is not None:
        progress.set_phase("authoring")
        progress.author_running(author.name)
    workspace = out_dir / "work" / f"{author.name}-author"
    make_workspace(workspace, task_text, tech)
    result = _with_retry(
        lambda: author.complete(cwd=str(workspace), prompt=author_prompt(tech), session_id=None, role="author"),
        lambda attempt: _did_not_run(attempt) and not (workspace / toolchain.HIDDEN).exists(),
    )
    hidden = _readable(workspace / toolchain.HIDDEN)
    perf = _readable(workspace / toolchain.PERF)
    notes: list[str] = []
    if not result.ok:
        notes.append(f"Test author {author.name} failed: {result.error}")
    if hidden is not None and toolchain.compile_error(hidden) is not None:
        notes.append("Hidden tests did not parse and were discarded.")
        hidden = None
    if perf is not None and toolchain.compile_error(perf) is not None:
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
    candidate: Callable[[], list[SolutionRun]] | None = None,
    tech: str = "python",
) -> None:
    extras = [] if candidate is None else candidate()
    jobs = [
        (attempt, agent)
        for solution in solutions
        for attempt in (solution.attempt_runs or [solution])
        for agent in agents
        if attempt.passed and family(agent.name) != family(solution.agent)
    ]
    jobs.extend((extra, agent) for extra in extras if extra.passed for agent in agents)
    _run_reviews(jobs, task_text, out_dir, progress, tech)
    _sync_chosen(solutions)


def _run_reviews(
    jobs: list[tuple[SolutionRun, CodingAgent]],
    task_text: str,
    out_dir: Path,
    progress: ProgressBoard | None,
    tech: str,
) -> None:
    if not jobs:
        return
    if progress is not None:
        for solution, agent in jobs:
            progress.review_started(agent.name, solution.agent, solution.attempts[0].number)
        progress.set_phase("reviewing")
    with ThreadPoolExecutor(max_workers=len(jobs)) as pool:
        notes = [
            future.result()
            for future in [pool.submit(_grade, job, task_text, out_dir, progress, tech) for job in jobs]
        ]
    for solution, note in notes:
        if note is not None:
            solution.reviews.append(note)


def _sync_chosen(solutions: list[SolutionRun]) -> None:
    for solution in solutions:
        for attempt in solution.attempt_runs:
            if attempt.attempts[0].chosen:
                solution.reviews = list(attempt.reviews)


def rerun_agent(
    solutions: list[SolutionRun],
    agent: CodingAgent,
    agents: list[CodingAgent],
    task_text: str,
    attempts: int,
    timeout_s: int,
    out_dir: Path,
    review: bool,
    progress: ProgressBoard | None = None,
    tech: str = "python",
) -> None:
    public_tests, hidden_tests, perf_cases = read_suite(out_dir, tech)
    if progress is not None:
        progress.reset_agent(agent.name)
        progress.set_phase("solving")
    shutil.rmtree(out_dir / "work" / agent.name, ignore_errors=True)
    solution = _solve_apart(
        agent, task_text, public_tests, hidden_tests, perf_cases, attempts, timeout_s, out_dir, progress, tech
    )
    if tech in WEB:
        _contract(solution, perf_cases, timeout_s, tech)
    others = [item for item in solutions if item.agent != agent.name]
    solutions[:] = [solution if item.agent == agent.name else item for item in solutions]
    if review:
        for other in others:
            for run in other.attempt_runs:
                run.reviews = [note for note in run.reviews if note.reviewer != agent.name]
        jobs = [
            (attempt, reviewer)
            for attempt in solution.attempt_runs
            for reviewer in agents
            if attempt.passed and family(reviewer.name) != family(agent.name)
        ]
        jobs.extend(
            (attempt, agent)
            for other in others
            for attempt in other.attempt_runs
            if attempt.passed and family(other.agent) != family(agent.name)
        )
        _run_reviews(jobs, task_text, out_dir, progress, tech)
        _sync_chosen(solutions)
    apply_profile(solutions)
    if progress is not None:
        progress.set_solutions(solutions)
        progress.set_phase("done")


def _contract(solution: SolutionRun, perf_cases: str | None, timeout_s: int, tech: str) -> None:
    for run in solution.attempt_runs:
        run.contract, run.contract_notes = lang(tech).contract_report(run.source, perf_cases, timeout_s)
    chosen = next(run for run in solution.attempt_runs if run.attempts[0].chosen)
    solution.contract, solution.contract_notes = chosen.contract, chosen.contract_notes


def _with_retry(call: Callable[[], AgentResult], broken: Callable[[AgentResult], bool]) -> AgentResult:
    result = call()
    if not broken(result):
        return result
    time.sleep(RETRY_DELAY_S)
    return call()


def _did_not_run(result: AgentResult) -> bool:
    return not result.ok and TIMED_OUT not in (result.error or "")


def _source(path: Path) -> str:
    return path.read_text() if path.exists() else ""


def _grade(
    job: tuple[SolutionRun, CodingAgent],
    task_text: str,
    out_dir: Path,
    progress: ProgressBoard | None = None,
    tech: str = "python",
) -> tuple[SolutionRun, ReviewNote | None]:
    from ctb.run.prompts import review_prompt

    solution, agent = job
    number = solution.attempts[0].number if solution.attempts else 1
    if progress is not None:
        progress.review_started(agent.name, solution.agent, number)
    print(f"grading {solution.agent} with {agent.name}", file=sys.stderr, flush=True)
    workspace = out_dir / "work" / f"review-{agent.name}-{solution.agent}-attempt-{number}"
    make_workspace(workspace, task_text, tech)
    (workspace / lang(tech).SOLUTION).write_text(solution.source)
    result = _with_retry(
        lambda: agent.complete(
            cwd=str(workspace),
            prompt=review_prompt(task_text, solution.source, tech),
            session_id=None,
            role="review",
        ),
        _did_not_run,
    )
    rules = rubric_rules(tech)
    lines = max(1, len(solution.source.splitlines()))
    note = None if not result.ok else parse_review(result.text, agent.name, rules, lines) or parse_review(
        _raw_text(result.raw), agent.name, rules, lines
    )
    if progress is not None:
        progress.review_finished(agent.name, solution.agent, note, number, "" if note is not None else _review_failure(result))
    return solution, note


def _review_failure(result: AgentResult) -> str:
    if result.ok:
        return "The reply did not match the review format."
    lines = [line.strip() for line in (result.error or "").splitlines() if line.strip()]
    return (lines[-1] if lines else "The reviewer exited without a reply.")[:300]


def _store_suite(
    out_dir: Path,
    public_tests: str | None,
    hidden_tests: str | None,
    perf_cases: str | None,
    tech: str = "python",
) -> None:
    toolchain = lang(tech)
    hidden_dir = out_dir / "hidden"
    hidden_dir.mkdir(exist_ok=True)
    for name, text in ((toolchain.PUBLIC, public_tests), (toolchain.HIDDEN, hidden_tests), (toolchain.PERF, perf_cases)):
        if text:
            (hidden_dir / name).write_text(text)


def read_suite(out_dir: Path, tech: str) -> tuple[str | None, str | None, str | None]:
    toolchain = lang(tech)
    hidden = out_dir / "hidden"
    return _readable(hidden / toolchain.PUBLIC), _readable(hidden / toolchain.HIDDEN), _readable(hidden / toolchain.PERF)


def _readable(path: Path) -> str | None:
    if not path.exists():
        return None
    return path.read_text()


def _raw_text(raw: dict[str, object]) -> str:
    import json

    return json.dumps(raw)


def family(agent_name: str) -> str:
    return agent_name.split("-", 1)[0]


def _title(task_text: str) -> str:
    for line in task_text.splitlines():
        stripped = line.strip()
        if stripped.startswith("#"):
            return stripped.lstrip("#").strip() or "Coding task"
        if stripped:
            return stripped[:80]
    return "Coding task"
