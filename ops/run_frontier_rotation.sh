#!/usr/bin/env bash
# Regional frontier miners at MAX frequency: ALL 7 regions daily, RESUMABLE (principal
# 2026-07-24: continue from where they left off, never restart fresh).
#
# WHY RESUMABLE: the first-ever run dug en, exhausted the model's credit pool mid-dig, and the
# other 6 regions were lost with no memory that they were owed. Now each region is skipped only
# if it already produced a REAL log today (>=1500b -- a stub does not count, per the
# outcome-not-config law), so re-invoking the rotation (cron retry, manual fire, or the next
# day's timer) continues the owed regions instead of re-digging en forever.
set -uo pipefail
cd /home/quant/quant-platform
# UNIFIED CYCLE (principal 2026-08-25): ONE EV-allocated dig replaces the fixed 7-region
# sequence -- the unified brain triages measured yields and owed cards, then digs the 1-3
# highest-EV grounds deep (ops/frontier_unified_prompt.txt; starvation floor keeps every
# ground's debt alive). The per-region briefs stay on disk and binding for whatever ground
# it picks. Same resume rule: a real unified log today means done.
TODAY="$(date -u +%Y%m%d)"
if find data/cro_ai_logs -name "frontier_unified_${TODAY}T*.log" -size +1500c 2>/dev/null | grep -q .; then
    echo "rotation: unified dig already produced today -- skipping (resume)"
else
    echo "rotation: digging unified frontier"
    bash ops/run_frontier_miner.sh "unified" || echo "rotation: unified failed -- next invocation resumes it"
fi

# BRAIN HUNTER -- same resume rule, its own ground. Runs AFTER the regions: it is the newest organ
# and the regional grounds are the ones with standing coverage debt, so a credit death should cost
# this run rather than a region's. It is not a region and takes no region argument.
if find data/cro_ai_logs -name "brain_hunter_${TODAY}T*.log" -size +1500c 2>/dev/null | grep -q .; then
    echo "rotation: brain-hunter already produced today -- skipping (resume)"
else
    echo "rotation: digging brain-hunter"
    bash ops/run_brain_hunter.sh || echo "rotation: brain-hunter failed -- next invocation resumes it"
fi
