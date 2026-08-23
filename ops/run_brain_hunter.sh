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
# The chain is NOT re-declared here. It arrives from brain_env.sh above, which sources the
# generated ops/model_chain.env -- see the same note in ops/run_frontier_miner.sh. This organ
# carried a literal copy from 2026-08-11 (d48c6408) until 2026-08-12, which is exactly the pin
# the single-source fence exists to stop: the hunter would have kept running yesterday's models
# the first time run_model_upgrade.py adopted a newer flagship, and nothing would have said so.
# The routing INTENT above is unchanged: fable head, walk down on exhaustion.
dig_dry_run "brain-hunter" "ops/brain_hunter_prompt.txt" && exit 0
# ATTEMPT-FIRST + the mutex this launcher never took: without it the hunter ran in parallel with
# the CRO brain (both drawing the same pool -- the exact drain brain_mutex exists to stop), and a
# logless auth death left no evidence for organ_catchup to retry (see run_frontier_miner.sh).
echo "=== brain-hunter attempt $(date -u) ===" >> "$LOG"
export BRAIN_MUTEX_LOGFILE="$LOG"
brain_mutex "brain-hunter"
CONTROLLER="claude"
if ! brain_auth_check; then
    # Claude subscription/auth outages previously erased the whole daily WorldQuant/competition
    # ground. Use the already-authenticated Codex seat against the SAME prompt, ledger and mutex;
    # this is controller failover, not a second miner. The VPS cannot use workspace-write/bwrap,
    # so the repository gates and research-only prompt remain the mutation fence.
    CODEX_BIN="${CODEX_BIN:-/home/quant/.local/bin/codex}"
    if [ -x "$CODEX_BIN" ] && "$CODEX_BIN" login status 2>&1 | grep -q "Logged in"; then
        CONTROLLER="codex"
        echo "claude auth unavailable -- using authenticated Codex fallback" >> "$LOG"
    else
        echo "all controller auth unavailable -- next run resumes ($(date -u))" >> "$LOG"
        exit 1
    fi
fi
echo "=== brain-hunter start $(date -u) ===" >> "$LOG"
if [ "$CONTROLLER" = "claude" ]; then
    claude --effort max --append-system-prompt "$_DOCTRINE" \
        -p "$(dig_prompt ops/brain_hunter_prompt.txt)" --dangerously-skip-permissions \
        >> "$LOG" 2>&1
    RC=$?
else
    { printf '%s\n\n' "$_DOCTRINE"; dig_prompt ops/brain_hunter_prompt.txt; } \
        | "$CODEX_BIN" --ask-for-approval never exec -C "$PWD" --sandbox danger-full-access \
            --model gpt-5.6-sol --config model_reasoning_effort=medium - >> "$LOG" 2>&1
    RC=$?
fi
echo "=== brain-hunter controller=$CONTROLLER exit $RC at $(date -u) ===" >> "$LOG"
exit "$RC"
