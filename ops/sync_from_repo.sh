#!/usr/bin/env bash
# PULL THE BRANCH AND RUN THE GATES, UNATTENDED. So a fix stops being a paste block.
#
# WHY THIS EXISTS. Every change an agent pushes has needed the principal to open a terminal, fetch,
# merge, resolve, run the gates and re-run whichever organ the change affected. That is a human
# doing a deterministic job, several times a day, and the cost is not the typing -- it is that
# work sits on the remote unapplied for hours while the box runs the old code and the clocks that
# depend on the fix keep accruing nothing.
#
# WHAT MAKES IT SAFE TO AUTOMATE, and these are the conditions, not decorations:
#
#   FAST-FORWARD ONLY. It never creates a merge commit and never resolves a conflict. A branch
#   that has diverged is a real decision (three agents write this tree) and it stops here with
#   the divergence named. Automating a conflict resolution is how a sibling's work disappears.
#
#   A DIRTY TREE IS A FULL STOP. R0423: several sessions share this worktree, and a checkout over
#   another agent's uncommitted work destroys it with no record. Uncommitted changes mean somebody
#   is mid-task, and the correct action is to wait, not to tidy.
#
#   IT NEVER PUSHES, NEVER COMMITS, NEVER STASHES. `git stash` restores to the index and a sibling
#   can check the tree out from under it -- three recorded instances of exactly that.
#
#   GATES RUN AFTER, AND RED IS REPORTED, NOT REPAIRED. A gate failure on freshly pulled code is
#   information the principal needs; an organ that tried to fix it would be editing code it did
#   not write, unattended, on the box that trades.
#
#   IT RUNS NO RESEARCH. The research cycle has its own schedule and its own budget. This does one
#   job: make the box's code equal the branch's code, or say precisely why it could not.
#
#     bash ops/sync_from_repo.sh            # once by hand, or from cron
set -uo pipefail
cd /home/quant/quant-platform || exit 1

BRANCH="${QUANT_BRANCH:-claude/llm-auto-upgrade-verify-gcjac3}"
LOG="data/cro_ai_logs/sync_$(date -u +%Y%m%d).log"
mkdir -p data/cro_ai_logs

{
  echo "=== sync $(date -u) branch=$BRANCH ==="

  # A DIRTY TREE MEANS A SIBLING IS MID-TASK. Untracked files are ignored deliberately: agents
  # scribble scratch constantly and none of it blocks a fast-forward. Modified TRACKED files do.
  if ! git diff --quiet || ! git diff --cached --quiet; then
      echo "STOP: tracked files are modified -- a session is mid-task and a checkout would"
      echo "      destroy uncommitted work (R0423). Nothing fetched, nothing changed."
      git status --short | head -20
      exit 0
  fi

  git fetch origin "$BRANCH" || { echo "FETCH FAILED -- network. Nothing changed."; exit 0; }

  LOCAL=$(git rev-parse HEAD)
  REMOTE=$(git rev-parse FETCH_HEAD)
  if [ "$LOCAL" = "$REMOTE" ]; then
      echo "already current at ${LOCAL:0:8} -- nothing to do"
      exit 0
  fi

  # FAST-FORWARD OR NOTHING. If the box carries commits the remote does not, that is a real
  # divergence between agents and it is named here rather than merged by a script at 3am.
  if ! git merge --ff-only FETCH_HEAD; then
      echo "STOP: branch has DIVERGED -- this box holds commits the remote does not."
      echo "      A merge here would be a judgement about whose work wins. Resolve by hand:"
      echo "        git log --oneline HEAD ^FETCH_HEAD    # what is only here"
      git log --oneline HEAD ^FETCH_HEAD 2>/dev/null | head -10
      exit 0
  fi
  echo "fast-forwarded ${LOCAL:0:8} -> $(git rev-parse --short HEAD)"
  git log --oneline "$LOCAL"..HEAD | head -20

  # GATES AFTER, ALWAYS. Pulled code that cannot pass its own gates is the single most useful
  # thing to learn early, and the box has just started running it.
  if bash ops/gates.sh; then
      echo "gates: GREEN on the new head"
  else
      echo "gates: RED on the new head -- the box is running this code NOW. Reported, not repaired."
  fi
  echo "=== sync exit $(date -u) ==="
} 2>&1 | tee -a "$LOG"
