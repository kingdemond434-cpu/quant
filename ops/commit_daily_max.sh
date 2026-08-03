#!/usr/bin/env bash
# Commit and push whatever the daily sweep produced. Output not pushed by end of cycle earns zero
# credit (§33): git is the institutional memory, VPS disk is not.
#
# DELIBERATELY NARROW. It stages ONLY tracked-file changes under docs/ -- never data/ (gitignored
# by design), never new files, never anything the sweep did not already own. A commit step with a
# wide net is how an automated loop ends up pushing something nobody reviewed.
set -uo pipefail
cd "$(dirname "$0")/.." || exit 0
git add -u docs/ 2>/dev/null || exit 0
if git diff --cached --quiet; then
    echo "commit_daily_max: nothing to commit"
    exit 0
fi
git -c user.name="quant-daily-max" -c user.email="noreply@localhost" \
    commit -q -m "chore(daily-max): sweep output $(date -u +%Y-%m-%d)" || exit 0
for i in 1 2 3 4; do
    git push origin HEAD 2>&1 && break || sleep $((2 ** i))
done
