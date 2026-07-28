"""UNOBSERVED OBSERVABLES -- unknown-unknowns we ALREADY OWN and have never looked at.

WHY THE EXISTING BLIND-SPOT STACK IS NOT ENOUGH. blind_spot.py, blindspot_prober.py,
info_class_map.py and feature_library's coverage % all find KNOWN unknowns: empty cells in a map
the desk drew. Kimi Wave 3 hunts unknown-unknowns but needs an LLM, credit, and trust in its
self-report. None of them can find a dimension that was never mapped.

THIS FINDS ONE CLASS OF GENUINE UNKNOWN-UNKNOWN MECHANICALLY: fields sitting in data this desk
ALREADY COLLECTS that no feature, screen or hypothesis has ever referenced. Not "data we should
acquire" -- data we possess, pay to store, and have never once looked at.

That is the cheapest possible frontier. Acquisition cost is zero, provenance is known, history is
already accumulating, and nobody else's coverage map has any bearing on it. A field collected for
two years and never read is a two-year head start nobody knew they had.

The output is deliberately NOT a hypothesis list. An unread field is not an edge; it is a question
nobody has asked. It enters Stage-A screening like anything else.
"""
from __future__ import annotations

import json
import pathlib
from collections import Counter
from datetime import UTC, datetime

ROOT = pathlib.Path(__file__).resolve().parent.parent
OUT = ROOT / "data/unobserved_observables.json"

# fields that are plumbing, not observables -- excluded so the signal is not drowned in ids
_PLUMBING = {"ts", "date", "timestamp", "time", "updated", "id", "pool", "symbol", "asset",
             "chain", "project", "src", "source", "note", "kind", "status", "period",
             "src_ts", "row_id", "provenance", "name", "event", "mock", "seat"}


def main() -> None:
    code = ""
    for d in ("scripts", "libs"):
        for p in (ROOT / d).rglob("*.py"):
            code += p.read_text("utf-8", errors="ignore")

    rows = []
    for f in sorted((ROOT / "data").glob("*.jsonl")):
        try:
            with f.open("r", encoding="utf-8", errors="ignore") as fh:
                sample = [json.loads(l) for i, l in enumerate(fh) if l.strip() and i < 200]
        except Exception:  # noqa: BLE001
            continue
        if not sample:
            continue
        keys = Counter()
        for r in sample:
            if isinstance(r, dict):
                keys.update(r.keys())
        n = len(sample)
        for k, cnt in keys.items():
            if k in _PLUMBING or cnt < n * 0.5:
                continue
            # "referenced" means the field name appears anywhere in the codebase OTHER than the
            # collector that writes it -- writing a field is not reading it.
            uses = code.count(f'"{k}"') + code.count(f"'{k}'")
            if uses <= 2:                       # its own writer + maybe a schema contract
                rows.append({"file": f.name, "field": k, "coverage_pct": round(cnt / n * 100, 1),
                             "code_references": uses})

    rows.sort(key=lambda r: (r["code_references"], -r["coverage_pct"]))
    print("=== UNOBSERVED OBSERVABLES -- data we own and have never read ===")
    print("    every other blind-spot tool finds empty cells in a map the desk DREW.")
    print("    this finds dimensions that were never mapped, at zero acquisition cost.\n")
    if not rows:
        print("  none -- every collected field is referenced somewhere. That would be the first")
        print("  time this desk has had no unread data, so verify before believing it.")
    else:
        print(f"  {'file':<34}{'field':<26}{'present':>9}{'refs':>6}")
        for r in rows:
            print(f"  {r['file']:<34}{r['field']:<26}{r['coverage_pct']:>8.0f}%"
                  f"{r['code_references']:>6}")
    by_file = Counter(r["file"] for r in rows)
    print(f"\n  {len(rows)} unread fields across {len(by_file)} files.")
    if by_file:
        w, c = by_file.most_common(1)[0]
        print(f"  worst: {w} with {c} fields collected and never referenced.")
    print("\n  AN UNREAD FIELD IS NOT AN EDGE. It is a question nobody has asked, and it enters")
    print("  Stage-A screening like anything else. What makes it valuable is that acquisition")
    print("  cost is already paid, provenance is known, and history is already accumulating --")
    print("  a field collected for two years and never read is a two-year head start nobody knew")
    print("  they had.")
    OUT.write_text(json.dumps({"updated": datetime.now(tz=UTC).isoformat(),
                               "n_unread": len(rows), "fields": rows}, indent=1), "utf-8")
    print(f"\n  -> {OUT}")


if __name__ == "__main__":
    main()
