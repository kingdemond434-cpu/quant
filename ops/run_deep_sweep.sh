#!/usr/bin/env bash
# Weekly Deep Cold Audit entrypoint (organ contract: bash script under ops/, logs to
# data/cro_ai_logs). Wrapped so organ_catchup can auto-resume it like any other organ.
set -uo pipefail
cd /home/quant/quant-platform
source ops/brain_env.sh
# SEALED AGAINST MID-RUN REWRITE (2026-08-26). bash reads a script INCREMENTALLY by byte
# offset; a commit that changes this file's LENGTH while it is running resumes execution inside
# a line. Measured on 63680c05 (ops/run_frontier_rotation.sh): comment text ran as a command,
# then a dangling `fi`, then the script RE-RAN ITSELF FROM THE TOP. Only the exit INSIDE the
# group ends the process before bash reads another byte. Do not unwrap; add nothing after `}`.
{
brain_mutex deep_sweep   # ONE brain desk-wide; defers (exit 0) if another organ holds it
brain_auth_check || exit 1
LOG="data/cro_ai_logs/deep_sweep_$(date -u +%Y%m%dT%H%M).log"
.venv/bin/python scripts/run_deep_sweep.py >> "$LOG" 2>&1

exit $?
}
