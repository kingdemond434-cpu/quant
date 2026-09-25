#!/usr/bin/env python3
"""THE REVERSION FENCE -- builder work the hourly adoption is about to eat, named BEFORE it eats it.

    python scripts/check_box_reversion.py [--json] [--require-git]

FAILURE 8 OF 2026-09-23: builder work sitting uncommitted on the trading box gets reverted by the
hourly adoption, silently. `MT5-AdoptRelease` runs at :12 every hour; `Adopt-And-Seal.ps1` "lands
the branch's tree in place", keeping only the STATE paths the box itself writes
(`libs.ops.release.STATE_PREFIXES` / `STATE_FILES`). Everything classified as CODE is restored to
the branch's version. An edit made at :05 and not committed is gone at :12, with no error, no
message, and a working tree that looks exactly like one nobody ever edited.

That is the same disease as the other seven: the loss produces no output. A builder cannot tell a
reverted file from a file they never wrote. This fence turns the silence into a defect ahead of
time, which is the only moment at which it is still fixable.

WHAT IT MEASURES, all of it CODE-ONLY -- state paths are the box's own evidence, they are KEPT by
the adoption by design, and flagging them would make the fence noise (L1.43) on a box that
rewrites hundreds of them an hour:

    UNCOMMITTED   a modified, staged, deleted or untracked CODE path. The adoption reverts it.
    UNPUSHED      a CODE path whose only home is a LOCAL commit not on origin/<branch>. The
                  adoption lands origin's tree, so this is reverted too -- committing on the box
                  is not enough on its own, and that is the half a builder is most likely to miss.

WHY IT DOES NOT SIMPLY REFUSE TO FAIL WHEN GIT IS ABSENT. Without git the answer is UNMEASURED,
which is a verdict and not a pass (L1.28a): `--require-git` makes it fail, and the box gate
passes that flag because on the box git is always there and its absence would mean the check
never ran at all.

THIS FENCE NEVER TOUCHES THE TREE. It does not commit, stash, checkout or push anything -- a
fence that "fixed" this by committing would be staging other builders' work under its own name,
and four builders are live in this repository. It names the paths and the deadline; the builder
decides.

Exit: 2 when CODE changes are at risk; 0 when the tree carries none.
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

_ROOT = Path(__file__).resolve().parents[1]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from libs.ops.fence_exit import FAIL, fence_exit  # noqa: E402
from libs.ops.release import is_state_path  # noqa: E402

_PASSING = frozenset({"CLEAN"})
#: The minute past the hour at which `MT5-AdoptRelease` lands the branch's tree in place.
ADOPT_MINUTE = 12


def _git(*args: str, root: Path | None = None) -> tuple[int, str]:
    try:
        r = subprocess.run(["git", *args], cwd=str(root or _ROOT), capture_output=True,
                           text=True, timeout=120, check=False)
        return r.returncode, (r.stdout or "")
    except (OSError, subprocess.SubprocessError):
        return 127, ""


def _minutes_to_adoption(now: datetime | None = None) -> int:
    n = now or datetime.now(UTC)
    return (ADOPT_MINUTE - n.minute) % 60


def build_report(*, root: Path | None = None) -> dict[str, Any]:
    rep: dict[str, Any] = {
        "generated": datetime.now(UTC).isoformat(timespec="seconds"),
        "root": str(root or _ROOT), "branch": "", "upstream": "",
        "uncommitted": [], "unpushed": [], "state_paths_ignored": 0,
        "minutes_to_adoption": _minutes_to_adoption(),
        "scanned": 0, "status": "UNMEASURED", "detail": "",
    }
    rc, branch = _git("branch", "--show-current", root=root)
    if rc != 0:
        rep["detail"] = "git is not available here, so nothing can be said about reversion risk"
        return rep
    rep["branch"] = branch.strip()

    # 1. UNCOMMITTED: anything the working tree or index carries that HEAD does not.
    rc, porcelain = _git("status", "--porcelain=v1", "--untracked-files=all", root=root)
    if rc != 0:
        rep["detail"] = "git status failed; reversion risk is unmeasured"
        return rep
    n_state = 0
    for line in porcelain.splitlines():
        if len(line) < 4:
            continue
        code, path = line[:2], line[3:].strip()
        # a rename reads "R  old -> new"; the NEW path is the one at risk
        if " -> " in path:
            path = path.split(" -> ", 1)[1]
        path = path.strip('"')
        rep["scanned"] += 1
        if is_state_path(path):
            n_state += 1
            continue
        rep["uncommitted"].append({"path": path, "git_status": code.strip() or "??",
                                   "why": "CODE path the hourly adoption reverts in place"})
    rep["state_paths_ignored"] = n_state

    # 2. UNPUSHED: CODE paths whose only home is a local commit origin does not have.
    upstream = ""
    for cand in (f"origin/{rep['branch']}", "@{u}"):
        rc, out = _git("rev-parse", "--verify", "--quiet", cand, root=root)
        if rc == 0 and out.strip():
            upstream = cand
            break
    rep["upstream"] = upstream
    if upstream:
        rc, names = _git("diff", "--name-only", f"{upstream}...HEAD", root=root)
        if rc != 0:
            rc, names = _git("diff", "--name-only", upstream, "HEAD", root=root)
        if rc == 0:
            for path in {p.strip() for p in names.splitlines() if p.strip()}:
                rep["scanned"] += 1
                if is_state_path(path):
                    rep["state_paths_ignored"] += 1
                    continue
                rep["unpushed"].append(
                    {"path": path, "git_status": "local-commit",
                     "why": f"committed here but not on {upstream}; the adoption lands "
                            f"origin's tree, so this is reverted too"})

    n_un, n_up = len(rep["uncommitted"]), len(rep["unpushed"])
    if n_un or n_up:
        rep["status"] = "AT_RISK"
        rep["detail"] = (
            f"{n_un} uncommitted and {n_up} unpushed CODE path(s) on branch "
            f"{rep['branch'] or '?'} will be reverted by the hourly adoption, in "
            f"{rep['minutes_to_adoption']} minute(s) at :{ADOPT_MINUTE:02d}. "
            f"{rep['state_paths_ignored']} state path(s) ignored: the adoption keeps those.")
    else:
        rep["status"] = "CLEAN"
        rep["detail"] = (f"no CODE path at risk on {rep['branch'] or '?'}; "
                         f"{rep['state_paths_ignored']} state path(s) are the box's own and are "
                         f"kept by the adoption")
    return rep


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=(__doc__ or "").split("\n")[0])
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--require-git", action="store_true",
                    help="an unmeasurable tree is a failure (box gate)")
    ap.add_argument("--root", type=Path, default=None)
    ap.add_argument("--report-only", action="store_true")
    a = ap.parse_args(argv)
    rep = build_report(root=a.root)
    if a.json:
        print(json.dumps(rep, indent=1, default=str))
    else:
        print(f"box reversion: {rep['status']} -- {rep['detail']}")
        for row in rep["uncommitted"][:30]:
            print(f"  UNCOMMITTED [{row['git_status']:>2}] {row['path']}")
        if len(rep["uncommitted"]) > 30:
            print(f"  ... and {len(rep['uncommitted']) - 30} more uncommitted")
        for row in rep["unpushed"][:30]:
            print(f"  UNPUSHED         {row['path']}")
        if len(rep["unpushed"]) > 30:
            print(f"  ... and {len(rep['unpushed']) - 30} more unpushed")
        if rep["status"] == "AT_RISK":
            print("  -> commit the CODE paths with explicit paths and push them; this fence "
                  "never touches the tree itself.")
    if a.report_only:
        return 0
    if rep["status"] == "UNMEASURED":
        return FAIL if a.require_git else 0
    return fence_exit(rep["status"], _PASSING, fail=FAIL, scanned=max(rep["scanned"], 1),
                      of="paths in the working tree and ahead of origin",
                      fence="check_box_reversion.py")


if __name__ == "__main__":
    raise SystemExit(main())
