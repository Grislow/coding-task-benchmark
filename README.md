# coding-task-benchmark

Paste a Codility-style task. The harness gives each coding agent its own directory and up to three attempts, then scores the `solution.py` files on one frozen test suite.

The solvers are the Claude Code and Grok CLIs in headless mode. The harness never logs into Codility. You read the report and submit the solution you are willing to defend.

## Run

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev,fastapi]"
```

`fastapi` installs FastAPI and httpx, which FastAPI tasks and the contract check need. Ruff is a dependency, so the static check always runs.

During the interview, pass only the task. The lineup is already chosen:

```bash
pbpaste | ./interview
./interview task.md
```

That runs three attempts on each of these models, at the same time. Each row has its own reasoning level, because that changes the code the model writes:

| Solver | Model | Reasoning |
| --- | --- | --- |
| Claude | opus | medium |
| Claude | sonnet | high |
| Codex | gpt-6-astra | high |
| Codex | gpt-6.1-sol | xhigh |
| Grok | grok-4.7 | high |

Opus at medium and gpt-6.1-sol at xhigh are fixed. The other three are high. Sonnet 5.5's FrontierCode score peaks at xhigh and falls at max, because max makes edits the grader treats as out of scope, and high is the step up from Claude Code's medium default. Astra's DeepSWE score barely moves above high. Grok 4.7's published DeepSWE number is the high-effort run, and high is that model's default. Codex is started with `--ignore-user-config`, so an `xhigh` in `~/.codex/config.toml` would not apply. The catalog default for these Codex models is low.

Claude Opus at high writes the hidden tests before those five start. It is not one of the solvers, so no solver is graded on tests it wrote itself. Change the list in [src/ctb/cli.py](src/ctb/cli.py) before the interview, not during it.

To pick models yourself:

```bash
ctb run examples/binary_gap.md --agents claude,grok
```

Offline walkthrough, with no model calls. The `fake` agent only knows the bundled BinaryGap sample, and it misses on purpose on attempt 1:

```bash
ctb run examples/binary_gap.md --agents fake --test-author fake --skip-review
```

The report is `runs/<timestamp>/report.md`.

## Local page

`./ui` opens the same five models in a browser on this machine. Paste the task there, watch each attempt, open a solution, and paste your own to score it on that run's suite. A line entered on the page is shown across the top for 5 seconds. It is not stored and not sent anywhere.

```bash
./ui
```

The page listens on `127.0.0.1` port 8765 only. `./interview` still runs in the terminal.

To open the page without calling a model:

```bash
ctb ui --agents fake --test-author fake --skip-review
```

## Before an interview

```bash
./check
```

Prints the `claude`, `codex` and `grok` versions, then gives each model in the lineup a one-line task in a real solve folder. It catches a missing login, an unknown model id, or a permission rule that blocks file access. It exits 1 if any model cannot run. `./ui` runs the same check when it starts and shows the result in the Agents section, with a Check again button.

During a run, a model that cannot run is retried once after 5 seconds. If it still fails, the attempt is marked Setup, is not scored or ranked, and shows the model's own message. Once the run finishes, Re-run in that model's lane runs it again on the same suite, with reviews.

## What a run does

1. Reads the task. Python blocks that contain `assert` become public tests.
2. The test-author CLI writes `test_hidden.py` and `perf_cases.py` in its own directory. Those files are copied out and frozen. Each solver works in its own temporary directory outside `runs/`, so it cannot reach the author's directory or `hidden/`. Its directory is copied to `runs/<timestamp>/work/` when it finishes.
3. Each solver gets a fresh git repo containing `task.md` and a `solution.py` stub. A git root in the workspace keeps Grok from treating this benchmark repo as the project. The solvers start together.
4. Each solver takes its attempts in order. Attempt 1 solves the task. Each later attempt sees the previous score and writes a different approach. The harness keeps the better one: passing tests, then a runtime at least 10 percent lower, then clearer code.
5. For a FastAPI task, the contract check probes each kept solution's app.
6. After every attempt has finished, each kept solution is reviewed by the agents from other model families. A model never reviews its own family's code. The reviews start together. A reviewer does not see the test score.
7. The profile is written from the weights below. A dimension that was not measured is dropped and the remaining weights are rescaled.

| Dimension | Weight | Source |
| --- | ---: | --- |
| Correctness | 40 | Frozen pytest suite. A failing public example scores 0. |
| Performance | 20 | Median runtime of `perf_cases.py`, with a cProfile trace of where the time went. Fastest passing solution scores 100. |
| Static | 15 | Function length and complexity (70 percent) and Ruff (30 percent, minus 10 per issue). The rule set depends on `--tech`. |
| Review | 15 | Mean of the reviewers' scores. Each review is a list of findings, and the score is 100 minus 25 per blocker, 10 per major and 3 per minor. |
| Contract | 10 | FastAPI only: share of contract checks passed. Dropped for Python tasks. |
| Cost | 10 | Token total and wall clock, averaged. Lower is better. Dollars are shown when the CLI reports them. |

## Tech, static checks and review

`--tech python` (the default) or `--tech fastapi` on `ctb run`, `ctb interview` and `ctb ui` picks the rule set. On the page, `POST /task?tech=fastapi` picks it per run.

| Tech | Ruff rules | Rubric |
| --- | --- | --- |
| python | `E,F,I,UP,B,A,SIM,C4,PERF,RET,PL`, ignoring `PLR2004` | `rubrics/common.md` + `rubrics/python.md` |
| fastapi | the Python rules plus `FAST,ASYNC`, also ignoring `PLR0913` and `PLR0917` because query parameters are arguments | the Python rubric + `rubrics/fastapi.md` |

The rubrics live in [src/ctb/rubrics](src/ctb/rubrics). Each rule has an id such as `PY-STDLIB` or `API-VALID` and a default severity. The reviewer sees the source with line numbers and replies with findings only: line, rule id, severity, issue and fix. The harness drops a finding whose rule is not in that tech's rubric or whose line does not exist, keeps one finding per line and rule, and computes the score itself. The reviewer is told not to report what a linter catches, not to judge correctness or speed, and never to reward comments. A comment that restates the code is a finding. A missing comment never is.

The contract check builds the app with `solution()`, passing the first `perf_cases.py` arguments when there are any. It checks that every route declares a response model (a 204 route is exempt) and that none answers bad input with a 500: a non-numeric path id, a non-numeric number in the query, and a missing, list or string body on POST, PUT and PATCH.

## Agents and models

Each entry is a CLI, `cli:model`, or `cli:model:effort`. The model id is whatever that CLI accepts. Claude's own help lists aliases such as `opus` and `sonnet`. Run `grok models` for Grok ids. Codex takes the id you would pass to `codex exec -m`. The effort is that CLI's reasoning level: Claude uses `--effort`, Grok uses `--effort`, and Codex uses `-c model_reasoning_effort`. Omit it to leave the CLI default. A model can reject a level its own menu does not list.

The same CLI can run twice when the models differ. `claude:opus,claude:sonnet` is two solvers. `claude,claude` is rejected because both would be named `claude`.

Omitting the model uses that CLI's configured default. The default agent list is `claude,grok`.

Codex is `codex exec --json`. The first attempt uses `--approve-for-me`, which runs in the workspace-write sandbox. Later attempts use `codex exec resume`, which has no sandbox flag, so those calls bypass approvals rather than hang on a prompt. Codex token totals come from each `turn.completed` usage object. Cached input is reported inside `input_tokens`, and the harness splits it back out. Dollar cost is not in that stream.

Claude Code:

- `claude -p --output-format json --safe-mode --disable-slash-commands --strict-mcp-config`
- Solvers use `--permission-mode bypassPermissions` so they can run Python in the workspace
- `--max-budget-usd` defaults to 2 per call
- Resume with `--resume`
- Add `--model <model>` when the agent entry is `claude:<model>`
- Add `--effort <level>` when the entry is `claude:<model>:<effort>` (`low`, `medium`, `high`, `xhigh`, `max`)

Grok:

- `grok -p --output-format json --sandbox strict --max-turns 25 --no-subagents --disable-web-search`
- `GROK_CLAUDE_SKILLS_ENABLED=false` and `GROK_CURSOR_SKILLS_ENABLED=false` for that process
- Resume with `-r`
- Add `-m <model>` when the agent entry is `grok:<model>`
- Add `--effort <level>` when the entry is `grok:<model>:<effort>` (`none`, `minimal`, `low`, `medium`, `high`, `xhigh`, `max`)

Codex:

- `codex exec --json --approve-for-me --ignore-user-config`. `--approve-for-me` runs in the workspace-write sandbox and cannot be combined with `--sandbox`
- Review uses `--sandbox read-only` and `--output-schema`
- Resume with `codex exec resume <thread-id>`
- Add `-m <model>` when the agent entry is `codex:<model>`
- Add `-c model_reasoning_effort="<level>"` on the first attempt and on resume. `--ignore-user-config` would otherwise drop it. Levels include `low`, `medium`, `high`, `xhigh`, `max`, and `ultra`.

Token counts are whatever that invocation's JSON `usage` object reports. Wall clock is the process time around the CLI. Grok often omits dollar cost on subscription logins. The cost score still uses tokens and time.

`--safe-mode` is deliberate. `--bare` would ignore the Claude subscription login.

## Limits

Grok's `strict` sandbox can read the workspace and not the rest of the disk. On macOS it does not block network for child processes. Web search is turned off anyway.

Claude with Bash can still read other files your user can read. Hidden tests live outside the solver directory and are not named in the prompt. The repair prompt includes pytest failure text, which reveals the assertion that failed.

The first real Grok run in a new folder may stop on a trust prompt. Run Grok's own trust command in that workspace if it says the folder is untrusted.

Codex attempts after the first bypass approvals. `codex exec resume` does not accept a sandbox flag, and a prompt would hang the run. Those later attempts can read files outside the workspace.

Usage on a resumed Grok session is stored as reported. If a live run shows cumulative totals, the next change is to store the difference between attempts.
