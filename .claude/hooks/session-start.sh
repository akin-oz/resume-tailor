#!/usr/bin/env bash
# SessionStart hook.
# Records the current branch (so `pre-commit.sh` can detect "user never
# branched off"), and warns loudly if the session is starting on main.
#
# Always exits 0; this hook is informational only.

set -euo pipefail

# Find the repo root; if we're not in one, do nothing.
ROOT=$(git rev-parse --show-toplevel 2>/dev/null || true)
if [ -z "$ROOT" ]; then
  exit 0
fi
cd "$ROOT"

mkdir -p .claude

BRANCH=$(git rev-parse --abbrev-ref HEAD 2>/dev/null || echo "unknown")
echo "$BRANCH" > .claude/.session-branch

if [ "$BRANCH" = "main" ] || [ "$BRANCH" = "master" ]; then
  cat <<EOF >&2
⚠️  Session started on $BRANCH. Per project policy, commits on $BRANCH are blocked.
   Create a feature branch before making changes:
       git checkout -b claude/<feature-name>
EOF
fi

exit 0
