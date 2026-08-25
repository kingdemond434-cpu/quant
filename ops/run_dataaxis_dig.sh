#!/usr/bin/env bash
# Standing WEEKLY free-data-alternatives dig -- uncapped, exhaustive. Operator-directed 2026-07-19.
set -uo pipefail
cd /home/quant/quant-platform
source ops/brain_env.sh
dig_dry_run dataaxis ops/dataaxis_dig_prompt.txt && exit 0
# ATTEMPT-FIRST: the stub below is written BEFORE the mutex/auth exits so a deferred or
# auth-dead run stays visible to organ_catchup, which reads "no logs today" as "not attempted --
# not ours to start" and would otherwise never retry it (the 2026-08-11 lost-day class).
mkdir -p data/cro_ai_logs
LOG="data/cro_ai_logs/dataaxis_$(date -u +%Y%m%dT%H%M).log"
echo "=== dataaxis attempt $(date -u) ===" >> "$LOG"
export BRAIN_MUTEX_LOGFILE="$LOG"
brain_mutex dataaxis   # ONE brain desk-wide; defers (exit 0) if another organ holds it
brain_auth_check || { echo "auth unavailable -- next run resumes ($(date -u))" >> "$LOG"; exit 1; }
# §33 CONVERSION PRIORITY. `dig_prompt` (ops/brain_env.sh) prepends the conversion duty
# to this organ's brief so the run spends its FIRST effort disposing of the backlog, then
# mines on in the SAME run -- mining is never throttled. It replaces a `_MINE_PRIORITY`
# variable that was computed here and never referenced, under this exact comment.
# ALL digs at max effort (principal 2026-07-24: Max plan, max everything).
_DIG_EFFORT="${BRAIN_EFFORT:-low}"
claude --effort "${BRAIN_EFFORT:-low}" --append-system-prompt "$_DOCTRINE" -p "$(dig_prompt ops/dataaxis_dig_prompt.txt)" --dangerously-skip-permissions >> "$LOG" 2>&1
