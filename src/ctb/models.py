from dataclasses import dataclass, field
from typing import Protocol


@dataclass(frozen=True)
class TokenUsage:
    input_tokens: int = 0
    output_tokens: int = 0
    cache_read_tokens: int = 0
    cache_creation_tokens: int = 0
    reasoning_tokens: int = 0

    @property
    def total(self) -> int:
        return (
            self.input_tokens
            + self.output_tokens
            + self.cache_read_tokens
            + self.cache_creation_tokens
            + self.reasoning_tokens
        )

    def add(self, other: "TokenUsage") -> "TokenUsage":
        return TokenUsage(
            input_tokens=self.input_tokens + other.input_tokens,
            output_tokens=self.output_tokens + other.output_tokens,
            cache_read_tokens=self.cache_read_tokens + other.cache_read_tokens,
            cache_creation_tokens=self.cache_creation_tokens + other.cache_creation_tokens,
            reasoning_tokens=self.reasoning_tokens + other.reasoning_tokens,
        )


@dataclass(frozen=True)
class AgentResult:
    ok: bool
    text: str
    session_id: str | None
    usage: TokenUsage
    wall_ms: int
    cost_usd: float | None
    error: str | None
    raw: dict[str, object] = field(default_factory=dict)


class CodingAgent(Protocol):
    name: str

    def complete(
        self,
        *,
        cwd: str,
        prompt: str,
        session_id: str | None,
        role: str,
    ) -> AgentResult: ...


@dataclass(frozen=True)
class AttemptRecord:
    number: int
    session_id: str | None
    usage: TokenUsage
    wall_ms: int
    cost_usd: float | None
    passed: bool
    tests_passed: int
    tests_total: int
    public_failed: bool
    failure_excerpt: str
    agent_error: str | None
    performance_ms: float | None = None
    readability: float = 0
    chosen: bool = False
    performance_note: str = ""
    readability_notes: str = ""
    setup_error: str | None = None


@dataclass(frozen=True)
class Finding:
    line: int
    rule: str
    severity: str
    issue: str
    fix: str


@dataclass(frozen=True)
class ReviewNote:
    reviewer: str
    score: float
    findings: tuple[Finding, ...]
    summary: str


@dataclass(frozen=True)
class EvalResult:
    passed: bool
    tests_passed: int
    tests_total: int
    public_failed: bool
    failure_excerpt: str
    performance_ms: float | None
    performance_note: str = ""


@dataclass
class SolutionRun:
    agent: str
    source: str
    attempts: list[AttemptRecord]
    performance_ms: float | None
    readability: float
    readability_notes: str
    reviews: list[ReviewNote] = field(default_factory=list)
    correctness: float | None = None
    performance: float | None = None
    review: float | None = None
    contract: float | None = None
    contract_notes: str = ""
    cost: float | None = None
    profile: float | None = None
    attempt_runs: list["SolutionRun"] = field(default_factory=list)

    @property
    def tokens(self) -> int:
        return sum(attempt.usage.total for attempt in self.attempts)

    @property
    def wall_ms(self) -> int:
        return sum(attempt.wall_ms for attempt in self.attempts)

    def chosen_attempt(self) -> AttemptRecord | None:
        for attempt in self.attempts:
            if attempt.chosen:
                return attempt
        if not self.attempts:
            return None
        return self.attempts[-1]

    @property
    def passed(self) -> bool:
        chosen = self.chosen_attempt()
        return chosen is not None and chosen.passed

    @property
    def cost_usd(self) -> float | None:
        amounts = [attempt.cost_usd for attempt in self.attempts if attempt.cost_usd is not None]
        if not amounts:
            return None
        return sum(amounts)


@dataclass(frozen=True)
class BenchmarkReport:
    task_title: str
    out_dir: str
    notes: list[str]
    solutions: list[SolutionRun]
    tech: str = "python"
