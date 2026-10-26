from pathlib import Path

from ctb.langs.python.contract import contract_report
from ctb.langs.python.grade import compile_source as compile_error
from ctb.langs.python.grade import evaluate_solution, extract_public_tests
from ctb.langs.python.lint import readability_report

RUNTIME = "Python"
SOLVER_NOTE = ""
FENCE = "python"
SOLUTION = "solution.py"
PUBLIC = "test_public.py"
HIDDEN = "test_hidden.py"
PERF = "perf_cases.py"
STUB = '''def solution(*args, **kwargs):
    raise NotImplementedError("replace this with the task's solution function")
'''

__all__ = [
    "compile_error",
    "contract_report",
    "evaluate_solution",
    "extract_public_tests",
    "prepare",
    "readability_report",
    "test_instructions",
]


def prepare(directory: Path) -> None:
    del directory


def test_instructions() -> str:
    return (
        f"Create {HIDDEN}. It must import the entry point with "
        "`from solution import solution` and use pytest asserts.\n"
        "Cover the examples in the task and the edge cases the statement implies.\n"
        f"Create {PERF} with a list named CASES. Each item is "
        "(args_tuple, kwargs_dict) for one call to solution.\n"
    )
