#!/usr/bin/env bash
# THE DEDICATED 24/7 MOAT MINER.
#
# Separate from the cadence on purpose. The cadence call is the FLOOR -- it guarantees the miner
# runs at all. This is the CEILING: it mines continuously, so coverage converges in hours instead
# of in as many days as there are cadence cycles. The moat is the desk's only un-replicable asset
# and its archive grows every second the recorders run, so anything less than continuous mining is
# under-exploration -- which P26 makes a constitutional breach rather than a preference.
#
# Read-only over data/moat. No keys, no network, no order paths. Safe to run unattended forever.
set -euo pipefail
cd "$(dirname "$0")/.."
LOG="${MOAT_MINER_LOG:-data/moat_miner.log}"
mkdir -p "$(dirname "$LOG")"
# MOAT_FILE_BUDGET is per PASS, not per day: a small budget with continuous passes explores far
# more than a large budget once, and it never blocks the box for minutes at a time.
export MOAT_FILE_BUDGET="${MOAT_FILE_BUDGET:-40}"
exec python3 scripts/mine_moat.py --loop --interval "${MOAT_MINER_INTERVAL:-15}" >> "$LOG" 2>&1
