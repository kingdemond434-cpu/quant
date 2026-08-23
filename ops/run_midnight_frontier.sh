#!/usr/bin/env bash
# One MT5/Fusion-only midnight frontier: fresh state snapshot, then the fenced Codex reasoner.
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

# Persistent MT5 workers collect and test continuously. Midnight snapshots their exact shared
# state instead of launching the legacy crypto-wide study registry (which is outside the standing
# MT5 venue mandate and previously OOM-killed this unit before the controller could start).
"${PYTHON:-.venv/bin/python}" scripts/audit_mt5_capability_reuse.py
REUSE_RC=$?
"${PYTHON:-.venv/bin/python}" scripts/build_mt5_midnight_state.py
STATE_RC=$?
PIPELINE_RC=$(( REUSE_RC != 0 ? REUSE_RC : STATE_RC ))
bash ops/run_midnight_codex_controller.sh "$PIPELINE_RC"
CONTROLLER_RC=$?

# A controller/auth failure is visible to systemd but never erases the deterministic result.
if [ "$CONTROLLER_RC" -ne 0 ]; then
    exit "$CONTROLLER_RC"
fi
exit "$PIPELINE_RC"
