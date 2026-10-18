from ctb.models import AttemptRecord, SolutionRun, TokenUsage
from ctb.score import apply_profile, chosen_index, correctness_score, weighted_score


def test_public_failure_zeros_correctness() -> None:
    assert correctness_score(4, 4, public_failed=True) == 0
    assert correctness_score(3, 4, public_failed=False) == 75
    assert correctness_score(0, 0, public_failed=False) is None


def test_later_attempt_is_kept_only_when_it_scores_better() -> None:
    first = _attempt(passed=True, tests_passed=2, performance_ms=10, readability=70)
    similar = _attempt(passed=True, tests_passed=2, performance_ms=9.5, readability=70, number=2)
    clearer = _attempt(passed=True, tests_passed=2, performance_ms=9.5, readability=90, number=2)
    faster = _attempt(passed=True, tests_passed=2, performance_ms=8, readability=70, number=3)
    failed = _attempt(passed=False, tests_passed=0, performance_ms=1, readability=100, number=2)
    assert chosen_index([first, similar]) == 0
    assert chosen_index([first, clearer]) == 1
    assert chosen_index([first, faster]) == 1
    assert chosen_index([failed, first]) == 1


def test_faster_cheaper_pass_ranks_higher() -> None:
    fast = _solution("fast", passed=True, tokens=100, wall_ms=1000, performance_ms=10)
    slow = _solution("slow", passed=True, tokens=100, wall_ms=2000, performance_ms=20)
    apply_profile([fast, slow])
    assert fast.performance == 100
    assert slow.performance == 50
    assert fast.cost == 100
    assert slow.cost == 75
    assert fast.profile is not None and slow.profile is not None
    assert fast.profile > slow.profile
    assert fast.profile == weighted_score(
        {
            "correctness": 100,
            "performance": 100,
            "readability": 80,
            "extensibility": None,
            "peer": None,
            "cost": 100,
        }
    )


def test_failed_solution_scores_zero_performance_when_another_passes() -> None:
    winner = _solution("winner", passed=True, tokens=100, wall_ms=1000, performance_ms=10)
    loser = _solution("loser", passed=False, tokens=50, wall_ms=100, performance_ms=1)
    apply_profile([winner, loser])
    assert loser.correctness == 0
    assert loser.performance == 0
    assert loser.cost == 0
    assert winner.profile is not None and loser.profile is not None
    assert winner.profile > loser.profile


def _attempt(
    passed: bool,
    tests_passed: int,
    performance_ms: float | None,
    readability: float,
    number: int = 1,
) -> AttemptRecord:
    return AttemptRecord(
        number=number,
        session_id="s",
        usage=TokenUsage(),
        wall_ms=1,
        cost_usd=None,
        passed=passed,
        tests_passed=tests_passed,
        tests_total=2,
        public_failed=False,
        failure_excerpt="",
        agent_error=None,
        performance_ms=performance_ms,
        readability=readability,
    )


def _solution(
    name: str,
    passed: bool,
    tokens: int,
    wall_ms: int,
    performance_ms: float | None,
) -> SolutionRun:
    return SolutionRun(
        agent=name,
        source="def solution(N):\n    return 0\n",
        attempts=[
            AttemptRecord(
                number=1,
                session_id="s",
                usage=TokenUsage(input_tokens=tokens),
                wall_ms=wall_ms,
                cost_usd=None,
                passed=passed,
                tests_passed=1 if passed else 0,
                tests_total=1,
                public_failed=False,
                failure_excerpt="",
                agent_error=None,
            )
        ],
        performance_ms=performance_ms,
        readability=80,
        readability_notes="",
    )
