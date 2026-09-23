"""Force cells into every EMPTY alpha cluster -- or name the exact artifact that makes it impossible.

THE BREADTH BOTTLENECK IS NOT EFFORT, AND MEASURING IT SETTLED AN ARGUMENT THE DESK HAS BEEN
HAVING WITH ITSELF FOR WEEKS. `EFFECTIVE_BREADTH` reads 4 of 15 clusters occupied and n_eff ~5.7
against 50 nominal sleeves, and the standing assumption was that exploration was underfunded. It
is not. Measured 2026-09-15, the eleven empty clusters split into three completely different
problems that were being treated as one:

    ATTACKED AND NOTHING SURVIVED   relative_value has 1,596 docket cells and zero certificates.
                                    volatility_transition 231, cross_asset_lead_lag 206,
                                    event_surprise 113. These clusters do not need more cells.
                                    Whatever is wrong is in the mechanism or in the gates, and
                                    another thousand cells buys nothing but multiplicity charge.

    REACHABLE AND NEVER GENERATED   cross_sectional_fx has ZERO cells and TWO registered families
                                    that classify into it (`cross_sectional`, `style_premia`).
                                    Nothing mints them. That is a pure wiring gap and it is what
                                    this file closes.

    STRUCTURALLY UNREACHABLE        execution_entry, news_reaction and options_implied have NO
                                    registered family that classifies into them at all. The desk
                                    declared fifteen clusters and built families for eleven.
                                    No amount of search reaches these: the missing artifact is a
                                    FAMILY MODULE, and saying so is the remedy.

The third case is why this file refuses to fake anything. Minting `event_reaction` cells and
calling them news_reaction would make the register green and change nothing about the book -- the
cluster would still be empty, and the next session would have to rediscover why. An unreachable
cluster is reported with the file that must exist for it to become reachable.

    python desks/mt5/research/empty_cluster_forcer.py            # report only
    python desks/mt5/research/empty_cluster_forcer.py --donate   # mint and donate the cells
"""
from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

BASE = Path(__file__).resolve().parents[1]
ROOT = BASE.parent.parent
for _p in (str(BASE), str(BASE / "research"), str(ROOT)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

BREADTH = BASE / "reports" / "EFFECTIVE_BREADTH.json"
MANDATE = BASE / "reports" / "BREADTH_MANDATE.json"
UNIVERSE = BASE / "data" / "universe" / "universe.json"
SEAT = BASE / "data" / "intelligence" / "breadth"
OUT = BASE / "reports" / "EMPTY_CLUSTER_FORCER.json"

#: Cells minted per reachable empty cluster per pass. Small on purpose -- the point is that the
#: attempt HAPPENS every hour and accumulates, not that one pass floods the docket. Trial count
#: is a shared cost and a flood raises the bar for every other cell the desk is testing.
CELLS_PER_CLUSTER = 6

#: Instruments a forced cell is minted on, in order. The book's own liquid ground first: a
#: cross-sectional FX cell on an exotic nobody quotes tightly is a cell that cannot survive costs
#: whatever its signal does.
PREFERRED = ("EURUSD", "GBPUSD", "USDJPY", "AUDUSD", "USDCAD", "EURJPY", "GBPJPY", "AUDJPY",
             "EURGBP", "XAUUSD", "XAGUSD", "NZDUSD")

#: What must EXIST for a cluster with no family to become reachable. Named per cluster, because
#: "write a family" is not a remedy and `desks/mt5/mt5desk/family_news_reaction.py` is.
MISSING_ARTIFACT = {
    "execution_entry": ("desks/mt5/mt5desk/family_execution_entry.py -- a family whose signal is "
                        "the ENTRY MECHANICS rather than the direction: the same directional "
                        "thesis entered on a pullback, at a level, or on a retest, scored "
                        "against entering at market. The desk already measures the raw material "
                        "(unfilled_fork splits TOUCHED from NEVER_REACHED, and markout prices "
                        "the entry) and no family consumes it."),
    "news_reaction": ("desks/mt5/mt5desk/family_news_reaction.py -- distinct from "
                      "`event_reaction`, which classifies into event_surprise: that family "
                      "trades the SCHEDULED release, this one trades the UNSCHEDULED headline, "
                      "whose arrival time is itself the signal. The 3,854 STRUCTURED_CB_SPEECH "
                      "cells minted on 2026-09-15 are its input and currently route to "
                      "event_reaction, which is the wrong clock."),
    "options_implied": ("NO ARTIFACT MAKES THIS REACHABLE ON THIS ACCOUNT. Fusion quotes no "
                        "options on any instrument in the universe registry, so there is no "
                        "implied surface to trade and no implied series to condition on. This "
                        "cluster is UNREACHABLE BY VENUE, not unattempted, and the honest "
                        "disposition is to say so rather than to leave it looking like a gap "
                        "somebody forgot. Reaching it needs a venue change, which is the "
                        "principal's decision and not a research task."),
}


def _read(p: Path, default: Any = None) -> Any:
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return default if default is not None else {}


#: Cluster -> the PROPOSER that owns it, for clusters no donated cell can reach. A family needing
#: a peer series, a driver or a COT print cannot be built from a donated row with family defaults,
#: so its cluster is reached by a proposer that supplies the input -- and naming that proposer is
#: the remedy, where "no family reaches it" would have been wrong.
CLUSTER_PROPOSER = {
    "cross_sectional_fx": "style_premia_sweep / a cross_sectional proposer -- the families exist "
                          "(cross_sectional, style_premia) and need a PEER PANEL, which a donated "
                          "row with family defaults cannot supply",
    "relative_value": "cross_asset_graph and anomaly_factory (correlation_regime, pca_residual, "
                      "cross_asset_residual, triangle) -- 1,596 cells already built",
    "cross_asset_lead_lag": "cross_asset_graph and asia_transmission -- 206 cells already built",
    "positioning_flow": "the COT families (cot_positioning, cot_change_fade, cot_net_fade), which "
                        "need a COT print per bar",
    "event_surprise": "event_reaction, fed by the calendar -- 113 cells already built",
}


def _families_by_cluster() -> tuple[dict[str, list[str]], dict[str, list[str]]]:
    """(donatable, registered) families per cluster.

    TWO SETS, BECAUSE THEY ANSWER DIFFERENT QUESTIONS and conflating them made this file lie on
    its first run. `_FAMILY_VOCAB` is the compiler's PROSE phrase-map: 28 price-only families that
    can be built from a paragraph with nothing but bars. The REGISTRY is 68 families -- everything
    `families` and `families_orthogonal` expose.

    The forty in the second set and not the first are not forgotten. They need an input a donated
    row cannot carry: a peer panel, a driver series, a COT print. They are reached by PROPOSERS,
    which is why a cluster with no donatable family is not necessarily unreachable -- and saying
    "no registered family classifies into this cluster" about `cross_sectional_fx`, which has two,
    was simply false.
    """
    from libs.research.alpha_clusters import classify_family

    from research.miner_candidate_compiler import _FAMILY_VOCAB, _registered_cached
    donatable: dict[str, list[str]] = {}
    registered: dict[str, list[str]] = {}
    for fam in sorted(_FAMILY_VOCAB):
        if _registered_cached(fam):
            donatable.setdefault(str(classify_family(fam)), []).append(fam)
    try:
        from mt5desk import families, families_orthogonal
        every = {n[len("family_"):] for n in dir(families) if n.startswith("family_")}
        every |= set(families_orthogonal.ORTHOGONAL_FAMILIES)
    except Exception:
        every = set(_FAMILY_VOCAB)
    for fam in sorted(every):
        registered.setdefault(str(classify_family(fam)), []).append(fam)
    return donatable, registered


def plan() -> dict[str, Any]:
    breadth = _read(BREADTH, {})
    clusters = breadth.get("clusters") or {}
    empty = sorted(set(clusters.get("empty_in_both") or []))
    counts = (_read(MANDATE, {}) or {}).get("cluster_cell_counts") or {}
    by_cluster, registered = _families_by_cluster()
    universe = _read(UNIVERSE, {})
    symbols = [s for s in PREFERRED if s in universe]

    rows: list[dict[str, Any]] = []
    cells: list[dict[str, Any]] = []
    for c in empty:
        n = int(counts.get(c, 0))
        fams = by_cluster.get(c) or []
        reg = registered.get(c) or []
        if not fams and reg:
            # REACHABLE, BUT NOT BY A DONATED CELL. The families exist and need an input a
            # donation cannot carry, so the owner is a proposer and the remedy is to check that
            # the proposer is running -- not to write a family that already exists.
            rows.append({"cluster": c, "cells_in_docket": n, "verdict": "PROPOSER_OWNED",
                         "families": reg,
                         "owner": CLUSTER_PROPOSER.get(
                             c, "a proposer supplying this family's external input; none named"),
                         "why": (f"{len(reg)} registered famil(ies) classify here -- "
                                 f"{', '.join(reg[:4])} -- and none is donatable because each "
                                 f"needs a peer panel, driver series or external print that a "
                                 f"donated row with family defaults cannot supply.")})
            continue
        if not fams:
            rows.append({"cluster": c, "cells_in_docket": n, "verdict": "UNREACHABLE",
                         "families": [],
                         "missing_artifact": MISSING_ARTIFACT.get(
                             c, "no registered family classifies into this cluster and none is "
                                "declared; the missing artifact has not been named"),
                         "why": ("NO registered family classifies into this cluster at all -- "
                                 "not in the 28-family donation vocabulary and not in the "
                                 "68-family registry. The missing artifact is a FAMILY MODULE, "
                                 "not more compute.")})
            continue
        if n > 0:
            rows.append({"cluster": c, "cells_in_docket": n, "verdict": "ALREADY_ATTACKED",
                         "families": fams,
                         "why": (f"{n} cell(s) already target this cluster and none has "
                                 f"certified. More cells buy multiplicity charge, not breadth -- "
                                 f"whatever is wrong is in the mechanism or the gates.")})
            continue
        # REACHABLE, AND NOBODY IS MINTING. The one case this file actually fixes.
        minted = 0
        for fam in fams:
            for sym in symbols:
                if minted >= CELLS_PER_CLUSTER:
                    break
                cells.append({
                    "kind": "hypothesis", "family": fam, "symbols": [sym],
                    "source": "breadth:empty_cluster_forcer",
                    "url": "", "title": f"empty-cluster forcing: {c}",
                    "alpha_cluster": c, "mechanism_status": "NAMED",
                    "text": (f"{fam} on {sym}. FORCED BREADTH CELL for the empty alpha cluster "
                             f"{c}: the cluster is declared worth having, a registered family "
                             f"reaches it, and zero cells have ever targeted it. The desk cannot "
                             f"say a cluster is empty because the market has nothing there when "
                             f"it has never looked. A hypothesis for the ten gates, not a claim."),
                })
                minted += 1
            if minted >= CELLS_PER_CLUSTER:
                break
        rows.append({"cluster": c, "cells_in_docket": 0, "verdict": "FORCED",
                     "families": fams, "cells_minted": minted,
                     "why": (f"reachable via {', '.join(fams)} and never generated: a pure "
                             f"wiring gap, closed by minting {minted} cell(s) this pass")})

    census = Counter(str(r["verdict"]) for r in rows)
    return {
        "generated_utc": datetime.now(UTC).isoformat(timespec="seconds"),
        "rule": ("an empty cluster is one of three things and they need three different "
                 "remedies: ATTACKED (the gates or the mechanism), REACHABLE-BUT-UNMINTED (a "
                 "wiring gap, closed here), or UNREACHABLE (a missing family module, named)."),
        "n_empty": len(empty),
        "census": dict(census),
        "cells_per_cluster": CELLS_PER_CLUSTER,
        "n_cells_minted": len(cells),
        "symbols": symbols,
        "clusters": rows,
        "cells": cells,
    }


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--donate", action="store_true", help="write the minted cells to the seat")
    args = ap.parse_args(argv)

    doc = plan()
    cells = doc.pop("cells")
    if args.donate and cells:
        SEAT.mkdir(parents=True, exist_ok=True)
        stamp = datetime.now(UTC).strftime("%Y%m%dT%H")
        out = SEAT / f"empty_cluster_{stamp}.json"
        tmp = out.with_suffix(".tmp")
        tmp.write_text(json.dumps(cells, indent=1), encoding="utf-8")
        tmp.replace(out)
        doc["donated_to"] = str(out)
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(doc, indent=1), encoding="utf-8")

    print(f"empty-cluster forcer: {doc['n_empty']} empty cluster(s) -> {doc['census']}")
    for r in doc["clusters"]:
        mark = {"FORCED": "  FORCED ", "UNREACHABLE": "  NO FAM ",
                "PROPOSER_OWNED": "  propsr ",
                "ALREADY_ATTACKED": "  attackd"}.get(str(r["verdict"]), "  ?      ")
        print(f"{mark} {r['cluster']!s:24} {r['cells_in_docket']:6} in docket  "
              f"{','.join(r['families'])[:34]}")
    for r in doc["clusters"]:
        if r["verdict"] == "UNREACHABLE":
            print(f"\n  {r['cluster']}: {str(r['missing_artifact'])[:150]}")
    if doc.get("donated_to"):
        print(f"\n  {doc['n_cells_minted']} cell(s) donated -> {doc['donated_to']}")
    print(f"  -> {OUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
