# Product

<!-- impeccable:product-schema 1 -->

## Platform

web

## Stack

Plain HTML, CSS, and JavaScript, served by the existing Python package on `127.0.0.1`. No frontend framework and no new dependencies. The choice was fixed in the approved local-page plan.

## Users

The person in a live Codility interview. They sit at this machine with the Codility tab beside this page, paste the task, watch the agents, and later paste a solution they can explain into Codility themselves.

Other people watch a screen recording of this same page. They do not use the controls. They read the board and the message the interviewee flashes.

## Product Purpose

Run one pasted coding task through the local harness and show, while it is happening, which attempt each agent is on, what it scored, and how the interviewee's own paste compares. Success is leaving the interview with a solution the interviewee can defend, and with the watchers able to read a short message on the recording.

## Positioning

The page is the harness, not a Codility client. Five headless coding CLIs solve the same frozen pytest suite in parallel, three attempts each, then grade each other. The interviewee's paste is scored on that same suite. Nothing in the product logs into Codility or submits an answer.

## Operating Context

Used once, beside a Codility tab, for the length of one task. The task text is copied from Codility. The chosen solution is copied back by hand. A recording is already running. The CLI `./interview` still works and is unchanged.

## Capabilities and Constraints

- Paste a task and start the fixed interview lineup: Claude Opus medium, Claude Sonnet high, Codex gpt-6-astra high, Codex gpt-6.1-sol xhigh, Grok 4.7 high. Sonnet also writes the hidden tests. Three attempts, 600 second timeout, $3 Claude budget, peer review on.
- One run at a time. A second task waits until the current one is done.
- Show each attempt as waiting, running, passed, or failed, with the test count when it has finished.
- Open any finished attempt's `solution.py`, and the kept solution.
- Show the same profile as `report.md`: correctness 40, performance 20, readability 15, extensibility 10, peer 10, cost 5. Missing dimensions are dropped and the rest rescaled.
- Paste the interviewee's own solution once the frozen suite exists. Score it on that suite and show the other agents' reviews. Their row is named `you`.
- A message field: Enter shows that line across the top for 5 seconds, large enough to read on the recording. The line is not stored and not sent anywhere.
- Listens on `127.0.0.1` only. `runs/` stays gitignored. No accounts, no network API, no Codility traffic.
- `ctb ui` may take `--agents` and `--test-author` so the page can be checked with the offline `fake` agent.

## Brand Commitments

Binding constraints from the interviewee, not a visual system: the page should feel calm and precise, with a clear point of view rather than a generic tool, and the nearest reference is a code editor. It must not feel playful, loud, like a marketing site, or like a cramped admin dashboard.

## Evidence on Hand

The harness in `src/ctb`, the report written to `runs/<timestamp>/report.md`, and the sample task `examples/binary_gap.md`. There is no logo, no photograph, and no existing interface.

## Product Principles

- The recording is a reader. Anything meant for the watchers is large and brief.
- The board shows the run that is actually happening, including failed attempts and empty scores.
- The interviewee's paste and the agents' code are scored on one frozen suite, so the numbers compare.
- The page never acts on Codility. Submitting stays a manual copy.
- One command opens it, and it never leaves the machine.
