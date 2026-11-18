"""Direct lane: land a change that touches no live money straight onto LIVE, with no PR and no
queue (zuck, 2026-11-17: "find another way to merge and merge it all fast as possible").

What it does, from a session's own checkout with its work COMMITTED on a branch:

  1. refuses a dirty tree (it lands commits, never a working copy), and lands only while the
     switch the fast lane obeys is on (zuck's ACTIVATE RELEASE CONTROLLER on #453, no newer
     trusted DEACTIVATE), read with LIVE's own gate code;
  2. merges the latest LIVE into the branch tip in the object store (no checkout); any conflict
     stops it -- scripts/resolve_pr_conflicts.py settles the generated ones first;
  3. classifies every path the merge would change on LIVE with LIVE's OWN classifier
     (.github/scripts/fast_lane.py read from a LIVE tree, never the branch's copy): one money,
     protected, box, suite or producer path and it stops -- that change takes a PR;
  4. runs the smoke check the fast lane runs in CI, locally: every test still collects, ruff
     E9/F63/F7/F82 on the changed Python, and the changed tests pass;
  5. pushes the merge commit to LIVE as a FAST-FORWARD. If LIVE moved meanwhile GitHub refuses
     it and it starts again from 2 (at most --tries times). Nothing is ever force-pushed.

After it lands, LIVE runs its full suite on the merged tree exactly as for any merge; the box
adopts only a sealed green LIVE, and a landing that turns LIVE red is reverted by the same
auto-revert as a fast-lane merge (audit_gate.is_registry_merge reads this commit's title). The
box takes the code because adopt_guard exempts what ITS sealed classifier calls non-money.

    python .github/scripts/land.py            # dry run: says whether it would land, and why
    python .github/scripts/land.py --push     # land it
"""

from __future__ import annotations

import argparse
import contextlib
import importlib.util
import json
import os
import subprocess
import sys
import tempfile
from collections.abc import Callable, Iterator, Sequence
from pathlib import Path
from typing import Any

LIVE = "claude/llm-auto-upgrade-verify-gcjac3"
REPO = "kingdemond434-cpu/quant"
APPROVALS_ISSUE = 453
TITLE = "Land (FAST lane, direct"
TRAILER = (
    "\n\nCo-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>\n"
    "Claude-Session: https://claude.ai/code/session_015zQxSBybnApU2oFCn8rxey"
)
HERE = Path(__file__).resolve().parent


class Refused(Exception):
    """This change does not land directly; the message says why."""


def git(cwd: Path, *args: str, check: bool = True, env: dict[str, str] | None = None) -> str:
    p = subprocess.run(["git", "-C", str(cwd), *args], capture_output=True, text=True,
                       check=False, env={**os.environ, **(env or {})})  # fmt: skip
    if check and p.returncode != 0:
        raise Refused(f"git {' '.join(args[:2])}: {(p.stderr or p.stdout).strip()[:300]}")
    return p.stdout


def _module(name: str, path: Path) -> Any:
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise Refused(f"cannot load {path}")
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


def board() -> list[dict[str, Any]]:
    """#453's comments, where the switches live."""
    out = subprocess.run(
        ["gh", "api", f"repos/{REPO}/issues/{APPROVALS_ISSUE}/comments?per_page=100",
         "--paginate", "--slurp"], capture_output=True, text=True, check=True,
    ).stdout  # fmt: skip
    return [c for page in json.loads(out) for c in page]


def switched_off(live_tree: Path, fetch: Callable[[], list[dict[str, Any]]] = board) -> str | None:
    """Why the lane is off, by LIVE's own gate (`activated`, as the fast lane reads it), or None.
    An unreadable board is off: never land blind."""
    gate = _module("land_gate", live_tree / ".github/scripts/audit_gate.py")
    try:
        comments = fetch()
    except (OSError, subprocess.CalledProcessError, ValueError) as exc:
        return f"#{APPROVALS_ISSUE} could not be read ({type(exc).__name__}): not landing blind"
    on, why = gate.activated(comments)
    return None if on else str(why)


def merged_tree(cwd: Path, head: str, live: str) -> tuple[str, list[str]]:
    """(the merge commit of LIVE into `head`, the paths it changes on LIVE). Refuses a conflict."""
    p = subprocess.run(["git", "-C", str(cwd), "merge-tree", "--write-tree", "--name-only",
                        "--no-messages", head, live], capture_output=True, text=True,
                       check=False)  # fmt: skip
    lines = p.stdout.splitlines()
    if p.returncode == 1:
        raise Refused("conflicts with LIVE: " + ", ".join(x for x in lines[1:] if x.strip())
                      + " (scripts/resolve_pr_conflicts.py settles generated files)")  # fmt: skip
    if p.returncode != 0 or not lines:
        raise Refused(f"merge-tree failed: {p.stderr.strip()[:300]}")
    tree = lines[0].strip()
    paths = [x for x in git(cwd, "diff", "--name-only", "--no-renames", live, tree).splitlines()
             if x.strip()]  # fmt: skip
    if not paths:
        raise Refused("nothing to land: LIVE already has this change")
    branch = git(cwd, "rev-parse", "--abbrev-ref", "HEAD").strip()
    msg = f"{TITLE}: {branch}) {len(paths)} path(s), no money path" + TRAILER
    sha = git(cwd, "commit-tree", tree, "-p", live, "-p", head, "-m", msg).strip()
    return sha, paths


#: A slim copy of LIVE: everything but the bulk data (3.9 GB -> ~155 MB), plus every data file
#: the classifier's base facts read (measured 2026-11-17: closure, held, suites, state names and
#: registry producers all identical to a full checkout's). LIMIT: a registry change that starts
#: reading another data file would under-read here; the box's adopt_guard judges on its full
#: tree, so such a slip HOLDS adoption (fails safe) and LIVE's full suite still runs.
SLIM = (
    "/*", "!/desks/mt5/data/", "!/data/", "!/docs/", "!/reports/", "!/desks/mt5/reports/",
    "!/desks/mt5/logs/", "!/logs/", "!/web/",
    "/desks/mt5/data/live_sleeve_policy.json", "/desks/mt5/data/CERT_BOOK_LIVE.json",
    "/desks/mt5/data/external_federation.json", "/desks/mt5/data/import_stems_cache.json",
    "/docs/research/tier1_program.json", "/docs/research/retirements.jsonl",
)
_CLEAN = {k: v for k, v in os.environ.items() if not k.startswith("GIT_")}


@contextlib.contextmanager
def live_tree(cwd: Path, live: str) -> Iterator[Path]:
    """A private, slim, detached checkout of `live`, removed afterwards."""
    with tempfile.TemporaryDirectory(prefix="land-live-") as tmp:
        wt = Path(tmp) / "live"
        git(cwd, "worktree", "add", "-q", "--detach", "--no-checkout", str(wt), live)
        try:
            for args in (("sparse-checkout", "set", "--no-cone", *SLIM), ("checkout", "-q")):
                r = subprocess.run(["git", "-C", str(wt), *args], env=_CLEAN,
                                   capture_output=True, text=True, check=False)  # fmt: skip
                if r.returncode != 0:
                    raise Refused(f"a LIVE checkout failed: {r.stderr.strip()[:300]}")
            yield wt
        finally:
            git(cwd, "worktree", "remove", "--force", str(wt), check=False)


def classify_on_live(wt: Path, sha: str, paths: Sequence[str]) -> str:
    """LIVE's own classifier on the paths the landing changes, in its own interpreter."""
    r = subprocess.run(
        [sys.executable, "-I", "-c",
         "import json,sys; sys.path.insert(0, sys.argv[1]);"
         "import importlib.util as u; s=u.spec_from_file_location('fl', sys.argv[2]);"
         "m=u.module_from_spec(s); sys.modules['fl']=m; s.loader.exec_module(m);"
         "print(json.dumps(m.classify(json.loads(sys.argv[3]), sys.argv[4])))",
         str(wt), str(wt / ".github/scripts/fast_lane.py"), json.dumps(list(paths)), sha],
        capture_output=True, text=True, env=_CLEAN, cwd=wt, check=False, timeout=900,
    )  # fmt: skip
    try:
        fast, why = json.loads(r.stdout.strip().splitlines()[-1])
    except (ValueError, IndexError) as exc:
        raise Refused(f"LIVE's classifier failed: {(r.stderr or r.stdout)[-300:]}") from exc
    if not fast:
        raise Refused(f"not a fast change: {why} -- open a PR")
    return str(why)


def smoke(cwd: Path, paths: Sequence[str]) -> None:
    """The fast lane's smoke job, here (ci.yml `smoke`)."""
    py = [p for p in paths if p.endswith(".py") and (cwd / p).is_file()]
    tests = [p for p in py if Path(p).name.startswith("test_")]
    steps: list[list[str]] = []
    if py:
        steps.append([sys.executable, "-m", "ruff", "check", "--isolated", "--target-version",
                      "py311", "--select", "E9,F63,F7,F82", *py])  # fmt: skip
    steps.append([sys.executable, "-m", "pytest", "--co", "-q", "-p", "no:randomly", "tests",
                  "desks/mt5/tests"])  # fmt: skip
    if tests:
        steps.append([sys.executable, "-m", "pytest", "-q", "-p", "no:randomly", *tests])
    for argv in steps:
        r = subprocess.run(argv, cwd=cwd, capture_output=True, text=True, check=False)
        if r.returncode != 0:
            raise Refused(f"smoke failed: {' '.join(argv[2:5])}: {(r.stdout + r.stderr)[-600:]}")


def land(cwd: Path, *, push: bool, tries: int = 3,
         fetch: Callable[[], list[dict[str, Any]]] = board,
         check: Callable[[Path, Sequence[str]], None] = smoke) -> str:  # fmt: skip
    """One line saying what happened. Raises Refused."""
    if git(cwd, "status", "--porcelain", "--untracked-files=no").strip():
        raise Refused("the working tree has uncommitted changes: commit them first")
    head = git(cwd, "rev-parse", "HEAD").strip()
    for _ in range(max(1, tries)):
        git(cwd, "fetch", "-q", "--no-tags", "origin",
            f"+refs/heads/{LIVE}:refs/remotes/origin/{LIVE}")  # fmt: skip
        live = git(cwd, "rev-parse", f"origin/{LIVE}").strip()
        sha, paths = merged_tree(cwd, head, live)
        with live_tree(cwd, live) as wt:
            if off := switched_off(wt, fetch):
                raise Refused(off)
            why = classify_on_live(wt, sha, paths)
        check(cwd, paths)
        if not push:
            return f"would land {sha[:9]} ({len(paths)} path(s)): {why}"
        p = subprocess.run(["git", "-C", str(cwd), "push", "-q", "origin",
                            f"{sha}:refs/heads/{LIVE}"], capture_output=True, text=True,
                           check=False)  # fmt: skip
        if p.returncode == 0:
            return f"landed {sha[:9]} on LIVE ({len(paths)} path(s)): {why}"
    raise Refused(f"LIVE kept moving: not landed after {tries} tries")


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--push", action="store_true", help="land it (default: dry run)")
    ap.add_argument("--tries", type=int, default=3)
    ap.add_argument("--repo-dir", type=Path, default=Path.cwd())
    a = ap.parse_args(argv)
    try:
        print(land(a.repo_dir, push=a.push, tries=a.tries))
    except Refused as exc:
        print(f"not landed: {exc}")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
