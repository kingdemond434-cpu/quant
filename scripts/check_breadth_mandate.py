"""BREADTH IS MANDATORY. An empty alpha cluster that received NO ATTEMPT is a defect.

THE LAW (principal, 2026-09-15): breadth is not a thing the desk hopes for while it optimises
something else. Every hour, every empty cluster must be ATTACKED, and a cluster nobody tried is a
defect with a name.

WHY THE EXISTING FLOORS DO NOT ALREADY DO THIS, which is the whole reason this file exists. The
research bandit floors EXPLORATION at 40% of compute and has done for weeks. It has not moved
breadth at all: `EFFECTIVE_BREADTH` still reads 4 of 15 clusters occupied and n_eff ~5.7 against
50 nominal sleeves. The reason is simple once it is stated -- EXPLORATION INSIDE AN OCCUPIED
CLUSTER IS STILL EXPLORATION. A sweep can spend every one of those compute-hours discovering its
four-hundredth session-liquidity variant and satisfy the floor completely, while eleven clusters
receive nothing. A floor on the ACTIVITY does not bind the DESTINATION.

`bandit.breadth_credit` is the other half of the same miss. It is measured and it works -- it
prices `new_mechanism` at 1.2491 and `combine_survivors` at 0.8295 -- but `new_mechanism` costs 9
declared units against 3, so a 1.5x credit spread loses to a 3x cost difference every time. A
credit that cannot outbid the cost of the thing it is trying to buy is a preference, not a floor.

SO THE MANDATE IS A FLOOR ON ATTEMPTS PER CLUSTER, and the distinction it holds is the same one
every other law on this desk holds:

    ATTEMPTED AND FAILED   cells were built for this cluster and none survived. FINE. That is a
                           measurement, and the answer to "is there an edge here" is allowed to
                           be no. It is recorded so the next session does not re-run it blind.
    NEVER ATTEMPTED        zero cells, ever, for a cluster the desk itself declared worth having.
                           A DEFECT. The desk cannot say a cluster is empty because the market
                           has nothing there when it has never looked.

n_eff RATCHETS UP AND NEVER DOWN, the same rule the coverage floors run on (L1.50). A book whose
effective breadth falls has become more concentrated, which raises the tail the allocator must
survive -- and that is measured: `pf_allocation` fails its own proof at n_eff 5.7 because the
dynamic book's drawdown probability is 0.4375. Breadth is not an aesthetic here. It is the
binding constraint on whether the desk's own allocator is allowed to deploy its book at all.

    python scripts/check_breadth_mandate.py
    python scripts/check_breadth_mandate.py --json
"""
from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
DESK = ROOT / "desks" / "mt5"
for _p in (str(ROOT), str(DESK), str(DESK / "research")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

BREADTH = DESK / "reports" / "EFFECTIVE_BREADTH.json"
DOCKET = DESK / "data" / "hypotheses" / "external_survivors.json"
OUT = DESK / "reports" / "BREADTH_MANDATE.json"
FLOOR = DESK / "data" / "breadth_floor.json"
FORCER = DESK / "reports" / "EMPTY_CLUSTER_FORCER.json"

#: Cells an empty cluster must receive per sweep before the desk may say it looked. Deliberately
#: small: the point is that the attempt HAPPENS, not that it is large. A cluster receiving three
#: cells an hour accumulates a real sample in a week, and a floor big enough to hurt would be
#: voted down by the same cost arithmetic that killed the credit.
MIN_CELLS_PER_EMPTY_CLUSTER = 3


def _read(p: Path, default: Any = None) -> Any:
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return default if default is not None else {}


#: The per-family docket census the judge-coverage leg writes every hour. THE ROOT CAUSE OF ROW 72
#: (2026-11-03): this mandate counted clusters by `json.load`-ing the WHOLE docket -- 1.82M cells
#: on the trading box -- inside a 150 s slice of the rotating fence battery. A load that size does
#: not finish there, `batteries.run_one` records TIMEOUT, and the artifact is written only at the
#: end, so BREADTH_MANDATE.json froze at 2026-10-29 16:35Z while its leg was "scheduled". The
#: judge already measures `mined` per family across that same docket, hourly, in 240 KB.
JUDGE_COVERAGE = DESK / "reports" / "JUDGE_COVERAGE.json"
#: An input older than this is a reading of a machine that stopped, not of this hour.
INPUT_MAX_AGE_H = 26.0
#: The docket fallback is read only below this size; above it the counts are UNMEASURED rather
#: than a load that cannot finish (the defect this replaces).
DOCKET_FALLBACK_MAX_BYTES = 64 * 1024 * 1024


def _age_h(stamp: Any, now: datetime | None = None) -> float | None:
    try:
        t = datetime.fromisoformat(str(stamp).replace("Z", "+00:00"))
    except (TypeError, ValueError):
        return None
    if t.tzinfo is None:
        t = t.replace(tzinfo=UTC)
    return round(((now or datetime.now(UTC)) - t).total_seconds() / 3600.0, 2)


def _counts_from_judge(doc: Any) -> tuple[dict[str, int], str] | None:
    """Cluster counts from JUDGE_COVERAGE's per-family `mined`, or None when it cannot answer."""
    try:
        from libs.research.alpha_clusters import UNCLASSIFIED, classify_family
    except Exception:
        return None
    fams = doc.get("families") if isinstance(doc, dict) else None
    if not isinstance(fams, dict) or not fams:
        return None
    counts: Counter = Counter()
    for fam, row in fams.items():
        mined = row.get("mined") if isinstance(row, dict) else None
        if not isinstance(mined, (int, float)) or mined <= 0:
            continue
        counts[str(classify_family(str(fam)) or UNCLASSIFIED)] += int(mined)
    age = _age_h(doc.get("at"))
    return dict(counts), (f"{sum(counts.values())} docket cell(s) by family from "
                          f"JUDGE_COVERAGE.json `families[*].mined` (at {doc.get('at')}, "
                          f"{age}h old)")


def _counts_from_docket() -> tuple[dict[str, int], str]:
    """The old whole-docket read, kept only for a docket small enough to finish."""
    try:
        from libs.research.alpha_clusters import UNCLASSIFIED, classify_family, classify_sleeve
    except Exception as exc:
        return {}, f"alpha_clusters unimportable: {type(exc).__name__}"
    try:
        size = DOCKET.stat().st_size
    except OSError:
        return {}, f"UNMEASURED: neither {JUDGE_COVERAGE.name} nor the docket is readable here"
    if size > DOCKET_FALLBACK_MAX_BYTES:
        return {}, (f"UNMEASURED: {JUDGE_COVERAGE.name} is absent or stale and the docket is "
                    f"{size / 1e6:.0f} MB, above the {DOCKET_FALLBACK_MAX_BYTES / 1e6:.0f} MB a "
                    f"fence pass can load")
    rows = _read(DOCKET, [])
    if not isinstance(rows, list):
        return {}, "docket is not a list of cells"
    counts: Counter = Counter()
    for r in rows:
        if not isinstance(r, dict):
            continue
        lab = None
        fam = r.get("family")
        if isinstance(fam, str) and fam:
            lab = classify_family(fam)
        if (not lab or lab == UNCLASSIFIED):
            for key in ("cell", "name", "symbol"):
                v = r.get(key)
                if isinstance(v, str) and v:
                    lab = classify_sleeve(v)
                    if lab and lab != UNCLASSIFIED:
                        break
        counts[str(lab or UNCLASSIFIED)] += 1
    return dict(counts), f"{len(rows)} docket cell(s) classified"


def _cluster_counts() -> tuple[dict[str, int], str]:
    """Docket cells per alpha cluster: the judge's hourly family census first, the docket only
    when that is absent or stale AND the docket is small enough to read inside a pass."""
    doc = _read(JUDGE_COVERAGE, {})
    age = _age_h(doc.get("at")) if isinstance(doc, dict) else None
    if age is not None and age <= INPUT_MAX_AGE_H:
        got = _counts_from_judge(doc)
        if got is not None:
            return got
    return _counts_from_docket()


def _declared_clusters() -> list[str]:
    try:
        from libs.research.alpha_clusters import CLUSTERS
        return [c.key for c in CLUSTERS]
    except Exception:
        return []


def _forcer_dispositions() -> dict[str, dict[str, Any]]:
    """What the forcer did last pass, per cluster (EMPTY_CLUSTER_FORCER.json), for the join."""
    doc = _read(FORCER, {})
    out: dict[str, dict[str, Any]] = {}
    for r in (doc.get("clusters") or []) if isinstance(doc, dict) else []:
        if isinstance(r, dict) and r.get("cluster"):
            out[str(r["cluster"])] = {k: r.get(k) for k in ("verdict", "cells_minted",
                                                           "families", "data_gap")
                                      if r.get(k) is not None}
            out[str(r["cluster"])]["at"] = doc.get("generated_utc")
    return out


def check() -> dict[str, Any]:
    breadth = _read(BREADTH, {})
    clusters = breadth.get("clusters") or {}
    declared = int(clusters.get("declared") or 0)
    occupied = sorted(set(clusters.get("occupied_either") or []))
    eff = (breadth.get("effective") or {}).get("effective_breadth")

    counts, why_counts = _cluster_counts()
    counts_measured = bool(counts)
    floor_doc = _read(FLOOR, {})
    recorded_floor = floor_doc.get("n_eff_floor")
    forcer = _forcer_dispositions()
    # EVERY DECLARED CLUSTER WITH ZERO CELLS IS JUDGED, not only the ones EFFECTIVE_BREADTH lists
    # as empty: that report is a separate leg's (alpha_breadth) and was itself 14 days old on
    # 2026-11-03, so a cluster could be never-attempted and absent from its `empty_in_both`.
    zero = {c for c in _declared_clusters() if counts_measured and int(counts.get(c, 0)) == 0}
    empty = sorted(set(clusters.get("empty_in_both") or []) | zero)
    if not declared:
        declared = len(_declared_clusters())

    rows: list[dict[str, Any]] = []
    for c in empty:
        n = int(counts.get(c, 0))
        if not counts_measured:
            rows.append({"cluster": c, "cells_in_docket": None, "verdict": "UNMEASURED",
                         "why": f"cluster cell counts are unmeasured: {why_counts}"})
        elif n >= MIN_CELLS_PER_EMPTY_CLUSTER:
            rows.append({"cluster": c, "cells_in_docket": n, "verdict": "ATTEMPTED",
                         "why": (f"{n} cell(s) target this cluster and none has certified. That "
                                 f"is a measurement -- the answer is allowed to be no.")})
        elif n > 0:
            rows.append({"cluster": c, "cells_in_docket": n, "verdict": "UNDER_FLOOR",
                         "why": (f"only {n} cell(s) against a floor of "
                                 f"{MIN_CELLS_PER_EMPTY_CLUSTER}: attempted, but not enough to "
                                 f"call the cluster looked at")})
        else:
            f = forcer.get(c) or {}
            if f.get("verdict") == "FORCED" and int(f.get("cells_minted") or 0) > 0:
                rows.append({"cluster": c, "cells_in_docket": 0, "verdict": "FORCED_PENDING",
                             "forcer": f,
                             "why": (f"zero cells in the docket yet, and the forcer minted "
                                     f"{f.get('cells_minted')} cell(s) for it at {f.get('at')} "
                                     f"via {', '.join(f.get('families') or [])}: attempted, "
                                     f"not yet compiled into the docket")})
            elif f.get("verdict") == "DATA_GAP":
                rows.append({"cluster": c, "cells_in_docket": 0, "verdict": "UNMEASURED",
                             "forcer": f,
                             "why": f"a named data gap blocks every family here: "
                                    f"{f.get('data_gap')}"})
            else:
                rows.append({"cluster": c, "cells_in_docket": 0, "verdict": "NEVER_ATTEMPTED",
                             **({"forcer": f} if f else {}),
                             "why": ("ZERO cells have ever targeted this cluster. The desk "
                                     "cannot say the market has nothing here when it has never "
                                     "looked.")})

    census = Counter(str(r["verdict"]) for r in rows)
    never = [r for r in rows if r["verdict"] == "NEVER_ATTEMPTED"]

    ratchet: dict[str, Any] = {"n_eff": eff, "floor": recorded_floor}
    if isinstance(eff, (int, float)):
        if not isinstance(recorded_floor, (int, float)):
            ratchet.update({"status": "FLOOR_SET", "why": "first measurement becomes the floor"})
        elif eff + 1e-9 < float(recorded_floor):
            ratchet.update({"status": "BREACH",
                            "why": (f"effective breadth {eff:.3f} is BELOW the recorded floor "
                                    f"{float(recorded_floor):.3f}. The book has become more "
                                    f"concentrated, which raises the tail the allocator must "
                                    f"survive -- and that is what fails its proof.")})
        else:
            ratchet.update({"status": "OK", "why": f"{eff:.3f} at or above floor "
                                                   f"{float(recorded_floor):.3f}"})
    else:
        ratchet.update({"status": "UNMEASURED",
                        "why": "EFFECTIVE_BREADTH carries no effective_breadth reading"})

    return {
        "generated_utc": datetime.now(UTC).isoformat(timespec="seconds"),
        "law": ("BREADTH IS MANDATORY. Every empty alpha cluster must receive at least "
                f"{MIN_CELLS_PER_EMPTY_CLUSTER} cells per sweep. ATTEMPTED AND FAILED is a "
                "measurement and is fine; NEVER ATTEMPTED is a defect. n_eff ratchets UP only."),
        "why_the_existing_floors_miss_it": (
            "the bandit floors EXPLORATION at 40% of compute, and exploration inside an OCCUPIED "
            "cluster is still exploration -- a sweep can satisfy the floor entirely on its "
            "four-hundredth session-liquidity variant while eleven clusters get nothing. And "
            "bandit.breadth_credit prices new_mechanism at 1.2491 against combine_survivors at "
            "0.8295, a 1.5x spread that cannot outbid a 3x declared cost difference."),
        "declared_clusters": declared,
        "occupied": occupied,
        "empty": empty,
        "cluster_cell_counts": counts,
        "counts_basis": why_counts,
        "inputs": {
            "effective_breadth": {"path": str(BREADTH), "generated_utc":
                                  breadth.get("generated_utc"),
                                  "age_h": _age_h(breadth.get("generated_utc")),
                                  "stale": (_age_h(breadth.get("generated_utc")) or 1e9)
                                  > INPUT_MAX_AGE_H},
            "judge_coverage": {"path": str(JUDGE_COVERAGE),
                               "at": (_read(JUDGE_COVERAGE, {}) or {}).get("at")},
            "forcer": {"path": str(FORCER), "clusters": len(forcer)},
            "rule": (f"an input older than {INPUT_MAX_AGE_H:g}h is named STALE here; counts "
                     "come from the judge's hourly family census, never a whole-docket load"),
        },
        "min_cells_per_empty_cluster": MIN_CELLS_PER_EMPTY_CLUSTER,
        "census": dict(census),
        "never_attempted": never,
        "ratchet": ratchet,
        "clusters": rows,
    }


def write(doc: dict[str, Any] | None = None, out: Path | None = None) -> dict[str, Any]:
    """Build (unless given) and write the mandate atomically; the forcer leg calls this hourly."""
    doc = doc if doc is not None else check()
    path = out or OUT
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(doc, indent=1), encoding="utf-8")
    tmp.replace(path)
    return doc


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--set-floor", action="store_true",
                    help="record the current n_eff as the floor it may never fall below")
    args = ap.parse_args(argv)

    doc = write()

    r = doc["ratchet"]
    if args.set_floor and isinstance(r.get("n_eff"), (int, float)):
        FLOOR.write_text(json.dumps({"n_eff_floor": r["n_eff"],
                                     "set_utc": doc["generated_utc"],
                                     "rule": "ratchets UP only (L1.50)"}, indent=1),
                         encoding="utf-8")
        print(f"floor set to {r['n_eff']}")

    if args.json:
        print(json.dumps(doc, indent=1))
        return 1 if doc["never_attempted"] else 0

    print(f"breadth mandate: {doc['declared_clusters']} declared cluster(s), "
          f"{len(doc['occupied'])} occupied, {len(doc['empty'])} empty -> {doc['census']}")
    print(f"  n_eff {r.get('n_eff')} vs floor {r.get('floor')}: {r.get('status')}")
    for row in doc["clusters"]:
        mark = {"NEVER_ATTEMPTED": "  DEFECT ", "UNDER_FLOOR": "  under  ",
                "ATTEMPTED": "  ok     ", "FORCED_PENDING": "  forced ",
                "UNMEASURED": "  unmeas "}.get(str(row["verdict"]), "  ?      ")
        print(f"{mark}{row['cluster']!s:24} {row['cells_in_docket']!s:>6} cell(s)")
    if doc["never_attempted"]:
        print(f"\n  {len(doc['never_attempted'])} cluster(s) NEVER ATTEMPTED. The desk cannot "
              f"call a cluster empty it has never looked at.")
    print(f"  -> {OUT}")
    return 1 if (doc["never_attempted"] or r.get("status") == "BREACH") else 0


if __name__ == "__main__":
    raise SystemExit(main())
