#!/usr/bin/env python3
"""THE ASYMMETRY LEDGER -- which of the desk's sources anyone else could have, and how deep we are.

WHY IT IS SEPARATE FROM info_class_map.py. That organ maps MODALITY x ACCESS and answers "has the
desk visited this carrier". It is a breadth map and it is complete on its own axis. It also files
`exchange_api_ohlcv` and self-recorded `orderbook_l2` identically as "covered", when every
participant on earth holds the first byte-for-byte and nobody holds the second. A map that cannot
separate those two will keep funding work on information already in the price.

This ledger adds the axis that decides edge: WHY A COMPETITOR CANNOT HAVE IT, and how far the desk
has actually mined it. Both are needed. Twenty sources at depth 1 is less knowledge than three at
depth 5, and a breadth-only count makes the first look better.

THE RANKING IT PRODUCES IS THE POINT. `shallow_gold` -- high asymmetry, low depth -- is where the
expensive half of the problem is already solved and the cheap half is not. Acquiring another
asymmetric source while an existing one sits at depth 1 grows the headline count and SHRINKS
realised asymmetry, which is the failure this exists to make visible.

CLAIMS EXPIRE. A RECONSTRUCTIBLE advantage lasts until somebody productises it -- the desk's own
graveyard carries vendor-replacement entries that are exactly that transition. Every claim has a
verified date and a half-life, and a stale one reports as UNVERIFIED rather than continuing to be
believed. An asymmetry claim nobody has re-checked is the desk's "not measured = fine" failure
applied to the one asset that supposedly justifies the enterprise.

Read-only. Writes one artifact. No network, no keys.
"""
from __future__ import annotations

import json
import sys
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from libs.data.asymmetry import (  # noqa: E402
    ASYMMETRY_CLASSES,
    DEPTH_LEVELS,
    AsymmetrySource,
    Portfolio,
)

REPORT = ROOT / "data/asymmetry_ledger.json"

#: THE DESK'S ACTUAL SOURCES, graded honestly. Depth is what has been BUILT, not what is planned.
#: Where a grade is uncomfortable it is left uncomfortable: the ledger is worthless if it flatters.
SOURCES = (
    # ---------------------------------------------------------------- genuinely exclusive
    AsymmetrySource(
        name="self_recorded_l2_tape", asymmetry="EXCLUSIVE", depth=2, verified="2026-08-03",
        why_not_replicable=(
            "15-second L2 depth + trades recorded continuously across three venues. Historical "
            "order-book state is NOT republished by the venues and no vendor sells this "
            "granularity for these pairs at any price -- once a second passes unrecorded it is "
            "destroyed at source. A competitor starting today begins their history today."),
        note="8.2GB and counting. THE desk's one irreplaceable asset."),
    AsymmetrySource(
        name="own_execution_fills", asymmetry="EXCLUSIVE", depth=0, verified="2026-08-03",
        why_not_replicable=(
            "our own fills, queue positions and realised slippage. Nobody else can observe them, "
            "and they are the only ground truth for a cost model."),
        note="DEPTH 0 AND HONEST: zero fills exist. Cannot rise until the desk trades."),
    AsymmetrySource(
        name="negative_knowledge_graveyard", asymmetry="EXCLUSIVE", depth=4, verified="2026-08-03",
        why_not_replicable=(
            "420 screened candidates with recorded death mechanisms. Nobody publishes what did "
            "NOT work, so this cannot be bought or scraped -- it is bought only with the same "
            "compute we already spent."),
        note="The most under-rated asset here: it is what stops the desk re-testing dead ground."),

    # ------------------------------------- reconstructible: bought with engineering, not money
    AsymmetrySource(
        name="wallet_entity_graph", asymmetry="RECONSTRUCTIBLE", depth=1, verified="2026-08-03",
        why_not_replicable=(
            "chain data is public and free; the CLUSTERING is not. Mapping addresses to "
            "exchange / market-maker / treasury / early-investor / retail entities takes "
            "heuristics, labelled seeds and sustained maintenance. Vendors sell this precisely "
            "because assembling it is the expensive part -- which is the definition of a "
            "processing asymmetry a small desk can actually win."),
        note=("THE BIGGEST OPEN GAP ON THIS AXIS. info_class_map grades it 'partial -- addresses "
              "read; clustering/identity not built', and triage #88 has it QUEUED. Depth 1.")),
    AsymmetrySource(
        name="onchain_flow_series", asymmetry="RECONSTRUCTIBLE", depth=2, verified="2026-08-03",
        why_not_replicable=(
            "stablecoin supply, reserves and throughput are readable from public RPC but only "
            "become a series if somebody records them on a clock; the history is not republished."),
        note="Collectors exist (collect_onchain_activity/metrics). Not screened."),
    AsymmetrySource(
        name="mempool_history", asymmetry="RECONSTRUCTIBLE", depth=1, verified="2026-08-03",
        why_not_replicable=(
            "pending-transaction state is observable live and is NOT archived by anyone -- "
            "history exists only for whoever recorded it, same structure as the L2 tape."),
        note="info_class_map: 'size/fees tested SCREEN-WEAK; pending-tx stream unbuilt'."),
    AsymmetrySource(
        name="liquidation_cascade_tape", asymmetry="RECONSTRUCTIBLE", depth=2,
        verified="2026-08-03",
        why_not_replicable=(
            "forced-liquidation prints are broadcast live and not served as history. Recording "
            "them yields a dataset of FORCED flow -- the one flow that persists after becoming "
            "public, because the seller has no choice."),
        note="The crypto-native mechanism most likely to survive being known."),
    AsymmetrySource(
        name="regional_language_corpus", asymmetry="RECONSTRUCTIBLE", depth=1,
        verified="2026-08-03",
        why_not_replicable=(
            "CN/KR/JP/RU/AR/PT sources are public but under-mined by English-language desks. The "
            "barrier is language coverage and sustained rotation, not access."),
        note="Frontier miners exist for 7 regions and are credit-blocked, not code-blocked."),

    # ------------------------------------------------------------------------- perishable
    AsymmetrySource(
        name="funding_at_settlement", asymmetry="PERISHABLE", depth=3, verified="2026-08-03",
        note="Public to all; only the settlement window matters. Latency race, mostly lost."),
    AsymmetrySource(
        name="listing_announcements", asymmetry="PERISHABLE", depth=2, verified="2026-08-03",
        note="Public the instant it posts. Minutes of value; run_listing_watch.py exists."),

    # ----------------------------------------------------------------------- interpretive
    AsymmetrySource(
        name="ict_pattern_family", asymmetry="INTERPRETIVE", depth=4, verified="2026-08-03",
        note=("22 detectors + strategy + neutral book on data every participant has. Graded "
              "INTERPRETIVE deliberately and uncomfortably: the claim is a better reading of "
              "public candles, which is where almost every losing retail strategy believes it "
              "is. Depth 4 with zero real-data evidence.")),
    AsymmetrySource(
        name="macro_liquidity_series", asymmetry="INTERPRETIVE", depth=3, verified="2026-08-03",
        note="FRED/SOMA/RRP/TGA. Public, widely modelled, no access advantage."),

    # -------------------------------------------------------------------------- commodity
    AsymmetrySource(
        name="exchange_ohlcv", asymmetry="COMMODITY", depth=5, verified="2026-08-03",
        note="Identical bytes for every participant. Infrastructure, never edge."),
    AsymmetrySource(
        name="headline_oi_funding", asymmetry="COMMODITY", depth=4, verified="2026-08-03",
        note="Published by the venues to everyone simultaneously."),
)


def main() -> int:
    p = Portfolio(sources=SOURCES)
    by_class = p.by_class()
    gold = p.shallow_gold()
    stale = p.stale_claims()

    out = {
        "ts": datetime.now(tz=UTC).isoformat(),
        "sources": len(SOURCES),
        "breadth_live_asymmetric": p.breadth,
        "mean_depth": round(p.mean_depth, 2),
        "realised_asymmetry_total": round(p.realised_total, 3),
        "by_class": {k: [s.name for s in v] for k, v in sorted(by_class.items())},
        "shallow_gold": [
            {"name": s.name, "class": s.asymmetry, "depth": s.depth,
             "depth_meaning": DEPTH_LEVELS[s.depth], "why": s.why_not_replicable, "note": s.note}
            for s in gold],
        "stale_claims": [s.name for s in stale],
        "depth_ladder": DEPTH_LEVELS,
        "class_weights": {k: v[0] for k, v in ASYMMETRY_CLASSES.items()},
        "note": (
            "REALISED asymmetry is weight x depth, and a zero in either factor zeroes it. Holding "
            "irreplaceable data at depth 0 realises exactly nothing, which is why breadth alone "
            "is a misleading score. Acquiring another asymmetric source while an existing one "
            "sits at depth 1 raises the headline count and LOWERS realised asymmetry."),
        "authority": "NONE. Ranks where to dig; acquires nothing and promotes nothing.",
    }
    REPORT.parent.mkdir(parents=True, exist_ok=True)
    REPORT.write_text(json.dumps(out, indent=1), "utf-8")

    print(f"asymmetry-ledger: {len(SOURCES)} sources | live asymmetric breadth {p.breadth} | "
          f"mean depth {p.mean_depth:.2f}/5 | realised {p.realised_total:.2f}")
    for cls in ("EXCLUSIVE", "RECONSTRUCTIBLE", "PERISHABLE", "INTERPRETIVE", "COMMODITY",
                "UNVERIFIED"):
        items = by_class.get(cls, [])
        if items:
            print(f"  {cls:<16} {len(items):>2}  " +
                  ", ".join(f"{s.name}(d{s.depth})" for s in items))
    print("\n  SHALLOW GOLD -- high asymmetry, low depth. Dig these BEFORE acquiring anything new:")
    for s in gold:
        print(f"    {s.name:<28} {s.asymmetry:<16} depth {s.depth} -- {DEPTH_LEVELS[s.depth]}")
    if stale:
        print(f"\n  STALE CLAIMS (re-verify or downgrade): {', '.join(s.name for s in stale)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
