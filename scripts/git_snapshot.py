"""Daily git snapshot of the code+docs surface -- forensic history the desk lacked.

2026-07-16 lesson: the 07-15 session's panel edits could not be diffed (no git, no backups) and
the 07-13 incident forensics relied on hand-made .bak files. One commit per day fixes both
forever. Secrets and generated state never enter the repo (.gitignore); this is history, not
deployment -- rollback_guard remains the revert mechanism for autonomous changes.

    python scripts/git_snapshot.py
"""

from __future__ import annotations

import subprocess
from datetime import UTC, datetime
from pathlib import Path


def _git(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(["git", *args], capture_output=True, text=True, check=False)


def _drop_accidental_gitlinks() -> list[str]:
    """Unstage mode-160000 entries in a repo that has no submodules.

    `git add -A` records any directory containing a `.git` entry as a GITLINK, and this desk
    creates git worktrees under .claude/worktrees/ routinely. A gitlink's recorded sha moves
    whenever that worktree commits, so the parent tree reads ` M <path>` permanently and cannot
    be cleaned -- committing it only re-points it. That dirt is what wedged the inbound deploy
    path for 8 days (0 deploys in 1078 ticks, measured 2026-08-12).

    .gitignore covers the path this actually happened on. This covers the CLASS: a worktree or a
    stray clone made anywhere else. If real submodules are ever adopted, .gitmodules exists and
    this stands down rather than fighting them.
    """
    if Path(".gitmodules").exists():
        return []
    staged = _git("ls-files", "-s")
    links = [ln.split("\t", 1)[1] for ln in staged.stdout.splitlines()
             if ln.startswith("160000 ") and "\t" in ln]
    if links:
        _git("rm", "--cached", "-r", "--quiet", "--", *links)
    return links


def main() -> None:
    if _git("rev-parse", "--git-dir").returncode != 0:
        print("git-snapshot: not a git repo -- skipped (run git init once)")
        return
    _git("add", "-A")
    for path in _drop_accidental_gitlinks():
        print(f"git-snapshot: refused to track gitlink {path} (worktree/clone, not a submodule)")
    if not _git("status", "--porcelain").stdout.strip():
        print("git-snapshot: no changes since last snapshot")
        return
    msg = f"desk snapshot {datetime.now(tz=UTC).isoformat()[:16]}Z"
    r = _git("commit", "-m", msg)
    if r.returncode == 0:
        print(f"git-snapshot: committed -- {msg}")
        pr = _git("push", "origin", "HEAD")
        print("git-snapshot: pushed to GitHub" if pr.returncode == 0
              else f"git-snapshot: push failed (offsite deferred): {(pr.stderr or '')[:80]}")
    else:
        print(f"git-snapshot: commit failed: {(r.stderr or r.stdout)[:140]}")


if __name__ == "__main__":
    main()
