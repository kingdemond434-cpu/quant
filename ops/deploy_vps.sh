#!/usr/bin/env bash
# BRING THE WHOLE DESK UP ON THE VPS -- one command, and it VERIFIES rather than reports success.
#
# WHY THIS EXISTS. Until 2026-08-03 the repository could start recorders, a moat miner and five
# credit-blocked diggers. It could not start the desk. Nothing in it launched:
#
#   the cadence engine   -- which fires the panel, tier-1, the moat screen, survivor promotion and
#                           the forward-clock review, AND enforces the never-sleepier floors
#   the pager            -- whose artifact has a 1.0h floor that was therefore violated from the
#                           first hour of any fresh install, permanently
#   the process supervisor -- whose own header records that when it died on 2026-07-11 the desk ran
#                           ELEVEN AND A HALF DAYS with the pager silent and the forward clocks
#                           frozen, because nothing restarted it
#   the Tier-3 ruin rail -- the last-resort protection against a 35% drawdown
#
# Every one of those lived exactly as long as someone remembered to type its name. That is the same
# failure that left the moat empty, and it is structural, not careless: unit files are easy to
# write and easy to never install.
#
# THE LAST STEP IS THE POINT. `systemctl is-active` proves a process is alive and never that it
# PRODUCED, so this ends by running scripts/verify_deployment.py, which asks of every organ when it
# last WROTE something. If that fails, the deploy failed -- whatever systemd says.
#
# Public market data + local research only. The one fund-moving unit is NOT enabled here; see the
# sign-off block at the end.
set -uo pipefail
cd "$(dirname "$0")/.." || exit 1
ROOT="$(pwd)"
UNITS_DIR=/etc/systemd/system

say() { printf '\n\033[1m%s\033[0m\n' "$*"; }
have_sudo() { sudo -n true 2>/dev/null; }

say "quant deploy -- $ROOT"

# ---------------------------------------------------------------- 0. sanity, before anything
if [ ! -x .venv/bin/python ]; then
    echo "  FAIL: .venv/bin/python missing. Create it first:"
    echo "     python3 -m venv .venv && .venv/bin/pip install -e '.[dev]'"
    exit 1
fi
PY=.venv/bin/python
echo "  python: $($PY --version)"

# A deploy that installs a broken tree is worse than no deploy: it looks finished. The gates are
# cheap and they are the same three CI runs, so there is no excuse for skipping them here.
say "1. gates (the same three CI runs -- a broken tree must not reach a live box)"
if ! .venv/bin/ruff check . >/dev/null 2>&1; then
    echo "  FAIL: ruff. Fix before deploying."; exit 1; fi
echo "  ok   ruff"
if ! .venv/bin/mypy >/dev/null 2>&1; then
    echo "  FAIL: mypy --strict. Fix before deploying."; exit 1; fi
echo "  ok   mypy --strict"
if ! .venv/bin/pytest -q >/dev/null 2>&1; then
    echo "  FAIL: pytest. Fix before deploying."; exit 1; fi
echo "  ok   pytest"

# ---------------------------------------------------------------- 1. install the units
say "2. install unit files"
UNITS=(
    quant-recorder-fut.service quant-recorder-spot.service quant-recorder-bybit.service
    quant-moat-miner.service quant-moat-screen.service
    quant-watchdog.service quant-watchdog.timer
    quant-alerts.service   quant-alerts.timer
    quant-cadence.service  quant-cadence.timer
    quant-daily-max.service quant-daily-max.timer
    quant-dataaxis.service quant-dataaxis.timer
    quant-prospector.service quant-prospector.timer
    quant-litminer.service quant-litminer.timer
    quant-frontier.service quant-frontier.timer
    quant-blindrediscovery.service quant-blindrediscovery.timer
    quant-deadman.service
)
if have_sudo; then
    for u in "${UNITS[@]}"; do
        [ -f "ops/$u" ] && sudo cp "ops/$u" "$UNITS_DIR/" && echo "  installed $u"
    done
    sudo systemctl daemon-reload
else
    echo "  NO SUDO -- /etc/systemd/system is unreachable."
    echo "  That is not a reason to leave the desk unstarted. Use the zero-privilege path:"
    echo "     bash ops/start_recorders_nosudo.sh"
    echo "     ( crontab -l 2>/dev/null | grep -v start_recorders_nosudo"
    echo "       echo '@reboot cd $ROOT && bash ops/start_recorders_nosudo.sh >> data/supervisor.log 2>&1'"
    echo "       echo '*/5 * * * * cd $ROOT && bash ops/start_recorders_nosudo.sh >> data/supervisor.log 2>&1'"
    echo "     ) | crontab -"
    echo "  ...then re-run this script's verification step:  $PY scripts/verify_deployment.py"
    exit 2
fi

# ---------------------------------------------------------------- 2. start, in dependency order
# RECORDERS FIRST, ALWAYS. Everything downstream reads what they write, and a miner reporting 0%
# because no tape exists is noise that hides the real signal. Every unrecorded second is
# permanently unbuyable -- the only cost on this desk money cannot fix afterwards.
say "3. start the recorders (tape first -- nothing downstream has anything to read without them)"
sudo systemctl enable --now quant-recorder-fut quant-recorder-spot quant-recorder-bybit
sleep 20
FILES=$(find data/moat -name '*.jsonl.gz' 2>/dev/null | wc -l)
echo "  tape files after 20s: $FILES"
if [ "$FILES" -eq 0 ]; then
    echo "  WARNING: still no tape. Check egress before continuing:"
    echo "     journalctl -u quant-recorder-fut -n 40 --no-pager"
    echo "  A 403 on CONNECT to fapi.binance.com means this box cannot reach the venue."
fi

say "4. start the survival organs (these are what had NO launcher at all)"
sudo systemctl enable --now quant-watchdog.timer quant-alerts.timer quant-cadence.timer

say "5. start the moat organs (mine describes the tape; screen interrogates it)"
sudo systemctl enable --now quant-moat-miner quant-moat-screen

say "6. start the daily sweep and the credit-gated diggers"
sudo systemctl enable --now quant-daily-max.timer
for t in dataaxis prospector litminer frontier blindrediscovery; do
    sudo systemctl enable --now "quant-$t.timer" 2>/dev/null \
        && echo "  enabled quant-$t.timer (fires only when OpenRouter credits exist)"
done

# ---------------------------------------------------------------- 3. verify PRODUCTION
say "7. verify -- production, not process status"
echo "  Giving the organs one cadence tick to write something before judging them."
sleep 90
$PY scripts/verify_deployment.py
RC=$?

say "8. the one unit this script will NOT arm for you"
cat <<'SIGNOFF'
  quant-deadman.service is the Tier-3 ruin rail. It polls combined book equity once a minute and,
  after five consecutive readings below 65% of the high-water mark, writes the executor kill file,
  market-flattens every futures position reduce-only, sells spot to USDT and pages you.

  It MOVES FUNDS, so arming it is your act and not a script's -- that is what its tier means.

  Before you run the line below, confirm three things:
    1. live API keys are present and have trade permission
    2. the high-water mark in the rail's state reflects the real book, not a test run
    3. 65% is the level you intend

      sudo systemctl enable --now quant-deadman

  Until you do, the desk has no automated protection against a 35% drawdown.
SIGNOFF

if [ $RC -eq 0 ]; then
    say "DEPLOYED -- every organ the repository can start is started and PRODUCING."
else
    say "INCOMPLETE -- see the FAIL lines above. Fix them before believing any number this desk reports."
fi
exit $RC
