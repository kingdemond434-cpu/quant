#!/usr/bin/env bash
# THE DEDICATED 24/7 MOAT SURVIVOR HUNT.
#
# THE ASYMMETRY THIS FIXES. `run_moat_miner.sh` has mined the archive continuously for weeks --
# coverage measured everywhere. Nothing ASKED that coverage a question more than once a day. The
# desk's one un-replicable asset was being described around the clock and interrogated on a
# cadence, which is the expensive half of owning it.
#
# The screen now carries its own persisted coverage frontier, so each pass lands on the (venue,
# symbol, day) x mechanism cells that owe the most mechanisms rather than on whatever files sort
# last. Continuous passes therefore converge on the WHOLE archive -- including the oldest tape,
# which is the part a competitor most conclusively cannot obtain, because unlike a live feed it
# cannot be bought or backfilled at any price.
#
# Survivors persist to data/moat_survivors.json WITH their misses. Romano-Wolf controls
# family-wise error inside one pass; across thousands of passes nothing does, so a survivor from
# a single pass is expected noise and only the hit rate over independent cells is evidence.
#
# Read-only over data/moat. No keys, no network, no order paths. Safe to run unattended forever.
set -euo pipefail
cd "$(dirname "$0")/.."
LOG="${MOAT_SCREEN_LOG:-data/moat_screen.log}"
mkdir -p "$(dirname "$LOG")"
# Per PASS, not per day. A small budget running continuously screens far more ground than a large
# budget once, and it never blocks the box for minutes at a time.
exec python3 scripts/screen_moat.py --files "${MOAT_SCREEN_FILES:-24}" \
  --loop --interval "${MOAT_SCREEN_INTERVAL:-30}" >> "$LOG" 2>&1
