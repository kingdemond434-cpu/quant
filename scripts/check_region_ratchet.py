"""EVERY REGION'S CELLS AND JUDGED CELLS RATCHET UP -- a region falling to zero is loud.

    python scripts/check_region_ratchet.py            # measure the ratchet, print, verdict
    python scripts/check_region_ratchet.py --json     # the artifact on stdout
    python scripts/check_region_ratchet.py --require-state   # the box gate: absence FAILS

THE DEFECT THIS CLOSES (measured 2026-09-23 on the trading box, vmi3571445).
`ATTRIBUTION_COVERAGE.json` read `UNATTRIBUTABLE 24,440 - NOT_REGIONAL 6,296 - LatAm 47 -
MENA 33 - every other region 0`, and `PACK_CELLS.json` read `0 of 14 regions holds a single
JUDGED cell`. Neither was a mining failure: 323,542 cells existed. 216,641 of them carried a
`miner:` filing prefix that `libs/research/attribution.py` read as part of the producer's NAME,
so `miner:discovery_compiler` (190,766 rows of the desk's own compiler) could not be recognised
as desk machinery and `miner:asia:rba_tables` (the Reserve Bank of Australia) could not be
recognised as Oceania. The regions were produced and then lost on a join.

A DEFECT THAT ARRIVED ONCE ARRIVES AGAIN, so the numbers are now a RATCHET and this is its fence.

WHAT FAILS, and it is deliberately the narrow set that cannot cry wolf (L1.43):

    a region that once held cells and now holds NONE      -- the exact shape of the defect
    a fall in the COUNT OF REGIONS THE DESK NAMES         -- no ratio is ever improved by
                                                             shrinking its denominator
    a fall in the TOTAL across regions, per measure       -- cells are never unmade

WHAT IS REPORTED AND NEVER FAILS: a non-zero dip in one region. The unique-cell basis is
`distinct grid_cell else content_hash` and a row's grid_cell can be filled in after birth, which
moves a count without the desk having lost ground. The fall to ZERO cannot be explained that way,
so that is the one this fence spends its authority on.

IT NEVER CAPS ANYTHING. No cell is refused, no region is throttled, no denominator is trimmed;
the artifact carries `caps_nothing: true` and `tests/test_region_ratchet.py` pins it, along with
the fact that this module cannot write the artifact it judges -- a fence that can rewrite its own
evidence can clear itself.

Artifact: `desks/mt5/reports/REGION_RATCHET.json`, written by
`desks/mt5/research/attribution_census.py` (hourly leg `attribution_census`). This fence READS
it -- it never measures the registry itself, so the fence and the organ cannot disagree.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from libs.research import attribution as A  # noqa: E402

RATCHET = ROOT / "desks" / "mt5" / "reports" / "REGION_RATCHET.json"
MEASURES = ("unique_cells", "judged_cells")


def read(path: Path) -> dict[str, Any]:
    try:
        doc = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    return doc if isinstance(doc, dict) else {}


def verdict(doc: dict[str, Any], *, require_state: bool,
            artifact: Path | None = None) -> dict[str, Any]:
    """The fence's reading. An absent artifact is UNMEASURED, which is a verdict (L1.28a).

    UNMEASURED passes in CI, where a fresh clone holds no registry and the organ has never run,
    and FAILS under `--require-state`, which is the box gate: there, an organ that produced
    nothing is an organ that did not run (L1.49).
    """
    path = artifact if artifact is not None else RATCHET
    out: dict[str, Any] = {"artifact": str(path), "caps_nothing": True,
                           "regions_named": len(A.REGIONS), "failures": [], "reported": []}
    if not doc:
        out["status"] = A.UNMEASURED
        out["why"] = (f"{A.UNMEASURED}: {path.name} is absent or unreadable -- "
                      "desks/mt5/research/attribution_census.py has not run on this host")
        if require_state:
            out["failures"].append(out["why"])
        return out
    named = int(doc.get("regions_named") or 0)
    high = int(doc.get("regions_named_high_water") or 0)
    out["regions_named_high_water"] = high
    if named < high:
        out["failures"].append(
            f"THE DESK NAMES FEWER REGIONS THAN IT DID: {named} < {high}. A region is never "
            "removed from the denominator; coverage is raised by filling regions, never by "
            "dropping them (LAWS: never reduce the denominator)")
    if named != len(A.REGIONS):
        out["reported"].append(f"the artifact names {named} regions, attribution.REGIONS names "
                               f"{len(A.REGIONS)}: the artifact is from an older build")
    measures = doc.get("measures")
    measures = measures if isinstance(measures, dict) else {}
    for name in MEASURES:
        row = measures.get(name)
        if not isinstance(row, dict):
            out["reported"].append(f"{A.UNMEASURED}: the ratchet carries no `{name}` measure")
            continue
        fell = [str(r) for r in (row.get("fell_to_zero") or [])]
        if fell:
            out["failures"].append(
                f"{name}: region(s) that once held cells now hold NONE: {', '.join(fell)}. A "
                "region with no cells cannot contribute an edge however deep its mining goes")
        if row.get("total_fell"):
            out["failures"].append(
                f"{name}: the total across regions fell to {row.get('total')} from a high-water "
                f"mark of {row.get('total_high_water')}; cells are never unmade")
        for dip in (row.get("regressions") or []):
            if isinstance(dip, dict):
                out["reported"].append(
                    f"{name}: {dip.get('region')} {dip.get('now')} < high-water "
                    f"{dip.get('high_water')} (reported, not fatal: the unique-cell basis can "
                    "move under a row without ground being lost)")
        raw_sp = row.get("spread")
        sp: dict[str, Any] = raw_sp if isinstance(raw_sp, dict) else {}
        out[f"{name}_spread"] = {k: sp.get(k) for k in
                                 ("regions_holding", "regions_named", "min", "median", "max",
                                  "evenness", "total", "regions_empty")}
    out["status"] = "BREACH" if out["failures"] else "OK"
    return out


def render(v: dict[str, Any]) -> str:
    lines = [f"region ratchet: {v['status']} -- {v['regions_named']} regions named, "
             f"high-water {v.get('regions_named_high_water', v['regions_named'])}"]
    for name in MEASURES:
        sp = v.get(f"{name}_spread")
        if sp:
            lines.append(f"  {name:<13} {sp.get('regions_holding')}/{sp.get('regions_named')} "
                         f"regions hold cells, total {sp.get('total')}, min {sp.get('min')} "
                         f"median {sp.get('median')} max {sp.get('max')}, evenness "
                         f"{sp.get('evenness')}")
            empty = sp.get("regions_empty") or []
            if empty:
                lines.append(f"                EMPTY: {', '.join(str(e) for e in empty)}")
    for line in v.get("reported") or []:
        lines.append(f"  reported  {line}")
    for line in v.get("failures") or []:
        lines.append(f"  FAIL      {line}")
    if v.get("why") and not v.get("failures"):
        lines.append(f"  {v['why']}")
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=str(__doc__ or "").splitlines()[0])
    ap.add_argument("--json", action="store_true", help="print the verdict as JSON")
    ap.add_argument("--require-state", action="store_true",
                    help="an absent ratchet FAILS (the box gate, never a fresh clone)")
    ap.add_argument("--artifact", type=Path, default=RATCHET)
    args = ap.parse_args(argv)
    v = verdict(read(args.artifact), require_state=bool(args.require_state),
                artifact=args.artifact)
    print(json.dumps(v, indent=1, default=str) if args.json else render(v))
    return 1 if v["failures"] else 0


if __name__ == "__main__":                       # pragma: no cover
    raise SystemExit(main())
