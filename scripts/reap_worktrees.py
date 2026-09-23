#!/usr/bin/env python3
"""Reap agent worktrees whose work has already LANDED in the live branch.

DRY-RUN BY DEFAULT. Pass --apply to remove. See libs/ops/worktree_reaper.py for why each safety
condition is load-bearing and for the 2026-08-20 measurement that produced this (18GB across 43
checkouts, 47% of the disk, disk-pausing the tape recorders while the desk was being asked to BUY
storage).

    reap_worktrees.py                    # report only
    reap_worktrees.py --apply            # remove the REAP set
    reap_worktrees.py --min-idle-h 24    # be more conservative
"""
from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from libs.ops.lawful import guard
from libs.ops.worktree_reaper import classify, reap_plan

MAIN = Path(__file__).resolve().parent.parent
GLOB = "qp-*"


def discover(main: Path, parent: str) -> set[Path]:
    """Every worktree git itself knows about, UNION the legacy `qp-*` glob.

    SCOPE IS DISCOVERED, NOT DECLARED -- the same repair run_stale_daemon_repair already made
    after its actuator was found iterating a four-entry roster while its detector read the process
    table. Here the roster was `parent/qp-*`, which is a claim about WHERE worktrees live, and it
    was wrong for seven of them: five under <repo>/.claude/worktrees/ (idle 190-196h), plus
    .codex-conversion-test and quant-platform-probe (321h). 1.16 GB that cron could never reap at
    ANY --min-idle-h, forever, and invisible in a report that said "examined 28 worktree(s)" --
    a count of what the glob matched, never of what exists (L1.57).

    `git worktree list` is the authoritative answer because git maintains it as trees are added
    and removed, so a future tree in a new location is covered on the day it is created rather
    than the day someone remembers to widen a pattern. The glob is kept in the union so a
    directory git has forgotten (a pruned entry whose files remain) is still seen.

    THIS WIDENS SCOPE ONLY. Every reaped tree still has to be LANDED, CLEAN and idle past the
    threshold -- `classify`/`reap_plan` are untouched, so nothing here can reap a tree that
    carries unmerged commits or uncommitted work.
    """
    found: set[Path] = set(Path(parent).glob(GLOB))
    r = subprocess.run(["git", "-C", str(main), "worktree", "list", "--porcelain"],
                       capture_output=True, text=True, check=False)
    if r.returncode != 0:
        # Never silently narrow: a failed enumeration falls back to the glob and SAYS SO, because
        # "git could not tell us" and "there are no other worktrees" are different claims (L1.60).
        print(f"reap: `git worktree list` failed ({r.stderr.strip()[:80]}) -- falling back to the "
              f"{GLOB} glob alone; scope is a LOWER BOUND this run")
        return found
    found.update(Path(ln[9:].strip()) for ln in r.stdout.splitlines()
                 if ln.startswith("worktree "))
    return found - {primary(main)}


def primary(main: Path) -> Path:
    """The MAIN checkout, which is never a reap candidate however it is reached.

    `MAIN` in this file is `__file__`'s repo, so running this script FROM a worktree makes the
    real primary checkout look like just another entry in `git worktree list`. Measured the day
    this was written: a dry run from a worktree listed `quant-platform` (9.6 GB, the live tree 46
    processes are cwd'd into) as an examined candidate. It survived only because the main tree is
    always dirty -- luck standing in for a guard, on the one directory whose loss is unrecoverable.

    `--git-common-dir` is the primary's `.git` regardless of which worktree asks, so its parent is
    the primary checkout. On failure this returns `main` unchanged: the caller's own
    `p.resolve() == MAIN.resolve()` check still holds, so the fallback is the previous behaviour,
    never a wider one.
    """
    r = subprocess.run(["git", "-C", str(main), "rev-parse", "--path-format=absolute",
                        "--git-common-dir"], capture_output=True, text=True, check=False)
    if r.returncode != 0 or not r.stdout.strip():
        return main
    return Path(r.stdout.strip()).parent.resolve()


def main() -> int:
    guard()
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true", help="actually remove (default: report only)")
    ap.add_argument("--min-idle-h", type=float, default=8.0)
    ap.add_argument("--parent", default=str(MAIN.parent), help="where worktrees live")
    a = ap.parse_args()

    live_head = subprocess.run(["git", "-C", str(MAIN), "rev-parse", "HEAD"],
                               capture_output=True, text=True, check=True).stdout.strip()
    now = time.time()
    trees = []
    for p in sorted(discover(MAIN, a.parent)):
        if p.resolve() == MAIN.resolve() or not p.is_dir():
            continue
        w = classify(p, live_head, MAIN, now, a.min_idle_h)
        if w is not None:
            trees.append(w)

    reapable, hist = reap_plan(trees)
    for w in trees:
        idle = "unmeasured" if w.idle_h is None else f"{w.idle_h:.0f}h"
        print(f"  {w.path.name:<34} {w.verdict:<16} idle={idle:<11} {w.size_mb:>5}MB")
    freed = sum(w.size_mb for w in reapable)
    print(f"\nexamined {len(trees)} worktree(s): "
          + ", ".join(f"{k}={v}" for k, v in sorted(hist.items())))
    usage = shutil.disk_usage(MAIN)
    print(f"disk {usage.used / usage.total:.1%} used, {usage.free / 1e9:.1f}GB free; "
          f"reapable {len(reapable)} worktree(s) / ~{freed}MB")

    if not a.apply:
        print("\nDRY RUN -- pass --apply to remove. Branches are never deleted, only checkouts.")
        return 0
    for w in reapable:
        r = subprocess.run(["git", "-C", str(MAIN), "worktree", "remove", "--force", str(w.path)],
                           capture_output=True, text=True, check=False)
        print(f"  {'removed' if r.returncode == 0 else 'REFUSED'} {w.path.name}"
              + ("" if r.returncode == 0 else f" -- {r.stderr.strip()[:80]}"))
    subprocess.run(["git", "-C", str(MAIN), "worktree", "prune"], check=False)
    usage = shutil.disk_usage(MAIN)
    print(f"disk now {usage.used / usage.total:.1%} used, {usage.free / 1e9:.1f}GB free")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
