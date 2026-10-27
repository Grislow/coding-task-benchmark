---
name: committer
description: Stage and commit the current working tree with Conventional-Commit message. Use when asked to commit work on a feature branch or main branch. Works from git state alone. Use on phrases like "commit".
---

# committer

You create a single well-formed commit from the current working tree. Derive everything from git. Run every git command from the project root.

## Rules

- ALWAYS commit as `25483360+Grislow@users.noreply.github.com`. If `git config user.email` shows another address, run `git config user.email 25483360+Grislow@users.noreply.github.com` before committing
- NEVER use `--no-verify`. If the pre-commit check fails, stop and report what it found

## Instructions

### Step 1 - Inspect state

```bash
git status
git diff
git diff --staged
git log --oneline -5
git branch --show-current
```

### Step 2 - Stage

If nothing is stages: `git add -A`.

### Step 3 - Resolve type from changes

You will always be committing to `main`.

Resolve the type of the change from the diffs.

This is an expanded version of conventional commits that includes planning and ideation.

Available types:

- ci
- docs
- refactor
- test
- build
- perf
- style
- chore
- ai
- idea
- plan

### Step 4 - Write the message

Follow the below format exactly. Keep it succinct.

Omit the `TICKET-ID` and `Refs` if one is not available.

```txt
[TICKET-ID] type(scope): short imperative description

- what changed
- why / impact, if useful

Refs: TICKET-ID

<the Co-Authored-By trailer for your provider, from the table below>
```

End the message with one `Co-Authored-By` trailer for the model writing it. Use the row for your provider and put your exact model name in place of `<model>`.

| Provider | Trailer |
|---|---|
| Anthropic (Claude) | `Co-Authored-By: Claude <model> <noreply@anthropic.com>` |
| OpenAI (Codex, GPT) | `Co-Authored-By: <model> <noreply@openai.com>` |
| xAI (Grok) | `Co-Authored-By: <model> <noreply@x.ai>` |

### Step 5 - Commit with a heredoc to preserve line breaks

```bash
git commit -F - <<'EOF'
...
EOF
```

### Step 6 - Output

Report the final subject line and the commit hash. Nothing else.
