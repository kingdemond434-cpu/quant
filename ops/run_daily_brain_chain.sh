#!/usr/bin/env bash
# DAILY BRAIN CHAIN (principal 2026-08-25, token-economy order): the three daily Claude cycles
# run BACK-TO-BACK inside one prompt-cache window instead of scattered across the day. Every
# organ carries the identical ~40KB doctrine+LAWS prefix; consecutive launches on the same model
# write that cache once and read it three times (measured cache writes were 10-40M tokens/day).
# Each runner self-skips if it already produced a real log today, so the root/user timers that
# also fire these organs become no-ops after the chain has run -- no double digs, no races.
set -uo pipefail
cd /home/quant/quant-platform
# SEALED AGAINST MID-RUN REWRITE (2026-08-26). bash reads a script INCREMENTALLY by byte
# offset; this desk commits ~200x/day into the tree these launchers execute from, and a dig
# holds its slot up to 3h, so a commit that changes this file's LENGTH mid-run makes bash
# resume from the middle of a line. Measured on 63680c05: comment text executed as a command,
# then a dangling `fi`, then the script RE-RAN ITSELF FROM THE TOP. A `{ ... }` alone protects
# the body but bash still reads past the closing brace; only the exit INSIDE the group ends the
# process before another byte is read. See ops/run_frontier_rotation.sh for the full account.
# DO NOT UNWRAP THE BRACE AND DO NOT ADD A LINE AFTER THE CLOSING `}`.
{
echo "=== brain chain start $(date -u) ==="
# TOKEN-FREE COLLECTORS FIRST (corpora-first law): the digs below judge what these gathered.
.venv/bin/python scripts/collect_youtube_corpus.py || echo "chain: youtube collector failed -- digs fall back to text/code routes"
.venv/bin/python scripts/run_miners_fallback.py || echo "chain: miners fallback failed"
.venv/bin/python scripts/promote_external_to_queue.py || echo "chain: external->queue promotion failed"
bash ops/run_cro_ai.sh          || echo "chain: cro-ai failed -- continuing"
bash ops/run_frontier_miner.sh unified || echo "chain: unified frontier failed -- continuing"
bash ops/run_video_hunter.sh    || echo "chain: video hunter failed -- continuing"
echo "=== brain chain done $(date -u) ==="

exit $?
}
