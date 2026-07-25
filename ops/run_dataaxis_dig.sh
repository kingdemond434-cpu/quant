#!/usr/bin/env bash
# Standing WEEKLY free-data-alternatives dig -- uncapped, exhaustive. Operator-directed 2026-07-19.
set -uo pipefail
cd /home/quant/quant-platform
source ops/brain_env.sh
brain_auth_check || exit 1
# §33 MINED-TO-WIRED GATE: an organ producing faster than the desk converts is producing
# DEBT, not value. max_audit writes data/mining_suspended while carded finds still owe a
# disposition; the whole dig slot then belongs to conversion. Exit 0 -- a suspended dig is a
# CORRECT outcome, not a failure, and must not trip the organ-liveness pager.
if [ -f data/mining_suspended ]; then
  echo "[§33] dig SUSPENDED -- backlog unconverted: $(cat data/mining_suspended)"
  exit 0
fi
mkdir -p data/cro_ai_logs
LOG="data/cro_ai_logs/dataaxis_$(date -u +%Y%m%dT%H%M).log"
# ALL digs at max effort (principal 2026-07-24: Max plan, max everything).
_DIG_EFFORT=max
claude --effort "$_DIG_EFFORT" --append-system-prompt "$_DOCTRINE" -p "$(cat ops/dataaxis_dig_prompt.txt)" --dangerously-skip-permissions >> "$LOG" 2>&1
