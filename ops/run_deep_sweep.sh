#!/usr/bin/env bash
# Weekly Deep Cold Audit entrypoint (organ contract: bash script under ops/, logs to
# data/cro_ai_logs). Wrapped so organ_catchup can auto-resume it like any other organ.
set -uo pipefail
cd /home/quant/quant-platform
source ops/brain_env.sh
brain_auth_check || exit 1
LOG="data/cro_ai_logs/deep_sweep_$(date -u +%Y%m%dT%H%M).log"
.venv/bin/python scripts/run_deep_sweep.py >> "$LOG" 2>&1
