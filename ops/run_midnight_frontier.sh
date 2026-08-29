#!/usr/bin/env bash
# One MT5/Fusion-only midnight frontier: fresh state snapshot, then the fenced Codex reasoner.
set -uo pipefail
cd "$(dirname "$0")/.."
# SEALED AGAINST MID-RUN REWRITE (2026-08-26). bash reads a script INCREMENTALLY by byte
# offset; this desk commits ~200x/day into the tree these launchers execute from, and a dig
# holds its slot up to 3h, so a commit that changes this file's LENGTH mid-run makes bash
# resume from the middle of a line. Measured on 63680c05: comment text executed as a command,
# then a dangling `fi`, then the script RE-RAN ITSELF FROM THE TOP. A `{ ... }` alone protects
# the body but bash still reads past the closing brace; only the exit INSIDE the group ends the
# process before another byte is read. See ops/run_frontier_rotation.sh for the full account.
# DO NOT UNWRAP THE BRACE AND DO NOT ADD A LINE AFTER THE CLOSING `}`.
{
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
"${PYTHON:-.venv/bin/python}" scripts/run_midnight_completion.py
COMPLETION_RC=$?
"${PYTHON:-.venv/bin/python}" scripts/audit_mt5_capability_reuse.py
REUSE_RC=$?
"${PYTHON:-.venv/bin/python}" scripts/build_mt5_midnight_state.py
STATE_RC=$?
# The state builder exits 1 whenever its snapshot REPORTS a defect (e.g. "markout stale") even
# though the snapshot itself succeeded -- which failed this unit every night and polluted the
# P0 failed-unit channel. Desk lesson: an exit code proves a process ended, never that it
# produced -- so grade the ARTIFACT: a fresh snapshot means the builder did its job and the
# defects inside it are graded by max_audit/organ fences, not by unit-red. A builder that could
# not produce (no fresh artifact) still fails loud.
if [ "$STATE_RC" -ne 0 ] && "${PYTHON:-.venv/bin/python}" - <<'PY'
import json, sys
from datetime import datetime, timezone
from pathlib import Path
try:
    d = json.loads(Path("data/intelligence/mt5_midnight_state.json").read_text())
    gen = datetime.fromisoformat(d["generated_at"])
except Exception:
    sys.exit(1)
age = (datetime.now(timezone.utc) - gen).total_seconds()
sys.exit(0 if 0 <= age < 600 and isinstance(d.get("defects"), list) else 1)
PY
then
    echo "midnight-state: snapshot PRODUCED (fresh artifact); its defects list is data for the fences, not a unit failure"
    STATE_RC=0
fi
PIPELINE_RC=$(( COMPLETION_RC != 0 ? COMPLETION_RC : (REUSE_RC != 0 ? REUSE_RC : STATE_RC) ))
bash ops/run_midnight_codex_controller.sh "$PIPELINE_RC"
CONTROLLER_RC=$?

# A controller/auth failure is visible to systemd but never erases the deterministic result.
if [ "$CONTROLLER_RC" -ne 0 ]; then
    exit "$CONTROLLER_RC"
fi
exit "$PIPELINE_RC"

exit $?
}
