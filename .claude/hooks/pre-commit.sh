#!/usr/bin/env bash
# PreToolUse hook on Bash tool.
# Runs only for `git commit` invocations. Two policies:
#   1. Branch policy: refuse commits on main, or on the same branch the
#      session started on if it has zero commits ahead of origin/main.
#   2. Quality gate: run `make check` (lint + typecheck + tests). If it
#      fails, block the commit.
#
# Exit 0 = allow tool. Exit 2 = block tool with the printed reason.

set -euo pipefail

ROOT=$(git rev-parse --show-toplevel 2>/dev/null || true)
if [ -z "$ROOT" ]; then
  exit 0
fi
cd "$ROOT"

# --- Read the tool input from stdin -------------------------------------
# Claude Code passes hook payload as JSON on stdin. We need .tool_input.command.
INPUT=$(cat || true)
COMMAND=$(printf '%s' "$INPUT" | python3 -c '
import json, sys
try:
    data = json.load(sys.stdin)
    print(data.get("tool_input", {}).get("command", ""))
except Exception:
    pass
' 2>/dev/null || true)

# Only intercept actual commit commands. Skips git status, log, diff, etc.
# Also skips `git rev-parse`, `git rev-list`, etc. used by other hooks.
if ! [[ "$COMMAND" =~ (^|[[:space:];|&]+)git[[:space:]]+commit([[:space:]]|$) ]]; then
  exit 0
fi

# --- Policy 1: branch ---------------------------------------------------
BRANCH=$(git rev-parse --abbrev-ref HEAD)

if [ "$BRANCH" = "main" ] || [ "$BRANCH" = "master" ]; then
  cat <<EOF >&2
✗ Refusing to commit on $BRANCH. Create a feature branch:
    git checkout -b claude/<feature-name>
EOF
  exit 2
fi

# Refuse if we started on this branch and it has no commits ahead of main —
# i.e. the branch isn't "fresh for this session's work".
SESSION_BRANCH_FILE=".claude/.session-branch"
if [ -f "$SESSION_BRANCH_FILE" ]; then
  STARTED_ON=$(cat "$SESSION_BRANCH_FILE")
  if [ "$BRANCH" = "$STARTED_ON" ]; then
    # Only enforce the ahead-count when we can trust origin/main locally.
    # On a fresh clone without `git fetch`, rev-list returns 0 even for
    # branches with real commits — that's a false positive we won't take.
    if git rev-parse --verify "origin/main" >/dev/null 2>&1; then
      AHEAD=$(git rev-list --count "origin/main..HEAD")
      if [ "$AHEAD" -eq 0 ]; then
        cat <<EOF >&2
✗ Session started on '$BRANCH' with no commits ahead of origin/main.
  Create a feature branch first:
      git checkout -b claude/<feature-name>
EOF
        exit 2
      fi
    fi
  fi
fi

# --- Policy 2: quality gate ---------------------------------------------
# Skip if there are no Python or TypeScript changes — pure docs/config
# commits don't need the full check.
TOUCHED=$(
  {
    git diff --cached --name-only
    git diff --name-only
  } | grep -E '^(api/|web/src/)' | head -1 || true
)

if [ -n "$TOUCHED" ]; then
  echo "→ Running 'make check' (api/ or web/ changes detected)..." >&2
  if ! make check >&2 2>&1; then
    cat <<EOF >&2

✗ make check failed — fix issues before committing.
  Run 'make format' to auto-fix style; mypy/test failures need real fixes.
EOF
    exit 2
  fi
  echo "✓ make check passed" >&2
fi

exit 0
