"""The orphan reaper, an actuator under the control plane (libs/ops/proctree.py has the story:
72 leaked pool workers held 147 GB of commit on 2026-09-22 and starved every new leg).

Runs every reconciler pass through `desk_actuators()["reap_orphans"]`; `--dry-run` only counts.
Writes reports/ORPHAN_REAPER.json and an events row. Exit 0 always: a reaper that cannot measure
says UNMEASURED in its artifact; it never fails the fixer that runs it.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

DESK = Path(__file__).resolve().parents[1]
ROOT = DESK.parents[1]
for _p in (str(ROOT), str(DESK)):
    if _p not in sys.path:
        sys.path.insert(0, _p)


def main(argv: list[str] | None = None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)
    apply = "--dry-run" not in args
    from libs.ops import proctree
    rep = proctree.reap_orphaned_workers(apply=apply)
    out = DESK / "reports" / "ORPHAN_REAPER.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(rep, indent=2, sort_keys=True), encoding="utf-8")
    try:
        from libs.ops import events
        events.emit("orphan_reaper", status="reaped" if rep["killed"] else "clean",
                    orphans=rep["orphans"], killed=rep["killed"],
                    commit_mb=rep["orphan_commit_mb"])
    except Exception:
        pass
    print(f"orphan reaper: workers={rep['workers_total']} orphans={rep['orphans']} "
          f"killed={rep['killed']} commit_mb={rep['orphan_commit_mb']} applied={rep['applied']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
