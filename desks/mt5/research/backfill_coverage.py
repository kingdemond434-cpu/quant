"""Hunt the asset classes the docket has ZERO coverage for -- whichever they happen to be.

WHY THIS EXISTS

The docket carried 6,024 candidates across eight asset classes and not one bond, while the broker
offers three usable ones (UKGILT, UST05Y, UST10Y) with 6,305 to 10,905 hourly bars apiece. The
searcher was not refusing them and they were not untestable -- probed directly on 2026-08-28 they
returned 67, 84 and 74 diverse hypotheses from roughly 950,000 trials. The rotation simply had
not reached them: bonds are 3 symbols out of 299, mined ground fills the head of every run's
budget, and a cursor that advances a fixed step per run can leave a thin class unvisited for
days while the breadth counter reports the gap and nothing acts on it.

A class with zero coverage is not a rounding error. Classes fail in DIFFERENT REGIMES by
construction -- a gilt answers rate expectations, cocoa answers West African weather, a JPY cross
answers carry -- so an absent class is absent diversification, and diversification is the binding
constraint on this book (n_eff ~5.5 across 23 certificates). The desk cannot manufacture that by
adding another parameterisation of a family it already owns.

DELIBERATELY NOT A BOND SCRIPT. It asks which classes are missing and hunts those, so it works
the same way the day equities or softs fall out of the rotation. Hardcoding tonight's gap would
reproduce exactly the frozen-whitelist defect that kept 35 families unreachable from the external
backtest door until it was replaced with auto-discovery.

It writes its OWN producer file. `merge_hypotheses` is the only writer of the docket, and one
producer per file is the rule that stopped stage 2 clobbering the merge's output every hour.
"""
from __future__ import annotations

import json
import sys
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path

BASE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE))
sys.path.insert(0, str(BASE / "research"))

HYP = BASE / "data" / "hypotheses"
UNIVERSE = BASE / "data" / "universe"
OUT = HYP / "coverage_search_results.json"

#: Symbols to hunt per starved class in one pass. Small on purpose: this runs beside the main
#: searcher and the box has 8GB shared with the live terminal.
PER_CLASS = 3


def _read(p: Path):
    try:
        return json.loads(p.read_text("utf-8"))
    except (OSError, ValueError):
        return None


def starved_classes() -> tuple[list[str], dict[str, int]]:
    """Classes with usable instruments in the offering but ZERO rows in the docket."""
    from mt5desk.universe import asset_class, classify_all

    registry = _read(UNIVERSE / "universe.json") or {}
    offered: Counter = Counter()
    for inst in classify_all(registry):
        if inst.usable and inst.asset_class != "unknown":
            offered[inst.asset_class] += 1

    docket = _read(HYP / "external_survivors.json") or []
    covered = Counter(asset_class(str(r.get("symbol") or ""))
                      for r in docket if isinstance(r, dict))
    return [c for c in sorted(offered) if not covered.get(c)], dict(covered)


def main() -> int:
    from research.edge_search import search_symbol

    starved, covered = starved_classes()
    print(f"docket coverage: {covered}")
    if not starved:
        print("no starved class -- every class the broker offers has docket coverage")
        OUT.write_text(json.dumps({
            "generated_at": datetime.now(tz=UTC).isoformat(timespec="seconds"),
            "starved_classes": [], "hypotheses": [],
        }, indent=1), "utf-8")
        return 0

    from mt5desk.universe import asset_class

    have_bars = sorted(p.stem.removesuffix("_H1") for p in UNIVERSE.glob("*_H1.parquet"))
    print(f"STARVED: {starved}")

    hypotheses: list[dict] = []
    for cls in starved:
        picks = [s for s in have_bars if asset_class(s) == cls][:PER_CLASS]
        if not picks:
            # The class is offered but its bars were never downloaded -- a DATA gap, not a
            # search gap, and the two need different repairs. Say which one this is.
            print(f"  {cls}: offered but NO H1 bars on this box -- data gap, not a search gap")
            continue
        for sym in picks:
            try:
                res = search_symbol(sym)
            except Exception as exc:
                print(f"  {sym} ({cls}): RAISED {type(exc).__name__}: {str(exc)[:120]}")
                continue
            rows = res.get("selected") or []
            for r in rows:
                r.setdefault("producer", "backfill_coverage")
                r.setdefault("coverage_class", cls)
            hypotheses.extend(rows)
            print(f"  {sym} ({cls}): status={res.get('status', 'ok')} "
                  f"selected={len(rows)} untestable_dropped={res.get('untestable_dropped')}")

    OUT.write_text(json.dumps({
        "generated_at": datetime.now(tz=UTC).isoformat(timespec="seconds"),
        "starved_classes": starved,
        "hypotheses": hypotheses,
    }, indent=1, default=str), "utf-8")
    print(f"{len(hypotheses)} hypothesis(es) for {len(starved)} starved class(es) -> {OUT}")
    return 0


def _cli_main() -> int:
    try:
        from research.job_lock import exclusive_job
    except ModuleNotFoundError:
        from job_lock import exclusive_job

    # Small beside the main searcher: three symbols at a time, not the whole offering.
    with exclusive_job("backfill_coverage", need_mb=700) as acquired:
        return main() if acquired else 75


if __name__ == "__main__":
    raise SystemExit(_cli_main())
