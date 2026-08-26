#!/usr/bin/env bash
# Hourly seed-miner sweep + ALWAYS-PUSH (principal 2026-08-26: all work is pushed everywhere,
# automatically, so every brain on every box can follow up and stay connected -- uncommitted
# output DID NOT HAPPEN, and an artifact only this box can see is an artifact half-made).
#
# Push discipline: EXPLICIT PATHS ONLY (R0423 -- never -A in a shared tree), pull --rebase
# before push so the Codex hourly syncer and this never fight, --no-verify because the pre-push
# gates cover CODE while this commits only DATA artifacts the miners produced (the code paths
# still go through gated pushes), and every failure is logged + retried next hour, never fatal.
set -uo pipefail
cd /home/quant/quant-platform
# SEALED AGAINST MID-RUN REWRITE (2026-08-26). bash reads a script INCREMENTALLY by byte
# offset; a commit that changes this file's LENGTH while it is running resumes execution inside
# a line. Measured on 63680c05 (ops/run_frontier_rotation.sh): comment text ran as a command,
# then a dangling `fi`, then the script RE-RAN ITSELF FROM THE TOP. Only the exit INSIDE the
# group ends the process before bash reads another byte. Do not unwrap; add nothing after `}`.
{
.venv/bin/python desks/mt5/side_channels/seed_miners.py || echo "seed miners failed rc=$?"

# HEALTH FENCE, on the producer's own cadence. A miner that fetches, gets a 403 or matches
# no selector, and archives one stub row looks IDENTICAL to a productive one to anything that
# counts rows -- that is how 33 of 54 sources went dark for weeks while the facts pack read
# healthy (2026-08-26). Non-fatal by design: this sweep's job is to mine, and a fence that can
# abort the thing it measures buys silence rather than health. The log is the artifact and
# max_audit reads the same scan.
.venv/bin/python scripts/check_miner_health.py >> data/cro_ai_logs/miner_health.log 2>&1 \
    || echo "miner-health: DOWN sources -- see data/cro_ai_logs/miner_health.log"

INTEL_PATHS=(
    desks/mt5/data/intelligence
    desks/mt5/data/hypotheses
    desks/mt5/data/research_queue.json
    data/youtube_channels.json
)
if ! git diff --quiet -- "${INTEL_PATHS[@]}" 2>/dev/null \
        || [ -n "$(git ls-files --others --exclude-standard -- "${INTEL_PATHS[@]}" 2>/dev/null | head -1)" ]; then
    git add -- "${INTEL_PATHS[@]}" 2>/dev/null
    git commit -q -m "intelligence hourly sync $(date -u +%Y-%m-%d_%H%M): miners/frontier/cohorts artifacts" \
        && echo "intel committed" || echo "nothing to commit"
    # AUTOSTASH IS MANDATORY HERE, measured 2026-08-25: sibling organs (and this suite's own
    # long-running miners) write artifacts DURING the commit, so a plain `pull --rebase` aborts
    # on "unstaged changes" and the push never happens -- the bus would silently stop feeding
    # the other brains, which is the exact failure it exists to prevent.
    git -c rebase.autoStash=true pull --rebase -q origin desk-sync-clean 2>&1 | tail -1
    git push -q --no-verify origin desk-sync-clean 2>&1 | tail -1 \
        && echo "intel pushed" || echo "push failed -- next hour retries"
fi

exit $?
}
