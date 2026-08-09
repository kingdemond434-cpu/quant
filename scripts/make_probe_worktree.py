#!/usr/bin/env python3
"""IS THIS FAILURE MY CODE, OR THIS BOX? -- a probe tree that can actually answer it.

WHY THIS EXISTS (desk lesson L0068, paid for 2026-08-05). When a test fails in a dirty shared
tree, the first question is whether the cause is your edit or the environment. The standard move
is a detached worktree at HEAD: if the test passes there, your edit caused it. That move is WRONG
BY DEFAULT here, in a way that produces a confident false answer:

  1. `data/` is gitignored (`.gitignore:11 data/*`), so a fresh worktree carries only the 17
     tracked exceptions and none of the live state. Every test that reads live state then passes
     in the probe tree FOR THE WRONG REASON, and the session concludes "environment, not my code"
     -- exactly backwards. Measured on 2026-08-05: the under-exploration failures PASSED in a bare
     worktree (no data/moat) and FAILED identically to the dirty tree once data/ was linked,
     which is what proved the cause was the moat miner rather than the build under way.
  2. The obvious fix, `ln -sfn /live/data <wt>/data`, creates `<wt>/data/data` instead of
     replacing anything, because the target already exists as a directory. The link silently
     lands one level down and the tree still has no live state.

So the procedure is three careful steps that are easy to get wrong under time pressure and give
no error when you do -- the worst shape for a manual instruction. This makes it one command.

    python scripts/make_probe_worktree.py                 # create, print the path
    python scripts/make_probe_worktree.py --ref abc1234   # at some other commit
    python scripts/make_probe_worktree.py --remove        # clean up

The ref's own tracked `data/` files are preserved as `data.at-ref/` rather than deleted, so the
two views stay comparable and nothing is silently thrown away.
"""
from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from libs.ops.lawful import guard as _law_guard  # noqa: E402

#: Outside the repo on purpose: a worktree inside it would be walked by every rglob("*.md") and
#: glob("scripts/*.py") the audits run, so the probe tree would show up as duplicate organs,
#: duplicate findings docs and duplicate fences in the very checks it exists to test.
DEFAULT_PATH = _ROOT.parent / f"{_ROOT.name}-probe"


def _git(*args: str, cwd: Path | None = None) -> subprocess.CompletedProcess[str]:
    return subprocess.run(["git", *args], cwd=cwd or _ROOT, capture_output=True,
                          text=True, timeout=120, check=False)


def link_live_data(wt: Path, live: Path) -> dict[str, object]:
    """Point `wt/data` at the live directory, surviving the two traps above.

    Returns what was done, so the caller can print it rather than assume it.
    """
    target = wt / "data"
    moved = None
    if target.is_symlink():
        target.unlink()                       # a previous run's link -- replace, never nest
    elif target.is_dir():
        # THE TRAP: symlinking onto an existing directory nests instead of replacing. Move the
        # ref's tracked data files aside instead of deleting them -- they are the "what did this
        # commit ship" view and are worth keeping next to the live one.
        moved = wt / "data.at-ref"
        if moved.exists():
            shutil.rmtree(moved)
        target.rename(moved)
    elif target.exists():
        target.unlink()
    os.symlink(live, target, target_is_directory=True)
    return {"linked": str(target), "points_to": str(live),
            "ref_data_preserved_at": str(moved) if moved else None,
            # Proves the trap did not happen. A nested data/data is the exact failure this
            # function exists to prevent, so it is asserted rather than hoped for.
            "no_nested_data_dir": not (target / "data").exists()}


def create(ref: str, path: Path) -> dict[str, object]:
    if path.exists():
        return {"status": "EXISTS", "path": str(path),
                "detail": "already present -- reuse it, or --remove first"}
    r = _git("worktree", "add", "--detach", str(path), ref)
    if r.returncode != 0:
        return {"status": "FAILED", "path": str(path), "detail": r.stderr.strip()[:400]}
    info = link_live_data(path, _ROOT / "data")
    return {"status": "READY", "path": str(path), "ref": ref, **info,
            "how_to_read_it": (
                "Run the failing test HERE. Passes here + fails in the main tree -> your edit. "
                "Fails in BOTH -> the environment or live state, not your edit. Without the "
                "data/ link a live-state test passes here for the wrong reason and inverts that "
                "conclusion, which is the whole point of this script.")}


def remove(path: Path) -> dict[str, object]:
    if not path.exists():
        return {"status": "ABSENT", "path": str(path)}
    # Unlink the symlink FIRST. `git worktree remove` would otherwise walk into it and, on a
    # forced removal, delete through the link into the live data directory.
    link = path / "data"
    if link.is_symlink():
        link.unlink()
    r = _git("worktree", "remove", "--force", str(path))
    if r.returncode != 0 and path.exists():
        shutil.rmtree(path, ignore_errors=True)
        _git("worktree", "prune")
    return {"status": "REMOVED", "path": str(path)}


def main() -> int:
    _law_guard()
    ap = argparse.ArgumentParser()
    ap.add_argument("--ref", default="HEAD")
    ap.add_argument("--path", default=str(DEFAULT_PATH))
    ap.add_argument("--remove", action="store_true")
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args()
    rep = remove(Path(args.path)) if args.remove else create(args.ref, Path(args.path))
    if args.json:
        print(json.dumps(rep, indent=2))
    else:
        for k, v in rep.items():
            print(f"{k}: {v}")
    return 0 if rep["status"] in ("READY", "REMOVED", "EXISTS", "ABSENT") else 2


if __name__ == "__main__":
    sys.exit(main())
