#!/usr/bin/env bash
set -uo pipefail
cd /home/quant/quant-platform
source ops/brain_env.sh
mkdir -p data/cro_ai_logs
LOG="data/cro_ai_logs/blindrediscovery_$(date -u +%Y%m%dT%H%M).log"
claude -p "$(cat ops/blindrediscovery_dig_prompt.txt)" --dangerously-skip-permissions >> "$LOG" 2>&1
