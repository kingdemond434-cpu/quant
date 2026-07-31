#!/usr/bin/env bash
# CAPABILITY HUNT (L1.31) -- daily two-family hunt for what the desk is MISSING, then build it.
# Thin wrapper so the organ inherits brain auth + the model chain like every other claude organ.
set -uo pipefail
cd /home/quant/quant-platform
source ops/brain_env.sh
echo "=== capability-hunt start $(date -u) ==="
SLOT="${1:-0}"
.venv/bin/python scripts/run_capability_hunt.py --slot "$SLOT"
echo "=== capability-hunt exit $? at $(date -u) ==="
