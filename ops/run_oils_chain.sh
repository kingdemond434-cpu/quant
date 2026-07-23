#!/usr/bin/env bash
# Chain: wait for the OI/LS universe download to finish, then run the cross-sectional held-out
# OOS and page the verdict. Detached so it completes autonomously (principal left the desk to it).
set -uo pipefail
cd /home/quant/quant-platform
echo "chain: waiting for downloader..." >> data/cro_ai_logs/oils_chain.log
while pgrep -f "dl_oi_ls_univers[e]" >/dev/null; do sleep 60; done
echo "chain: download done $(date -u +%FT%TZ); running OOS" >> data/cro_ai_logs/oils_chain.log
.venv/bin/python scripts/backfill_oi_ls_oos.py >> data/cro_ai_logs/oils_chain.log 2>&1
echo "chain: complete $(date -u +%FT%TZ)" >> data/cro_ai_logs/oils_chain.log
