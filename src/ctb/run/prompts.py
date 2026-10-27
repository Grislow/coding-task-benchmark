import json
import re
from pathlib import Path

from ctb.langs import RUBRICS, lang

_RUBRIC_DIR = Path(__file__).parent.parent / "langs"

RUBRIC_SCHEMA = json.dumps(
    {
        "type": "object",
        "additionalProperties": False,
        "properties": {
            "findings": {
                "type": "array",
                "items": {
                    "type": "object",
                    "additionalProperties": False,
                    "properties": {
                        "line": {"type": "integer"},
                        "rule": {"type": "string"},
                        "severity": {"type": "string", "enum": ["blocker", "major", "minor"]},
                        "issue": {"type": "string"},
                        "fix": {"type": "string"},
                    },
                    "required": ["line", "rule", "severity", "issue", "fix"],
                },
            },
            "summary": {"type": "string"},
        },
        "required": ["findings", "summary"],
    }
)


def rubric_text(tech: str) -> str:
    return "\n\n".join((_RUBRIC_DIR / f"{name}.md").read_text().strip() for name in RUBRICS[tech])


def rubric_rules(tech: str) -> frozenset[str]:
    return frozenset(re.findall(r"\*\*([A-Z]+-[A-Z]+)\*\*", rubric_text(tech)))


def wrap_up_s(timeout_s: int) -> int:
    return min(max(60, timeout_s // 5), timeout_s // 3)


def deadline_note(timeout_s: int, role: str = "solve") -> str:
    amount = f"{timeout_s // 60} minutes" if timeout_s % 60 == 0 else f"{timeout_s} seconds"
    if role == "review":
        return f"You have {amount}. This process is killed when that time is up, and an unfinished reply is lost, so reply well before then.\n\n"
    return (
        f"You have {amount}. This process is killed when that time is up.\n"
        "Only what your files hold at that moment counts. Save a working version within the first half of the time, then improve it.\n"
        "Run `sh time-left` in this directory between steps to see the seconds you have left. Do not edit or delete that file.\n"
        f"When {wrap_up_s(timeout_s)} seconds or fewer remain, it tells you to wrap up: stop exploring and leave your files in their final state.\n\n"
    )


def solver_prompt(tech: str = "python") -> str:
    toolchain = lang(tech)
    return (
        "Solve the coding task in task.md.\n"
        f"Edit only {toolchain.SOLUTION} in this directory.\n"
        "Define a function named solution with the behaviour the task describes.\n"
        f"{toolchain.SOLVER_NOTE}"
        f"You may run {toolchain.RUNTIME} here to check your own ideas.\n"
        "The grader's tests are not in this directory. Do not search outside it.\n"
        f"Leave {toolchain.SOLUTION} as the only file you change."
    )


def next_approach_prompt(number: int, passed: bool, tests_passed: int, tests_total: int, performance_ms: float | None, readability: float, failure_excerpt: str, source: str, tech: str = "python") -> str:
    toolchain = lang(tech)
    excerpt = failure_excerpt.strip()
    timed_out = "Timed out after" in excerpt
    if source.strip() in {"", toolchain.STUB.strip()}:
        reason = "it ran out of time" if timed_out else "it did not edit the file"
        lines = [
            f"Attempt {number} left {toolchain.SOLUTION} unchanged because {reason}.",
            "Write a working solution first, then improve it if time remains.",
        ]
    else:
        outcome = "passed the tests" if passed else "failed the tests"
        runtime = "no timing" if performance_ms is None else f"{performance_ms:.3f} ms median"
        lines = [
            f"Attempt {number} {outcome}" + (" and ran out of time" if timed_out else "") + ".",
            f"Tests {tests_passed}/{tests_total}. Runtime {runtime}. Readability {readability:.0f}.",
            f"Its {toolchain.SOLUTION} was:",
            f"```{toolchain.FENCE}",
            source.rstrip(),
            "```",
            f"Replace {toolchain.SOLUTION} with a different approach.",
            "Keep the function named solution.",
            "A better attempt passes the tests, then runs at least 10 percent faster, then is clearer.",
        ]
        if excerpt and not timed_out:
            lines.extend(["Failure output:", excerpt[:4000]])
    lines.append("Everything you need is in this message and task.md. Do not look for earlier attempts or search outside this directory.")
    return "\n".join(lines)


def author_prompt(tech: str = "python") -> str:
    return (
        "Read task.md and write tests for it. Do not write the solution.\n"
        f"{lang(tech).test_instructions()}"
        "Include a few small cases and one larger case. Keep the cases at 20 or fewer.\n"
        "Do not read or write anything outside this directory."
    )


def review_prompt(task_text: str, source: str, tech: str) -> str:
    lines = enumerate(source.splitlines(), 1)
    numbered = "\n".join(f"{number:>4}  {line}" for number, line in lines)
    return (
        "Review this solution for code quality against the rubric below. You have not seen its test results.\n"
        "Report only violations of the rubric's rules, each with the line number from the numbered source, "
        "the rule id, a severity, the issue and a concrete fix.\n"
        "Use the rule's default severity unless the case is clearly worse (blocker) or milder (minor).\n"
        "Do not judge correctness or speed. Tests and a profiler measure those.\n"
        "Do not report formatting, import order, unused names or anything else a linter catches. "
        "A linter scores those separately.\n"
        "Do not reward comments or docstrings, and never report their absence.\n"
        "Clean code gets no findings. An empty list is the right answer when nothing breaks a rule.\n"
        "Reply with JSON only, matching the requested schema. The summary is one sentence.\n\n"
        f"Rubric:\n{rubric_text(tech)}\n\n"
        f"Task:\n{task_text.strip()}\n\n"
        f"Solution:\n{numbered}"
    )
