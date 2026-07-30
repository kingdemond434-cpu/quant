#!/usr/bin/env bash
set -uo pipefail
cd /home/quant/quant-platform
source ops/brain_env.sh
brain_mutex litminer   # ONE brain desk-wide; defers (exit 0) if another organ holds it
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
mkdir -p data/cro_ai_logs
LOG="data/cro_ai_logs/litminer_$(date -u +%Y%m%dT%H%M).log"
# ALL digs at max effort (principal 2026-07-24: Max plan, max everything).
_DIG_EFFORT=max
claude --effort "$_DIG_EFFORT" --append-system-prompt "$_DOCTRINE" -p "$(cat ops/litminer_dig_prompt.txt)" --dangerously-skip-permissions >> "$LOG" 2>&1
