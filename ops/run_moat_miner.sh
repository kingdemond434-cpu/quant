#!/usr/bin/env bash

# ---------------------------------------------------------------------------------------------
# MID-RUN REWRITE SEAL (gap-fixer 2026-08-29; same seal as ops/run_frontier_rotation.sh).
#
# bash reads a script INCREMENTALLY, BY BYTE OFFSET. This desk commits ~200x/day into the tree
# this launcher executes from, and this one loops CONTINUOUSLY, so it is exposed for as long as
# it lives. IT HAS HAPPENED: 63680c05 grew a comment in run_frontier_rotation.sh by ~120 bytes
# mid-run and seat_frontier.log recorded comment text executed as a command, output from the
# STALE version, then `syntax error near unexpected token 'fi'`. The dig died and it looked
# like an ordinary non-zero exit.
#
# The seal is a COMPOUND COMMAND: bash must parse to the closing brace before executing any of
# it, so the whole body is in memory before the first line runs. The `exit` must be INSIDE the
# group -- measured, not assumed: a bare `{ ... }` still let bash read past the brace and RE-RUN
# the script from the top. Only the exit inside the group ends the process before another byte
# is read. The `}` must be the file's last line.
# ---------------------------------------------------------------------------------------------
{
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
python3 scripts/mine_moat.py --loop --interval "${MOAT_MINER_INTERVAL:-15}" >> "$LOG" 2>&1
exit $?
}
