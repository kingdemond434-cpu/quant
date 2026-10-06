"""Is this push STATE ONLY? The pre-push hook's question before it spends a minute on code gates.

WHY (post-merge audit of #181, 2026-10-06). `ops/githooks/pre-push` ran `ops/gates.sh` (ruff,
compileall, pytest collection, mypy) and then every constitutional law fence on EVERY push from
the trading box -- including `sync_shadow_to_git.ps1`'s one-commit publication of the box's own
ledgers and reports. A state commit changes no code, so there is nothing in it for those gates to
judge; what they judged instead was the rest of the box's tree, and any red fence anywhere refused
the box's evidence (libs/ops/state_publication.py records the two-week stall this caused).

THE RULE IS NARROW ON PURPOSE. A push is state-only when EVERY path it changes is box state by
`libs.ops.release.is_state_path` -- the one classification the seal, Adopt-Release and the gateway
already share -- EXCEPT `docs/`, which release.py counts as state for adoption but which carries the
laws the fences read. One code path anywhere in the push and the full gate runs, exactly as before.
Anything this script cannot measure (no ref lines, an object missing locally, git failing, the
classifier unimportable) is NOT state-only: the default is the full gate, never a skip.

    python scripts/push_scope.py < <pre-push ref lines>    # read from stdin, as git hands them
    exit 0  -> state-only, gates may be skipped        exit 1 -> run the gates
"""
from __future__ import annotations

import subprocess
import sys
from collections.abc import Iterable
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ZERO = "0" * 40
#: release.py counts docs/ as state (the box may carry its own rendering of them), but the law
#: fences read docs/LAWS.md and friends -- a docs change is exactly what they exist to judge.
NOT_STATE_FOR_PUSH: tuple[str, ...] = ("docs/",)


def is_push_state(rel: str) -> bool:
    if str(ROOT) not in sys.path:
        sys.path.insert(0, str(ROOT))
    from libs.ops.release import is_state_path
    p = str(rel).replace("\\", "/").lstrip("./")
    if any(p.startswith(pre) for pre in NOT_STATE_FOR_PUSH):
        return False
    return bool(is_state_path(p))


def _git(root: Path, *args: str) -> tuple[int, str]:
    try:
        r = subprocess.run(["git", "-C", str(root), *args], capture_output=True, text=True,
                           encoding="utf-8", errors="replace", timeout=120, check=False)
    except (OSError, subprocess.SubprocessError):
        return 127, ""
    return r.returncode, r.stdout


def changed_paths(root: Path, lines: Iterable[str]) -> list[str] | None:
    """Every path the pushed refs change on the remote, or None when that is unmeasurable."""
    out: set[str] = set()
    seen = False
    for ln in lines:
        parts = ln.split()
        if len(parts) != 4:
            continue
        seen = True
        _local_ref, local_sha, _remote_ref, remote_sha = parts
        if local_sha == ZERO:
            continue                                   # a deletion changes no file
        if remote_sha == ZERO:
            # A new remote ref: the commits not yet on any remote-tracking ref, each against its
            # parents. No such commits (a branch cut at a pushed commit) changes nothing.
            rc, revs = _git(root, "rev-list", local_sha, "--not", "--remotes")
            if rc != 0:
                return None
            for c in revs.split():
                rc, names = _git(root, "diff-tree", "--no-commit-id", "--name-only", "-r",
                                 "-m", "--root", c)
                if rc != 0:
                    return None
                out.update(n for n in names.splitlines() if n.strip())
            continue
        rc, names = _git(root, "diff", "--name-only", "--no-renames", remote_sha, local_sha)
        if rc != 0:
            return None                                # remote object absent here: unmeasured
        out.update(n for n in names.splitlines() if n.strip())
    return sorted(out) if seen else None


def verdict(root: Path, lines: Iterable[str]) -> tuple[bool, str]:
    paths = changed_paths(root, lines)
    if paths is None:
        return False, "push scope UNMEASURED -- running the full gate"
    try:
        code = [p for p in paths if not is_push_state(p)]
    except Exception as exc:                           # classifier missing: never a skip
        return False, f"state classifier unavailable ({type(exc).__name__}) -- running the gate"
    if code:
        return False, f"{len(code)} non-state path(s) in this push (e.g. {code[0]})"
    return True, f"state-only push: {len(paths)} path(s), all box state"


def main() -> int:
    ok, why = verdict(ROOT, sys.stdin.read().splitlines())
    print(f"pre-push: {why}", file=sys.stderr)
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
