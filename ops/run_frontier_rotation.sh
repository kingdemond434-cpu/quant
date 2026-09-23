#!/usr/bin/env bash
# THE UNIFIED CYCLE. ONE dig, no regions, no quota, no EV allocation (principal 2026-08-27:
# "no it's not ev allocated, no quota, just one roi big unified cycle"). The header below
# described the retired 7-region rotation and called the replacement "EV-allocated", and a stale
# header is not a harmless comment: reading it is what nearly caused a regional rotation loop to
# be re-added on 2026-08-27, undoing the consolidation. What the file DOES is one unified dig
# plus the brain-hunter; what it used to do is kept only where it explains a decision.
#
# Historical note, retained because it explains the resume rule below: this was originally
# 2026-07-24: continue from where they left off, never restart fresh).
#
# WHY RESUMABLE: the first-ever run dug en, exhausted the model's credit pool mid-dig, and the
# other 6 regions were lost with no memory that they were owed. Now each region is skipped only
# if it already produced a REAL log today (>=1500b -- a stub does not count, per the
# outcome-not-config law), so re-invoking the rotation (cron retry, manual fire, or the next
# day's timer) continues the owed regions instead of re-digging en forever.
set -uo pipefail
cd /home/quant/quant-platform
# ---------------------------------------------------------------------------------------
# THE BRACE IS LOAD-BEARING. DO NOT UNWRAP IT, AND DO NOT ADD A LINE AFTER THE CLOSING `}`.
#
# bash reads a script INCREMENTALLY, keeping a byte offset into the file. This desk commits
# ~200 times a day into the very tree these launchers execute from, and a dig holds its slot
# for up to three hours (TimeoutStartSec=3h), so any commit that changes this file's LENGTH
# mid-run invalidates that offset. bash then resumes from the middle of a line.
#
# IT HAPPENED HERE, 2026-08-26. Commit 63680c05 landed at 11:22 and grew a comment by ~120
# bytes while a dig was running. data/cro_ai_logs/seat_frontier.log records the result:
#     rotation: digging unified frontier
#     ops/run_frontier_rotation.sh: line 24: rotation: digging unified frontier: command not found
#     unified frontier: already produced today -- skipping (chain/timer no-op)
#     ops/run_frontier_rotation.sh: line 26: syntax error near unexpected token `fi'
# -- comment text executed as a command, then a stale version's output, then a dangling `fi`.
#
# REPRODUCED AND THE FIX MEASURED, not assumed. An unguarded script rewritten mid-run executed
# garbage AND THEN RE-RAN ITSELF FROM THE TOP. A `{ ... }` alone protected the body but bash
# still read past the closing brace and re-ran. Only `{ ... exit N }` -- the exit INSIDE the
# group, so the process is gone before bash ever reads another byte -- ran exactly once, cleanly,
# with the right status. That is why the exit is where it is.
#
# The group is a COMPOUND COMMAND: bash must parse it to the closing brace before executing any
# of it, so the whole body is in memory before the first line runs.
# ---------------------------------------------------------------------------------------
{
# UNIFIED CYCLE (principal 2026-08-25, corrected 2026-08-27): ONE dig replaces the fixed 7-region
# sequence -- the unified brain triages measured yields and owed cards, then digs EVERY ground
# whose expected survivor-value clears the bar (no numeric cap: a count is a quota in disguise,
# principal 2026-08-26; skipping a ground is a decision that must be named) (ops/frontier_unified_prompt.txt; starvation floor keeps every
# ground's debt alive). The per-region briefs stay on disk and binding for whatever ground
# it picks. Same resume rule: a real unified log today means done.
TODAY="$(date -u +%Y%m%d)"
# COMPLETED, NOT MERELY BIG. This asked whether today's log exceeded 1,500 bytes, which is the
# same bytes-as-success metric the principal rejected outright: "max ROI testable candidates
# mined is success, not token wastage". Measured 2026-08-28 -- the 06:20 dig was cut off after
# writing 10,667 bytes of genuine work and never finished, and this gate read those bytes and
# skipped the rest of the day. A dig killed by a session limit therefore never resumed, which is
# the exact opposite of the standing instruction to pick up from the same spot once the limit
# lifts.
# The miner now writes an exit marker under a trap, so it survives being killed. Asking for that
# marker asks the only question that matters: did today's dig FINISH?
if [ -f "data/.digs/frontier_unified_${TODAY}.running" ]; then
    echo "rotation: today's unified dig was CUT OFF (sentinel present) -- resuming it"
    bash ops/run_frontier_miner.sh "unified" || echo "rotation: unified failed -- next invocation resumes it"
elif grep -lq "=== frontier-unified exit" data/cro_ai_logs/frontier_unified_${TODAY}T*.log 2>/dev/null; then
    echo "rotation: unified dig COMPLETED today -- skipping (resume)"
else
    echo "rotation: digging unified frontier"
    bash ops/run_frontier_miner.sh "unified" || echo "rotation: unified failed -- next invocation resumes it"
fi

# BRAIN HUNTER -- same resume rule, its own ground. Runs AFTER the regions: it is the newest organ
# and the regional grounds are the ones with standing coverage debt, so a credit death should cost
# this run rather than a region's. It is not a region and takes no region argument.
if grep -lq "brain-hunter exit" data/cro_ai_logs/brain_hunter_${TODAY}T*.log 2>/dev/null; then
    echo "rotation: brain-hunter COMPLETED today -- skipping (resume)"
else
    echo "rotation: digging brain-hunter"
    bash ops/run_brain_hunter.sh || echo "rotation: brain-hunter failed -- next invocation resumes it"
fi

exit 0
}
