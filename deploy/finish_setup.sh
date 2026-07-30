#!/usr/bin/env bash
# ONE-COMMAND FINISHER -- everything between "code is on the box" and "waiting for the deposit".
#
#     bash deploy/finish_setup.sh
#
# Built 2026-07-30 (launch day) because the manual runbook was nine steps across two terminals and
# the operator asked for one. Every step here is IDEMPOTENT: run it five times, nothing doubles.
# It never asks for anything it already has, never prints a secret back, and ends by printing the
# ONE command that remains (recording the deposit -- deliberately a human act, see
# scripts/record_capital_event.py: only a signed capital event may clear the ruin stop).
#
# Safe-by-order: arming happens LAST and only after an explicit y/n, and even armed the book
# cannot open -- the ruin rail holds it flat until the deposit is recorded. That is the designed
# launch posture: fully set up, held, deposit is the trigger.
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

step "3/7 Binance keys (create on Binance: TRADE-ONLY, withdrawals DISABLED, IP-restrict to this VPS)"
mkdir -p data/secrets && chmod 700 data/secrets
if [ -s data/secrets/binance_live.json ]; then
    echo "futures key: already present -- skipping (delete data/secrets/binance_live.json to redo)"
else
    printf 'Futures API key (Enter to skip for now): '; IFS= read -r FK
    if [ -n "${FK:-}" ]; then
        printf 'Futures API secret (typing hidden): '; IFS= read -rs FS; echo
        printf '{"key": "%s", "secret": "%s"}\n' "$FK" "$FS" > data/secrets/binance_live.json
        chmod 600 data/secrets/binance_live.json; echo "futures key: written"
    else echo "futures key: SKIPPED"; fi
fi
if [ -s data/secrets/binance_live_spot.json ]; then
    echo "spot key: already present -- skipping"
elif [ -s data/secrets/binance_live.json ]; then
    printf 'Use the SAME key for spot? [y/n] '; IFS= read -r SAME
    if [ "${SAME:-n}" = "y" ]; then
        cp data/secrets/binance_live.json data/secrets/binance_live_spot.json
        chmod 600 data/secrets/binance_live_spot.json; echo "spot key: copied from futures"
    else
        printf 'Spot API key (Enter to skip): '; IFS= read -r SK
        if [ -n "${SK:-}" ]; then
            printf 'Spot API secret (typing hidden): '; IFS= read -rs SS; echo
            printf '{"key": "%s", "secret": "%s"}\n' "$SK" "$SS" > data/secrets/binance_live_spot.json
            chmod 600 data/secrets/binance_live_spot.json; echo "spot key: written"
        else echo "spot key: SKIPPED"; fi
    fi
fi

step "4/7 launch sizing (Gate 0: capital <=10% of book, 4-5 names)"
$PY - <<'EOF'
import json
p = "data/cashcarry_config.json"
d = json.load(open(p))
if d.get("capital") == 200 and d.get("top") == 4:
    print(f"already set: capital=200 top=4")
else:
    print(f"was: capital={d.get('capital')} top={d.get('top')}")
    d["capital"], d["top"] = 200, 4
    json.dump(d, open(p, "w"), indent=2)
    print("now: capital=200 top=4 (live-tunable; the executor picks it up next rebalance)")
EOF

step "5/7 miner credentials (unlocks all 11 discovery seats; needs a 'claude setup-token' paste)"
if [ -s data/secrets/claude_oauth_token ]; then
    echo "brain token: already present -- skipping"
else
    printf 'Set up the miner token now? [y/n] (n = do later with: bash ops/setup_brain_token.sh) '
    IFS= read -r TOK
    [ "${TOK:-n}" = "y" ] && bash ops/setup_brain_token.sh || echo "brain token: deferred"
fi

step "6/7 ARM (safe: the ruin rail holds the book FLAT until the deposit is recorded)"
if [ -f data/LIVE_ENABLE ] && [ -f data/LIVE_VPS_VERIFIED ]; then
    echo "already armed"
else
    printf 'Is THIS host the durable production box (not a rebuild)? [y/n] '; IFS= read -r DUR
    if [ "${DUR:-n}" = "y" ]; then
        touch data/LIVE_VPS_VERIFIED data/LIVE_ENABLE
        echo "ARMED (stand down instantly any time: rm data/LIVE_ENABLE)"
    else echo "NOT armed -- rerun when on the durable host"; fi
fi

step "7/7 verification"
$PY scripts/check_scheduler_manifest.py 2>&1 | tail -1
$PY scripts/check_constitution_core.py
$PY scripts/run_drills.py 2>&1 | head -1
$PY scripts/check_gate0_ready.py 2>&1 | tail -20

printf '\n\033[1m== DONE. The one remaining step, whenever the money lands: ==\033[0m\n'
echo '  1. Deposit $200 on Binance (~$100 spot wallet, ~$100 futures wallet)'
echo '  2. Run:'
echo '     .venv/bin/python scripts/record_capital_event.py --deposit 200 \'
echo '         --by "principal" --reason "Gate 0 launch tranche: 200 USD live evidence book"'
echo 'The next rebalance opens the book on its own. Nothing else to run, ever, for this launch.'
