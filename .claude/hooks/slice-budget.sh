#!/usr/bin/env bash
# Stop hook.
# Warns loudly when the staged + unstaged diff vs origin/main exceeds the
# slice budget (400 LOC, lockfiles excluded). Pure warning — never blocks.

set -euo pipefail

ROOT=$(git rev-parse --show-toplevel 2>/dev/null || true)
if [ -z "$ROOT" ]; then
  exit 0
fi
cd "$ROOT"

BUDGET=400

# Use origin/main if available; fall back to current HEAD's last merge base.
BASE="origin/main"
if ! git rev-parse --verify "$BASE" >/dev/null 2>&1; then
  BASE=$(git merge-base HEAD HEAD~10 2>/dev/null || echo "HEAD")
fi

# Diffstat excluding lockfiles. Sum insertions only — deletions are usually
# offset by inserts for refactors and the rule is about new code.
LINES=$(
  git diff "$BASE"...HEAD --shortstat \
    -- ':(exclude)*.lock' \
       ':(exclude)package-lock.json' \
       ':(exclude)uv.lock' \
       ':(exclude)pnpm-lock.yaml' \
       ':(exclude)yarn.lock' \
    2>/dev/null \
  | grep -oE '[0-9]+ insertion' \
  | grep -oE '^[0-9]+' \
  || echo 0
)

# Add unstaged + staged work to the count too — still relevant pre-commit.
LIVE=$(
  git diff HEAD --shortstat \
    -- ':(exclude)*.lock' \
       ':(exclude)package-lock.json' \
       ':(exclude)uv.lock' \
       ':(exclude)pnpm-lock.yaml' \
       ':(exclude)yarn.lock' \
    2>/dev/null \
  | grep -oE '[0-9]+ insertion' \
  | grep -oE '^[0-9]+' \
  || echo 0
)

TOTAL=$(( ${LINES:-0} + ${LIVE:-0} ))

if [ "$TOTAL" -gt "$BUDGET" ]; then
  cat <<EOF >&2

⚠️  Slice budget exceeded: $TOTAL lines (budget: $BUDGET, lockfiles excluded).
   Per CLAUDE.md, each PR should be one vertical slice ≤ $BUDGET LOC.
   Options:
     • Run the slice-splitter subagent for a proposed 2-/3-way split
     • If this is genuinely one slice (e.g. central to the project thesis),
       call it out in the PR description with the rationale.

EOF
fi

exit 0
