# Running the agents in Docker

Research notes, 2026-10-24. Nothing here is built yet.

## Why

Today every solver runs on this Mac as the logged-in user:

- Claude solves with `--permission-mode bypassPermissions` and the Bash tool. It can read and write anything the user can.
- Codex runs every attempt in its `workspace-write` sandbox. Sessions are no longer resumed, so no attempt needs `--dangerously-bypass-approvals-and-sandbox`.
- Grok uses its own `--sandbox strict`, which is the only real limit we have.
- pytest and the perf runner execute each agent's `solution.py` on the host, also unsandboxed.

The prompt asks agents to stay in their directory, but the prompt is not a boundary. A container makes one: the agent sees its workspace and nothing else, and the grader runs untrusted code with no network.

Docker also fixes some interoperability problems. The Python, pytest, ruff and FastAPI versions that grade the run would be the same on every machine, so the results don't depend on what is installed on this Mac.

## Login inside a Linux container

Each CLI stores its login differently. A container can't see the macOS Keychain.

| CLI | Where the login lives on this Mac | What works in a container |
| --- | --- | --- |
| claude | macOS Keychain (`Claude Code-credentials`) | `claude setup-token` once on the host, then pass `CLAUDE_CODE_OAUTH_TOKEN` (uses the subscription). Or `ANTHROPIC_API_KEY`, billed per token. |
| codex | `~/.codex/auth.json` | Mount it read-only at `/root/.codex/auth.json`, or pass `CODEX_API_KEY`. Keep `--ignore-user-config`. |
| grok | `~/.grok/auth.json` | Mount it read-only. This needs a check: the token may be tied to the machine or refresh in place, and a read-only mount stops a refresh. |

Pass the tokens with `--env-file`, never in the command line. `ps` and the run logs would show them otherwise.

## Recommended shape

1. **One image**, `ctb-agent`: Debian slim, Node 22, Python 3.12, pytest, ruff, fastapi, httpx, and the three CLIs pinned to the versions `ctb check` prints. Build it once before the interview.
2. **One container per agent per run**, started with `docker run -d --rm` and the workspace bind-mounted at `/work`. Each attempt is a `docker exec`. Sessions are not resumed: each retry prompt carries the previous attempt's code and results, so a fresh container per attempt would also work.
3. **The CLIs' own sandboxes off inside the container.** Codex's Landlock sandbox and Grok's strict profile often can't start in an unprivileged container, and the container already sets the limit. So the flags would become: Codex always `--dangerously-bypass-approvals-and-sandbox`, Grok `--sandbox off` (check the exact name).
4. **Network**: the solvers need their API hosts. Start with the default bridge network. An egress allowlist (api.anthropic.com, api.openai.com / chatgpt.com, the grok.com API) via a small proxy is a later step.
5. **Grading in its own container** with `--network none --read-only`, a tmpfs at `/tmp`, `--cpus 1 --memory 1g`, and a `--pids-limit`. Untrusted code then can't call out or fork-bomb the Mac, and timings are steadier because each grade gets the same CPU share.
6. **Timeouts**: killing the `docker exec` client does not stop the process inside the container. The harness has to run `docker kill <container>` (or `timeout` inside the exec) when an attempt hits the limit. The process-group kill added on 2026-10-24 only works for the host path.

## Cost

- Startup: `docker run` takes about 1 s per agent per run. `docker exec` adds about 100 ms per attempt. That's small next to minute-long agent calls.
- macOS bind mounts are slower than native disk. Workspaces are tiny, so it shouldn't matter. Keep `runs/` on the host and copy results out at the end, as `_solve_apart` already does.
- Docker Desktop has to be running during the interview. That's one more thing that can fail live, so the startup check should check it too.
- The Grok login is the biggest unknown. Prove it works in a container before building the rest.

## Where it would plug in

- `agents._invoke` gets a `runner` that wraps the command as `docker exec -w /work/<agent> <container> …`. The command builders don't change.
- `workspace.make_workspace` keeps writing to the host. The bind mount exposes it.
- `evaluate._run` and `contract.contract_report` wrap their subprocess calls the same way, against the grading container.
- A `--docker` flag on `ctb run`, `ui` and `check` selects it. Keep the host path as the default until one full interview has run in containers.
