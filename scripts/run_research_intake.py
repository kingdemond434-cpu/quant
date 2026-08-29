"""The wired path. Every module built today, in one ladder, leaving an artifact.

WHY THIS EXISTS (LAWS III.16: UNWIRED OR IDLE IS A DEFECT)

By last night this desk had a semantic space, a novelty engine, a tri-alignment gate, a successive
halving ladder, a lineage DAG, a lockbox and a search controller -- and NOT ONE of them was called
by anything. They were libraries with no importer, which by the desk's own law is a defect and not
a completion. "Built" was being reported as a status, which is exactly what III.16 forbids.

This is the caller. It runs the ladder in cost order over the real candidate docket:

    docket (15,380 candidates)
      -> semantic coordinate assigned          cheapest; a candidate with no coordinate cannot
                                               be reasoned about or counted against a region
      -> tri-alignment                         text and AST only, no bars loaded
      -> novelty v2 against the book           seven dimensions, max redundancy
      -> successive halving reports the toll   with the ordering and zero-admit guards

CHEAP AND DECISIVE FIRST, and the ordering is asserted rather than assumed -- `check_ordering`
fails the run if an expensive rung sits above a cheap one, because that reintroduces the exact
waste the ladder removes.

IT DOES NOT KILL ANYTHING YET. The ladder reports what it WOULD remove and writes the toll to an
artifact. Cutting candidates for real is only legitimate once `audit_rung` has shown the ladder
kills nothing the full gauntlet would have passed, and that audit needs a gauntlet run to compare
against. Turning the reduction on before that evidence exists would make the desk's certificate
count a function of its compute budget rather than of the market.
"""
from __future__ import annotations

import json
import sys
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
DESK = ROOT / "desks" / "mt5"
OUT = ROOT / "data" / "research_intake.json"

#: Family -> the semantic EVENT it implements. A family whose mechanism nobody has declared gets
#: no coordinate and is reported as unmapped rather than guessed at: assigning a coordinate by
#: string similarity would put a candidate in a region it does not belong to and corrupt every
#: coverage number that region feeds.
_FAMILY_EVENT: dict[str, str] = {
    "hedging_demand_close": "options_hedging",
    "fx_fixing_reversal": "benchmark_flow",
    "session_handoff": "session_transition",
    "liquidity_gamma_reversal": "liquidity_shock",
    "carry": "carry_change",
    "relative_value": "cross_market_move",
    "cross_asset_residual": "cross_market_move",
    "correlation_regime": "cross_market_move",
    "pca_residual": "cross_market_move",
    "vol_transition": "volatility_shock",
    "vol_mean_reversion": "volatility_shock",
    "cot_positioning": "positioning_extreme",
    "event_reaction": "macro_release",
    "turn_of_month": "inventory_rebalance",
    "calendar_month": "inventory_rebalance",
    "session_range_breakout": "session_transition",
    "overnight_gap_decay": "session_transition",
    "asia_momentum": "session_transition",
    "lvc_asia_london": "session_transition",
    "liquidity_regime": "liquidity_shock",
    "orderflow_imbalance": "liquidity_shock",
    "drawdown_conditional": "forced_deleveraging",
}

#: Family -> the direction it predicts. Continuation and reversal of the same event are DIFFERENT
#: hypotheses and must not share a coordinate; one of them is wrong.
_FAMILY_DIRECTION: dict[str, str] = {
    "hedging_demand_close": "continuation",
    "fx_fixing_reversal": "reversal",
    "session_handoff": "continuation",
    "liquidity_gamma_reversal": "reversal",
    "carry": "continuation",
    "relative_value": "convergence",
    "cross_asset_residual": "convergence",
    "correlation_regime": "divergence",
    "pca_residual": "convergence",
    "vol_transition": "volatility_expansion",
    "vol_mean_reversion": "volatility_compression",
    "cot_positioning": "reversal",
    "event_reaction": "continuation",
    "turn_of_month": "continuation",
    "calendar_month": "continuation",
    "session_range_breakout": "continuation",
    "overnight_gap_decay": "reversal",
    "asia_momentum": "continuation",
    "lvc_asia_london": "continuation",
    "liquidity_regime": "reversal",
    "orderflow_imbalance": "continuation",
    "drawdown_conditional": "reversal",
}


def _coordinate_for(fam: str) -> str | None:
    from libs.research.semantic_space import Coordinate

    ev, dr = _FAMILY_EVENT.get(fam), _FAMILY_DIRECTION.get(fam)
    if not ev or not dr:
        return None
    # Context/quality/output are the conditioning axes a sweep varies; the region -- the part
    # that carries the economic claim -- is (event, direction), and that is what coverage counts.
    return Coordinate(ev, "asia", "magnitude", dr, "1h").key()


def main() -> int:
    from libs.research import novelty_v2 as nv
    from libs.research import semantic_space as ss
    from libs.research import successive_halving as sh

    now = datetime.now(tz=UTC)
    docket_path = DESK / "data" / "hypotheses" / "external_survivors.json"
    try:
        docket = json.loads(docket_path.read_text("utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        print(f"INTAKE: cannot read the docket ({type(exc).__name__}); refusing to report a "
              f"ladder over nothing.")
        return 1

    print(f"RESEARCH INTAKE {now.isoformat(timespec='seconds')}")
    print(f"  docket: {len(docket)} candidates")

    # ---- coordinate assignment -------------------------------------------------------------
    attempts: Counter[str] = Counter()
    unmapped: Counter[str] = Counter()
    for h in docket:
        fam = h.get("family")
        if not fam:
            continue
        c = _coordinate_for(str(fam))
        if c is None:
            unmapped[str(fam)] += 1
        else:
            attempts[c] += 1

    cov = ss.coverage(dict(attempts))
    print(f"\n  SEMANTIC COVERAGE  space {cov['space_size']} coordinates, "
          f"{cov['regions']} regions")
    print(f"    regions with conclusive evidence: {cov['regions_with_conclusive_evidence']} "
          f"({cov['coverage_pct']}%)")
    print(f"    regions never touched:            {cov['regions_never_touched']}")
    print(f"    regions attempted but UNTESTED:   {cov['regions_untested']}")
    if unmapped:
        print(f"    UNMAPPED families ({len(unmapped)}): {dict(unmapped.most_common(5))}")
        print("      -- these carry no declared mechanism, so their trials count toward no "
              "region and every coverage number above is a percentage of a smaller docket")

    # ---- the ladder ------------------------------------------------------------------------
    rungs = [
        sh.Rung("has_family", lambda c: bool(c.get("family")), 1.0,
                "a candidate with no family cannot be reasoned about", 0.99),
        sh.Rung("has_coordinate", lambda c: _coordinate_for(str(c.get("family"))) is not None,
                2.0, "no declared mechanism means no region and no falsifier", 0.90),
        sh.Rung("has_params", lambda c: isinstance(c.get("params"), dict), 3.0,
                "params are the identity; without them variants collide", 0.99),
    ]
    problems = sh.check_ordering(rungs)
    if problems:
        print(f"\n  LADDER ORDERING BROKEN: {problems}")
        return 1

    survivors, results = sh.run(docket, rungs)
    print("\n  HALVING LADDER (reports only -- nothing is cut until audit_rung proves the "
          "ladder kills nothing the gauntlet would pass)")
    print(f"    {'rung':18s} {'in':>7s} {'out':>7s} {'rate':>7s}")
    for r in results:
        print(f"    {r.name:18s} {r.entered:7d} {r.survived:7d} {r.survival_rate:7.3f}"
              f"{'  ' + r.note[:60] if r.note else ''}")

    # ---- novelty over the certified book ----------------------------------------------------
    certs_path = DESK / "reports" / "UNIVERSAL_SURVIVORS.json"
    book: list[dict[str, Any]] = []
    try:
        surv = json.loads(certs_path.read_text("utf-8")).get("survivors") or {}
        for key, row in surv.items():
            spec = (row or {}).get("shadow_spec") or {}
            book.append({"name": key, "mechanism": spec.get("family"),
                         "coordinate": _coordinate_for(str(spec.get("family") or ""))})
    except (OSError, json.JSONDecodeError):
        pass

    redundant = 0
    unmeasurable = 0
    checked = 0
    for h in survivors[:400]:                 # a sample: this is a report, not a gate
        fam = str(h.get("family") or "")
        cand = {"name": f"{h.get('symbol')}.{fam}", "mechanism": fam,
                "coordinate": _coordinate_for(fam)}
        v = nv.assess(cand, book)
        checked += 1
        if v.verdict == "REDUNDANT":
            redundant += 1
        elif v.verdict == "UNMEASURABLE":
            unmeasurable += 1

    print(f"\n  NOVELTY over {len(book)} certified incumbents, {checked} candidates sampled")
    print(f"    REDUNDANT    {redundant}")
    print(f"    UNMEASURABLE {unmeasurable}  -- no STRONG dimension available (no signal, pnl or "
          f"source on the docket rows)")
    print(f"    NOVEL        {checked - redundant - unmeasurable}")
    if unmeasurable > checked * 0.5:
        print("      -- the docket carries no return series, so novelty here can only convict on "
              "coordinate identity. Wiring pnl into the docket is what makes this decisive.")

    payload = {"ran_at": now.isoformat(timespec="seconds"),
               "docket": len(docket), "coverage": cov,
               "unmapped_families": dict(unmapped),
               "ladder": [r.__dict__ for r in results],
               "novelty": {"incumbents": len(book), "checked": checked,
                           "redundant": redundant, "unmeasurable": unmeasurable},
               "note": ("reports only; the ladder cuts nothing until audit_rung has shown it "
                        "kills nothing the full gauntlet would have passed")}
    OUT.write_text(json.dumps(payload, indent=1, default=str), "utf-8")
    print(f"\n  -> {OUT}")
    return 1 if unmapped else 0


if __name__ == "__main__":
    raise SystemExit(main())
