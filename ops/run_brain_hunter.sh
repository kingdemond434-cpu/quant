#!/usr/bin/env bash
# BRAIN HUNTER -- dedicated daily dig on the public WorldQuant BRAIN corpus and everything
# reachable from it (principal activation 2026-08-07).
#
# WHY A SEPARATE ORGAN RATHER THAN A LINE IN THE REGIONAL MINERS' BRIEF: the desk was caught short
# by this one taxonomy TWICE IN TWO DAYS -- the entire unary-transform axis missing on 08-06, then
# group_rank/group_zscore/ts_backfill/trade_when missing on 08-07, found in a single forwarded
# screenshot. A generic miner that touches this ground occasionally keeps producing findings of
# that size one screenshot at a time; a dedicated organ works it and keeps working it.
set -uo pipefail
cd /home/quant/quant-platform
source ops/brain_env.sh
mkdir -p data/cro_ai_logs
LOG="data/cro_ai_logs/brain_hunter_$(date -u +%Y%m%dT%H%M).log"
# Same dual-pool routing as the regional rotation: fable's metered pool first, then the Max seat.
# Safe for the same reason -- the run is resumable, so a mid-dig credit death costs a log, not work.
export _BRAIN_MODEL_CHAIN="claude-fable-5 claude-opus-5 claude-opus-4-8"
dig_dry_run "brain-hunter" "ops/brain_hunter_prompt.txt" && exit 0
# ATTEMPT-FIRST + the mutex this launcher never took: without it the hunter ran in parallel with
# the CRO brain (both drawing the same pool -- the exact drain brain_mutex exists to stop), and a
# logless auth death left no evidence for organ_catchup to retry (see run_frontier_miner.sh).
echo "=== brain-hunter attempt $(date -u) ===" >> "$LOG"
export BRAIN_MUTEX_LOGFILE="$LOG"
brain_mutex "brain-hunter"
brain_auth_check || { echo "auth unavailable -- next run resumes ($(date -u))" >> "$LOG"; exit 1; }
echo "=== brain-hunter start $(date -u) ===" >> "$LOG"
claude --effort max --append-system-prompt "$_DOCTRINE" -p "$(dig_prompt ops/brain_hunter_prompt.txt)" --dangerously-skip-permissions >> "$LOG" 2>&1
echo "=== brain-hunter exit $? at $(date -u) ===" >> "$LOG"
