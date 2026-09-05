#!/usr/bin/env bash
# Ship the solved book to the box that trades it.
#
# THE ALLOCATOR RUNS HERE AND THE GATEWAY RUNS THERE. `research/pf_allocator.py` writes
# desks/mt5/reports/pf_allocation.json on the VPS; `gateway.allocator_heat()` reads it on
# contabo-mt5. Nothing moved it, so arming the allocator did exactly nothing: the gateway
# reported "no pf_allocation.json" and silently kept the derived budget (measured 2026-09-02).
# An arm switch that authorises a file the consumer cannot see is not a switch.
#
# FAILS QUIETLY BY DESIGN. The gateway's own staleness check is what protects it: a book older
# than an hour is refused there, so a failed sync degrades to the derived budget rather than to a
# stale one. This must never fail an allocator pass -- the artifact on this box is still correct.
set -uo pipefail
cd /home/quant/quant-platform || exit 0
SRC=desks/mt5/reports/pf_allocation.json
[ -s "$SRC" ] || exit 0
timeout 90 scp -q -o ConnectTimeout=20 "$SRC" "contabo-mt5:C:/opt/quant/$SRC" 2>/dev/null \
  && echo "allocation synced to the desk box" \
  || echo "allocation sync FAILED; the gateway keeps its derived budget (fail-closed)"
exit 0
