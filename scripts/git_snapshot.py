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


def _git(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(["git", *args], capture_output=True, text=True, check=False)


def main() -> None:
    if _git("rev-parse", "--git-dir").returncode != 0:
        print("git-snapshot: not a git repo -- skipped (run git init once)")
        return
    _git("add", "-A")
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
