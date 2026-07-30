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
#   * CI RED -> pull is REVERTED to the exact prior commit, then exit non-zero. Leaving the box on
#     code that fails its own gate is strictly worse than leaving it on the old code, and a
#     half-applied deploy is the state nobody can reason about at 3am.
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
if [ -n "$(git status --porcelain --untracked-files=no 2>/dev/null)" ]; then
    say "REFUSING -- tracked files are modified. Uncommitted work here is an operator hotfix"
    say "mid-flight; a fast-forward that overwrites it destroys the only copy. Commit or stash it."
    git status --short --untracked-files=no | head -20
    record refused-dirty "$(git rev-parse --short HEAD)" "-" "modified tracked files"
    exit 2
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

PLAN=$(printf '%s\n' "$CHANGED" | "$PY" -m libs.ops.deploy_plan --directives || true)
printf '%s\n' "$CHANGED" | "$PY" -m libs.ops.deploy_plan || true

if [ "$DRY" -eq 1 ]; then
    say "--dry-run: nothing applied (still at $OLD_SHORT)"
    exit 0
fi

# ---------------------------------------------------------------- apply, then gate, then revert
git merge --ff-only FETCH_HEAD >/dev/null 2>&1 || {
    say "fast-forward failed unexpectedly -- box left at $OLD_SHORT"
    record ff-failed "$OLD_SHORT" "$NEW_SHORT" "git merge --ff-only failed"; exit 2; }
say "fast-forwarded to $NEW_SHORT -- running the CI gate before restarting anything"

if ! "$PY" "$ROOT/scripts/run_ci.py"; then
    say "CI GATE RED on $NEW_SHORT -- REVERTING to $OLD_SHORT"
    git reset --hard "$OLD" >/dev/null 2>&1 || say "WARNING: revert failed -- box is on RED code"
    say "nothing was restarted; the desk keeps running the code that passed its gate."
    record ci-red "$OLD_SHORT" "$NEW_SHORT" "reverted -- run_ci.py failed on the new commit"
    exit 1
fi
say "CI gate green"

# ---------------------------------------------------------------- restart only what changed
# OUTCOMES, NOT INTENTIONS. The loop runs in a subshell (it is on the right of a pipe), so a
# counter incremented inside it is lost on exit -- the first cut of this script counted DIRECTIVES
# with grep instead and reported "1 restart(s)" on a box where the restart had actually been
# refused for permissions. An evidence line that overstates what happened is the same lie this
# whole path exists to end, so outcomes are journalled to a file and counted from that.
OUTCOMES=$(mktemp) || exit 2
trap 'rm -f "$OUTCOMES"' EXIT INT TERM

if [ -n "$PLAN" ]; then
    printf '%s\n' "$PLAN" | while IFS='	' read -r verb target why; do
        [ -n "${verb:-}" ] || continue
        case "$verb" in
        RESTART)
            if ! command -v systemctl >/dev/null 2>&1; then
                say "OWED (no systemctl): sudo systemctl restart $target   [$why]"
                echo owed >> "$OUTCOMES"
            elif systemctl restart "$target" >/dev/null 2>&1; then
                say "restarted $target   [$why]"
                echo restarted >> "$OUTCOMES"
            else
                # This box denies systemctl to the quant user (scripts/watchdog.py:78), so
                # printing the exact command IS the deliverable -- and the watchdog's 3-min
                # heartbeat respawn is the backstop until the operator runs it.
                say "OWED (permission denied): sudo systemctl restart $target   [$why]"
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
ESCALATED=$(n_of escalated); SCHED=$(n_of scheduler)

# OWED and ESCALATED both mean "a process is still running stale code, pending a human". Say so in
# the status field itself, so a box parked in that state cannot read as a clean deploy.
STATUS=deployed
[ "$OWED" -eq 0 ] && [ "$ESCALATED" -eq 0 ] || STATUS=deployed-action-owed
record "$STATUS" "$OLD_SHORT" "$NEW_SHORT" \
    "$N_CHANGED paths; $RESTARTED restarted, $OWED owed, $ESCALATED escalated, $SCHED sched"
say "done -- $OLD_SHORT -> $NEW_SHORT, CI green; $RESTARTED restarted, $OWED owed, $ESCALATED escalated"
[ "$STATUS" = deployed ] || say "ACTION OWED -- a supervised process is still running stale code"
