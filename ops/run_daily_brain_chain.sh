#!/usr/bin/env bash
# DAILY BRAIN CHAIN (principal 2026-08-25, token-economy order): the three daily Claude cycles
# run BACK-TO-BACK inside one prompt-cache window instead of scattered across the day. Every
# organ carries the identical ~40KB doctrine+LAWS prefix; consecutive launches on the same model
# write that cache once and read it three times (measured cache writes were 10-40M tokens/day).
# Each runner self-skips if it already produced a real log today, so the root/user timers that
# also fire these organs become no-ops after the chain has run -- no double digs, no races.
set -uo pipefail
cd /home/quant/quant-platform
echo "=== brain chain start $(date -u) ==="
bash ops/run_cro_ai.sh          || echo "chain: cro-ai failed -- continuing"
bash ops/run_frontier_miner.sh unified || echo "chain: unified frontier failed -- continuing"
bash ops/run_video_hunter.sh    || echo "chain: video hunter failed -- continuing"
echo "=== brain chain done $(date -u) ==="
