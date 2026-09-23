"""RE-JUDGE STATISTICAL_ONLY REJECTS WHOSE MECHANISM THE DESK CAN NOW NAME.

A gate-1 terminal reject says "no economic mechanism is NAMED for this cell" -- a verdict about
the desk's mechanism map at judgment time, not about the market. When the map grows (2026-08-27:
behavioural-flow causes -- forced-seller drawdown, chase exhaustion, opening-gap failed auction,
scheduled session/calendar flow, volatility-regime transition), every historical reject whose
feature now carries a named cause deserves to re-enter the SAME ten gates. Nothing here lowers
a bar: the cells still face the full gauntlet; only their gate-1 status is re-derived from the
same map every fresh discovery uses (research/edge_search.mechanism_for_feature).

Usage:
    python scripts/requeue_named_mechanisms.py <docket_snapshot.json>

Writes data/hypotheses/requeue_named.json (consumed by merge_hypotheses as a source; hourly
runs skip it once its mtime predates the pipeline, so it merges exactly once per rebuild).
"""
from __future__ import annotations

import json
import sys
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "desks" / "mt5" / "data" / "hypotheses" / "requeue_named.json"

sys.path.insert(0, str(ROOT / "desks" / "mt5" / "research"))
sys.path.insert(0, str(ROOT / "desks" / "mt5"))


def main() -> int:
    if len(sys.argv) != 2:
        print(__doc__)
        return 2
    rows = json.loads(Path(sys.argv[1]).read_text("utf-8"))
    from edge_search import mechanism_for_feature

    flips, still, nonfeature = [], 0, 0
    seen: set[str] = set()
    for r in rows:
        if r.get("family") != "discovered" or r.get("mechanism_status") != "STATISTICAL_ONLY":
            continue
        feature = str((r.get("params") or {}).get("feature") or "")
        if not feature:
            nonfeature += 1
            continue
        status, note = mechanism_for_feature(feature)
        if status != "NAMED":
            still += 1
            continue
        key = json.dumps({"s": r.get("symbol") or r.get("sym"), "f": "discovered",
                          "p": r.get("params")}, sort_keys=True, default=str)
        if key in seen:
            continue
        seen.add(key)
        flips.append({**r, "mechanism_status": status, "mechanism_note": note,
                      "requeued_at": datetime.now(UTC).isoformat(timespec="seconds"),
                      "requeue_reason": ("mechanism map extension named this feature's cause; "
                                         "re-entering the identical ten gates")})

    kinds = Counter(str((r.get("params") or {}).get("feature", "")).split("_")[0]
                    for r in flips)
    OUT.write_text(json.dumps(flips, indent=1, default=str), "utf-8")
    print(f"requeue: {len(flips)} of {len(rows)} rows flip to NAMED under the current map "
          f"({still} remain STATISTICAL_ONLY -- honestly; {nonfeature} carried no feature)")
    print(f"  by feature stem: {dict(kinds.most_common(10))}")
    print(f"  -> {OUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
