#!/usr/bin/env bash
# Regional frontier miner (principal activation 2026-07-20; ledger #114).
# Lightweight daily dig via Prospector infrastructure -- one region per invocation.
set -uo pipefail
cd /home/quant/quant-platform
source ops/brain_env.sh
REGION="${1:?region arg required (en|cn|ru|kr|jp|ar|br)}"
mkdir -p data/cro_ai_logs
LOG="data/cro_ai_logs/frontier_${REGION}_$(date -u +%Y%m%dT%H%M).log"
# DUAL-POOL ROUTING (principal 2026-07-25): try the fable-5 METERED pool FIRST, then fall back
# to the Max subscription seat. brain_auth_check walks this chain and exports the winner, so the
# 7 regions AUTO-LOAD-BALANCE -- the first consume fable's ~1-run-per-5h-window, the rest land on
# opus-5 automatically. Safe here and nowhere else: the rotation is RESUMABLE (a region without a
# real log today is re-dug next invocation), so a mid-dig credit death costs nothing, and every
# miner run on fable is Max-seat headroom preserved for the brain cycle and the deep sweep.
export _BRAIN_MODEL_CHAIN="claude-fable-5 claude-opus-5 claude-opus-4-8"
dig_dry_run "frontier-$REGION" "ops/frontier_${REGION}_prompt.txt" && exit 0
brain_auth_check || exit 1
# §33 CONVERSION PRIORITY. `dig_prompt` (ops/brain_env.sh) prepends the conversion duty
# to this organ's brief so the run spends its FIRST effort disposing of the backlog, then
# mines on in the SAME run -- mining is never throttled. It replaces a `_MINE_PRIORITY`
# variable that was computed here and never referenced, under this exact comment.
echo "=== frontier-$REGION start $(date -u) ===" >> "$LOG"
claude --effort max --append-system-prompt "$_DOCTRINE" -p "$(dig_prompt ops/frontier_${REGION}_prompt.txt)" --dangerously-skip-permissions >> "$LOG" 2>&1
echo "=== frontier-$REGION exit $? at $(date -u) ===" >> "$LOG"
