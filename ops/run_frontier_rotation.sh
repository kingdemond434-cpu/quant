#!/usr/bin/env bash
# Regional frontier miners at MAX frequency (principal 2026-07-23): ALL 7 regions dug DAILY.
# Reverted from the 3-region rotation -- the principal wants max digger frequency, quota is no
# longer the constraint (Max plan). Each region's dig BLOCKS (claude -p in foreground), so the 7
# run SEQUENTIALLY in one invocation -- no concurrent-auth or memory spike on the 4GB box, just
# spread across the afternoon. DIGGING_CHARTER s14 parity: no region left behind, all mined equally.
set -uo pipefail
cd /home/quant/quant-platform
REGIONS=(en cn ru kr jp ar br)
for r in "${REGIONS[@]}"; do
    bash ops/run_frontier_miner.sh "$r"
done
