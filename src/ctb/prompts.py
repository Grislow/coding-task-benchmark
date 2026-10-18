import json

SOLUTION_STUB = '''def solution(*args, **kwargs):
    raise NotImplementedError("replace this with the task's solution function")
'''

RUBRIC_SCHEMA = json.dumps(
    {
        "type": "object",
        "additionalProperties": False,
        "properties": {
            "correctness": {"type": "integer", "minimum": 0, "maximum": 100},
            "readability": {"type": "integer", "minimum": 0, "maximum": 100},
            "extensibility": {"type": "integer", "minimum": 0, "maximum": 100},
            "summary": {"type": "string"},
        },
        "required": ["correctness", "readability", "extensibility", "summary"],
    }
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


def review_prompt(task_text: str, source: str) -> str:
    return (
        "Grade this Python solution against the task. You have not seen its test results.\n"
        "Reply with JSON only, matching the requested schema.\n"
        "Score correctness, readability, and extensibility from 0 to 100.\n"
        "Extensibility means a later reader could add a case without rewriting the function.\n\n"
        "Task:\n"
        f"{task_text.strip()}\n\n"
        "Solution:\n"
        f"{source}"
    )
