# Product

<!-- impeccable:product-schema 1 -->

## Platform

web

## Stack

Plain HTML, CSS, and JavaScript, served by the existing Python package on `127.0.0.1`. No frontend framework and no new dependencies. The choice was fixed in the approved local-page plan.

## Users

A developer who wants to test themselves against AI. They paste a programming task, watch coding agents race on it, and paste their own solution to see how it ranks on the same hidden tests.

Sometimes other people watch a screen recording of the page, for example when the developer works through a task in front of reviewers. Those viewers do not use the controls. They read the board and any message the developer shows across the top.

## Product Purpose

Run one pasted coding task through the local harness and show, while it is happening, which attempt each agent is on, what it scored, and how the developer's own solution compares. Success is a fair, side-by-side comparison: every solution, human or AI, graded on one frozen suite.

## Positioning

The page is the harness, not a client for any task platform. Headless coding CLIs solve the same frozen test suite in parallel, three attempts each, then review each other. The developer's paste is scored on that same suite. Nothing in the product logs into a task platform or submits an answer.

## Operating Context

Used for the length of one task. The task text is pasted in, and any solution leaves the page by hand. A screen recording may be running. Start it with `make start`.

## Capabilities and Constraints

- Paste a task and start the default lineup from `ctb.toml`. The test author writes the hidden tests first and is not one of the solvers. The config dialog can switch models, reasoning levels and time limits. A model never reviews its own family's code.
- One run at a time. A second task waits until the current one is done.
- Show each attempt as waiting, running, passed, or failed, with the test count when it has finished.
- Open any finished attempt's solution, and the kept solution.
- Show the same profile as `report.md`: correctness 40, performance 20, static 15, review 15, contract 10 (FastAPI and Express only), cost 10. Missing dimensions are dropped and the rest rescaled.
- Paste your own solution once the frozen suite exists, as many times as you like. Each paste is scored on that suite and reviewed by the agents. Their rows are named `you`.
- A message field: Enter shows that line across the top, 10 seconds by default, large enough to read on a recording. Messages stack. They are not stored and not sent anywhere.
- Listens on `127.0.0.1` only. `runs/` stays gitignored. No accounts, no network API, no traffic to a task platform.
- `make demo` opens the page with the offline `fake` agent.

## Brand Commitments

The page should feel calm and precise, with a clear point of view rather than a generic tool, and the nearest reference is a code editor. It must not feel playful, loud, like a marketing site, or like a cramped admin dashboard.

## Evidence on Hand

The harness in `src/ctb`, the report written to `runs/<timestamp>/report.md`, and the sample task `examples/binary_gap.md`.

## Product Principles

- The board shows the run that is actually happening, including failed attempts and empty scores.
- Your paste and the agents' code are scored on one frozen suite, so the numbers compare.
- A recording is a reader. Anything meant for viewers is large and brief.
- The page never acts on a task platform. Submitting stays a manual copy.
- One command opens it, and it never leaves the machine.
