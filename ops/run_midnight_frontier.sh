#!/usr/bin/env bash
# One midnight frontier: deterministic evidence production, then the fenced Codex reasoner.
set -uo pipefail
cd "$(dirname "$0")/.."
mkdir -p data
exec 8>data/.midnight_controller_cycle.lock
if ! flock -n 8; then
    echo "midnight controller cycle already running; refusing a duplicate launch"
    exit 0
fi

# Publish the in-progress state before long-running deterministic work. This prevents yesterday's
# successful status from masking a hung current cycle.
bash ops/run_midnight_codex_controller.sh --pipeline-start || exit $?

# The cycle builds bars before running every registered study, including full_sweep. Skipping
# the wrapper's pre-bars sweep prevents duplicate compute and a stale-bars false BLOCKED result.
bash ops/run_sweep_then_cycle.sh --cycle-only --wait-existing
PIPELINE_RC=$?
bash ops/run_midnight_codex_controller.sh "$PIPELINE_RC"
CONTROLLER_RC=$?

# A controller/auth failure is visible to systemd but never erases the deterministic result.
if [ "$CONTROLLER_RC" -ne 0 ]; then
    exit "$CONTROLLER_RC"
fi
exit "$PIPELINE_RC"
