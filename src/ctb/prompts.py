import json
import re
from pathlib import Path

SOLUTION_STUB = '''def solution(*args, **kwargs):
    raise NotImplementedError("replace this with the task's solution function")
'''

TECHS = ("python", "fastapi")
_RUBRIC_FILES = {"python": ("common", "python"), "fastapi": ("common", "python", "fastapi")}
_RUBRIC_DIR = Path(__file__).parent / "rubrics"

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
    return "\n\n".join((_RUBRIC_DIR / f"{name}.md").read_text().strip() for name in _RUBRIC_FILES[tech])


def rubric_rules(tech: str) -> frozenset[str]:
    return frozenset(re.findall(r"\*\*([A-Z]+-[A-Z]+)\*\*", rubric_text(tech)))


def deadline_note(timeout_s: int) -> str:
    amount = f"{timeout_s // 60} minutes" if timeout_s % 60 == 0 else f"{timeout_s} seconds"
    return (
        f"You have {amount}. This process is killed when that time is up.\n"
        "Run `sh time-left` in this directory to see the seconds you have left. Do not edit or delete that file.\n"
        "When fewer than 60 seconds remain, stop exploring and leave your files in their final state.\n"
        "If you cannot run commands, you still have only that long, so answer before it ends.\n\n"
    )


def solver_prompt() -> str:
    return (
        "Solve the coding task in task.md.\n"
        "Edit only solution.py in this directory.\n"
        "Define a function named solution with the behaviour the task describes.\n"
        "You may run Python here to check your own ideas.\n"
        "The grader's tests are not in this directory. Do not search outside it.\n"
        "Leave solution.py as the only file you change."
    )


def next_approach_prompt(number: int, passed: bool, tests_passed: int, tests_total: int, performance_ms: float | None, readability: float, failure_excerpt: str) -> str:
    outcome = "passed the tests" if passed else "failed the tests"
    if performance_ms is None:
        runtime = "no timing"
    else:
        runtime = f"{performance_ms:.3f} ms median"
    lines = [
        f"Attempt {number} {outcome}.",
        f"Tests {tests_passed}/{tests_total}. Runtime {runtime}. Readability {readability:.0f}.",
        "Replace solution.py with a different approach.",
        "Keep the function named solution.",
        "A better attempt passes the tests, then runs at least 10 percent faster, then is clearer.",
        "Do not search outside this directory.",
    ]
    excerpt = failure_excerpt.strip()
    if excerpt:
        lines.extend(["Failure output:", excerpt[:4000]])
    return "\n".join(lines)


def author_prompt() -> str:
    return (
        "Read task.md and write tests for it. Do not write the solution.\n"
        "Create test_hidden.py. It must import the entry point with "
        "`from solution import solution` and use pytest asserts.\n"
        "Cover the examples in the task and the edge cases the statement implies.\n"
        "Create perf_cases.py with a list named CASES. Each item is "
        "(args_tuple, kwargs_dict) for one call to solution.\n"
        "Include a few small cases and one larger case. Keep CASES at 20 items or fewer.\n"
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
