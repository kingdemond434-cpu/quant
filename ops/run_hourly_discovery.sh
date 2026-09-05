#!/usr/bin/env bash
# HOURLY DISCOVERY (principal 2026-09-05): "all miners etc should be hourly minimum or 24/7 --
# for maximum datasets, moats and edge discoveries, for max geometric growth potential."
#
# One pass an hour over every miner, proposer and data organ, each in its own subprocess on a
# bandit-weighted budget (desks/mt5/research/hourly_discovery.py). The pass writes
# desks/mt5/reports/HOURLY_DISCOVERY.json and the per-organ state the next hour orders by; the
# external pipeline at :05 compiles whatever this pass donated into gauntlet cells.
#
# SEALED AGAINST MID-RUN REWRITE, like every other ops script here: bash reads a script
# incrementally, so the whole body runs inside one group and exits from inside it.
#
# Install once on the VPS (user units):
#   cp ops/quant-hourly-discovery.{service,timer} ~/.config/systemd/user/
#   systemctl --user daemon-reload && systemctl --user enable --now quant-hourly-discovery.timer
set -uo pipefail
cd /home/quant/quant-platform || exit 1
{
PY=.venv/bin/python
[ -x "$PY" ] || PY=python3
LOG=data/cro_ai_logs/hourly_discovery.log
mkdir -p data/cro_ai_logs
echo "=== hourly discovery $(date -u +%FT%TZ) ===" >> "$LOG"
$PY desks/mt5/research/hourly_discovery.py --budget-s "${HOURLY_DISCOVERY_BUDGET_S:-2700}" >> "$LOG" 2>&1
rc=$?
echo "=== exit $rc $(date -u +%FT%TZ) ===" >> "$LOG"
exit "$rc"
}
