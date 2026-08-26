"""Worktree reap: the scheduled caller for libs/ops/worktree_reaper (III.16 wire, GAP 128 kin).

R0423 orders every worker into its own worktree and nothing retired them: measured 2026-08-20 at
18GB across 43 checkouts (47% of the disk) while the tape recorders paused on the disk fuse. The
library encodes the lossless-reap conditions (LANDED ancestor of the live branch + CLEAN + IDLE
measured >= 8h; unmeasured NEVER reaps, L1.28a); this script enumerates, classifies, publishes
the histogram, and with ``--reap`` removes the checkouts (never the branches).

    python scripts/check_worktree_reap.py            # report only -> data/worktree_reap.json
    python scripts/check_worktree_reap.py --reap     # remove REAP-verdict checkouts

Exit 0 always: the artifact is the product; a reap that frees nothing is distinguishable from a
reap that examined nothing by the published histogram (L1.57).
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
import time
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from libs.ops.worktree_reaper import classify, reap_plan, remove_checkout  # noqa: E402

OUT = ROOT / "data" / "worktree_reap.json"


def _worktree_paths(main_repo: Path) -> list[Path]:
    txt = subprocess.run(["git", "-C", str(main_repo), "worktree", "list", "--porcelain"],
                         capture_output=True, text=True, check=False).stdout
    paths = [Path(line.split(" ", 1)[1]) for line in txt.splitlines()
             if line.startswith("worktree ")]
    return [p for p in paths if p.resolve() != main_repo.resolve()]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--reap", action="store_true", help="remove REAP-verdict checkouts")
    ap.add_argument("--min-idle-h", type=float, default=8.0)
    args = ap.parse_args()

    live_head = subprocess.run(["git", "-C", str(ROOT), "rev-parse", "HEAD"],
                               capture_output=True, text=True, check=False).stdout.strip()
    now = time.time()
    trees = [w for p in _worktree_paths(ROOT)
             if (w := classify(p, live_head, ROOT, now, min_idle_h=args.min_idle_h))]
    reapable, hist = reap_plan(trees)

    reaped: list[str] = []
    failed: list[str] = []
    if args.reap:
        for w in reapable:
            ok, why = remove_checkout(w.path, ROOT)
            (reaped if ok else failed).append(f"{w.path} ({why})")

    payload = {
        "measured": datetime.now(tz=UTC).isoformat(),
        "live_head": live_head,
        "histogram": hist,
        "n_trees": len(trees),
        "reap_candidates": [{"path": str(w.path), "idle_h": w.idle_h, "size_mb": w.size_mb}
                            for w in reapable],
        "reaped": reaped,
        "reap_failed": failed,
        "mode": "reap" if args.reap else "report-only",
    }
    OUT.write_text(json.dumps(payload, indent=2))
    print(json.dumps({"histogram": hist, "reaped": len(reaped), "failed": len(failed),
                      "candidates_mb": sum(w.size_mb for w in reapable)}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
