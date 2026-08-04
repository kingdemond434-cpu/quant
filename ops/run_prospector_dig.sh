#!/usr/bin/env bash
set -uo pipefail
cd /home/quant/quant-platform
source ops/brain_env.sh
dig_dry_run prospector ops/prospector_dig_prompt.txt && exit 0
brain_mutex prospector   # ONE brain desk-wide; defers (exit 0) if another organ holds it
brain_auth_check || exit 1
# §33 CONVERSION PRIORITY. `dig_prompt` (ops/brain_env.sh) prepends the conversion duty
# to this organ's brief so the run spends its FIRST effort disposing of the backlog, then
# mines on in the SAME run -- mining is never throttled. It replaces a `_MINE_PRIORITY`
# variable that was computed here and never referenced, under this exact comment.
mkdir -p data/cro_ai_logs
LOG="data/cro_ai_logs/prospector_$(date -u +%Y%m%dT%H%M).log"
# ALL digs at max effort (principal 2026-07-24: Max plan, max everything).
_DIG_EFFORT=max
claude --effort "$_DIG_EFFORT" --append-system-prompt "$_DOCTRINE" -p "$(dig_prompt ops/prospector_dig_prompt.txt)" --dangerously-skip-permissions >> "$LOG" 2>&1
