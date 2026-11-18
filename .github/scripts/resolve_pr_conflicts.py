"""Merge LIVE into a conflicting PR branch when the only conflicts are in generated or append-only
files, and resolve those mechanically (Hourly pass, 2026-11-17: 87 of 164 open PRs conflicted
with LIVE, 47 of them ONLY on these files).

What each file gets (3-way: the merge base, the PR's side, LIVE's side):
  - line files (context/decision_journal.jsonl, ops/money_closure.txt, .gitignore): LIVE's
    lines, minus any the PR removed, plus the PR's added lines that LIVE lacks, in the PR's order.
  - docs/research/runtime_state.json and RUNTIME_STATE.md: LIVE's copies, byte for byte (the
    attesting host owns the monolith), and every organ row the PR's monolith adds that LIVE
    (monolith or sidecars) lacks is written as its own sidecar under runtime_state.d/ -- the
    one-file-per-organ form runtime_attestation.attest_only_missing writes since 2026-11-14.
  - docs/research/experiment_contracts.json: a 3-way merge by key, recursively; a key both sides
    changed differently is a real conflict and the PR is left alone.
Any other conflicted path, or any step that fails, aborts the merge and leaves the branch as it
was. Nothing is force-pushed: the merge commit's first parent is the PR head, so the push is a
fast-forward and GitHub refuses it if the branch moved meanwhile.

A merge-in changes the PR's diff bytes, so an Auditor CLEAR does not carry (audit_gate.patch_id):
a fast-lane PR needs none; any other PR needs a new CLEAR of the new head.

    python .github/scripts/resolve_pr_conflicts.py --pr 1191 --pr 1187 [--push] [--quiet-min 60]

It lives beside audit_gate.py and land.py because it is PR plumbing run on demand against
GitHub, not a desk organ: nothing in the desk calls it and no clock may push into other
sessions' branches unattended (the component registry walks scripts/, never .github/).
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import subprocess
import sys
import tempfile
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

LIVE = "claude/llm-auto-upgrade-verify-gcjac3"
REPO = "kingdemond434-cpu/quant"
LINE_FILES = ("context/decision_journal.jsonl", "ops/money_closure.txt", ".gitignore")
STATE_JSON = "docs/research/runtime_state.json"
STATE_MD = "docs/research/RUNTIME_STATE.md"
SIDECARS = "docs/research/runtime_state.d"
CONTRACTS = "docs/research/experiment_contracts.json"
HANDLED = frozenset({*LINE_FILES, STATE_JSON, STATE_MD, CONTRACTS})
TRAILER = (
    "\n\nCo-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>\n"
    "Claude-Session: https://claude.ai/code/session_015zQxSBybnApU2oFCn8rxey"
)


class Conflict(Exception):
    """A real conflict this resolver will not decide."""


# ------------------------------------------------------------------------------ the merges


def merge_lines(base: str, ours: str, theirs: str) -> str:
    """LIVE's (`theirs`) lines minus what the PR (`ours`) removed, plus the PR's new lines."""
    b, o, t = (x.splitlines() for x in (base, ours, theirs))
    bs, os_, ts = set(b), set(o), set(t)
    removed = bs - os_
    out = [ln for ln in t if ln not in removed]
    out += [ln for ln in o if ln not in bs and ln not in ts]
    nl = "\n" if (theirs.endswith("\n") or ours.endswith("\n") or not theirs) else ""
    return "\n".join(out) + (nl if out else "")


_MISSING = object()


def merge_json(base: Any, ours: Any, theirs: Any, where: str = "") -> Any:
    """3-way merge: a side that did not change a value takes the other's; dicts merge by key
    (LIVE's key order, then the PR's new keys); anything else changed differently raises."""
    if ours == theirs:
        return theirs
    if ours == base:
        return theirs
    if theirs == base:
        return ours
    if isinstance(ours, dict) and isinstance(theirs, dict):
        b = base if isinstance(base, dict) else {}
        out: dict[str, Any] = {}
        for k in [*theirs, *(k for k in ours if k not in theirs)]:
            v = merge_json(b.get(k, _MISSING), ours.get(k, _MISSING), theirs.get(k, _MISSING),
                           f"{where}/{k}")  # fmt: skip
            if v is not _MISSING:
                out[k] = v
        return out
    raise Conflict(f"{CONTRACTS}{where or '/'}: both sides changed it differently")


def dump_like(doc: Any, like: str) -> str:
    """JSON in the formatting LIVE's copy uses (indent read from it, trailing newline kept)."""
    m = re.search(r"\n( +)\"", like)
    text = json.dumps(doc, indent=len(m.group(1)) if m else 1, ensure_ascii=False)
    return text + ("\n" if like.endswith("\n") else "")


def sidecar_name(organ: str) -> str:
    """runtime_attestation.sidecar_name, restated (stdlib only): NTFS-legal and unique."""
    slug = re.sub(r"[^A-Za-z0-9._-]", "~", organ)[:80]
    return f"{slug}-{hashlib.sha256(organ.encode('utf-8')).hexdigest()[:8]}.json"


def state_sidecars(ours: str, theirs: str, live_sidecars: set[str]) -> dict[str, str]:
    """{sidecar path: content} for each organ row the PR's monolith adds that LIVE lacks."""
    try:
        mine, live = json.loads(ours), json.loads(theirs)
    except ValueError as exc:
        raise Conflict(f"{STATE_JSON}: unreadable ({exc})") from exc
    have = {str(r.get("organ")) for r in live.get("organs") or [] if isinstance(r, dict)}
    out: dict[str, str] = {}
    for r in mine.get("organs") or []:
        if not isinstance(r, dict) or not r.get("organ") or str(r["organ"]) in have:
            continue
        path = f"{SIDECARS}/{sidecar_name(str(r['organ']))}"
        if path not in live_sidecars:
            out[path] = json.dumps(r, indent=1, default=str, sort_keys=False) + "\n"
    return out


# ------------------------------------------------------------------------------- git side
# No checkout and no hook: `git merge-tree --write-tree` merges in the object store, each
# resolved file is written as a blob into a private index over that tree, and the merge commit is
# made with commit-tree. Nothing on disk changes, so a tree of any size costs nothing to merge.


def git(cwd: Path, *args: str, check: bool = True, env: dict[str, str] | None = None,
        data: bytes | None = None) -> str:  # fmt: skip
    p = subprocess.run(["git", "-C", str(cwd), *args], capture_output=True, input=data,
                       check=False, env={**os.environ, **(env or {})})  # fmt: skip
    if check and p.returncode != 0:
        err = (p.stderr or p.stdout).decode("utf-8", "replace").strip()
        raise RuntimeError(f"git {' '.join(args[:2])}: {err[:300]}")
    return p.stdout.decode("utf-8", "replace")


def show(cwd: Path, rev: str, path: str) -> str:
    """`path` at `rev`, or '' when it does not exist there."""
    return git(cwd, "show", f"{rev}:{path}", check=False)


def resolve(cwd: Path, base: str, head: str, live: str, unmerged: list[str]) -> dict[str, str]:
    """{path: resolved text} for every conflicted path. Raises Conflict on anything else."""
    other = [p for p in unmerged if p not in HANDLED]
    if other:
        raise Conflict("real conflicts: " + ", ".join(other))
    out: dict[str, str] = {}
    for path in unmerged:
        b, o, t = (show(cwd, rev, path) for rev in (base, head, live))
        if path in LINE_FILES:
            out[path] = merge_lines(b, o, t)
        elif path in (STATE_JSON, STATE_MD):
            out[path] = t
        else:  # CONTRACTS
            try:
                docs = [json.loads(x) if x else {} for x in (b, o, t)]
            except ValueError as exc:
                raise Conflict(f"{path}: unreadable ({exc})") from exc
            out[path] = dump_like(merge_json(*docs), t)
    if STATE_JSON in unmerged:
        have = set(git(cwd, "ls-tree", "-r", "--name-only", live, "--", SIDECARS).split())
        out.update(state_sidecars(show(cwd, head, STATE_JSON), show(cwd, live, STATE_JSON), have))
    return out


def merge_commit(cwd: Path, head: str, live: str, branch: str) -> tuple[str, list[str]]:
    """(the merge commit of `live` into `head`, the paths it resolved). Raises Conflict."""
    p = subprocess.run(["git", "-C", str(cwd), "merge-tree", "--write-tree", "--name-only",
                        "--no-messages", head, live], capture_output=True, text=True,
                       check=False)  # fmt: skip
    if p.returncode not in (0, 1):
        raise RuntimeError(f"merge-tree: {p.stderr.strip()[:300]}")
    lines = p.stdout.splitlines()
    tree, unmerged = lines[0].strip(), sorted({x for x in lines[1:] if x.strip()})
    resolved: dict[str, str] = {}
    if unmerged:
        base = git(cwd, "merge-base", head, live).strip()
        resolved = resolve(cwd, base, head, live, unmerged)
        with tempfile.TemporaryDirectory(prefix="resolve-idx-") as tmp:
            env = {"GIT_INDEX_FILE": str(Path(tmp) / "index")}
            git(cwd, "read-tree", tree, env=env)
            for path, text in resolved.items():
                blob = git(cwd, "hash-object", "-w", "--stdin", data=text.encode("utf-8")).strip()
                git(cwd, "update-index", "--add", "--cacheinfo", f"100644,{blob},{path}", env=env)
            tree = git(cwd, "write-tree", env=env).strip()
    msg = (f"Merge LIVE into {branch}; generated and append-only files resolved by "
           f".github/scripts/resolve_pr_conflicts.py "
           f"({', '.join(sorted(resolved)) or 'no conflicts'})"
           + TRAILER)  # fmt: skip
    sha = git(cwd, "commit-tree", tree, "-p", head, "-p", live, "-m", msg).strip()
    return sha, sorted(resolved)


def gh(*args: str) -> Any:
    out = subprocess.run(["gh", "api", *args], capture_output=True, text=True, check=True).stdout
    return json.loads(out) if out.strip() else None


def one(repo_dir: Path, pr: int, *, push: bool, quiet_min: float,
        now: Callable[[], datetime] = lambda: datetime.now(UTC)) -> str:  # fmt: skip
    """Resolve one PR; a line saying what happened."""
    p = gh(f"repos/{REPO}/pulls/{pr}")
    if p["state"] != "open" or p["base"]["ref"] != LIVE:
        return f"#{pr}: skipped ({p['state']}, base {p['base']['ref']})"
    if (p["head"].get("repo") or {}).get("full_name") != REPO:
        return f"#{pr}: skipped (a fork)"
    branch, head = p["head"]["ref"], p["head"]["sha"]
    age = (now() - datetime.fromisoformat(p["updated_at"].replace("Z", "+00:00"))).total_seconds()
    if age < quiet_min * 60:
        return f"#{pr}: skipped (moved {age / 60:.0f} min ago; its session may still be pushing)"
    try:
        git(repo_dir, "fetch", "-q", "--no-tags", "origin",
            f"+refs/heads/{LIVE}:refs/remotes/origin/live", head)  # fmt: skip
        live = git(repo_dir, "rev-parse", "origin/live").strip()
        sha, files = merge_commit(repo_dir, head, live, branch)
        if not files:  # it merges cleanly: a merge-in would only queue a full CI set for nothing
            return f"#{pr}: skipped (merges cleanly with LIVE; nothing to resolve)"
        if push:  # a fast-forward of the branch: refused if it moved meanwhile
            git(repo_dir, "push", "-q", "origin", f"{sha}:refs/heads/{branch}")
        verb = "pushed" if push else "resolved (dry run)"
        return f"#{pr}: {verb} {sha[:9]} on {branch}: {', '.join(files) or 'no conflicts'}"
    except (Conflict, RuntimeError) as exc:
        return f"#{pr}: left alone -- {exc}"


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--pr", type=int, action="append", required=True)
    ap.add_argument("--push", action="store_true", help="push the merge (default: dry run)")
    ap.add_argument("--quiet-min", type=float, default=60.0,
                    help="leave a PR that moved this recently (its session may be pushing)")
    ap.add_argument("--repo-dir", type=Path, default=Path(__file__).resolve().parents[2])
    a = ap.parse_args(argv)
    for pr in a.pr:
        print(one(a.repo_dir, pr, push=a.push, quiet_min=a.quiet_min), flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
