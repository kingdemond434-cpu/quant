"""AGENT WORKTREES ARE THE DESK'S LARGEST UNOWNED DISK CONSUMER, and nothing reaped them.

MEASURED 2026-08-20. Root was 97% full, 1.4GB free on 38GB. `data/moat` -- the tape the desk calls
irreplaceable -- was 1.4GB. The agent worktrees were **18GB across 43 checkouts**, 47% of the disk,
each ~500MB, created at a rate of roughly ten a day by the standing order that every worker take
its own tree (R0423, and that order is correct: eight recorded index collisions justify it).

WHAT IT COST, AND IT WAS NOT THE DISK. Above `_DISK_MAX_FRAC = 0.80` all three tape recorders
pause themselves and keep a fresh heartbeat, so two fences fired -- `recorder-scope-shrank` and
`tape-recording-stopped` -- and BOTH named the recorder. Meanwhile `tape-disk-deadline` was live
and acked, saying "Buy storage; every hour past the pause is permanently unbuyable". THE DESK WAS
BEING ASKED TO PURCHASE DISK WHILE HALF ITS DISK WAS DEAD SESSIONS. Reclaiming 19 of them freed
7.7GB (97% -> 75%) and the recorders resumed writing within three minutes.

THE ORDER CREATES THE TREES AND NOTHING RETIRES THEM -- the whole lifecycle was half-specified, so
this recurs on its own within days at ~5GB/day of new checkouts. That is the defect: not any one
worktree, but the missing second half of a rule the desk enforces vigorously in its first half.

WHAT MAKES A WORKTREE SAFE TO REAP, and every condition is load-bearing:

  LANDED   its tip is an ANCESTOR of the live branch, so every commit it holds is already in the
           branch. This is the condition that makes the whole operation lossless -- not "old",
           not "looks finished". A worktree that is merely idle may hold the only copy of work.
  CLEAN    no uncommitted or untracked changes, so nothing unrecorded dies with it. The `.venv`
           symlink every worker creates is expected and does not count as dirty.
  IDLE     no file written for `min_idle_h`. A live session's Bash cwd resets to the main repo
           between calls, so "no process has a cwd in here" is NOT evidence of deadness -- that
           check passed for all 43 trees while several sessions were demonstrably live.

THE BRANCH IS NEVER DELETED, only the checkout. A branch is a few bytes and the whole point of the
reap is that its commits are already in the live branch anyway; deleting refs would convert a
disk-space operation into a history operation, which is a different risk class entirely.

AND THE INSTRUMENT THAT NEARLY DECIDED THIS WRONG. The first idle measurement used
`find -newermt "-14 days"`; the `find` on this box is `bfs`, which rejects that timestamp, printed
its error to stderr and **exited 0**. The pipeline read empty, every worktree scored an identical
"idle 56 years", and acting on it would have reaped live sessions. It was caught only because a
value identical for every entity is a broken instrument, never a measurement -- the same tell as
`/proc/<pid>` mtime being identical for every pid. A failed measurement here returns None and the
tree is KEPT (L1.28a): absence must never resolve to the permissive answer.
"""
from __future__ import annotations

import subprocess
from dataclasses import dataclass
from pathlib import Path

__all__ = ["Worktree", "classify", "reap_plan"]

#: Untracked paths every worker is told to create; their presence is not uncommitted work.
_EXPECTED_UNTRACKED = frozenset({".venv"})


@dataclass(frozen=True)
class Worktree:
    path: Path
    tip: str
    landed: bool
    dirty: int
    idle_h: float | None      # None == could not measure; NEVER treated as "very idle"
    size_mb: int

    @property
    def verdict(self) -> str:
        """REAP | KEEP-AHEAD | KEEP-DIRTY | KEEP-ACTIVE | KEEP-UNMEASURED."""
        if not self.landed:
            return "KEEP-AHEAD"
        if self.dirty:
            return "KEEP-DIRTY"
        if self.idle_h is None:
            return "KEEP-UNMEASURED"
        return "REAP" if self.idle_h >= self._min_idle_h else "KEEP-ACTIVE"

    _min_idle_h: float = 8.0


def _run(args: list[str], cwd: Path | None = None) -> str:
    return subprocess.run(args, cwd=cwd, capture_output=True, text=True,
                          check=False).stdout.strip()


def _newest_mtime(root: Path) -> float | None:
    """Newest mtime of any non-.git file, or None if it could not be measured.

    Walked in python rather than shelled out to `find`: the box's `find` is bfs, whose flag
    dialect differs and which exits 0 on a rejected argument (see the module docstring).
    """
    newest: float | None = None
    seen = False
    for p in root.rglob("*"):
        if ".git" in p.parts:
            continue
        # A SYMLINK'S MTIME IS THE TARGET'S, AND THE TARGET IS OFTEN THE LIVE REPO (2026-08-20).
        # `p.stat()` resolves the link, so a worktree holding a symlink into the main checkout
        # inherited that file's mtime and read as ACTIVE forever. Measured: qp-owed-b3-absorb
        # holds three symlinks to data/ files that cron rewrites hourly, so the reaper computed
        # idle 3.2h against a true local idle of 174.7h -- the age gate silently disabled, and
        # PERMANENTLY, not for one run. Skipped rather than lstat'd: creating a symlink is not
        # the local work this gate measures, and a tree of nothing but symlinks then returns
        # None -> KEEP-UNMEASURED, which never reaps (L1.28a).
        try:
            if p.is_symlink() or not p.is_file():
                continue
            m = p.stat().st_mtime
        except OSError:
            continue                      # skipped, and `seen` records that we did walk
        seen = True
        if newest is None or m > newest:
            newest = m
    return newest if seen else None


def classify(path: Path, live_head: str, main_repo: Path, now: float,
             min_idle_h: float = 8.0) -> Worktree | None:
    """Classify one worktree. Returns None if it is not a readable git worktree."""
    tip = _run(["git", "-C", str(path), "rev-parse", "HEAD"])
    if not tip:
        return None
    landed = subprocess.run(
        ["git", "-C", str(main_repo), "merge-base", "--is-ancestor", tip, live_head],
        capture_output=True, check=False).returncode == 0
    status = _run(["git", "-C", str(path), "status", "--porcelain"])
    dirty = sum(1 for line in status.splitlines()
                if line.strip() and line[3:].strip() not in _EXPECTED_UNTRACKED)
    newest = _newest_mtime(path)
    idle_h = None if newest is None else max(0.0, (now - newest) / 3600.0)
    size_mb = int(sum(p.stat().st_size for p in path.rglob("*") if p.is_file()) / 1e6) \
        if newest is not None else 0
    return Worktree(path=path, tip=tip, landed=landed, dirty=dirty, idle_h=idle_h,
                    size_mb=size_mb, _min_idle_h=min_idle_h)


def reap_plan(worktrees: list[Worktree]) -> tuple[list[Worktree], dict[str, int]]:
    """(reapable, verdict histogram). The histogram is published so a reap that frees nothing is
    distinguishable from a reap that examined nothing (L1.57)."""
    hist: dict[str, int] = {}
    for w in worktrees:
        hist[w.verdict] = hist.get(w.verdict, 0) + 1
    return [w for w in worktrees if w.verdict == "REAP"], hist
