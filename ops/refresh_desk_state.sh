#!/usr/bin/env bash
# Pull whatever the trading box published, and rebuild the page from it. Every few minutes.
#
# THE LINK THAT WAS NEVER BUILT. The box publishes its state to git -- `sync_shadow_to_git.ps1`
# every 15 minutes as MT5-ShadowSync, and the hourly cycle as a second path. Both were working on
# 2026-09-06: "mt5 desk hourly sync 2026-09-06_1918" and "..._2010" landed on desk-sync-clean that
# evening. The VPS serves the page from `web/desk_state.json`, which `build_zentech_state.py`
# builds from the artifacts in ITS checkout. Nothing pulled the branch and nothing rebuilt the
# file, so the page kept serving a build from 17:12 and reported the box SILENT for 266 hours
# while the box's state sat in GitHub, delivered, ten minutes old.
#
# Every piece worked and the chain had no last link. That is the shape of this whole outage: the
# scp path it replaced was dead, and its replacement was only ever half-installed.
#
# NEVER RESETS, NEVER STASHES. The VPS authors artifacts of its own -- it runs gauntlet sweeps and
# forward reconciliation -- so a hard reset here would silently discard work this host produced.
# A conflict aborts the merge and says so; the page then serves the last good copy, and its own
# age field tells the truth about how old that is.
set -uo pipefail

ROOT="${QUANT_ROOT:-$HOME/quant-platform}"
# THE BRANCH THE BOX ACTUALLY PUBLISHES TO. Its log says so on every tick: "pulling
# origin/claude/llm-auto-upgrade-verify-gcjac3". The first version of this script pulled
# desk-sync-clean -- where the miners' "mt5 desk hourly sync" commits land -- so it would have
# fetched faithfully every three minutes and never once seen the box's state. Two hourly jobs
# push to two different branches and only one of them carries the dashboard's inputs; picking the
# wrong one produces a refresher that works perfectly and delivers nothing.
BRANCH="${BOX_SYNC_BRANCH:-claude/llm-auto-upgrade-verify-gcjac3}"
cd "$ROOT" 2>/dev/null || { echo "no checkout at $ROOT"; exit 2; }

git config core.editor true          # an editor opening in a timer job blocks until the timeout
git config pull.rebase false         # merge: this host has its own commits and rebasing rewrites them

# THE MERGE PUBLISHES ITS OWN STATUS (2026-09-08). "Abort so the next tick tries again" was the
# whole failure mode: the same three conflicts aborted this merge every three minutes from
# 2026-09-06 17:08 to 2026-09-08 21:00 -- roughly 960 times -- and nothing but a log line on this
# host recorded it. Both machines kept committing, each believing it was deploying the other's
# work; 57 VPS commits never reached the box's compiler and 147 desk commits never ran here.
# So every tick now writes web/refresh_status.json -- behind count, the conflicting paths captured
# BEFORE the abort erases them, the consecutive-conflict streak, the last time this host was
# actually in step -- where the dashboard and any session can read it (L0292).
STATUS="web/refresh_status.json"
changed=0
fetch_ok=0
behind=0
conflict=0
conflict_paths=""
merge_tail=""
head_before="$(git rev-parse --short HEAD 2>/dev/null || echo '?')"
fetch_head=""
if git fetch --quiet origin "$BRANCH" 2>/dev/null; then
  fetch_ok=1
  fetch_head="$(git rev-parse --short FETCH_HEAD 2>/dev/null || echo '?')"
  behind="$(git rev-list --count "HEAD..FETCH_HEAD" 2>/dev/null || echo 0)"
  if [ "${behind:-0}" -gt 0 ]; then
    if out="$(git merge --no-edit FETCH_HEAD 2>&1)"; then
      echo "merged $behind commit(s) from origin/$BRANCH"
      changed=1
    else
      # A conflict is a human's problem, not a timer's. Abort so the tree stays usable and the
      # next tick tries again -- a half-merged checkout would break every later rebuild. But
      # name the paths first: after the abort nothing on disk says what collided.
      conflict=1
      conflict_paths="$(git diff --name-only --diff-filter=U 2>/dev/null | head -20 | tr '\n' ' ')"
      merge_tail="$(printf '%s\n' "$out" | tail -3 | tr '\n' ' ')"
      git merge --abort 2>/dev/null
      echo "MERGE CONFLICT against origin/$BRANCH -- aborted, serving the last good state"
      echo "  conflicting: ${conflict_paths:-(unknown)}"
      printf '%s\n' "$out" | tail -3
    fi
  fi
else
  echo "fetch failed -- rebuilding from what is already here"
fi
REFRESH_BRANCH="$BRANCH" REFRESH_FETCH_OK="$fetch_ok" REFRESH_BEHIND="${behind:-0}" \
REFRESH_MERGED="$changed" REFRESH_CONFLICT="$conflict" REFRESH_CONFLICT_PATHS="$conflict_paths" \
REFRESH_MERGE_TAIL="$merge_tail" REFRESH_HEAD_BEFORE="$head_before" REFRESH_FETCH_HEAD="$fetch_head" \
REFRESH_HEAD_AFTER="$(git rev-parse --short HEAD 2>/dev/null || echo '?')" REFRESH_STATUS="$STATUS" \
python3 - <<'PY' 2>/dev/null || echo "refresh status NOT written (python3 failed)"
import json, os, pathlib
from datetime import UTC, datetime
p = pathlib.Path(os.environ["REFRESH_STATUS"])
try:
    prev = json.loads(p.read_text("utf-8"))
except Exception:
    prev = {}
now = datetime.now(UTC).isoformat(timespec="seconds")
e = os.environ
fetch_ok, behind = e["REFRESH_FETCH_OK"] == "1", int(e["REFRESH_BEHIND"] or 0)
merged, conflict = e["REFRESH_MERGED"] == "1", e["REFRESH_CONFLICT"] == "1"
in_step = fetch_ok and (merged or behind == 0)
doc = {
    "at": now, "branch": e["REFRESH_BRANCH"], "fetch_ok": fetch_ok, "behind_before": behind,
    "merged": merged, "conflict": conflict,
    "conflict_paths": [x for x in e["REFRESH_CONFLICT_PATHS"].split() if x],
    "merge_tail": e["REFRESH_MERGE_TAIL"][:400],
    "head_before": e["REFRESH_HEAD_BEFORE"], "head_after": e["REFRESH_HEAD_AFTER"],
    "fetch_head": e["REFRESH_FETCH_HEAD"],
    "last_in_step_at": now if in_step else prev.get("last_in_step_at"),
    "consecutive_conflicts": (int(prev.get("consecutive_conflicts") or 0) + 1) if conflict else 0,
    "first_conflict_at": ((prev.get("first_conflict_at") or now) if conflict else None),
    "note": ("in step with origin" if in_step else
             "DIVERGED: this host is not running the desk branch; merge by hand and push the "
             "same commit to desk-sync-clean and the desk branch" if conflict else
             "fetch failed; serving what is here"),
}
p.parent.mkdir(parents=True, exist_ok=True)
tmp = p.with_suffix(".json.tmp")
tmp.write_text(json.dumps(doc, indent=1), "utf-8")
tmp.replace(p)
PY

# REBUILD EVERY TICK, EVEN WITH NOTHING NEW. The page's freshness gauges are computed at build
# time, so a desk that stops publishing must show an age that GROWS. Rebuilding only on change
# would freeze the age at the moment of the last update and make a dead box look merely quiet --
# which is the exact confusion this desk keeps paying for.
if python3 scripts/build_zentech_state.py >/dev/null 2>&1; then
  age="$(python3 - <<'PY' 2>/dev/null
import json, pathlib
try:
    d = json.loads(pathlib.Path("web/desk_state.json").read_text("utf-8"))
    h = (d.get("health") or {}).get("box") or {}
    print(f"{d.get('generated_at')} box={h.get('status')}")
except Exception as exc:
    print(f"unreadable ({exc})")
PY
)"
  # `${changed:+...}` expands for "0" as well as "1" -- it tests for a non-EMPTY value, not a
  # true one -- so this claimed every rebuild followed a merge, including the ones that merged
  # nothing. A log line that says the same thing whatever happened carries no information.
  [ "$changed" = 1 ] && suffix=" (after a merge)" || suffix=""
  echo "rebuilt: ${age}${suffix}"
  exit 0
fi
echo "build_zentech_state.py FAILED -- the page keeps its previous copy"
exit 1
