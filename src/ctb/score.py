from ctb.models import AttemptRecord, SolutionRun

WEIGHTS: dict[str, float] = {
    "correctness": 40,
    "performance": 20,
    "readability": 15,
    "extensibility": 10,
    "peer": 10,
    "cost": 5,
}


def correctness_score(tests_passed: int, tests_total: int, public_failed: bool) -> float | None:
    if tests_total <= 0:
        return None
    if public_failed:
        return 0.0
    return 100.0 * tests_passed / tests_total


def performance_scores(times_ms: list[float | None], passed: list[bool]) -> list[float | None]:
    return _ratio_scores(times_ms, passed)


def cost_scores(tokens: list[int], wall_ms: list[int], passed: list[bool]) -> list[float | None]:
    token_score = _ratio_scores([float(value) for value in tokens], passed)
    time_score = _ratio_scores([float(value) for value in wall_ms], passed)
    combined: list[float | None] = []
    for tokens_part, time_part in zip(token_score, time_score, strict=True):
        if tokens_part is None or time_part is None:
            combined.append(None)
        else:
            combined.append((tokens_part + time_part) / 2)
    return combined


def chosen_index(attempts: list[AttemptRecord]) -> int:
    best = 0
    for index, attempt in enumerate(attempts):
        if index > 0 and _better_attempt(attempt, attempts[best]):
            best = index
    return best


def apply_profile(solutions: list[SolutionRun]) -> None:
    passed = [solution.passed for solution in solutions]
    performances = performance_scores(
        [solution.performance_ms for solution in solutions],
        passed,
    )
    costs = cost_scores(
        [solution.tokens for solution in solutions],
        [solution.wall_ms for solution in solutions],
        passed,
    )
    for solution, performance, cost in zip(solutions, performances, costs, strict=True):
        selected = solution.chosen_attempt()
        if selected is None:
            solution.correctness = None
        else:
            solution.correctness = correctness_score(
                selected.tests_passed,
                selected.tests_total,
                selected.public_failed,
            )
        solution.performance = performance
        solution.cost = cost
        solution.extensibility = _mean([review.extensibility for review in solution.reviews])
        solution.peer = _mean(
            [
                (review.correctness + review.readability + review.extensibility) / 3
                for review in solution.reviews
            ]
        )
        solution.profile = weighted_score(_parts(solution))


def weighted_score(parts: dict[str, float | None]) -> float | None:
    present = {name: value for name, value in parts.items() if value is not None}
    weight_total = sum(WEIGHTS[name] for name in present)
    if weight_total == 0:
        return None
    return sum(present[name] * WEIGHTS[name] for name in present) / weight_total


def _better_attempt(new: AttemptRecord, old: AttemptRecord) -> bool:
    new_score = _rank_correctness(new)
    old_score = _rank_correctness(old)
    if new_score != old_score:
        return new_score > old_score
    if _clearly_faster(new.performance_ms, old.performance_ms):
        return True
    if _clearly_faster(old.performance_ms, new.performance_ms):
        return False
    return new.readability > old.readability


def _rank_correctness(attempt: AttemptRecord) -> float:
    score = correctness_score(attempt.tests_passed, attempt.tests_total, attempt.public_failed)
    if score is None:
        return -1
    return score


def _clearly_faster(new_ms: float | None, old_ms: float | None) -> bool:
    if new_ms is None:
        return False
    if old_ms is None:
        return True
    return new_ms < old_ms * 0.9


def _parts(solution: SolutionRun) -> dict[str, float | None]:
    return {
        "correctness": solution.correctness,
        "performance": solution.performance,
        "readability": solution.readability,
        "extensibility": solution.extensibility,
        "peer": solution.peer,
        "cost": solution.cost,
    }


def _ratio_scores(values: list[float | None], passed: list[bool]) -> list[float | None]:
    eligible = [
        value
        for value, ok in zip(values, passed, strict=True)
        if ok and value is not None and value > 0
    ]
    if not eligible:
        return [None for _ in values]
    best = min(eligible)
    scores: list[float | None] = []
    for value, ok in zip(values, passed, strict=True):
        if not ok or value is None or value <= 0:
            scores.append(0.0)
        else:
            scores.append(100.0 * best / value)
    return scores


def _mean(values: list[float]) -> float | None:
    if not values:
        return None
    return sum(values) / len(values)
