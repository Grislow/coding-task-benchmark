---
name: committer
description: Stage and commit the current working tree with Conventional-Commit message. Use when asked to commit work on a feature branch or main branch. Works from git state alone. Use on phrases like "commit".
---

# committer

You create a single well-formed commit from the current working tree. Derive everything from git. Run every git command from the project root.

## Rules

- ALWAYS push after committing - this is a personal project and not deployed anywhere, perfectly safe

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

You will always be pushing to `main`.

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

Co-Authored-By: {your model name from system context} <noreply@anthropic.com> {same format but other model / email for grok or openai}
```

### Step 5 - Commit with a heredoc to preserve line breaks

```bash
git commit -F - <<'EOF'
...
EOF
```

### Step 6 - Push

```bash
git push
```

### Step 7 - Output

Report the final subject line and the commit hash. Nothing else.
