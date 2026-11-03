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

THE THIRD CASE IS NOW TWO FAMILIES AND A CLASSIFICATION (row 72, 2026-11-03). `jump` -- the
calendar-free discontinuity family -- classifies into news_reaction; `entry_alpha` (a resting-limit
re-entry of a market-entry base) reaches execution_entry; `implied_vol` (VIX against the index's
own realised vol, from LIVE's FRED pull) reaches options_implied. `mt5desk/families_cluster_reach`
holds both. A cluster with ZERO cells and a buildable forcing family is FORCED here on the
family's explicit parameters (an EXACT_RECIPE row); a forcing family whose input this host cannot
read is DATA_GAP with the path named, never minted blind and never reported clean.

THIS LEG ALSO WRITES THE MANDATE. `BREADTH_MANDATE.json` was written only by a fence in the
rotating battery, which loaded the whole 1.8M-cell docket inside a 150 s slice and timed out
before writing -- the file froze on 2026-10-29 while this leg ran every hour. The mandate now
counts from JUDGE_COVERAGE's family census and is written here, before the plan reads it and again
after, so its FORCED_PENDING rows name what this pass minted.

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


def _testable(families: list[str]) -> tuple[list[str], dict[str, str]]:
    """(families the SEALED gauntlet can build, {family: why not} for the rest).

    A registered family is not a testable one. `research/gauntlet_buildability` reads the sealed
    `build_cell` and measured three families it calls with their data input None -- `lead_lag`
    (no driver), `event_reaction` (a bare index where it reads event mappings), `execution_state`
    (no surface) -- so a cluster "owned" by those has cells that are judged as a market "no" the
    market never gave. An unimportable probe marks every family testable (L1.28a)."""
    try:
        from research.gauntlet_buildability import BUILDABLE, family_verdict
    except Exception:
        return list(families), {}
    ok: list[str] = []
    bad: dict[str, str] = {}
    for fam in families:
        verdict, why = family_verdict(fam)
        if verdict == BUILDABLE:
            ok.append(fam)
        else:
            bad[fam] = f"{verdict}: {why}"
    return ok, bad


def _symbols_for(family: str, universe: dict[str, Any], turn: int) -> list[str]:
    """Where a forced cell of `family` is minted this hour: a ROTATING window over every
    hypothesis-lane instrument with bars, least-judged-for-this-family first.

    It was the fixed twelve-name PREFERRED tuple, so a forced cluster was attempted on the same
    twelve instruments forever and nowhere else. The count per pass is unchanged
    (CELLS_PER_CLUSTER); the window slides one width per hour, so a lap reaches the whole lane.
    PREFERRED stays as the fallback when the lane cannot be read here."""
    try:
        from research.breadth_rotation import hypothesis_symbols, orthogonal_ring, rotating_window
        lane = [s for s in hypothesis_symbols() if not universe or s in universe]
        if lane:
            return rotating_window(orthogonal_ring(lane, family), CELLS_PER_CLUSTER, turn=turn)
    except Exception:
        pass
    return [s for s in PREFERRED if s in universe]


#: Clusters whose reach is a NAMED forcing family: minted on explicit parameters whenever the
#: cluster holds zero cells. `params(turn, i)` -> the i-th cell's params; `symbols` -> where.
ENTRY_OFFSETS = (0.25, 0.5, 1.0)
IMPLIED_MODES = ("harvest", "stress")
JUMP_MODES = ("continue", "revert")


def _mandate_module() -> Any:
    import importlib.util
    path = ROOT / "scripts" / "check_breadth_mandate.py"
    spec = importlib.util.spec_from_file_location("check_breadth_mandate", path)
    if spec is None or spec.loader is None:
        raise ImportError(f"cannot load {path}")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _forced_cells(cluster: str, universe: dict[str, Any], turn: int
                  ) -> tuple[str, list[dict[str, Any]], str] | None:
    """(family, cells, data_gap) for a cluster with a named forcing family, or None.

    `data_gap` non-empty means the family's input is unreadable on this host and nothing is
    minted -- the cluster is UNMEASURED with that gap named, never NEVER_ATTEMPTED, never clean."""
    from mt5desk import families_cluster_reach as reach
    picks: list[tuple[str, dict[str, Any]]] = []
    if cluster == "execution_entry":
        fam = "entry_alpha"
        syms = _symbols_for(fam, universe, turn)
        for i, sym in enumerate(syms[:CELLS_PER_CLUSTER]):
            base = reach.ENTRY_BASES[(turn + i) % len(reach.ENTRY_BASES)]
            off = ENTRY_OFFSETS[(turn + i) % len(ENTRY_OFFSETS)]
            picks.append((sym, {"base_family": base, "offset_atr": off, "wait_bars": 4}))
    elif cluster == "options_implied":
        fam = "implied_vol"
        gaps: list[str] = []
        for series, unders in reach.IMPLIED_UNDERLYINGS.items():
            ok, why = reach.source_state(series)
            if not ok:
                gaps.append(why)
                continue
            for sym in unders:
                if universe and sym not in universe:
                    continue
                for mode in IMPLIED_MODES:
                    picks.append((sym, {"vol_series": series, "mode": mode}))
        if not picks:
            return fam, [], ("no free implied-vol series is readable on this host -- "
                             + "; ".join(gaps[:1]) + " (LIVE's FRED pull registers VIXCLS in "
                             "data/data_registry.json; the box's copy is the source)")
        start = (turn * CELLS_PER_CLUSTER) % len(picks)
        picks = (picks[start:] + picks[:start])[:CELLS_PER_CLUSTER]
    elif cluster == "news_reaction":
        fam = "jump"
        syms = _symbols_for(fam, universe, turn)
        picks = [(sym, {"mode": JUMP_MODES[(turn + i) % 2]})
                 for i, sym in enumerate(syms[:CELLS_PER_CLUSTER])]
    else:
        return None
    cells = [{
        "kind": "hypothesis", "family": fam, "symbols": [sym], "params": params,
        "source": "breadth:empty_cluster_forcer", "url": "",
        "title": f"empty-cluster forcing: {cluster}", "alpha_cluster": cluster,
        "mechanism_status": "NAMED",
        "mechanism": (f"forced breadth cell for the never-attempted cluster {cluster}: "
                      f"{fam} on {sym} with {params}"),
        "text": (f"{fam} on {sym} ({params}). FORCED BREADTH CELL for the alpha cluster "
                 f"{cluster}, which held ZERO docket cells. A hypothesis for the ten gates, "
                 f"not a claim."),
    } for sym, params in picks]
    return fam, cells, ""


def plan(mandate: dict[str, Any] | None = None) -> dict[str, Any]:
    breadth = _read(BREADTH, {})
    clusters = breadth.get("clusters") or {}
    mdoc = mandate if mandate is not None else (_read(MANDATE, {}) or {})
    # The mandate's `empty` already unions EFFECTIVE_BREADTH's empty set with every declared
    # cluster holding zero cells, so a stale breadth report cannot hide a never-attempted one.
    empty = sorted(set(clusters.get("empty_in_both") or []) | set(mdoc.get("empty") or []))
    counts = mdoc.get("cluster_cell_counts") or {}
    by_cluster, registered = _families_by_cluster()
    universe = _read(UNIVERSE, {})
    turn = int(datetime.now(UTC).timestamp() // 3600)
    symbols_used: set[str] = set()

    rows: list[dict[str, Any]] = []
    cells: list[dict[str, Any]] = []
    for c in empty:
        n = int(counts.get(c, 0))
        # Forced only on a MEASURED zero: with no counts the mandate could not read the docket,
        # and an unmeasured cluster is not a never-attempted one (L1.28a).
        forced = _forced_cells(c, universe, turn) if (counts and n == 0) else None
        if forced is not None:
            fam, fcells, gap = forced
            verdict, why = family_verdict_of(fam)
            if gap:
                rows.append({"cluster": c, "cells_in_docket": 0, "verdict": "DATA_GAP",
                             "families": [fam], "cells_minted": 0, "data_gap": gap,
                             "why": f"{fam} reaches this cluster and its input is unreadable "
                                    f"here; nothing minted, the gap is named: {gap}"})
                continue
            if verdict == "BUILDABLE" and fcells:
                cells.extend(fcells)
                symbols_used.update(s for cell in fcells for s in cell["symbols"])
                rows.append({"cluster": c, "cells_in_docket": 0, "verdict": "FORCED",
                             "families": [fam], "cells_minted": len(fcells),
                             "why": (f"zero cells ever; {fam} reaches it and the sealed "
                                     f"gauntlet builds it ({why}); {len(fcells)} cell(s) "
                                     f"minted on explicit params this pass")})
                continue
        fams = by_cluster.get(c) or []
        reg = registered.get(c) or []
        testable, untestable = _testable(reg)
        if reg and not testable:
            # REGISTERED, AND NOT ONE OF THEM TESTABLE BY THE SEALED JUDGE. Every cell any
            # producer mints here builds with no signals, so more cells buy multiplicity charge
            # and no information. The remedy is a sealed-gauntlet branch (principal-gated), named.
            rows.append({"cluster": c, "cells_in_docket": n,
                         "verdict": "BLOCKED_BY_SEALED_GAUNTLET", "families": reg,
                         "untestable": untestable,
                         "why": ("every registered family of this cluster is one the sealed "
                                 "external_gauntlet.build_cell cannot supply the data input of; "
                                 "its cells are judged with that input None and return no "
                                 "signals. Reaching this cluster needs a build_cell branch, "
                                 "which is a sealed edit and the principal's decision.")})
            continue
        if not fams and reg:
            # REACHABLE, BUT NOT BY A DONATED CELL. The families exist and need an input a
            # donation cannot carry, so the owner is a proposer and the remedy is to check that
            # the proposer is running -- not to write a family that already exists.
            rows.append({"cluster": c, "cells_in_docket": n, "verdict": "PROPOSER_OWNED",
                         "untestable": untestable,
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
        for fam in [f for f in fams if f in testable]:
            for sym in _symbols_for(fam, universe, turn):
                symbols_used.add(sym)
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
        "symbols": sorted(symbols_used),
        "symbol_rotation": ("a window of CELLS_PER_CLUSTER over every hypothesis-lane "
                            "instrument, least-judged first, one width further per hour"),
        "clusters": rows,
        "cells": cells,
    }


def family_verdict_of(family: str) -> tuple[str, str]:
    """The sealed gauntlet's buildability verdict; an unimportable probe is UNMEASURED."""
    try:
        from research.gauntlet_buildability import family_verdict
        return family_verdict(family)
    except Exception as exc:
        return "UNMEASURED", f"gauntlet_buildability unimportable: {type(exc).__name__}"


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--donate", action="store_true", help="write the minted cells to the seat")
    args = ap.parse_args(argv)

    # THE MANDATE FIRST, so the plan reads this hour's counts and the artifact moves every pass.
    try:
        mandate_mod = _mandate_module()
        mandate: dict[str, Any] | None = mandate_mod.write()
    except Exception as exc:
        mandate_mod, mandate = None, None
        print(f"breadth mandate NOT written: {type(exc).__name__}: {exc}")
    doc = plan(mandate)
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
    tmp_out = OUT.with_suffix(".tmp")
    tmp_out.write_text(json.dumps(doc, indent=1), encoding="utf-8")
    tmp_out.replace(OUT)
    # AND AGAIN AFTER, so FORCED_PENDING / DATA_GAP in the mandate name THIS pass's dispositions.
    if mandate_mod is not None:
        try:
            mandate_mod.write()
        except Exception as exc:
            print(f"breadth mandate re-write failed: {type(exc).__name__}: {exc}")

    print(f"empty-cluster forcer: {doc['n_empty']} empty cluster(s) -> {doc['census']}")
    for r in doc["clusters"]:
        mark = {"FORCED": "  FORCED ", "UNREACHABLE": "  NO FAM ", "DATA_GAP": "  DATAGAP",
                "PROPOSER_OWNED": "  propsr ", "BLOCKED_BY_SEALED_GAUNTLET": "  SEALED ",
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
