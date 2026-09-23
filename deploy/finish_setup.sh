#!/usr/bin/env bash
# ONE-COMMAND FINISHER -- everything between "code is on the box" and "waiting for the deposit".
#
#     bash deploy/finish_setup.sh
#
# Built 2026-07-30 (launch day) because the manual runbook was nine steps across two terminals and
# the operator asked for one. Every step here is IDEMPOTENT: run it five times, nothing doubles.
# It never asks for anything it already has and never prints a secret back.
#
# RETARGETED 2026-09-05 under the MT5 universe mandate (2026-08-18). This script was the
# crypto-exchange desk's launch runbook: it provisioned Binance API keys, sized a cash-and-carry
# book and armed the executor on this host. That desk is retired. What remains here is the part
# that was never about the venue -- code install, scheduler reconstitution, miner credentials and
# verification -- and the retired steps are recorded in place, with reasons, rather than deleted,
# so an operator who remembers the seven-step version can see what happened to steps 3, 4 and 6.
#
# THIS BOX HOLDS NO BROKER CREDENTIALS. The live desk is desks/mt5/ on the Windows host, executing
# through the MetaTrader 5 terminal; this VPS is research, scheduling and coordination. A research
# box that cannot authenticate to a broker cannot place a trade however wrong its code goes, and
# that is a deliberate topology, not an omission.
set -uo pipefail
cd /home/quant/quant-platform || { echo "FATAL: /home/quant/quant-platform missing"; exit 2; }
umask 077
PY=.venv/bin/python
step() { printf '\n\033[1m== %s ==\033[0m\n' "$1"; }

step "1/7 code + install (idempotent)"
git pull origin master 2>&1 | tail -1
$PY -m pip install -e . --quiet 2>/dev/null && echo "package install: OK"
cd /tmp && /home/quant/quant-platform/$PY -c "import libs, app" 2>/dev/null \
    && echo "imports from outside the repo: OK" \
    || { echo "FATAL: import libs fails -- stop and report this"; exit 2; }
cd /home/quant/quant-platform

step "2/7 scheduler (idempotent; systemd part may print 'owed' lines without root)"
sh deploy/reconstitute_cron.sh 2>&1 | grep -E "installed|REFUS|owed:|sudo " | head -12

# RETIRED 2026-09-05 under the MT5 universe mandate (2026-08-18): step 3 provisioned Binance
# futures/spot API keys and step 4 sized the cash-and-carry book. Both belonged to the
# crypto-exchange desk, which is retired -- there is no Binance account, no
# data/secrets/binance_live*.json and no data/cashcarry_config.json on this box any more, and
# there must never be again. They are recorded here rather than silently dropped because an
# operator who remembers a seven-step runbook needs to be told which two steps went and why,
# otherwise the missing prompts read as a broken script.
#
# WHERE THE MONEY PATH WENT. This VPS no longer holds trading credentials of any kind. The live
# desk is desks/mt5/, executing through the MetaTrader 5 terminal on the Windows host, and its
# broker credentials live in that terminal -- not in this repository and not in a JSON file. This
# box is research, scheduling and coordination only. That separation is the point: a box that
# cannot authenticate to a broker cannot place a trade, however wrong its code goes.
step "3/5 credentials: NONE on this host (money path is desks/mt5 on the Windows box)"
mkdir -p data/secrets && chmod 700 data/secrets
for stale in data/secrets/binance_live.json data/secrets/binance_live_spot.json; do
    [ -e "$stale" ] && echo "WARNING: $stale exists on a desk that retired that venue -- delete it"
done
echo "exchange keys: N/A by design (MT5 terminal holds the broker session)"

step "4/5 miner credentials (unlocks all 11 discovery seats; needs a 'claude setup-token' paste)"
if [ -s data/secrets/claude_oauth_token ]; then
    echo "brain token: already present -- skipping"
else
    printf 'Set up the miner token now? [y/n] (n = do later with: bash ops/setup_brain_token.sh) '
    IFS= read -r TOK
    [ "${TOK:-n}" = "y" ] && bash ops/setup_brain_token.sh || echo "brain token: deferred"
fi

step "5/5 host marker (this box is research/scheduling; it cannot reach a broker)"
if [ -f data/LIVE_VPS_VERIFIED ]; then
    echo "already marked as the durable host"
else
    printf 'Is THIS host the durable production box (not a rebuild)? [y/n] '; IFS= read -r DUR
    if [ "${DUR:-n}" = "y" ]; then
        touch data/LIVE_VPS_VERIFIED
        echo "marked durable"
    else echo "NOT marked -- rerun when on the durable host"; fi
fi
# RETIRED 2026-09-05: this step used to `touch data/LIVE_ENABLE`, which armed the crypto executor
# on THIS box. Arming now belongs to the MT5 gateway on the Windows host and its own CANARY
# authority ramp -- see desks/mt5/mt5desk/gateway.py. A Linux research box that can arm a trading
# book is the topology the desk deliberately left behind, so the flag is not written here.

step "verification"
$PY scripts/check_scheduler_manifest.py 2>&1 | tail -1
$PY scripts/check_constitution_core.py
# RETIRED 2026-09-05: scripts/run_drills.py and scripts/check_gate0_ready.py were deleted with the
# crypto-exchange desk (Gate 0 was that desk's live-capital staging ladder). The MT5 desk's
# readiness is reported by its own chain under desks/mt5/; do not re-add a Gate-0 check here
# without a script that actually exists, or this runbook starts lying about what it verified.

printf '\n\033[1m== DONE. This box is set up. ==\033[0m\n'
echo 'There is no deposit step here any more: the money path is desks/mt5/ on the Windows host,'
echo 'and this VPS holds no broker credentials by design. Capital events are still recorded'
echo 'deliberately and by a human -- scripts/record_capital_event.py -- because only a signed'
echo 'capital event may clear the ruin stop.'
