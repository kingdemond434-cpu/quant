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

# ---------------------------------------------------------------- 0.5 WHICH CODE IS THIS?
# A deploy that installs a STALE tree is the same failure class as one that installs a broken tree:
# it looks finished. On 2026-08-05 the operator's `git pull --rebase` died on "cannot pull with
# rebase: You have unstaged changes" (organs rewrite generated JSON as they run), and this script
# then deployed the un-pulled tree and reported success -- roughly 100 commits of work silently
# absent from a box that had just been told it was up to date. The gates below all passed, because
# the stale tree was internally consistent; nothing here asked WHICH code it was gating.
#
# So: state the provenance out loud, and refuse by default when the tree is not what the operator
# thinks it is. --allow-stale exists because deploying a known-stale tree is sometimes deliberate
# (rolling back, or a box deliberately pinned) -- but it must be a decision someone TYPED, not the
# silent default it was.
ALLOW_STALE=0
for a in "$@"; do [ "$a" = "--allow-stale" ] && ALLOW_STALE=1; done

say "0.5 code provenance -- which commit is about to become the desk?"
if git rev-parse --git-dir >/dev/null 2>&1; then
    BRANCH="$(git rev-parse --abbrev-ref HEAD 2>/dev/null || echo '?')"
    HEAD_SHA="$(git rev-parse --short HEAD 2>/dev/null || echo '?')"
    DIRTY="$(git status --porcelain 2>/dev/null | wc -l | tr -d ' ')"
    echo "  branch: $BRANCH    head: $HEAD_SHA    locally-modified tracked files: $DIRTY"
    # Fetch is read-only and cannot touch the working tree, so it is safe even mid-incident.
    if git fetch origin "$BRANCH" >/dev/null 2>&1; then
        BEHIND="$(git rev-list --count "HEAD..origin/$BRANCH" 2>/dev/null || echo 0)"
        AHEAD="$(git rev-list --count "origin/$BRANCH..HEAD" 2>/dev/null || echo 0)"
        echo "  vs origin/$BRANCH: $BEHIND behind, $AHEAD ahead"
    else
        BEHIND=0; AHEAD=0
        echo "  vs origin/$BRANCH: UNKNOWN (fetch failed -- offline or no remote access)"
    fi
    if [ "$BEHIND" -gt 0 ] || [ "$DIRTY" -gt 0 ]; then
        echo ""
        echo "  ================================================================"
        echo "  STALE OR DIRTY TREE -- this deploy would NOT be today's code."
        [ "$BEHIND" -gt 0 ] && echo "    $BEHIND commit(s) exist on origin/$BRANCH that are not here."
        [ "$DIRTY" -gt 0 ] && echo "    $DIRTY tracked file(s) modified locally (organs rewrite generated JSON)."
        echo ""
        echo "  To sync (stash keeps the generated files recoverable -- 'git stash list'):"
        echo "    git stash push -m vps-generated && git pull --rebase origin $BRANCH"
        echo ""
        echo "  NEVER use 'git stash -u' or '-a' on this box: the moat tape under data/ is the"
        echo "  one un-replicable asset here, and -a would try to pack it."
        echo ""
        echo "  To deploy this tree anyway, deliberately:  bash ops/deploy_vps.sh --allow-stale"
        echo "  ================================================================"
        if [ "$ALLOW_STALE" -eq 0 ]; then
            echo "  FAIL: refusing to deploy a stale/dirty tree without --allow-stale."; exit 1; fi
        echo "  --allow-stale given: proceeding on the operator's explicit decision."
    else
        echo "  ok   tree matches origin/$BRANCH and is clean"
    fi
else
    echo "  WARN: not a git checkout -- provenance UNVERIFIABLE, continuing"
fi

# A deploy that installs a broken tree is worse than no deploy: it looks finished. The gates are
# cheap and they are the same three CI runs, so there is no excuse for skipping them here.
#
# EVERY GATE IS WALL-CLOCK BOUNDED, and that is not belt-and-braces. A gate that can hang has no
# failure mode a human ever sees: `pytest -q` stalling on a socket read (which it does -- see the
# timeout block in pyproject.toml) leaves this script sitting at step 1 indefinitely, and an
# operator who ran the deploy and walked away comes back to a box that is neither deployed nor
# reported as failed. Silence reads as progress. The suite-level per-test timeout catches the
# common case from inside; these bounds catch what it cannot -- a hang during collection, an
# import that blocks, or a box where the plugin is missing entirely. Belt outside the braces,
# because the thing being protected against is precisely the gate's own machinery not running.
say "1. gates (the same three CI runs -- a broken tree must not reach a live box)"
gate() {  # gate <seconds> <label> <cmd...>
    local secs="$1" label="$2"; shift 2
    timeout --kill-after=30 "$secs" "$@" >/dev/null 2>&1
    local rc=$?
    if [ $rc -eq 124 ] || [ $rc -eq 137 ]; then
        echo "  FAIL: $label HUNG (>${secs}s, killed). A hang is a failure, not a slow pass."
        echo "     Reproduce with:  .venv/bin/pytest -q --timeout=150 --timeout-method=signal"
        echo "     A network-blocked test on a filtered-egress box is the usual cause."
        exit 1
    fi
    [ $rc -ne 0 ] && { echo "  FAIL: $label. Fix before deploying."; exit 1; }
    echo "  ok   $label"
}
gate 300  "ruff"        .venv/bin/ruff check .
gate 900  "mypy --strict" .venv/bin/mypy
gate 2700 "pytest"      .venv/bin/pytest -q

# ---------------------------------------------------------------- 1. install the units
say "2. install unit files"
# RETIRED 2026-09-05 under the MT5 universe mandate (2026-08-18): quant-recorder-fut.service,
# quant-recorder-spot.service and quant-recorder-bybit.service recorded the Binance/Bybit tape.
# The units are deleted from ops/ and must not come back -- the desk's tape is the MT5/Fusion one
# (docs/research/MOAT_NODE_SPEC.md), recorded on the Windows host. They are named here rather than
# silently dropped because `[ -f ops/$u ]` would have skipped them in silence, and a deploy script
# that quietly installs three fewer units than its list claims is how a box drifts from its manifest.
UNITS=(
    quant-watchdog.service quant-watchdog.timer
    quant-alerts.service   quant-alerts.timer
    quant-cadence.service  quant-cadence.timer
    quant-daily-max.service quant-daily-max.timer
    quant-midnight-frontier.service quant-midnight-frontier.timer
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
    # Migration from the old colliding midnight unit. Retire ONLY its timer; the identically
    # named deploy/quant-research.service is the autonomous supervisor and must remain intact.
    if [ -e "$UNITS_DIR/quant-research.timer" ] || [ -L "$UNITS_DIR/quant-research.timer" ]; then
        sudo systemctl disable --now quant-research.timer >/dev/null 2>&1 || true
        sudo rm -f "$UNITS_DIR/quant-research.timer"
        echo "  retired legacy quant-research.timer; preserved quant-research.service"
    fi
    sudo systemctl daemon-reload
else
    echo "  NO SUDO -- /etc/systemd/system is unreachable."
    echo "  That is not a reason to leave the desk unstarted. Use the zero-privilege path:"
    # REPAIRED 2026-09-05. The four lines here were an identical retired-comment stub repeated
    # four times, left behind when start_recorders_nosudo.sh was retired on 2026-08-17 -- so the
    # operator was told "use the zero-privilege path", shown nothing, and then handed a dangling
    # `) | crontab -`. The path that actually works without root is the user-timer route:
    echo "     bash ops/install_early_seat_timers.sh    # user-level systemd timers, no root"
    echo "     sh deploy/reconstitute_cron.sh           # or re-home the manifest rows into cron"
    echo "  ...then re-run this script's verification step:  $PY scripts/verify_deployment.py"
    exit 2
fi

# ---------------------------------------------------------------- 2. start, in dependency order
# RETIRED 2026-08-17, and finished 2026-09-05 under the MT5 universe mandate (2026-08-18).
# This step used to start the Binance/Bybit recorders and then block for 20 seconds counting tape
# files under data/moat, warning the operator to check egress to fapi.binance.com if none arrived.
# All three recorder units are gone, so the step counted a directory nothing writes any more,
# always found zero, and always printed a warning naming a venue this desk may not reach -- a
# deploy that ends in a false alarm teaches an operator to ignore its output.
#
# THE TAPE STILL MATTERS; IT IS JUST NOT RECORDED HERE. Every unrecorded second is permanently
# unbuyable, which is the one cost money cannot fix afterwards -- but the desk's tape is now the
# MT5/Fusion one, recorded on the Windows moat node (docs/research/MOAT_NODE_SPEC.md), not on this
# Linux box. Nothing to start here, and the 20-second sleep is gone with it.
say "3. tape: recorded on the MT5 moat node, not on this host"
echo "   crypto recorders: RETIRED (constitution 224 + MT5 universe mandate 2026-08-18)"
echo "   MT5 tape health is reported by the desk chain under desks/mt5/, not by this script"

say "4. start the survival organs and the unique midnight frontier timer"
sudo systemctl enable --now quant-watchdog.timer quant-alerts.timer quant-cadence.timer quant-midnight-frontier.timer

# RETIRED 2026-09-05 under the MT5 universe mandate (2026-08-18): the moat organs
# (quant-moat-miner, quant-moat-screen, their run_moat_*.sh launchers and scripts/mine_moat.py +
# scripts/screen_moat.py) described and interrogated the crypto L2 tape under data/moat. That tape
# is no longer recorded and the venue is retired ground, so the pair looped over an empty
# directory. All six files are deleted. The desk's moat is now the MT5/Fusion tape on the Windows
# moat node (docs/research/MOAT_NODE_SPEC.md), which has its own describe/screen path.
say "5. moat organs: RETIRED (crypto L2 tape); MT5 moat lives on the Windows moat node"

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
