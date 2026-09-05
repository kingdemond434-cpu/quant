#!/usr/bin/env python3
"""Generated truth about point-in-time provenance: what fraction of ingested rows carry it.

    python scripts/check_pit.py                 # print the census, write reports/PIT_CENSUS.json
    python scripts/check_pit.py --floor 0.10    # exit 1 if the stamped fraction fell below

The doctrine names the fields; this measures them. Per source, so the sources whose ingestor
has not been moved onto `libs.data.pit.stamp` are listed by name rather than averaged away.
The floor RATCHETS: the high-water mark is stored and the check refuses a regression, exactly as
the bar-history floor does.
"""
from __future__ import annotations

import argparse
import glob
import json
import sys
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from libs.data.pit import census  # noqa: E402

INTEL = ROOT / "desks" / "mt5" / "data" / "intelligence"
OUT = ROOT / "desks" / "mt5" / "reports" / "PIT_CENSUS.json"
HIGH_WATER = ROOT / "desks" / "mt5" / "data" / "pit_high_water.json"


def _rows(path: Path) -> list:
    try:
        d = json.loads(path.read_text("utf-8"))
    except (OSError, ValueError):
        return []
    return d if isinstance(d, list) else (d.get("discoveries") or d.get("rows") or [])


def run() -> dict:
    per_source: dict[str, dict] = {}
    all_rows: list[dict] = []
    for src_dir in sorted(p for p in INTEL.iterdir() if p.is_dir()) if INTEL.exists() else []:
        files = sorted(glob.glob(str(src_dir / "discoveries_*.json")))[-3:]
        rows = [r for f in files for r in _rows(Path(f)) if isinstance(r, dict)]
        if not rows:
            continue
        per_source[src_dir.name] = census(rows)
        all_rows.extend(rows)
    total = census(all_rows)
    doc = {"generated_utc": datetime.now(tz=UTC).isoformat(), "total": total,
           "per_source": per_source,
           "unstamped_sources": sorted(s for s, c in per_source.items()
                                       if (c["stamped_frac"] or 0.0) < 0.5)}
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(doc, indent=1), "utf-8")
    return doc


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--floor", type=float, default=None,
                    help="minimum stamped fraction; defaults to the stored high-water mark")
    a = ap.parse_args()
    doc = run()
    frac = doc["total"]["stamped_frac"] or 0.0
    try:
        hw = float(json.loads(HIGH_WATER.read_text("utf-8")).get("stamped_frac", 0.0))
    except (OSError, ValueError):
        hw = 0.0
    floor = a.floor if a.floor is not None else hw
    print(f"PIT census: {doc['total']['rows']} rows across {len(doc['per_source'])} sources; "
          f"stamped {frac:.1%} (high-water {hw:.1%}, floor {floor:.1%})")
    for s in doc["unstamped_sources"][:20]:
        print(f"  unstamped: {s}  ({doc['per_source'][s]['stamped_frac']:.0%})")
    if frac > hw:
        HIGH_WATER.parent.mkdir(parents=True, exist_ok=True)
        HIGH_WATER.write_text(json.dumps({"stamped_frac": frac,
                                          "at": doc["generated_utc"]}), "utf-8")
    if frac + 1e-9 < floor:
        print(f"PIT REGRESSION: stamped fraction {frac:.1%} below floor {floor:.1%}")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
