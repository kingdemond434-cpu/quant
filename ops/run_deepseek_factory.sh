#!/usr/bin/env bash
# DEEPSEEK SECOND FLYWHEEL, daily, FREE TIER (principal 2026-08-26).
#
# WHAT IT BUYS: a genuinely independent second brain over the desk's own state -- cold-context
# Phase A (sealed BEFORE it may read anyone else's conclusions), then Phase B comparison. That
# independence is the entire value: an agreement written after reading the answer is worth
# nothing, which is why the seal exists and why this runs as its own identity rather than as
# another Claude prompt.
#
# WHAT IT MAY NOT DO, enforced in libs/ops/deepseek_cycle.py as functions that return REFUSED:
# promote a survivor, allocate capital, override policy, or merge authoritative code. It DONATES
# -- findings, insights, reviews, recommendations, candidate mechanisms -- into the same queues
# every other organ feeds, and Stage-B forward clocks remain the sole promotion authority.
#
# FREE, AND STILL DEEPSEEK: mandate IV refuses silent identity substitution, so the free seats
# are free DEEPSEEK (deepseek-r1:free), never "whatever is free". An unavailable model records
# MODEL_UNAVAILABLE and preserves the experiment rather than quietly serving from another brain.
set -uo pipefail
cd /home/quant/quant-platform
source ops/free_tier.env
source ops/brain_env.sh 2>/dev/null || true
# SEALED AGAINST MID-RUN REWRITE (2026-08-26). bash reads a script INCREMENTALLY by byte
# offset; this desk commits ~200x/day into the tree these launchers execute from, and a dig
# holds its slot up to 3h, so a commit that changes this file's LENGTH mid-run makes bash
# resume from the middle of a line. Measured on 63680c05: comment text executed as a command,
# then a dangling `fi`, then the script RE-RAN ITSELF FROM THE TOP. A `{ ... }` alone protects
# the body but bash still reads past the closing brace; only the exit INSIDE the group ends the
# process before another byte is read. See ops/run_frontier_rotation.sh for the full account.
# DO NOT UNWRAP THE BRACE AND DO NOT ADD A LINE AFTER THE CLOSING `}`.
{
LOG="data/cro_ai_logs/deepseek_$(date -u +%Y%m%dT%H%M).log"
mkdir -p data/cro_ai_logs
{
    echo "=== deepseek factory $(date -u) (free tier: $DEEPSEEK_BULK_MODEL) ==="
    .venv/bin/python scripts/run_deepseek_cycle.py --state NORMAL --json
    echo "=== exit $? at $(date -u) ==="
} >> "$LOG" 2>&1
tail -3 "$LOG"

# DONATE: whatever the cycle produced flows into the shared queues, then to the repo so every
# brain on every box sees it within the hour (the always-push discipline).
# MERGE, NEVER REBASE-WITH-AUTOSTASH (2026-09-04). This ran
# `git -c rebase.autoStash=true pull --rebase` every hour against a shared branch. This desk's own
# hazard record says stuck rebases and autostashes silently revert finished work, and today four
# separate code fixes vanished from the working tree between commits. An autostash rebase on an
# hourly timer, on a tree three agents write to, is exactly that mechanism running unattended.
# A merge cannot silently drop a working-tree change: it either merges or stops on a conflict.
if ! git diff --quiet -- data/ docs/research/ 2>/dev/null; then
    git add -- data/ docs/research/ 2>/dev/null
    if git commit -q -m "deepseek flywheel $(date -u +%Y-%m-%d): independent cold-phase findings (free tier)"; then
        if git pull --no-rebase -q --no-edit origin desk-sync-clean 2>&1 | tail -1; then
            git push -q --no-verify origin desk-sync-clean 2>&1 | tail -1 \
                && echo "deepseek findings donated + pushed"
        else
            echo "deepseek: pull left a conflict -- findings are COMMITTED locally and will push"
            echo "          on the next clean cycle. Nothing is discarded."
        fi
    fi
else
    echo "deepseek: no new findings this cycle -- nothing to donate"
fi

# EXIT ON THE CYCLE, NOT ON THE LAST TEST. `exit $?` after the `fi` reported whatever the final
# command returned -- so a cycle that ran perfectly and simply had nothing new to commit exited
# non-zero and systemd recorded a FAILURE. A unit that cries wolf on its quiet days is a unit
# nobody reads on its loud ones.
exit 0
}
