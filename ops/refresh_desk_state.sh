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
BRANCH="${BOX_SYNC_BRANCH:-desk-sync-clean}"
cd "$ROOT" 2>/dev/null || { echo "no checkout at $ROOT"; exit 2; }

git config core.editor true          # an editor opening in a timer job blocks until the timeout
git config pull.rebase false         # merge: this host has its own commits and rebasing rewrites them

changed=0
if git fetch --quiet origin "$BRANCH" 2>/dev/null; then
  behind="$(git rev-list --count "HEAD..FETCH_HEAD" 2>/dev/null || echo 0)"
  if [ "${behind:-0}" -gt 0 ]; then
    if out="$(git merge --no-edit FETCH_HEAD 2>&1)"; then
      echo "merged $behind commit(s) from origin/$BRANCH"
      changed=1
    else
      # A conflict is a human's problem, not a timer's. Abort so the tree stays usable and the
      # next tick tries again -- a half-merged checkout would break every later rebuild.
      git merge --abort 2>/dev/null
      echo "MERGE CONFLICT against origin/$BRANCH -- aborted, serving the last good state"
      printf '%s\n' "$out" | tail -3
    fi
  fi
else
  echo "fetch failed -- rebuilding from what is already here"
fi

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
