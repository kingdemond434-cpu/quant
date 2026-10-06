"""CRO D18, MEASURED ON READS: how many datasets on this box no consumer actually read.

THE DUTY (docs/cro/CRO_CYCLE.md D18, "No unfed datasets", target 0) read MISSED every pass because
no organ published an `unfed_datasets` number. This organ publishes it every hour, and it counts
on the strictest evidence the desk has: a RECORDED READ (`libs/data/dataset_use`) by a consumer,
with the version it saw, inside the last `STALE_AFTER_S`. Listed, fetched, parsed and "cells
emitted" are all weaker states and none of them counts as fed here.

THE UNIVERSE, read from disk every pass (never a hand list):

    acquired:<series>   every series in `data/acquired/registry.json` (acquire_datasets)
    axis:<id>           every `data/axes/*.json` (the axis door: alt_proxies, macro, packs)
    lake:<stem>         every `data/lake/series/*.{csv,parquet}` (the lake's PIT envelope)

STATUS per dataset:

    FED          at least one consumer read it inside the window; its uses are listed
    STALE        it was read once, but not inside the window
    UNFED        no recorded read at all

`unfed_datasets` = UNFED + STALE. A dataset kind whose readers record nothing yet is not excused:
it reads UNFED, because "nobody can show they read it" is exactly the defect the duty names.
Before the readers that record (PR #192) reach the box, every dataset reads UNFED -- that is the
measurement, not an outage.

THE TARGET IS 0 AND THE FIX IS A READER, NEVER A DELETION. Retiring a dataset to improve this
number is the museum the principal forbade in the other direction; the list is the work queue.

    python desks/mt5/research/dataset_use_census.py
"""
from __future__ import annotations

import json
import os
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

DESK = Path(__file__).resolve().parents[1]
ROOT = DESK.parent.parent
for _p in (str(DESK), str(DESK / "research"), str(ROOT)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from libs.data import dataset_use as U  # noqa: E402

ACQUIRED = DESK / "data" / "acquired" / "registry.json"
AXES = DESK / "data" / "axes"
LAKE = DESK / "data" / "lake" / "series"
REPORT = DESK / "reports" / "DATASET_USE.json"
#: The small COMMITTED copy (reports/ is gitignored): counts plus the oldest unfed ids, so the
#: cloud and the CRO pass can read D18 without the box.
DIGEST = DESK / "data" / "digests" / "dataset_use_digest.json"
DIGEST_LIST = 200


def universe(acquired: Path = ACQUIRED, axes: Path = AXES, lake: Path = LAKE) -> dict[str, str]:
    """dataset id -> kind, for everything on disk."""
    out: dict[str, str] = {}
    try:
        reg = json.loads(acquired.read_text("utf-8"))
        for name in (reg.get("series") or {}):
            out[f"acquired:{name}"] = "acquired"
    except (OSError, ValueError, AttributeError):
        pass
    for p in sorted(axes.glob("*.json")) if axes.exists() else []:
        out[f"axis:{p.stem}"] = "axis"
    if lake.exists():
        for p in sorted(lake.iterdir()):
            if p.suffix in (".csv", ".parquet") and not p.name.startswith("."):
                out[f"lake:{p.stem}"] = "lake"
    return out


def build(now: datetime | None = None, *, use_root: Path | None = None,
          acquired: Path = ACQUIRED, axes: Path = AXES, lake: Path = LAKE) -> dict[str, Any]:
    now = now or datetime.now(UTC)
    held = universe(acquired, axes, lake)
    reads = U.census(use_root, now=now)
    rows: list[dict[str, Any]] = []
    for ds, kind in sorted(held.items()):
        e = reads.get(ds)
        if e and e["live_consumers"] > 0:
            status = "FED"
        elif e:
            status = "STALE"
        else:
            status = "UNFED"
        rows.append({"dataset": ds, "kind": kind, "status": status,
                     "uses": (e or {}).get("uses", []),
                     "consumers": sorted((e or {}).get("consumers", {}))})
    by_kind: dict[str, dict[str, int]] = {}
    for r in rows:
        k = by_kind.setdefault(r["kind"], {"held": 0, "fed": 0, "unfed": 0})
        k["held"] += 1
        k["fed" if r["status"] == "FED" else "unfed"] += 1
    by_use: dict[str, int] = {u: 0 for u in U.USES}
    for r in rows:
        for u in r["uses"]:
            by_use[u] = by_use.get(u, 0) + 1
    unfed = [r for r in rows if r["status"] != "FED"]
    orphan_reads = sorted(set(reads) - set(held))
    return {
        "measured_at": now.isoformat(timespec="seconds"),
        "duty": "CRO D18 -- no unfed datasets",
        "unfed_datasets": len(unfed),
        "target": 0,
        "datasets_held": len(rows),
        "fed": len(rows) - len(unfed),
        "by_kind": by_kind,
        "fed_by_use": by_use,
        "unfed": [{"dataset": r["dataset"], "kind": r["kind"], "status": r["status"]}
                  for r in unfed],
        "fed_rows": [r for r in rows if r["status"] == "FED"],
        "reads_of_datasets_not_on_disk": orphan_reads[:200],
        "evidence": ("a recorded consumer read (libs/data/dataset_use) inside "
                     f"{U.STALE_AFTER_S // 3600}h; listing, fetching, parsing and emitting cells "
                     "are weaker states and do not count as fed"),
    }


def _atomic(path: Path, doc: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(f".tmp{os.getpid()}")
    tmp.write_text(json.dumps(doc, indent=1, default=str), "utf-8")
    os.replace(tmp, path)


def main() -> int:
    doc = build()
    _atomic(REPORT, doc)
    digest = {k: doc[k] for k in ("measured_at", "duty", "unfed_datasets", "target",
                                  "datasets_held", "fed", "by_kind", "fed_by_use", "evidence")}
    digest["unfed_first"] = doc["unfed"][:DIGEST_LIST]
    digest["report"] = "desks/mt5/reports/DATASET_USE.json"
    _atomic(DIGEST, digest)
    print(f"dataset use: {doc['fed']}/{doc['datasets_held']} fed, unfed_datasets="
          f"{doc['unfed_datasets']} (target 0); by kind {doc['by_kind']}")
    print("YIELD " + json.dumps({"targets": doc["unfed_datasets"]}))
    return 0


if __name__ == "__main__":
    sys.exit(main())
