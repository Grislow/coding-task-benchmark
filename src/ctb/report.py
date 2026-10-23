import json
from pathlib import Path

from ctb.models import BenchmarkReport, SolutionRun
from ctb.progress import review_row
from ctb.score import WEIGHTS


def write_report(report: BenchmarkReport, destination: Path) -> None:
    destination.mkdir(parents=True, exist_ok=True)
    (destination / "report.md").write_text(_markdown(report))
    (destination / "report.json").write_text(json.dumps(_payload(report), indent=2) + "\n")


def _markdown(report: BenchmarkReport) -> str:
    ranked = sorted(
        report.solutions,
        key=lambda solution: solution.profile if solution.profile is not None else -1,
        reverse=True,
    )
    lines = [
        f"# {report.task_title}",
        "",
        "Profile weights: "
        + ", ".join(f"{name} {int(weight)}" for name, weight in WEIGHTS.items())
        + ". A missing dimension is left out and the rest are rescaled.",
        "",
        "Performance is the median time of the frozen cases. "
        "The fastest solution that passes scores 100. "
        "Cost splits token total and wall clock the same way, then averages them. "
        "A solution that fails scores 0 on performance and cost when another solution passes.",
        "",
    ]
    if report.notes:
        lines.append("## Notes")
        lines.append("")
        for note in report.notes:
            lines.append(f"- {note}")
        lines.append("")
    lines.extend(
        [
            "## Leaderboard",
            "",
            "| Agent | Profile | Correctness | Performance | Static | Review | Contract | Cost | Wall | Tokens |",
            "| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
        ]
    )
    for solution in ranked:
        lines.append(
            "| {agent} | {profile} | {correctness} | {performance} | {static} | "
            "{review} | {contract} | {cost} | {wall} | {tokens} |".format(
                agent=solution.agent,
                profile=_num(solution.profile),
                correctness=_num(solution.correctness),
                performance=_num(solution.performance),
                static=_num(solution.readability),
                review=_num(solution.review),
                contract=_num(solution.contract),
                cost=_num(solution.cost),
                wall=_seconds(solution.wall_ms),
                tokens=solution.tokens,
            )
        )
    lines.append("")
    for solution in ranked:
        lines.extend(_card(solution))
    return "\n".join(lines)


def _card(solution: SolutionRun) -> list[str]:
    lines = [
        f"## {solution.agent}",
        "",
        _measured_line(solution),
        "",
        "| Attempt | Result | Tests | Wall | Tokens | USD |",
        "| ---: | --- | ---: | ---: | ---: | ---: |",
    ]
    details: list[str] = []
    for attempt in solution.attempts:
        result = "pass" if attempt.passed else "fail"
        if attempt.chosen:
            result = f"{result}, kept"
        tests = f"{attempt.tests_passed}/{attempt.tests_total}"
        usd = "—" if attempt.cost_usd is None else f"{attempt.cost_usd:.4f}"
        lines.append(
            f"| {attempt.number} | {result} | {tests} | {_seconds(attempt.wall_ms)} | "
            f"{attempt.usage.total} | {usd} |"
        )
        if attempt.agent_error:
            details.extend(["", f"Attempt {attempt.number} error: {attempt.agent_error}"])
        elif attempt.failure_excerpt:
            details.extend(
                [
                    "",
                    f"Attempt {attempt.number} failure:",
                    "",
                    "```text",
                    attempt.failure_excerpt[:1500],
                    "```",
                ]
            )
    lines.append("")
    lines.extend(details)
    if details:
        lines.append("")
    if solution.contract_notes:
        lines.extend([f"Contract: {solution.contract_notes}", ""])
    if solution.reviews:
        lines.append("### Reviews")
        lines.append("")
        for review in solution.reviews:
            lines.append(f"- {review.reviewer}: {review.score:.0f}. {review.summary}")
            for finding in review.findings:
                lines.append(
                    f"  - line {finding.line}, {finding.rule} ({finding.severity}): "
                    f"{finding.issue} Fix: {finding.fix}"
                )
        lines.append("")
    lines.extend(["### solution.py", "", "```python", solution.source.rstrip(), "```", ""])
    return lines


def _payload(report: BenchmarkReport) -> dict[str, object]:
    return {
        "task_title": report.task_title,
        "out_dir": report.out_dir,
        "notes": report.notes,
        "weights": WEIGHTS,
        "solutions": [_solution_payload(solution) for solution in report.solutions],
    }


def _solution_payload(solution: SolutionRun) -> dict[str, object]:
    return {
        "agent": solution.agent,
        "profile": solution.profile,
        "correctness": solution.correctness,
        "performance": solution.performance,
        "static": solution.readability,
        "review": solution.review,
        "contract": solution.contract,
        "contract_notes": solution.contract_notes,
        "cost": solution.cost,
        "performance_ms": solution.performance_ms,
        "tokens": solution.tokens,
        "wall_ms": solution.wall_ms,
        "cost_usd": solution.cost_usd,
        "source": solution.source,
        "attempts": [
            {
                "number": attempt.number,
                "passed": attempt.passed,
                "tests_passed": attempt.tests_passed,
                "tests_total": attempt.tests_total,
                "wall_ms": attempt.wall_ms,
                "tokens": attempt.usage.total,
                "cost_usd": attempt.cost_usd,
                "session_id": attempt.session_id,
            }
            for attempt in solution.attempts
        ],
        "reviews": [review_row(review) for review in solution.reviews],
    }


def _measured_line(solution: SolutionRun) -> str:
    chosen = solution.chosen_attempt()
    profile = "" if chosen is None or not chosen.performance_note else f" {chosen.performance_note}"
    return f"Runtime median: {_ms(solution.performance_ms)}.{profile} {solution.readability_notes}."


def _num(value: float | None) -> str:
    if value is None:
        return "—"
    return f"{value:.1f}"


def _seconds(wall_ms: int) -> str:
    return f"{wall_ms / 1000:.1f}s"


def _ms(value: float | None) -> str:
    if value is None:
        return "—"
    if value < 1:
        return f"{value:.3f} ms"
    return f"{value:.2f} ms"
