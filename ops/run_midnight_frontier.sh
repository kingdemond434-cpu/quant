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

bash ops/run_sweep_then_cycle.sh
PIPELINE_RC=$?
bash ops/run_midnight_codex_controller.sh "$PIPELINE_RC"
CONTROLLER_RC=$?

# A controller/auth failure is visible to systemd but never erases the deterministic result.
if [ "$CONTROLLER_RC" -ne 0 ]; then
    exit "$CONTROLLER_RC"
fi
exit "$PIPELINE_RC"
