"""Drain the box's unpushed backlog without ever pushing the box's branch.

MEASURED 2026-10-06 (read-only census, vmi3571445 15:43Z): the box's branch is 823 commits ahead
of origin. Pushing that branch is exactly what died on `RPC failed; HTTP 408` on 2026-09-24 (506
commits of parquet then), so the publisher no longer does it: the box's STATE now travels as one
commit on origin's tip (`Publish-StateOnto`). What that leaves stranded is anything else the box
committed -- a hand fix made on the box, a box-side session's code -- which no one off the box can
see, review or keep.

WHAT THIS DOES, every run:

1. Lists the backlog (`<upstream>..HEAD`, merges counted apart -- a merge of origin into the box
   carries origin's own code, not the box's).
2. Classifies each non-merge commit: STATE-ONLY when every path it touches is state
   (`libs.ops.release.is_state_path` -- the one classification the adopter and the seal use), else
   CODE-TOUCHING. State-only commits are superseded by the fresh state publish and are dropped
   from consideration; nothing is deleted on the box.
3. For the code paths those commits touched, keeps the ones whose blob at the box's HEAD differs
   from origin's tip (a path the box changed and origin has since caught up with is not news), and
   skips any blob over MAX_BLOB_BYTES (that is how 408s start).
4. With --push: lays those blobs over origin's tip in a PRIVATE index and pushes ONE commit to
   `box/backlog-<YYYYMMDD-HHMM>` -- a review branch, never the live branch, never the production or
   release refs (refused in code, not by convention). A human or a thread reviews and lands it.
5. Writes desks/mt5/reports/BOX_BACKLOG.json: counts, the code paths, the branch and the push
   result. An unreadable backlog is UNMEASURED, never zero.

HEAD, the real index and the working tree are never touched. git runs with `git_env` (the box's
ownership setting) and inherits the caller's credential header when the publisher launches it.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
import sys
import tempfile
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from libs.ops.box_git_env import git_env  # noqa: E402
from libs.ops.release import is_state_path as is_state  # noqa: E402

OUT_REL = "desks/mt5/reports/BOX_BACKLOG.json"
REVIEW_PREFIX = "box/backlog-"
MAX_BLOB_BYTES = 2_000_000
#: Refs this module may never write, whatever it is asked.
FORBIDDEN_REFS = ("claude/llm-auto-upgrade-verify-gcjac3", "production", "master", "main",
                  "desk-sync-clean")


def _git(root: Path, *args: str, env: dict[str, str] | None = None,
         timeout: float = 300.0) -> tuple[int, str, str]:
    try:
        r = subprocess.run(["git", "-C", str(root), *args], capture_output=True, text=True,
                           encoding="utf-8", errors="replace", timeout=timeout, check=False,
                           env=env or git_env(root))
    except (OSError, subprocess.SubprocessError) as exc:
        return 127, "", f"{type(exc).__name__}: {exc}"
    return r.returncode, r.stdout, r.stderr


def review_branch(now: datetime) -> str:
    return f"{REVIEW_PREFIX}{now.strftime('%Y%m%d-%H%M')}"


def _assert_review_ref(branch: str) -> None:
    name = branch.removeprefix("refs/heads/")
    if not name.startswith(REVIEW_PREFIX) or name in FORBIDDEN_REFS or name.startswith("release/"):
        raise ValueError(f"refusing to write {branch!r}: the backlog goes to {REVIEW_PREFIX}* only")


def classify(root: Path, upstream: str) -> dict[str, Any]:
    doc: dict[str, Any] = {"upstream": upstream}
    rc, out, err = _git(root, "rev-list", "--count", f"{upstream}..HEAD")
    if rc != 0:
        doc.update(verdict="UNMEASURED", why=f"cannot list the backlog: {err.strip()[:300]}")
        return doc
    doc["ahead"] = int(out.strip() or 0)
    rc, out, _ = _git(root, "rev-list", "--count", "--merges", f"{upstream}..HEAD")
    doc["merges"] = int(out.strip() or 0) if rc == 0 else None
    # One pass: "@@<sha>" header per non-merge commit, then the paths it touched.
    rc, out, err = _git(root, "log", "--no-merges", "--format=@@%H", "--name-only",
                        f"{upstream}..HEAD")
    if rc != 0:
        doc.update(verdict="UNMEASURED", why=f"cannot read the backlog: {err.strip()[:300]}")
        return doc
    commits: dict[str, list[str]] = {}
    cur = None
    for line in out.splitlines():
        if line.startswith("@@"):
            cur = line[2:].strip()
            commits[cur] = []
        elif line.strip() and cur:
            commits[cur].append(line.strip())
    code_commits = [c for c, paths in commits.items() if any(not is_state(p) for p in paths)]
    code_paths = sorted({p for c in code_commits for p in commits[c] if not is_state(p)})
    doc.update(non_merge=len(commits), state_only=len(commits) - len(code_commits),
               code_touching=len(code_commits), code_commits=code_commits[:200],
               code_paths_touched=len(code_paths), verdict="MEASURED")
    doc["_code_paths"] = code_paths
    return doc


Blob = tuple[str, str, str]


def differing_blobs(root: Path, upstream: str,
                    paths: list[str]) -> tuple[list[Blob], list[dict[str, Any]]]:
    """(mode, sha, path) for paths whose HEAD blob differs from upstream's, and the skipped."""
    keep: list[tuple[str, str, str]] = []
    skipped: list[dict[str, Any]] = []
    for i in range(0, len(paths), 200):
        chunk = paths[i:i + 200]
        _, head_out, _ = _git(root, "ls-tree", "-l", "HEAD", "--", *chunk)
        _, up_out, _ = _git(root, "ls-tree", upstream, "--", *chunk)
        up = {}
        for line in up_out.splitlines():
            meta, _, rel = line.partition("\t")
            f = meta.split()
            if len(f) >= 3:
                up[rel] = f[2]
        for line in head_out.splitlines():
            meta, _, rel = line.partition("\t")
            f = meta.split()
            if len(f) < 4 or f[1] != "blob":
                continue
            mode, sha, size = f[0], f[2], f[3]
            if up.get(rel) == sha:
                continue
            if size.isdigit() and int(size) > MAX_BLOB_BYTES:
                skipped.append({"path": rel, "bytes": int(size), "why": "over MAX_BLOB_BYTES"})
                continue
            keep.append((mode, sha, rel))
    return keep, skipped


def push_review(root: Path, upstream: str, blobs: list[tuple[str, str, str]], branch: str,
                remote: str = "origin") -> dict[str, Any]:
    _assert_review_ref(branch)
    rc, base, err = _git(root, "rev-parse", f"{upstream}^{{commit}}")
    if rc != 0:
        return {"pushed": False, "why": f"upstream unreadable: {err.strip()[:300]}"}
    base = base.strip()
    fd, idx = tempfile.mkstemp(prefix="box-backlog-index-")
    os.close(fd)
    os.unlink(idx)
    env = {**git_env(root), "GIT_INDEX_FILE": idx}
    try:
        rc, _, err = _git(root, "read-tree", base, env=env)
        if rc != 0:
            return {"pushed": False, "why": f"read-tree failed: {err.strip()[:300]}"}
        for mode, sha, rel in blobs:
            _git(root, "update-index", "--add", "--cacheinfo", f"{mode},{sha},{rel}", env=env)
        rc, tree, err = _git(root, "write-tree", env=env)
    finally:
        if os.path.exists(idx):
            os.unlink(idx)
    if rc != 0:
        return {"pushed": False, "why": f"write-tree failed: {err.strip()[:300]}"}
    msg = (f"box backlog for review: {len(blobs)} code path(s) the box changed and origin lacks\n\n"
           f"Built by libs/ops/box_backlog.py on origin's tip {base[:12]}. Review branch only; "
           "it never lands on the live branch by itself.")
    rc, commit, err = _git(root, "commit-tree", tree.strip(), "-p", base, "-m", msg)
    if rc != 0:
        return {"pushed": False, "why": f"commit-tree failed: {err.strip()[:300]}"}
    commit = commit.strip()
    # A NEW ref every run (minute-stamped), so the push never needs force over anything.
    rc, _, err = _git(root, "push", "--porcelain", remote, f"{commit}:refs/heads/{branch}")
    if rc != 0:
        return {"pushed": False, "commit": commit, "why": err.strip()[-600:]}
    return {"pushed": True, "commit": commit, "branch": branch}


def _digest(blobs: list[tuple[str, str, str]]) -> str:
    return hashlib.sha256("\n".join(f"{m} {s} {p}" for m, s, p in sorted(blobs, key=lambda b: b[2]))
                          .encode("utf-8")).hexdigest()[:16]


def _previous(out: Path) -> dict[str, Any]:
    try:
        data = json.loads(out.read_text("utf-8"))
    except (OSError, ValueError):
        return {}
    return data if isinstance(data, dict) else {}


def run(root: Path, *, upstream: str, push: bool, now: datetime | None = None,
        remote: str = "origin", out: Path | None = None) -> dict[str, Any]:
    now = now or datetime.now(UTC)
    doc = classify(root, upstream)
    doc["measured_at"] = now.isoformat(timespec="seconds")
    code_paths = doc.pop("_code_paths", [])
    if doc.get("verdict") != "MEASURED":
        return doc
    blobs, skipped = differing_blobs(root, upstream, code_paths)
    doc.update(code_paths_differing=len(blobs), code_paths=[b[2] for b in blobs][:500],
               skipped=skipped, blob_digest=_digest(blobs))
    prev = _previous(out) if out else {}
    raw_push = prev.get("push")
    prev_push: dict[str, Any] = raw_push if isinstance(raw_push, dict) else {}
    if not blobs:
        doc["push"] = {"pushed": False, "why": "nothing to drain: no box-only code differs"}
    elif prev.get("blob_digest") == doc["blob_digest"] and prev_push.get("pushed"):
        # The same box-only code is already on a review branch; a new branch every slot is noise.
        doc["push"] = {**prev_push, "repeated": True}
    elif push:
        doc["push"] = push_review(root, upstream, blobs, review_branch(now), remote=remote)
    else:
        doc["push"] = {"pushed": False, "why": "dry run (no --push)"}
    return doc


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--upstream", default="@{u}")
    ap.add_argument("--push", action="store_true")
    ap.add_argument("--out", type=Path, default=ROOT / OUT_REL)
    args = ap.parse_args(argv)
    doc = run(ROOT, upstream=args.upstream, push=args.push, out=args.out)
    try:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(json.dumps(doc, indent=2), "utf-8")
    except OSError as exc:
        print(f"box backlog: report not written ({exc})", file=sys.stderr)
    push = doc.get("push") or {}
    print(f"box backlog: {doc.get('verdict')} ahead={doc.get('ahead')} merges={doc.get('merges')} "
          f"state_only={doc.get('state_only')} code_touching={doc.get('code_touching')} "
          f"code_paths_differing={doc.get('code_paths_differing')} "
          f"pushed={push.get('pushed')} {push.get('branch') or push.get('why', '')}")
    return 0 if doc.get("verdict") == "MEASURED" else 1


if __name__ == "__main__":
    raise SystemExit(main())
