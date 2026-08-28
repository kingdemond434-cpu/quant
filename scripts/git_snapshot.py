"""Daily git snapshot of the code+docs surface -- forensic history the desk lacked.

2026-07-16 lesson: the 07-15 session's panel edits could not be diffed (no git, no backups) and
the 07-13 incident forensics relied on hand-made .bak files. One commit per day fixes both
forever. Secrets and generated state never enter the repo (.gitignore); this is history, not
deployment -- rollback_guard remains the revert mechanism for autonomous changes.

    python scripts/git_snapshot.py
"""

from __future__ import annotations

import re
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
        _report_push(_git("push", "origin", "HEAD"))
    else:
        print(f"git-snapshot: commit failed: {(r.stderr or r.stdout)[:140]}")


def _head_is_on_remote() -> bool:
    """Ask the REMOTE what it holds, rather than a local tracking ref.

    `@{u}` is wrong here twice over: this pushes `origin HEAD`, so the branch need not have an
    upstream configured at all (on a box where it does not, an ancestor test against `@{u}` fails
    and reports a perfectly good push as lost), and a tracking ref is a local cache that a failed
    fetch leaves stale. `ls-remote` is the only answer that came from the server.
    """
    branch = _git("rev-parse", "--abbrev-ref", "HEAD").stdout.strip()
    if not branch or branch == "HEAD":
        return False  # detached: nothing to compare, so never claim it landed
    ls = _git("ls-remote", "origin", f"refs/heads/{branch}")
    if ls.returncode != 0 or not ls.stdout.strip():
        return False
    remote_sha = ls.stdout.split()[0]
    return _git("merge-base", "--is-ancestor", "HEAD", remote_sha).returncode == 0


def _report_push(pr) -> None:
    """Judge the push from the REMOTE, never from git's exit code.

    `git push` EXITS 0 ON A REMOTE REJECT: the pre-receive hook declines, the transport
    succeeded, and the exit code reports the transport. This desk has paid for that three
    times, and it was still live here -- daily_research_cycle logged
    `[git_snapshot] {'ok': True, 'rc': 0, 'tail': ' ! [remote rejected]   HEAD -> desk-sy'}`,
    i.e. the offsite snapshot announcing success for a push that landed nothing. An offsite
    backup that reports green while shipping nothing is worse than no backup, because it is
    the one failure nobody goes looking for.

    Two independent arms, because either alone has been fooled before: grep the OUTPUT for a
    refusal, and confirm from the remote-tracking ref that HEAD is actually contained in it.
    """
    out = f"{pr.stdout or ''}\n{pr.stderr or ''}"
    refused = re.search(r"rejected|denied|error:|failed to push", out, re.I)
    landed = _head_is_on_remote()
    if pr.returncode == 0 and landed and not refused:
        print("git-snapshot: pushed to GitHub")
        return
    why = "REJECTED by the remote" if refused else (
        "exit 0 but HEAD is not on the upstream ref" if pr.returncode == 0 else "transport failed")
    print(f"git-snapshot: PUSH DID NOT LAND ({why}) -- this snapshot exists only on this box: "
          f"{out.strip()[:200].replace(chr(10), ' ')}")


if __name__ == "__main__":
    main()
