#!/usr/bin/env bash
# Regional frontier miner (principal activation 2026-07-20; ledger #114).
# Lightweight daily dig via Prospector infrastructure -- one region per invocation.
set -uo pipefail
cd /home/quant/quant-platform
source ops/brain_env.sh
REGION="${1:?region arg required (en|cn|ru|kr|jp|ar|br)}"
dig_dry_run "frontier-$REGION" "ops/frontier_${REGION}_prompt.txt" && exit 0
# ATTEMPT-FIRST (2026-08-11): the stub is written BEFORE the mutex/auth exits. organ_catchup
# reads "no logs today" as "timer has not fired -- not ours to start", so a logless deferral made
# the region invisible to its own retry loop: at 15:00 all 7 regions deferred behind the 14:45
# brain run, left zero logs, and the daily timer was the only other invoker -- a silent mutex
# collision cost the entire day, repeatedly (the organ-never-frontier-* fence class).
mkdir -p data/cro_ai_logs
LOG="data/cro_ai_logs/frontier_${REGION}_$(date -u +%Y%m%dT%H%M).log"
echo "=== frontier-$REGION attempt $(date -u) ===" >> "$LOG"
export BRAIN_MUTEX_LOGFILE="$LOG"
# ONE brain desk-wide. Deferring is safe here BY DESIGN: run_frontier_rotation.sh only skips a
# region that produced a real (>=1500b) log today, so a deferred region stays owed and the next
# rotation invocation resumes it -- the mutex composes with the existing resume point.
brain_mutex "frontier-${REGION}"
# DUAL-POOL ROUTING (principal 2026-07-25): try the fable-5 METERED pool FIRST, then fall back
# to the Max subscription seat. brain_auth_check walks this chain and exports the winner, so the
# 7 regions AUTO-LOAD-BALANCE -- the first consume fable's ~1-run-per-5h-window, the rest land on
# opus-5 automatically. Safe here and nowhere else: the rotation is RESUMABLE (a region without a
# real log today is re-dug next invocation), so a mid-dig credit death costs nothing, and every
# miner run on fable is Max-seat headroom preserved for the brain cycle and the deep sweep.
#
# The chain itself is NO LONGER re-declared here (2026-07-30). It arrives from brain_env.sh, which
# sources the generated ops/model_chain.env. Re-exporting a literal at this line would silently
# pin the miners to yesterday's models the first time run_model_upgrade.py adopts a newer flagship
# -- the organ doing the most model-bound work would be the last to benefit from a better one.
# The routing INTENT above is unchanged: fable head, walk down, auto-load-balance across regions.
brain_auth_check || { echo "auth unavailable -- next run resumes ($(date -u))" >> "$LOG"; exit 1; }
# §33 CONVERSION PRIORITY. `dig_prompt` (ops/brain_env.sh) prepends the conversion duty
# to this organ's brief so the run spends its FIRST effort disposing of the backlog, then
# mines on in the SAME run -- mining is never throttled. It replaces a `_MINE_PRIORITY`
# variable that was computed here and never referenced, under this exact comment.
echo "=== frontier-$REGION start $(date -u) ===" >> "$LOG"
claude --effort max --append-system-prompt "$_DOCTRINE" -p "$(dig_prompt ops/frontier_${REGION}_prompt.txt)" --dangerously-skip-permissions >> "$LOG" 2>&1
echo "=== frontier-$REGION exit $? at $(date -u) ===" >> "$LOG"
