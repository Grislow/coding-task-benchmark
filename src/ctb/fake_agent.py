from ctb.models import AgentResult, TokenUsage

_BINARY_GAP = '''def solution(N):
    best = 0
    gap = 0
    seen_one = False
    while N:
        if N & 1:
            best = max(best, gap)
            gap = 0
            seen_one = True
        elif seen_one:
            gap += 1
        N >>= 1
    return best
'''

_HIDDEN = """from solution import solution

def test_examples():
    assert solution(9) == 2
    assert solution(529) == 4
    assert solution(20) == 1
    assert solution(15) == 0
    assert solution(32) == 0

def test_one():
    assert solution(1) == 0
"""

_PERF = """CASES = [
    ((9,), {}),
    ((529,), {}),
    ((1,), {}),
    ((2 ** 20,), {}),
]
"""


class FakeAgent:
    """Offline stand-in for the BinaryGap sample. It does not call a model."""

    name = "fake"

    def __init__(self) -> None:
        self._solves = 0

    def complete(
        self,
        *,
        cwd: str,
        prompt: str,
        session_id: str | None,
        role: str,
    ) -> AgentResult:
        del prompt, session_id
        from pathlib import Path

        root = Path(cwd)
        if role == "author":
            (root / "test_hidden.py").write_text(_HIDDEN)
            (root / "perf_cases.py").write_text(_PERF)
            text = "wrote tests"
        elif role == "review":
            text = (
                '{"correctness": 70, "readability": 80, "extensibility": 75, '
                '"summary": "Offline stand-in review."}'
            )
        else:
            self._solves += 1
            source = "def solution(N):\n    return 0\n" if self._solves == 1 else _BINARY_GAP
            (root / "solution.py").write_text(source)
            text = "edited solution.py"
        return AgentResult(
            ok=True,
            text=text,
            session_id="fake-session",
            usage=TokenUsage(input_tokens=100 * max(self._solves, 1), output_tokens=40),
            wall_ms=50 * max(self._solves, 1),
            cost_usd=None,
            error=None,
            raw={},
        )
