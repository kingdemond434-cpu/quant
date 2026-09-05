#!/usr/bin/env bash
# CAPABILITY HUNT (L1.31) -- daily two-family hunt for what the desk is MISSING, then build it.
# Thin wrapper so the organ inherits brain auth + the model chain like every other claude organ.
set -uo pipefail
cd /home/quant/quant-platform
source ops/brain_env.sh
# SEALED AGAINST MID-RUN REWRITE (2026-08-26). bash reads a script INCREMENTALLY by byte
# offset; a commit that changes this file's LENGTH while it is running resumes execution inside
# a line. Measured on 63680c05 (ops/run_frontier_rotation.sh): comment text ran as a command,
# then a dangling `fi`, then the script RE-RAN ITSELF FROM THE TOP. Only the exit INSIDE the
# group ends the process before bash reads another byte. Do not unwrap; add nothing after `}`.
{
echo "=== capability-hunt start $(date -u) ==="
SLOT="${1:-0}"
.venv/bin/python scripts/run_capability_hunt.py --slot "$SLOT"
echo "=== capability-hunt exit $? at $(date -u) ==="

exit $?
}
