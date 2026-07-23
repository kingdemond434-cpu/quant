#!/usr/bin/env bash
set -uo pipefail
cd /home/quant/quant-platform
source ops/brain_env.sh
brain_auth_check || exit 1
mkdir -p data/cro_ai_logs
LOG="data/cro_ai_logs/blindrediscovery_$(date -u +%Y%m%dT%H%M).log"
# ALL digs at max effort (principal 2026-07-24: Max plan, max everything).
_DIG_EFFORT=max
claude --effort "$_DIG_EFFORT" --append-system-prompt "$_DOCTRINE" -p "$(cat ops/blindrediscovery_dig_prompt.txt)" --dangerously-skip-permissions >> "$LOG" 2>&1
