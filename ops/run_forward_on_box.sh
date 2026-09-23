#!/usr/bin/env bash
# Run the forward engine ON THE TRADING BOX, where the bars are live.
#
# WHY THIS EXISTS (2026-09-04)
#
# NOTHING RAN IT ON A SCHEDULE. The VPS timer was disabled (correctly -- the VPS bar cache was
# eight days stale, so it recomputed forward state from a dead market and overwrote the mirror),
# and the trading box has no scheduler entry for it at all. So the engine ran only when a human
# ran it, and every clock sat on whatever state the last manual run left behind: 52 rows reading
# IDENTITY_BROKEN with 234 real trades frozen, while `verify()` on current code returns NO DRIFT
# for all 53 and would clear them on the next pass.
#
# ON THE BOX, NOT HERE. The box holds live MT5 bars (299 parquets written minutes ago); the VPS
# holds a copy that is only as fresh as the last pull. Forward evidence must be computed where the
# market data actually is.
set -uo pipefail
cd "$(dirname "$0")/.." || exit 1
REMOTE="${REMOTE:-contabo-mt5}"
timeout 1800 ssh -o BatchMode=yes -o ConnectTimeout=20 -o ServerAliveInterval=20 \
  -o ServerAliveCountMax=60 "$REMOTE" \
  'cd C:\opt\quant\desks\mt5 && py -3 -W ignore runfwd.py' 2>&1 | tail -25
rc=$?

# THE STATE ROW CAN GO STALE AGAINST ITS OWN REGISTRY, AND NOTHING ELSE NOTICES. Seven
# clocks sat IDENTITY_BROKEN on 2026-09-04 while the registry read LIVE and verify()
# returned no drift on BOTH boxes -- the identity was intact and only the state file
# disagreed. A watchdog reported it for hours and nothing repaired it. This runs right
# after the engine writes the state, clears only rows the registry calls LIVE and
# verify() calls clean, and never touches forward_start.
timeout 300 ssh -o BatchMode=yes -o ConnectTimeout=20 "$REMOTE" \
  'cd C:\opt\quant\desks\mt5 && py -3 -W ignore scripts\repair_identity_state.py --apply' 2>&1 | tail -8

echo "forward engine on $REMOTE exited $rc"
exit 0
