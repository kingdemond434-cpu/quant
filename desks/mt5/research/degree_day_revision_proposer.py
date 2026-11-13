"""Mint `degree_day_revision` cells from NOAA CPC degree-day forecast revisions (their consumer).

One family (`mt5desk.family_degree_day_revision`) over the four daily CPC 7-day products the lake
holds (`data/lake/series/noaa_<product>.parquet`, written by `noaa_forecast_vintage`), each read on
its own measure:

  cpc_dd7_gas_hdd   gas-weighted HDD    residential/commercial burn
  cpc_dd7_elec_hdd  electricity HDD     power-sector burn in winter
  cpc_dd7_pop_hdd   population HDD      the HDD the market quotes as "the weather"
  cpc_dd7_pop_cdd   population CDD      gas-fired power burn in summer

Region: `conus` only. A sweep over the nine census divisions would multiply the charged trials by
ten on the same national gas price; a division is a recipe value the gauntlet can still judge
when named by hand. The monthly product is not swept: its regions are census regions and states
with no `conus` column, and one issue a month is too few events per cell.

Declared direction: MORE degree days than the previous issue said (a revision `up`) means more
expected burn, so gas `long`; a revision `down` means `short`. The opposite signs are not tested:
they are not the hypothesis. Grid per product: 2 (move, direction) x 1 threshold x 1 window x 2
holds, charged in full on every row -- every variant that reached the screen counts, across all
products, in the deflation.

Symbols: XNGUSD only (universe.json carries no power instrument).

A PRODUCT WITH NO INPUT PARKS, BY NAME AND BY COUNT: its block in the report says the family's
refusal code (`noaa_degree_day_absent`) and why. Nothing is screened for it, and a pass where
every product parks is UNMEASURED as a whole -- never zero.

The screen is the shared `proposer_common.screen`, unchanged; it is not the gauntlet, it only
keeps the gauntlet from being handed every variant.

    python desks/mt5/research/degree_day_revision_proposer.py --once --budget-s 300
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

DESK = Path(__file__).resolve().parents[1]
ROOT = DESK.parents[1]
for _p in (str(ROOT), str(DESK), str(DESK / "research")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from mt5desk import family_degree_day_revision as F  # noqa: E402

from research import proposer_common as pc  # noqa: E402

SOURCE = "degree_day_revision"
FAMILY = "degree_day_revision"
REPORT = DESK / "reports" / "DEGREE_DAY_REVISION_PROPOSER.json"
UNMEASURED = "UNMEASURED"
DEFAULT_BUDGET_S = 300.0
MIN_BARS = 2000

#: product -> the measure its columns carry.
PRODUCT_MEASURE: dict[str, str] = {
    "cpc_dd7_gas_hdd": "hdd",
    "cpc_dd7_elec_hdd": "hdd",
    "cpc_dd7_pop_hdd": "hdd",
    "cpc_dd7_pop_cdd": "cdd",
}
REGION = "conus"
#: (move, direction): the declared hypothesis -- more degree days, more burn, gas up.
PAIRS: tuple[tuple[str, str], ...] = (("up", "long"), ("down", "short"))
MIN_ABS = 2.0
WINDOWS: tuple[int, ...] = (60,)
HOLDS: tuple[int, ...] = (24, 72)


def _write(path: Path, doc: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(doc, indent=1, default=str), "utf-8")
    tmp.replace(path)


def charge(rows: list[dict[str, Any]], grid: int) -> list[dict[str, Any]]:
    """The shared deflation, then the sweep charge raised to the WHOLE grid run this pass.

    `proposer_common.deflate` charges the rows that reached it (variants that fired). A variant
    that fired nothing was still a test of the hypothesis, so the charge here is every variant the
    grid ran, never fewer than the rows -- the bar only ever rises. The rule that marks a row
    proposed is the shared one, re-applied on the larger charge."""
    from research.multiplicity import deflate_t
    rows = pc.deflate(rows)
    for r in rows:
        n = max(int(grid), int(r["n_tests_sweep"]))
        extra = n - int(r["n_tests_sweep"])
        r["n_tests_sweep"] = n
        r["t_deflated_sweep"] = round(deflate_t(float(r["t_gross"]), n), 3)
        r["n_tests_lifetime"] = int(r["n_tests_lifetime"]) + extra
        r["t_deflated_lifetime"] = round(deflate_t(float(r["t_gross"]),
                                                   r["n_tests_lifetime"]), 3)
        r["proposed"] = bool(r.get("clears_cost") and r["t_deflated_sweep"] > pc.PROPOSE_T
                             and int(r.get("n_independent", 0)) >= pc.MIN_TRADES)
    return rows


def reach(meta: dict[str, Any]) -> dict[str, dict[str, Any]]:
    """Per product: the symbols it would sweep and its issue count, or the named refusal."""
    from research import universe_policy as up
    syms = [s for s in F.SYMBOLS if isinstance(meta.get(s), dict) and up.may_hypothesise(s)]
    out: dict[str, dict[str, Any]] = {}
    for product, measure in PRODUCT_MEASURE.items():
        try:
            r = F.revisions(product, REGION, measure)
        except F.DegreeDayUnavailable as exc:
            out[product] = {"parked_reason": F.ABSENT, "why": str(exc)[:300],
                            "symbols_parked": len(syms)}
            continue
        out[product] = {"symbols": syms, "measure": measure, "region": REGION,
                        "revised_issues": len(r),
                        "last_available": str(r["available_time"].max()) if len(r) else None}
    return out


def run(*, budget_s: float = DEFAULT_BUDGET_S, now: datetime | None = None,
        donate: bool = True) -> dict[str, Any]:
    now = now or datetime.now(UTC)
    t0 = time.monotonic()
    meta = pc.universe_meta()
    products = reach(meta)
    rep: dict[str, Any] = {"generated_at": now.isoformat(timespec="seconds"),
                           "organ": "desks/mt5/research/degree_day_revision_proposer.py",
                           "family": FAMILY,
                           "consumes": [f"data/lake/series/noaa_{p}.parquet"
                                        for p in PRODUCT_MEASURE] + ["data/universe/*_H1.parquet"],
                           "products": products}
    work = sorted({(s, p) for p, v in products.items() for s in v.get("symbols", ())})
    if not work:
        rep.update({"status": UNMEASURED, "tests_run": UNMEASURED, "cells_proposed": UNMEASURED,
                    "why": "every product is parked: see products[*].parked_reason"})
        _write(REPORT, rep)
        return rep
    rows: list[dict[str, Any]] = []
    grid = 0
    swept: list[str] = []
    skipped: dict[str, str] = {}
    for sym in sorted({s for s, _ in work}):
        if time.monotonic() - t0 > budget_s:
            break
        d = pc.bars(sym)
        if d is None or len(d) < MIN_BARS:
            skipped[sym] = "no or too few H1 bars"
            swept.append(sym)
            continue
        cost = pc.cost_frac(sym, meta, d["close"])
        if cost is None:
            skipped[sym] = "no contract terms"
            swept.append(sym)
            continue
        unf = pc.artifact_hours(d)
        for product in (p for s, p in work if s == sym):
            for move, direction in PAIRS:
                for window in WINDOWS:
                    for hold in HOLDS:
                        params: dict[str, Any] = {
                            "product": product, "region": REGION,
                            "measure": PRODUCT_MEASURE[product], "move": move,
                            "min_abs": MIN_ABS, "direction": direction, "window": window,
                            "hold_bars": hold}
                        grid += 1
                        try:
                            sig = F.family_degree_day_revision(d, **params)
                        except F.DegreeDayUnavailable as exc:
                            skipped[f"{sym}.{product}"] = str(exc)[:160]
                            continue
                        sc = pc.screen(d, sig, cost, unf)
                        if sc is None:
                            continue
                        rows.append({"cell": f"{sym}.{FAMILY}.{product}", "symbol": sym,
                                     "params": params, **sc})
        swept.append(sym)
    rows = charge(rows, grid)
    proposals = pc.best_per_cell(rows)
    cands = [pc.candidate(
        SOURCE, r["symbol"], FAMILY, dict(r["params"]),
        mechanism=(f"CPC {r['params']['product']} {r['params']['region']} "
                   f"{r['params']['measure'].upper()} forecast revised {r['params']['move']} by "
                   f"at least {r['params']['min_abs']} sigma of its prior revisions: expected gas "
                   f"burn moved, so {r['symbol']} reprices {r['params']['direction']} over the "
                   f"{r['params']['hold_bars']} bars after the issue is public"),
        title=f"{r['cell']} {r['params']['move']} {r['params']['direction']} "
              f"h{r['params']['hold_bars']}",
        evidence={k: r.get(k) for k in ("n_independent", "gross_per_trade", "net_per_trade",
                                        "cost_frac", "t_gross", "t_deflated_sweep",
                                        "n_tests_sweep")}) for r in proposals]
    donated = None
    if donate and cands:
        donated = pc.donate(SOURCE, cands, grid)
    rep.update({"status": "OK", "symbols_swept": len(swept),
                "tests_run": grid, "variants_screened": len(rows), "cells_proposed": len(proposals),
                "donated": len(cands) if donated else 0, "donation_path": str(donated or ""),
                "donation_refusals": dict(pc.LAST_DONATION) if donated is None and cands
                else None,
                "skipped": skipped, "elapsed_s": round(time.monotonic() - t0, 1),
                "proposals": proposals[:50]})
    _write(REPORT, rep)
    return rep


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n", 1)[0])
    ap.add_argument("--once", action="store_true")
    ap.add_argument("--budget-s", type=float, default=DEFAULT_BUDGET_S)
    a = ap.parse_args(argv)
    r = run(budget_s=a.budget_s)
    parked = sorted(p for p, v in r.get("products", {}).items() if "parked_reason" in v)
    print(f"degree_day_revision_proposer: status={r['status']} swept={r.get('symbols_swept', 0)} "
          f"tests={r['tests_run']} proposed={r['cells_proposed']} "
          f"donated={r.get('donated', 0)} parked={','.join(parked) or '-'}", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
