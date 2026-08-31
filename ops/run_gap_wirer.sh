#!/usr/bin/env bash
# WEEKLY GAP-FIXER/WIRER -- principal-ordered 2026-08-25. The desk's only scheduled organ whose
# sole job is REPAIR: fix open gap-register rows, wire unwired organs (III.16), hunt and fix
# weaknesses the detectors keep finding. Detection without scheduled repair was the measured
# failure mode: 535 unwired modules, 4 silent dead days, money-path reverts.
set -uo pipefail
cd /home/quant/quant-platform
source ops/brain_env.sh
# SEALED AGAINST MID-RUN REWRITE (2026-08-26). bash reads a script INCREMENTALLY by byte
# offset; this desk commits ~200x/day into the tree these launchers execute from, and a dig
# holds its slot up to 3h, so a commit that changes this file's LENGTH mid-run makes bash
# resume from the middle of a line. Measured on 63680c05: comment text executed as a command,
# then a dangling `fi`, then the script RE-RAN ITSELF FROM THE TOP. A `{ ... }` alone protects
# the body but bash still reads past the closing brace; only the exit INSIDE the group ends the
# process before another byte is read. See ops/run_frontier_rotation.sh for the full account.
# DO NOT UNWRAP THE BRACE AND DO NOT ADD A LINE AFTER THE CLOSING `}`.
{
dig_dry_run gap-wirer ops/gap_wirer_prompt.txt && exit 0
mkdir -p data/cro_ai_logs
LOG="data/cro_ai_logs/gap_wirer_$(date -u +%Y%m%dT%H%M).log"
echo "=== gap-wirer attempt $(date -u) ===" >> "$LOG"
export BRAIN_MUTEX_LOGFILE="$LOG"
brain_mutex gap-wirer
brain_mem_gate || exit 0
brain_auth_check || { echo "auth unavailable -- next run resumes ($(date -u))" >> "$LOG"; exit 1; }
claude --effort max --append-system-prompt "$_DOCTRINE" -p "$(dig_prompt ops/gap_wirer_prompt.txt)" --dangerously-skip-permissions >> "$LOG" 2>&1
echo "=== gap-wirer exit $? at $(date -u) ===" >> "$LOG"

exit $?
}
