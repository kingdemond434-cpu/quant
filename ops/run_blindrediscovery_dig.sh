#!/usr/bin/env bash
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
dig_dry_run blindrediscovery ops/blindrediscovery_dig_prompt.txt && exit 0
# ATTEMPT-FIRST: the stub below is written BEFORE the mutex/auth exits so a deferred or
# auth-dead run stays visible to organ_catchup, which reads "no logs today" as "not attempted --
# not ours to start" and would otherwise never retry it (the 2026-08-11 lost-day class).
mkdir -p data/cro_ai_logs
LOG="data/cro_ai_logs/blindrediscovery_$(date -u +%Y%m%dT%H%M).log"
echo "=== blindrediscovery attempt $(date -u) ===" >> "$LOG"
export BRAIN_MUTEX_LOGFILE="$LOG"
brain_mutex blindrediscovery   # ONE brain desk-wide; defers (exit 0) if another organ holds it
brain_auth_check || { echo "auth unavailable -- next run resumes ($(date -u))" >> "$LOG"; exit 1; }
# §33 CONVERSION PRIORITY. `dig_prompt` (ops/brain_env.sh) prepends the conversion duty
# to this organ's brief so the run spends its FIRST effort disposing of the backlog, then
# mines on in the SAME run -- mining is never throttled. It replaces a `_MINE_PRIORITY`
# variable that was computed here and never referenced, under this exact comment.
# ALL digs at max effort (principal 2026-07-24: Max plan, max everything).
_DIG_EFFORT="${BRAIN_EFFORT:-low}"
_DIG_START_TS=$(date -u +%s)
claude --effort "${BRAIN_EFFORT:-low}" --append-system-prompt "$_DOCTRINE" -p "$(dig_prompt ops/blindrediscovery_dig_prompt.txt)" --dangerously-skip-permissions >> "$LOG" 2>&1
# Stamp the trigger state ONLY on verified production (deliverable advanced past run
# start): runs 1 and 2 completed without updating the baseline, so the due-by-state
# trigger kept demanding digs over ground fresh eyes had already seen. stamp() refuses
# on a dead run -- an exit code proves the process ended, never that it produced.
.venv/bin/python -c "from libs.ops.blind_trigger import stamp; print(stamp(min_artifact_ts=$_DIG_START_TS))" >> "$LOG" 2>&1

exit $?
}
