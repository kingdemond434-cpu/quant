#!/usr/bin/env bash
# Quota-free crypto hypothesis factory harness (autodiscovery). Pure Python, 0 Claude calls --
# runs INDEPENDENTLY of the quota-limited brain cycle so generation "always runs" (principal ask).
# Runs BOTH timeframes; D1 last so the dashboard (web/autodiscovery_crypto.json) shows the richer
# cumulative view.
#
# HONEST NOTE (2026-07-22 diagnosis): the price-family hypothesis space is EXHAUSTED --
#   D1: 390 tested / 0 survivors ; H8: 130 tested / 0 survivors, all net-of-cost.
# The factory's own information-value pilot verdict: "the constraint is DATA/MECHANISM, not
# volume." So this harness will re-skip duplicates in seconds until NEW mechanism generators
# (keyed to the free-data axes: OI / long-short / liquidations / basis / stablecoin flows) or
# maturing forward-clock windows give it something genuinely new to test. That is EXPECTED, not a
# failure -- the harness exists so those additions get tested automatically the moment they land,
# with no brain/quota dependency. It does NOT, by itself, move the 390 number.
set -euo pipefail
cd /home/quant/quant-platform
LOG=data/cro_ai_logs/crypto_factory_cron.log
echo "=== $(date -u +%FT%TZ) crypto factory harness ===" >> "$LOG"
.venv/bin/python scripts/run_crypto_research.py --timeframe H8 >> "$LOG" 2>&1 || echo "H8 run failed" >> "$LOG"
.venv/bin/python scripts/run_crypto_research.py --timeframe D1 >> "$LOG" 2>&1 || echo "D1 run failed" >> "$LOG"
echo "=== done $(date -u +%FT%TZ) ===" >> "$LOG"
