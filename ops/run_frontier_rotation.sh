#!/usr/bin/env bash
# Regional frontier miners at 3x/week-per-region parity (DIGGING_CHARTER s14: no digger left behind).
# Digs 3 regions per invocation on a deterministic day-of-year rotation, so each of the 7 regions is
# mined ~3x/week -- matching the prospector/litminer cadence -- while capping load at 3 heavy digs/day
# so the recorder + connector (the money path) keep brain-time first (the constitution's tuned-not-
# maxed rule). Offset = (day-of-year * 3) mod 7 visits each region exactly 3 times per 7-day cycle.
set -uo pipefail
cd /home/quant/quant-platform
REGIONS=(en cn ru kr jp ar br)
n=${#REGIONS[@]}
offset=$(( ($(date -u +%j | sed 's/^0*//') * 3) % n ))
for i in 0 1 2; do
    bash ops/run_frontier_miner.sh "${REGIONS[$(( (offset + i) % n ))]}"
done
