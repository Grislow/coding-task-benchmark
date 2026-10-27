#!/bin/sh
set -u
mode=${1:-tracked}
pattern='/Users/[A-Za-z]|/home/[a-z][a-z0-9_-]*/|sk-ant-[A-Za-z0-9_-]{20}|sk-[A-Za-z0-9]{40}|xai-[A-Za-z0-9]{20}|AIza[0-9A-Za-z_-]{30}|ghp_[A-Za-z0-9]{30}|-----BEGIN [A-Z ]*PRIVATE KEY-----'
extra="$(git rev-parse --git-dir)/info/private-patterns"
if [ -s "$extra" ]; then
  pattern="$pattern|$(grep -v '^#' "$extra" | grep . | paste -sd '|' -)"
fi
status=0
if [ "$mode" = staged ]; then
  found=$(git diff --cached -U0 --no-color -- . ':!scripts/check-private.sh' | grep -E '^\+' | grep -nE "$pattern")
  email=$(git var GIT_AUTHOR_IDENT | sed -E 's/.*<([^>]*)>.*/\1/')
  case "$email" in
    *@users.noreply.github.com) ;;
    *) echo "Commit email $email is not a GitHub noreply address. Run: git config user.email <id>+<login>@users.noreply.github.com"; status=1 ;;
  esac
else
  found=$(git grep -nE "$pattern" -- . ':!scripts/check-private.sh')
fi
if [ -n "$found" ]; then
  echo "Private paths, emails or keys found:"
  echo "$found"
  status=1
fi
exit $status
