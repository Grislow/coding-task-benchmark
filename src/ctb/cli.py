import argparse
import sys
from datetime import datetime, timezone
from pathlib import Path

from ctb.agents import ClaudeAgent, CodexAgent, GrokAgent
from ctb.fake_agent import FakeAgent
from ctb.models import CodingAgent
from ctb.orchestrate import run_benchmark
from ctb.report import write_report
from ctb.server import bind
from ctb.session import RunSession

# Opus medium and gpt-6.1-sol xhigh are fixed choices. The other three are high:
# Sonnet's FrontierCode score peaks at xhigh and drops at max, and high is the
# step up from Claude Code's medium default for a harder coding task. Astra's
# DeepSWE score barely moves above high. Grok 4.7 publishes DeepSWE at high.
INTERVIEW_AGENTS = (
    "claude:opus:medium",
    "claude:sonnet:high",
    "codex:gpt-6-astra:high",
    "codex:gpt-6.1-sol:xhigh",
    "grok:grok-4.7:high",
)
INTERVIEW_AUTHOR = "claude:sonnet:high"

# Levels each CLI documents. A model can still reject a level its own menu omits.
_EFFORTS = {
    "claude": frozenset({"low", "medium", "high", "xhigh", "max"}),
    "grok": frozenset({"none", "minimal", "low", "medium", "high", "xhigh", "max"}),
    "codex": frozenset({"none", "minimal", "low", "medium", "high", "xhigh", "max", "ultra"}),
}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="ctb",
        description="Benchmark one coding task across headless Claude Code, Grok, and Codex.",
    )
    sub = parser.add_subparsers(dest="command", required=True)
    run = sub.add_parser("run", help="Paste a task and score each agent's solution.")
    run.add_argument(
        "task",
        nargs="?",
        help="Markdown file with the task. Omit it, or pass -, to read stdin.",
    )
    run.add_argument("--attempts", type=int, default=3)
    run.add_argument(
        "--agents",
        default="claude,grok",
        help=(
            "Comma-separated cli, cli:model, or cli:model:effort entries. "
            "For example claude:opus:medium."
        ),
    )
    run.add_argument(
        "--test-author",
        default="claude",
        help="Who writes the hidden tests. Same cli or cli:model form, or none.",
    )
    run.add_argument("--timeout", type=int, default=600)
    run.add_argument("--budget-usd", type=float, default=2.0)
    run.add_argument("--out", default="runs")
    run.add_argument("--skip-review", action="store_true")
    interview = sub.add_parser(
        "interview",
        help="Run the fixed five-model lineup. Pass a task file, or pipe the task on stdin.",
    )
    interview.add_argument(
        "task",
        nargs="?",
        help="Markdown file with the task. Omit it, or pass -, to read stdin.",
    )
    ui = sub.add_parser(
        "ui",
        help="Open the interview page on 127.0.0.1. Pass no task; paste it in the browser.",
    )
    ui.add_argument(
        "--agents",
        default=",".join(INTERVIEW_AGENTS),
        help="Comma-separated cli, cli:model, or cli:model:effort entries.",
    )
    ui.add_argument(
        "--test-author",
        default=INTERVIEW_AUTHOR,
        help="Who writes the hidden tests. Same form as --agents, or none.",
    )
    ui.add_argument("--port", type=int, default=8765)
    ui.add_argument("--skip-review", action="store_true")
    args = parser.parse_args(argv)
    if args.command == "ui":
        return _serve_ui(args)
    if args.command == "interview":
        args.attempts = 3
        args.agents = ",".join(INTERVIEW_AGENTS)
        args.test_author = INTERVIEW_AUTHOR
        args.timeout = 600
        args.budget_usd = 3.0
        args.out = "runs"
        args.skip_review = False
    if args.attempts < 1:
        print("attempts must be at least 1", file=sys.stderr)
        return 2
    task_text = _read_task(args.task)
    if not task_text.strip():
        print("The task description is empty.", file=sys.stderr)
        return 2
    try:
        agents = [_build_agent(name, args.timeout, args.budget_usd) for name in _names(args.agents)]
        author = None if args.test_author == "none" else _build_agent(args.test_author, args.timeout, args.budget_usd)
    except ValueError as exc:
        print(str(exc), file=sys.stderr)
        return 2
    if len({agent.name for agent in agents}) != len(agents):
        print("Agent names must be unique.", file=sys.stderr)
        return 2
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    out_dir = Path(args.out) / stamp
    print(f"Running {', '.join(agent.name for agent in agents)} -> {out_dir}", file=sys.stderr)
    report = run_benchmark(
        task_text=task_text,
        agents=agents,
        test_author=author,
        attempts=args.attempts,
        timeout_s=args.timeout,
        out_dir=out_dir,
        review=not args.skip_review,
    )
    write_report(report, out_dir)
    print(out_dir / "report.md")
    return 0


def _serve_ui(args: argparse.Namespace) -> int:
    try:
        agents = [_build_agent(name, 600, 3.0) for name in _names(args.agents)]
        author = None if args.test_author == "none" else _build_agent(args.test_author, 600, 3.0)
    except ValueError as exc:
        print(str(exc), file=sys.stderr)
        return 2
    if len({agent.name for agent in agents}) != len(agents):
        print("Agent names must be unique.", file=sys.stderr)
        return 2
    session = RunSession(
        agents,
        author,
        attempts=3,
        timeout_s=600,
        review=not args.skip_review,
        out_root=Path("runs"),
    )
    return _serve(session, args.port)


def _serve(session: RunSession, port: int) -> int:
    page = (Path(__file__).resolve().parent / "ui.html").read_text()
    server = bind(session, page, port)
    host, bound = server.server_address
    print(f"http://{host}:{bound}", file=sys.stderr)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        server.shutdown()
    return 0


def _build_agent(name: str, timeout_s: int, budget_usd: float) -> CodingAgent:
    cli, model, effort = _split_agent(name)
    if cli == "claude":
        return ClaudeAgent(timeout_s, budget_usd, model, effort)
    if cli == "grok":
        return GrokAgent(timeout_s, model, effort)
    if cli == "codex":
        return CodexAgent(timeout_s, model, effort)
    if cli == "fake":
        if model is not None or effort is not None:
            raise ValueError("fake does not take a model.")
        return FakeAgent()
    raise ValueError(f"Unknown agent '{name}'. Use claude, grok, codex, or fake.")


def _split_agent(raw: str) -> tuple[str, str | None, str | None]:
    text = raw.strip()
    cli, separator, rest = text.partition(":")
    cli = cli.strip().lower()
    if not cli:
        raise ValueError(f"Unknown agent '{raw}'. Use claude, grok, codex, or fake.")
    if not separator:
        return cli, None, None
    model, effort_separator, effort = rest.partition(":")
    chosen = model.strip()
    if not chosen:
        raise ValueError(f"Agent '{raw}' is missing a model id after the colon.")
    if not effort_separator:
        return cli, chosen, None
    level = effort.strip().lower()
    if not level:
        raise ValueError(f"Agent '{raw}' is missing a reasoning level after the model.")
    allowed = _EFFORTS.get(cli)
    if allowed is None or level not in allowed:
        raise ValueError(f"Agent '{raw}' has an unknown reasoning level '{level}'.")
    return cli, chosen, level


def _names(raw: str) -> list[str]:
    names = [part.strip() for part in raw.split(",") if part.strip()]
    if not names:
        raise ValueError("Name at least one agent.")
    return names


def _read_task(path: str | None) -> str:
    if path is None or path == "-":
        return sys.stdin.read()
    return Path(path).read_text()
