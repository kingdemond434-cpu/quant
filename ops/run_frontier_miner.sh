#!/usr/bin/env bash
# Regional frontier miner (principal activation 2026-07-20; ledger #114).
# Lightweight daily dig via Prospector infrastructure -- one region per invocation.
set -uo pipefail
cd /home/quant/quant-platform
source ops/brain_env.sh
REGION="${1:?region arg required (en|cn|ru|kr|jp|ar|br)}"
mkdir -p data/cro_ai_logs
LOG="data/cro_ai_logs/frontier_${REGION}_$(date -u +%Y%m%dT%H%M).log"
brain_auth_check || exit 1
echo "=== frontier-$REGION start $(date -u) ===" >> "$LOG"
claude --effort max --append-system-prompt "$_DOCTRINE" -p "$(cat ops/frontier_${REGION}_prompt.txt)" --dangerously-skip-permissions >> "$LOG" 2>&1
echo "=== frontier-$REGION exit $? at $(date -u) ===" >> "$LOG"
