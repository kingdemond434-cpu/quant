#!/bin/sh
# deploy/pull_deploy.sh -- the INBOUND half of the deploy path (EXECUTION_QUEUE.md RANK 7).
#
# THE GAP THIS CLOSES. scripts/git_snapshot.py pushes VPS -> GitHub. NOTHING pulled
# GitHub -> VPS, so merging to master deployed NOTHING and every change needed a manual SSH.
# The desk already paid for that at the worst layer: on 2026-07-26 an orphaned executor ran
# PRE-FIX code for 8h, so "the funding-measurement fix committed that evening was inert in the
# process that actually owned the book" (scripts/watchdog.py:66-76). This converts "the principal
# must SSH for every change" into "merge is deploy".
#
# WHAT IT REFUSES TO DO, and why each refusal is the safe direction:
#   * DIRTY TREE -> refuse. Uncommitted work on the box is an operator hotfix mid-flight; a deploy
#     that clobbers it destroys the only copy. Not deploying is always recoverable.
#   * DIVERGED / BOX AHEAD -> refuse. This is FAST-FORWARD ONLY. Resolving a real merge
#     unattended, on the box that owns the book, is not a thing a cron job may attempt.
#   * CI RED -> nothing is merged. The gate runs in a DETACHED WORKTREE at the fetched commit, so
#     the live tree never moved and there is nothing to revert (R0246). This also means the box is
#     never, at any instant, sitting on code that failed its own gate.
#   * TREE MOVED MID-GATE -> the MERGE refuses, and refusing costs nothing because the tree was
#     never touched. The CI window is minutes long; work that lands in it (a session's commit, an
#     operator hotfix) is the only copy, and on 2026-07-31 the then-unconditional revert destroyed
#     exactly that. `git reset --hard` is no longer reachable from this script at all.
#     (run_ci is invoked --fail-on-lock here: "another gate is mid-run" is not "green".)
#   * RUIN RAIL CHANGED -> reported, never restarted. A deadman restart is a window with no ruin
#     rail; no unattended script opens that window (libs/ops/deploy_plan.py explains the tiering).
#
# WHAT TO RESTART IS COMPUTED, NOT LISTED. libs/ops/deploy_plan.py derives each supervised
# process's blast radius from its real first-party import closure, so adding an import widens it
# automatically. A hand-kept list would rot silently and leave stale code owning the book -- the
# exact 2026-07-26 failure, arriving by a second route.
#
#     sh deploy/pull_deploy.sh [--dry-run] [--branch NAME]
#
# --dry-run fetches, computes and PRINTS the full plan while touching nothing. Use it the first
# time on the live box, and any time the plan might include the executor.
set -eu

SELF_DIR=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
ROOT=$(CDPATH= cd -- "$SELF_DIR/.." && pwd)
cd "$ROOT"

BRANCH=""
DRY=0
while [ $# -gt 0 ]; do
    case "$1" in
        --dry-run) DRY=1 ;;
        --branch)  shift; [ $# -gt 0 ] || { echo "pull-deploy: --branch needs a value" >&2; exit 2; }
                   BRANCH="$1" ;;
        -h|--help) sed -n '2,32p' "$0"; exit 0 ;;
        *) echo "pull-deploy: unknown argument '$1'" >&2; exit 2 ;;
    esac
    shift
done

LOG_DIR="$ROOT/data/cro_ai_logs"
STATE="$ROOT/data/pull_deploy_state.json"
mkdir -p "$LOG_DIR" "$ROOT/data"
NOW=$(date -u +%Y-%m-%dT%H:%M:%SZ)

# venv python first (desk convention), system python3 as the restore-day fallback.
PY="$ROOT/.venv/bin/python"
[ -x "$PY" ] || PY=$(command -v python3) || { echo "pull-deploy: no python3" >&2; exit 2; }

say() { echo "pull-deploy: $*"; }

# ONE trap for the whole script, installed before anything it cleans up exists. Two `trap ... EXIT`
# calls do not compose -- the second REPLACES the first -- and the gate worktree must be removed on
# every path including a kill, or one crashed tick wedges every tick after it.
CLEAN_GATE=""
OUTCOMES=""
cleanup() {
    if [ -n "$CLEAN_GATE" ]; then
        git worktree remove --force "$CLEAN_GATE" >/dev/null 2>&1 || rm -rf "$CLEAN_GATE"
        git worktree prune >/dev/null 2>&1 || true
    fi
    [ -z "$OUTCOMES" ] || rm -f "$OUTCOMES"
}
trap cleanup EXIT INT TERM

# Evidence artifact: one flat object, last run wins. max_audit fences it so a box that silently
# stopped pulling -- or that is parked on a REVERTED red deploy -- cannot look healthy.
record() {   # record <status> <from> <to> <note>
    printf '{"ts":"%s","status":"%s","from":"%s","to":"%s","branch":"%s","note":"%s"}\n' \
        "$NOW" "$1" "$2" "$3" "$BRANCH" "$4" > "$STATE"
    echo "$NOW $1 $2->$3 $4" >> "$LOG_DIR/pull_deploy.log"
}

git rev-parse --git-dir >/dev/null 2>&1 || {
    say "not a git repo -- nothing to deploy"; exit 2; }

if [ -z "$BRANCH" ]; then
    BRANCH=$(git rev-parse --abbrev-ref HEAD 2>/dev/null || echo "")
    [ -n "$BRANCH" ] && [ "$BRANCH" != "HEAD" ] || {
        say "detached HEAD and no --branch given -- refusing to guess"; exit 2; }
fi

# ---------------------------------------------------------------- refuse on a dirty/ahead box
# TRACKED modifications only (--untracked-files=no). The distinction is not pedantry: a modified
# tracked file is an operator hotfix a fast-forward would destroy, so refusing is right. An
# UNTRACKED file cannot be lost -- git aborts a merge that would overwrite one -- so refusing on
# it buys nothing and costs a deadlock class: this script writes its own evidence into data/, and
# on any box where that is not ignored, run #1 would wedge every run after it. Found by the
# end-to-end drill, not by reading the code.
# THE REFUSAL IS NARROWED TO THE ONLY CASE THAT LOSES DATA: a dirty path the fast-forward would
# ITSELF overwrite. It is NOT weakened -- that case still refuses, and refuses earlier and louder
# than before, naming the colliding paths instead of dumping the whole status.
#
# WHY THE OLD ANY-DIRT TEST HAD TO GO, measured rather than argued (2026-08-12): 1078 logged ticks
# since 08-04, 91.1% refused-dirty, and `deployed` appears ZERO times -- this desk's only inbound
# deploy path had never once deployed. That is a WELDED GATE (L1.43): a control that refuses ~100%
# carries no information and is a wall, not a bar. The dirt is not operator work and never was:
# organs rewrite TRACKED files on a cadence (recommendation_ledger.json on every recommendations.py
# call, backups/moat/*, reports/*, data/*_record.json), and `git add -A` had recorded four agent
# worktrees as accidental GITLINKS whose shas move whenever a sibling session commits -- dirt that
# cannot be cleaned even in principle, because committing a gitlink only re-points it.
#
# WHY THE INTERSECTION IS THE RIGHT PREDICATE, verified empirically before this was written rather
# than reasoned from the man page: git ALREADY enforces exactly this rule. A fast-forward over a
# file dirty-but-absent-from-the-diff SUCCEEDS and preserves the local content; over a file dirty
# AND in the diff it ABORTS with "Your local changes would be overwritten", leaving the hotfix
# intact. So the operator-hotfix protection this refusal exists for is a property of git itself,
# and the script's job is only to decide EARLIER, record the status, and say which paths collided.
# The two fixes considered before this one -- move organ state out of git, or give the script an
# allowlist of artifacts it may `reset` -- are both strictly worse: an allowlist rots, and anything
# that discards a tracked file on a live box can destroy the only copy of a session's work, which
# this desk has already paid for once (R0144, 2026-07-31).
dirty_paths() { git diff --name-only -z HEAD 2>/dev/null | tr '\0' '\n' | sed '/^$/d' | sort -u; }
DIRTY=$(dirty_paths)
is_dirty() { printf '%s\n' "$DIRTY" | grep -Fxq -- "$1"; }

# SELF-INSTALLING SCHEDULER (2026-07-30). The manifest is source; the live crontab is derived
# state -- and nothing re-derived it. A manifest change deployed by this very script sat
# uninstalled until a human remembered deploy/reconstitute_cron.sh, which on launch day meant the
# operator was the deployment mechanism for a desk whose whole premise is that it is not.
# STATE-BASED, not diff-based, on purpose: the pull that DELIVERS a new manifest is executed by
# the OLD copy of this script (cron runs whatever is on disk at tick time), so a diff hook would
# miss exactly the change that introduces it. Comparing a stored hash of the last INSTALLED
# manifest against the current file catches that case and every future one, including manifests
# that arrive while the puller is broken. reconstitute_cron.sh is idempotent (fenced crontab
# block) and needs no root for the cron half; its systemd half degrades to printed "owed" lines.
# LAW-GATE HOOK INSTALL (L1.37): every clone of this repo gets the pre-push gate, so a breach
# cannot leave any box for master. Idempotent; a symlink would break on Windows checkouts.
# Both self-installers below used to sit BEHIND the any-dirt refusal, so on a permanently-dirty box
# neither had run since 08-04 either -- the welded gate had two silent victims, not one. They are
# restored here under a PRECISE predicate instead of a blanket one: install only when the source
# file itself is unmodified, which is exactly the "drifted box" hazard (installing an operator's
# uncommitted manifest or hook) and nothing wider.
if [ -d "$ROOT/.git/hooks" ] && [ -f "$ROOT/deploy/git_hooks/pre-push" ] \
   && ! is_dirty deploy/git_hooks/pre-push; then
    cp "$ROOT/deploy/git_hooks/pre-push" "$ROOT/.git/hooks/pre-push" 2>/dev/null || true
    chmod +x "$ROOT/.git/hooks/pre-push" 2>/dev/null || true
fi

# ROLE SELECTION (R0107): a box with `research` in ops/role installs the research-twin
# manifest; everything else keeps the full manifest. ops/role is gitignored per-box state.
_ROLE=$(cat "$ROOT/ops/role" 2>/dev/null || echo primary)
_MAN_FILE="$ROOT/ops/crontab.manifest"
[ "$_ROLE" = "research" ] && _MAN_FILE="$ROOT/ops/crontab.research.manifest"
_MAN_REL=${_MAN_FILE#"$ROOT"/}
if [ "$DRY" -eq 0 ] && [ -f "$_MAN_FILE" ] && ! is_dirty "$_MAN_REL"; then
    _MAN_WANT=$(cksum "$_MAN_FILE" | cut -d' ' -f1)
    _MAN_HAVE=$(cat "$ROOT/data/.crontab_installed_hash" 2>/dev/null || echo none)
    if [ "$_MAN_WANT" != "$_MAN_HAVE" ]; then
        say "scheduler manifest not yet installed at this hash ($_MAN_HAVE -> $_MAN_WANT)"
        mkdir -p "$ROOT/data/cro_ai_logs"
        if sh "$ROOT/deploy/reconstitute_cron.sh" >> "$ROOT/data/cro_ai_logs/reconstitute_auto.log" 2>&1; then
            printf '%s\n' "$_MAN_WANT" > "$ROOT/data/.crontab_installed_hash"
            say "crontab reinstalled from manifest (log: data/cro_ai_logs/reconstitute_auto.log)"
        else
            say "reconstitute refused (repo checks failed) -- crontab left as-is, retrying next tick"
        fi
    fi
fi

OLD=$(git rev-parse HEAD)
OLD_SHORT=$(git rev-parse --short HEAD)

say "fetching origin/$BRANCH"
FETCHED=0
for delay in 0 2 4 8; do
    [ "$delay" -eq 0 ] || { say "fetch failed -- retrying in ${delay}s"; sleep "$delay"; }
    if git fetch origin "$BRANCH" >/dev/null 2>&1; then FETCHED=1; break; fi
done
[ "$FETCHED" -eq 1 ] || {
    say "fetch failed after retries -- offsite unreachable, box left untouched"
    record fetch-failed "$OLD_SHORT" "-" "git fetch origin $BRANCH failed"; exit 2; }

NEW=$(git rev-parse FETCH_HEAD)
NEW_SHORT=$(git rev-parse --short FETCH_HEAD)

if [ "$OLD" = "$NEW" ]; then
    say "already at $NEW_SHORT -- nothing to deploy"
    record up-to-date "$OLD_SHORT" "$NEW_SHORT" "no new commits"
    exit 0
fi

# FAST-FORWARD ONLY. If HEAD is not an ancestor of the fetched tip, either the box carries local
# commits or history was rewritten upstream. Both need a human; neither is a merge a cron job does.
if ! git merge-base --is-ancestor "$OLD" "$NEW"; then
    say "REFUSING -- $OLD_SHORT is not an ancestor of $NEW_SHORT (diverged, or upstream rewrote"
    say "history). This path is fast-forward only. Reconcile by hand:"
    say "  git log --oneline --left-right $OLD...$NEW"
    record refused-diverged "$OLD_SHORT" "$NEW_SHORT" "not fast-forwardable"
    exit 2
fi

CHANGED=$(git diff --name-only "$OLD" "$NEW")
N_CHANGED=$(printf '%s\n' "$CHANGED" | grep -c . || true)
say "$N_CHANGED changed path(s) between $OLD_SHORT and $NEW_SHORT"

# ---------------------------------------------------------------- the collision test
# Only NOW can the dirty set be judged, because "would this deploy destroy local work?" is a
# question about the INTERSECTION of what is dirty with what this specific commit range touches --
# it is unanswerable before the fetch, which is why the old test asked the answerable-but-wrong
# question instead. Loop rather than `comm`/process-substitution: DIRTY is a handful of paths, and
# this is #!/bin/sh where <(...) does not exist.
# `if` rather than `grep && printf`: under `set -e` the short-circuit leaves the loop -- and so the
# command substitution -- non-zero on the NO-COLLISION path, which killed the script exactly when
# it should have proceeded. A deploy guard whose happy path exits 1 is the welded gate again.
COLLIDE=$(printf '%s\n' "$DIRTY" | while IFS= read -r p; do
    [ -n "$p" ] || continue
    if printf '%s\n' "$CHANGED" | grep -Fxq -- "$p"; then printf '%s\n' "$p"; fi
done) || true

if [ -n "$COLLIDE" ]; then
    N_COLLIDE=$(printf '%s\n' "$COLLIDE" | grep -c . || true)
    say "REFUSING -- $N_COLLIDE locally-modified path(s) are also changed by this fast-forward."
    say "Uncommitted work here is an operator hotfix mid-flight and the deploy would destroy the"
    say "only copy. Commit it (or move it aside) and the next tick deploys:"
    printf '%s\n' "$COLLIDE" | sed 's/^/    /' | head -20
    if [ "$DRY" -eq 0 ]; then
        record refused-dirty "$OLD_SHORT" "$NEW_SHORT" "$N_COLLIDE dirty path(s) collide with the incoming diff"
        exit 2
    fi
    say "--dry-run: reporting only."
elif [ -n "$DIRTY" ]; then
    # SAY IT OUT LOUD. Proceeding over a dirty tree is the new behaviour and a reader of this log
    # must never infer the tree was clean; git will still abort the merge if this judgement is wrong.
    N_DIRTY=$(printf '%s\n' "$DIRTY" | grep -c . || true)
    say "$N_DIRTY tracked path(s) locally modified, none of them touched by this range -- proceeding"
fi

PLAN=$(printf '%s\n' "$CHANGED" | "$PY" -m libs.ops.deploy_plan --directives || true)
printf '%s\n' "$CHANGED" | "$PY" -m libs.ops.deploy_plan || true

if [ "$DRY" -eq 1 ]; then
    say "--dry-run: nothing applied (still at $OLD_SHORT)"
    exit 0
fi

# ---------------------------------------------------------------- gate ELSEWHERE, merge on green
# THE ORDER IS THE WHOLE SECURITY PROPERTY (R0246). This block used to `git merge --ff-only` and
# only THEN run the gate -- so the live tree held unreviewed upstream code, and the very first
# thing to execute from it was that code's own copy of run_ci.py. The control the desk counted on
# as its safety gate WAS the payload trigger, on the box that owns the live broker credentials,
# every 10 minutes. (The credential named here at the time was data/secrets/binance_live.json, on
# the crypto-exchange desk retired 2026-08-18; the box now owns the MT5/Fusion login instead. The
# inversion this paragraph describes is a property of the ORDER of operations, not of the venue,
# which is why the record is kept verbatim in every other respect.) Two further paths inherited the same inversion by running from the live tree
# on the NEXT tick: the pre-push hook this script copies into .git/hooks and chmods +x (line 110),
# and reconstitute_cron.sh installing an arbitrary crontab on a manifest-hash change (line 126).
# Gating a DETACHED WORKTREE and merging only on green means the live tree -- and therefore both
# of those paths, and every supervised process that imports from it -- can only ever hold code
# that has already passed. It also deletes the revert entirely: there is no window in which the
# box sits on red code, so `git reset --hard` (which destroyed a session's only copy of its work
# on 2026-07-31, R0144) is no longer reachable from this script at all.
#
# WHAT THIS IS NOT. A worktree is NOT A SANDBOX. Gating still EXECUTES the fetched commit as the
# quant user, and an attacker who can push can trivially make a gate green by editing the gate.
# The only control that stops execution is verifying WHO signed the commit before running it, and
# this repo has no signing at all (`git log --format=%G?` is N for every commit) -- provisioning a
# key is a principal decision, rowed separately. What is closed here is narrower and real: the
# live tree, the hook, the crontab and the running daemons are no longer downstream of ungated
# code, and the ~10-minute unvetted-execution window (G8a) is gone.
GATE_DIR="$ROOT/../.pull_deploy_gate"

# A crashed run leaves a worktree registered; prune before adding so a single bad tick cannot
# wedge every tick after it (the deadlock class the refuse-on-dirty check was already bitten by).
git worktree remove --force "$GATE_DIR" >/dev/null 2>&1 || true
rm -rf "$GATE_DIR"
git worktree prune >/dev/null 2>&1 || true

if ! git worktree add --detach "$GATE_DIR" "$NEW" >/dev/null 2>&1; then
    say "could not create the gate worktree -- box left at $OLD_SHORT, nothing merged"
    record gate-setup-failed "$OLD_SHORT" "$NEW_SHORT" "git worktree add failed"; exit 2
fi
CLEAN_GATE="$GATE_DIR"

# A BARE WORKTREE MAKES LIVE-STATE TESTS PASS FOR THE WRONG REASON, which in this position is a
# FALSE GREEN in the gate that decides whether untrusted code reaches the box -- the worst possible
# direction. Measured 2026-08-05 (desk lesson L0068): a bare worktree PASSED the enforcement tests
# purely because data/moat was absent, while the same worktree with data/ linked in FAILED
# identically to the real tree. So the box's real untracked state is linked in, per ENTRY and never
# as a whole directory: data/ carries 18 TRACKED files that must come from the COMMIT BEING GATED,
# and `ln -s` of the parent would both shadow those and (onto an existing dir) silently create
# data/data.
link_missing() {   # link_missing <relative-path>
    if [ -e "$ROOT/$1" ] && [ ! -e "$GATE_DIR/$1" ]; then
        ln -s "$ROOT/$1" "$GATE_DIR/$1"
    fi
}
link_missing .venv          # run_ci resolves its interpreter relative to its own tree
link_missing lake
link_missing reports

# The CI lock must be SHARED with the live tree, not re-created inside the gate. Two concurrent
# pytest runs is not a style question on a 3.8GB swapless box: it is the measured cause of the
# OOM kills behind ci-gate-red (513ba24). Touching it first guarantees there is a file to link.
[ -e "$ROOT/data/.ci_run.lock" ] || : > "$ROOT/data/.ci_run.lock"
mkdir -p "$GATE_DIR/data"
for entry in "$ROOT"/data/* "$ROOT"/data/.[!.]*; do
    [ -e "$entry" ] || continue
    link_missing "data/$(basename "$entry")"
done

say "gating $NEW_SHORT in a detached worktree -- the live tree is still at $OLD_SHORT"

# --fail-on-lock: a lock-skip exits 0 for organs, but "someone else is mid-gate" is NOT "green"
# for a deploy decision -- without the flag this branch shipped unvetted commits (R0145, was R0136).
GATE_PY="$GATE_DIR/.venv/bin/python"
[ -x "$GATE_PY" ] || GATE_PY="$PY"
if ! "$GATE_PY" "$GATE_DIR/scripts/run_ci.py" --fail-on-lock; then
    say "CI GATE NOT GREEN on $NEW_SHORT -- nothing merged, box still at $OLD_SHORT"
    say "no revert was needed: the live tree never moved."
    record ci-red "$OLD_SHORT" "$NEW_SHORT" "gate red in worktree -- live tree untouched at $OLD_SHORT"
    exit 1
fi
say "CI gate green on $NEW_SHORT -- merging into the live tree"

# ONLY NOW does the live tree move. --ff-only is what makes this safe against a session that
# committed during the gate window: HEAD is then no longer an ancestor of NEW, the merge refuses,
# and the next tick re-gates whatever the tree by then holds. Nothing is ever discarded.
if ! git merge --ff-only "$NEW" >/dev/null 2>&1; then
    say "REFUSING MERGE -- the tree moved during the CI window (HEAD $(git rev-parse --short HEAD),"
    say "expected $OLD_SHORT). A session is working here; the next tick re-gates."
    record refused-merge-tree-moved "$OLD_SHORT" "$NEW_SHORT" "gate green but tree changed mid-gate; nothing merged, nothing restarted"
    exit 1
fi
say "fast-forwarded to $NEW_SHORT"

# ---------------------------------------------------------------- restart only what changed
# OUTCOMES, NOT INTENTIONS. The loop runs in a subshell (it is on the right of a pipe), so a
# counter incremented inside it is lost on exit -- the first cut of this script counted DIRECTIVES
# with grep instead and reported "1 restart(s)" on a box where the restart had actually been
# refused for permissions. An evidence line that overstates what happened is the same lie this
# whole path exists to end, so outcomes are journalled to a file and counted from that.
OUTCOMES=$(mktemp) || exit 2

# ---------------------------------------------------------------- L1.38: hold the money path
# THE MERGE IS NEVER HELD, ONLY THE RESTART. Code lands on disk as always; a money-path process
# keeps running its old copy until the cockpit opens. This is the same gate
# scripts/run_stale_daemon_repair.py already applies, and its absence here was reachable only once
# the dirty-tree refusal above stopped being a no-op -- repairing the deploy path without it would
# have ARMED an unattended executor restart inside a live RAIL_BREACH window.
if HELD_UNITS=$("$PY" "$ROOT/scripts/check_change_window.py" --held-units 2>/dev/null); then
    [ -z "$HELD_UNITS" ] || say "L1.38: money-path restarts held this tick ($(printf '%s' "$HELD_UNITS" | tr '\n' ' '))"
else
    # Fail toward STERILE. A window we cannot read is not an open one, and the cost asymmetry is
    # the same one build_report() itself is written around: a wrong OPEN is unbounded.
    HELD_UNITS=$(printf '%s\n' "$PLAN" | awk -F'\t' '$1=="RESTART"{print $2}')
    say "change-window fence unreadable -- holding EVERY restart this tick (L1.38 fails closed)"
fi

if [ -n "$PLAN" ]; then
    printf '%s\n' "$PLAN" | while IFS='	' read -r verb target why; do
        [ -n "${verb:-}" ] || continue
        case "$verb" in
        RESTART)
            if printf '%s\n' "$HELD_UNITS" | grep -Fxq -- "$target"; then
                say "HELD (L1.38): $target is on the money path and the window is not OPEN"
                say "  the commit IS merged; this process keeps its old code until the window opens"
                echo held >> "$OUTCOMES"
            elif ! command -v systemctl >/dev/null 2>&1; then
                say "OWED (no systemctl): sudo systemctl restart $target   [$why]"
                echo owed >> "$OUTCOMES"
            elif systemctl restart "$target" >/dev/null 2>&1; then
                say "restarted $target   [$why]"
                echo restarted >> "$OUTCOMES"
            elif $PY "$ROOT/scripts/ship_restart.py" "$target" >/dev/null 2>&1; then
                # This box denies systemctl to the quant user (scripts/watchdog.py:78). Printing
                # the command used to be the whole deliverable, and the claimed backstop -- "the
                # watchdog's 3-min heartbeat respawn" -- DOES NOT COVER THIS CASE: watchdog's
                # _systemd_owns() deliberately refuses to spawn while systemd has a live MainPID,
                # so it rescues a DEAD process and never an alive-but-STALE one. That is the
                # entire failure mode here, and it left a money-path fix inert for 11.8h on
                # 2026-08-05 ($4,805.61 misreported to hurdle_rate.py:97).
                # ship_restart performs the restart deploy_plan ALREADY authorises for this tier,
                # via SIGTERM + Restart=always, and refuses when the unit would not come back.
                say "restarted $target via ship_restart (systemctl denied)   [$why]"
                say "  RESTARTED is not FIXED -- confirm the new behaviour in the producer's own"
                say "  output, against a key only the new code can write."
                echo restarted >> "$OUTCOMES"
            else
                say "OWED (permission denied, ship_restart refused): sudo systemctl restart $target   [$why]"
                say "  reason:  $PY scripts/ship_restart.py $target"
                echo owed >> "$OUTCOMES"
            fi
            ;;
        ESCALATE)
            say "*** RUIN RAIL INVALIDATED: $target   [$why]"
            say "*** NOT restarted here. Operator must supervise:"
            say "***   sudo systemctl restart $target   (then confirm exactly ONE instance)"
            echo escalated >> "$OUTCOMES"
            ;;
        SCHEDULER)
            say "SCHEDULER SOURCE CHANGED: $target   [$why]"
            say "  review drift:  $PY scripts/check_scheduler_manifest.py --report-only"
            say "  then, only if the drift is understood:  sh deploy/reconstitute_cron.sh"
            echo scheduler >> "$OUTCOMES"
            ;;
        esac
    done
fi

n_of() { grep -c "^$1\$" "$OUTCOMES" 2>/dev/null || true; }
RESTARTED=$(n_of restarted); OWED=$(n_of owed)
ESCALATED=$(n_of escalated); SCHED=$(n_of scheduler); HELD=$(n_of held)

# OWED and ESCALATED both mean "a process is still running stale code, pending a human". Say so in
# the status field itself, so a box parked in that state cannot read as a clean deploy.
# HELD counts too, and for the same reason: an L1.38 hold is a DELIBERATE stale process, but it is
# still a stale process, and a status that reads `deployed` would tell every downstream reader the
# new code is live in it. Deliberate and invisible is how a temporary hold becomes a permanent one.
STATUS=deployed
[ "$OWED" -eq 0 ] && [ "$ESCALATED" -eq 0 ] && [ "$HELD" -eq 0 ] || STATUS=deployed-action-owed
record "$STATUS" "$OLD_SHORT" "$NEW_SHORT" \
    "$N_CHANGED paths; $RESTARTED restarted, $OWED owed, $HELD held(L1.38), $ESCALATED escalated, $SCHED sched"
say "done -- $OLD_SHORT -> $NEW_SHORT, CI green; $RESTARTED restarted, $OWED owed, $HELD held, $ESCALATED escalated"
[ "$STATUS" = deployed ] || say "ACTION OWED -- a supervised process is still running stale code"
