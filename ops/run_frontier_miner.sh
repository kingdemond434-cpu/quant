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
#
# The chain itself is NO LONGER re-declared here (2026-07-30). It arrives from brain_env.sh, which
# sources the generated ops/model_chain.env. Re-exporting a literal at this line would silently
# pin the miners to yesterday's models the first time run_model_upgrade.py adopts a newer flagship
# -- the organ doing the most model-bound work would be the last to benefit from a better one.
# The routing INTENT above is unchanged: fable head, walk down, auto-load-balance across regions.
brain_auth_check || exit 1
# §33 MINED-TO-WIRED GATE: an organ producing faster than the desk converts is producing DEBT,
# not value. The gate is RECOMPUTED here, never read from a flag -- `rm data/mining_suspended`
# §33 CONVERSION PRIORITY (never a blocker -- mining is never throttled, principal
# 2026-07-25): recompute the backlog and prepend it to this run's instructions so the
# dig spends its FIRST effort converting, then mines on in the SAME run.
_MINE_PRIORITY="$(.venv/bin/python scripts/mine_gate.py 2>/dev/null || true)"
# §33 CONVERSION PRIORITY (NEVER a blocker -- mining is never throttled, principal
# 2026-07-25). Recompute the backlog and prepend it to this run so the dig spends its FIRST
# effort converting, then mines on in the SAME run. Acquisition is never cut to meet
# extraction; extraction scales up to meet acquisition.
echo "=== frontier-$REGION start $(date -u) ===" >> "$LOG"
claude --effort max --append-system-prompt "$_DOCTRINE" -p "$(cat ops/frontier_${REGION}_prompt.txt)" --dangerously-skip-permissions >> "$LOG" 2>&1
echo "=== frontier-$REGION exit $? at $(date -u) ===" >> "$LOG"
