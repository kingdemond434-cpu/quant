"""Build the cross-asset information graph and propose the strong edges as lead_lag cells.

PAIRS come from the economic-driver registry: every (driver role instrument, target) pair
`economic_drivers.driver_sets` declares is a CAUSAL_ROLE candidate; the book's own symbols
against each other are STATISTICAL candidates held to a higher bar. `libs.research.lead_lag`
measures each edge (lag, t, state dependence, stability, out-of-sample value); the strong
ones are swept through `family_lead_lag` at the measured lag and both entry thresholds, screened
net of cost, deflated by everything tried, and donated. The graph itself is written to
`reports/CROSS_ASSET_GRAPH.json` for the state builder and the genome.

EVENT PROPAGATION is measured on the same pairs around the calendar's high-impact stamps: an
abnormal leader reaction that predicts the laggard's follow-through is a second-order event
edge, reported beside the plain lead-lag ones.

BREADTH (2026-10-01). The sweep used to be `book_symbols()[:12]`: the alphabetical first twelve
of the certified book, so AUDCAD..EURUSD were ever measured and USDJPY/XAUUSD never were, and no
instrument outside the book could lead anything. It now spans the book PLUS every
hypothesis-lane instrument with H1 bars. All ordered pairs of that set are too many for one
pass (n^2 at ~0.3 s an edge), so the economic-driver pairs are measured EVERY pass and the
statistical pairs are walked by a persisted cursor, as many as the graph budget allows, wrapping
round. Every edge measured on any pass is kept in the graph (refreshed when re-measured), so the
published graph is the whole universe's, and `coverage` says how much of the pair space it holds.
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from datetime import UTC, datetime
from pathlib import Path

_DESK = Path(__file__).resolve().parents[1]
_ROOT = _DESK.parent.parent
for p in (str(_DESK), str(_DESK / "research"), str(_ROOT)):
    if p not in sys.path:
        sys.path.insert(0, p)

from mt5desk.family_lead_lag import family_lead_lag  # noqa: E402

from libs.research import lead_lag  # noqa: E402
from research import proposer_common as pc  # noqa: E402

SOURCE = "cross_asset_graph"
GRAPH = _DESK / "reports" / "CROSS_ASSET_GRAPH.json"
REPORT = _DESK / "reports" / "cross_asset_graph.json"
CURSOR = _DESK / "reports" / "cross_asset_graph_cursor.json"
#: Share of the pass budget spent measuring edges; the rest sweeps the EDGE ones into cells.
GRAPH_SHARE = 0.5
ENTRY_Z = (1.5, 2.0)
HOLDS = (4, 8)


def _book_symbols() -> list[str]:
    try:
        from research.state_vector_build import book_symbols
        return book_symbols()
    except Exception:
        return []


def _universe(book: list[str], have: set[str]) -> list[str]:
    """The book first (its edges matter to live risk), then every other hypothesis-lane symbol
    with H1 bars. Single names are never hunted for lead_lag (universe_policy)."""
    try:
        import universe_policy as up
        lane_ok = [s for s in sorted(have) if up.may_hypothesise(s, "lead_lag")]
    except Exception:
        lane_ok = []
    out = [s for s in book if s in have]
    return out + [s for s in lane_ok if s not in set(out)]


def _read_json(path: Path) -> dict:
    try:
        doc = json.loads(path.read_text("utf-8"))
    except (OSError, ValueError):
        return {}
    return doc if isinstance(doc, dict) else {}


def _pairs(symbols: list[str], meta: dict, have: set[str]) -> list[tuple[str, str, str | None]]:
    pairs: list[tuple[str, str, str | None]] = []
    try:
        from mt5desk.economic_drivers import ROLES, driver_sets
        for t in symbols:
            for ds in driver_sets(t, meta, have):
                for d in ds.drivers:
                    role = next((r for r, c in ROLES.items() if d in c), None)
                    pairs.append((d, t, role))
    except Exception:
        pass
    seen = {(p[0], p[1]) for p in pairs}       # a set: the list scan was O(n^4) at universe width
    for a in symbols:
        for b in symbols:
            if a != b and (a, b) not in seen:
                seen.add((a, b))
                pairs.append((a, b, None))
    return pairs


def _event_times() -> list[str]:
    try:
        from libs.regime.state_admission import _calendar
        rows = _calendar()
    except Exception:
        return []
    return [str(r.get("event_date")) for r in rows
            if isinstance(r, dict) and str(r.get("impact", "")).lower() == "high"
            and r.get("event_date")]


def run(symbols: list[str] | None = None, budget_s: float = 900.0) -> dict:
    meta = pc.universe_meta()
    have = {p.stem.removesuffix("_H1") for p in pc.UNI.glob("*_H1.parquet")}
    syms = ([s for s in symbols if s in have] if symbols
            else _universe(_book_symbols(), have))
    pairs = _pairs(syms, meta, have)
    causal = [p for p in pairs if p[2] is not None]
    stat = [p for p in pairs if p[2] is None]
    cur = _read_json(CURSOR)
    at = int(cur.get("next", 0)) % len(stat) if stat and cur.get("n_stat") == len(stat) else 0
    order = causal + stat[at:] + stat[:at]
    bars: dict = {}

    def _bar(sym: str):
        if sym not in bars:
            bars[sym] = pc.bars(sym)
        return bars[sym]

    started = time.monotonic()
    graph_budget = budget_s * GRAPH_SHARE
    measured: list[dict] = []
    n_stat_done = 0
    for d, t, role in order:
        if role is None and time.monotonic() - started > graph_budget:
            break
        bd, bt = _bar(d), _bar(t)
        if bd is None or bt is None or d == t:
            n_stat_done += role is None
            continue
        measured.append({"driver": d, "target": t, **lead_lag.edge(bd, bt, plausible_role=role)})
        n_stat_done += role is None
    if not symbols:
        CURSOR.parent.mkdir(parents=True, exist_ok=True)
        CURSOR.write_text(json.dumps({"n_stat": len(stat),
                                      "next": (at + n_stat_done) % max(len(stat), 1),
                                      "walked_this_pass": n_stat_done,
                                      "updated_utc": datetime.now(tz=UTC).isoformat()}), "utf-8")
    measured.sort(key=lambda e: -abs(float(e.get("t", 0.0))))
    g = {"n_pairs": len(measured), "n_edges": sum(1 for e in measured
                                                   if e.get("verdict") == "EDGE"),
         "edges": measured}
    # The published graph keeps every edge any pass measured, refreshed when re-measured.
    keep = {(e["driver"], e["target"]): e for e in (_read_json(GRAPH).get("edges") or [])
            if isinstance(e, dict) and e.get("driver") and e.get("target")} if not symbols else {}
    keep.update({(e["driver"], e["target"]): e for e in measured})
    whole = sorted(keep.values(), key=lambda e: -abs(float(e.get("t", 0.0) or 0.0)))
    events = _event_times()
    chains = []
    for e in measured:
        if e.get("verdict") != "EDGE" or not events:
            continue
        if time.monotonic() - started > budget_s:
            break
        ch = lead_lag.event_propagation(bars[e["driver"]], bars[e["target"]], events)
        chains.append({"driver": e["driver"], "target": e["target"], **ch})
    GRAPH.parent.mkdir(parents=True, exist_ok=True)
    GRAPH.write_text(json.dumps({
        "generated_utc": datetime.now(tz=UTC).isoformat(), "symbols": syms,
        "n_pairs": len(whole), "n_edges": sum(1 for e in whole if e.get("verdict") == "EDGE"),
        "edges": whole, "event_chains": chains,
        "coverage": {"symbols": len(syms), "pairs_in_space": len(pairs),
                     "pairs_held": len(whole), "measured_this_pass": len(measured),
                     "causal_pairs": len(causal), "statistical_cursor": at}},
        indent=1, default=str), "utf-8")
    rows: list[dict] = []
    skipped: dict[str, str] = {}
    for e in g["edges"]:
        if e.get("verdict") != "EDGE":
            continue
        if time.monotonic() - started > budget_s:
            skipped[f"{e['driver']}->{e['target']}"] = "budget exhausted"
            continue
        t = _bar(e["target"])
        cost = pc.cost_frac(e["target"], meta, t["close"])
        if cost is None:
            skipped[e["target"]] = "no contract terms"
            continue
        unf = pc.artifact_hours(t)
        for z in ENTRY_Z:
            for h in HOLDS:
                params = {"driver_symbol": e["driver"], "lag": int(e["lag"]),
                          "direction": e["direction"], "entry_z": z, "norm": 240,
                          "hold_bars": h}
                sig = family_lead_lag(t, driver=_bar(e["driver"]), **params)
                sc = pc.screen(t, sig, cost, unf)
                if sc is None:
                    continue
                rows.append({"cell": f"{e['target']}.lead_lag.{e['driver']}",
                             "symbol": e["target"], "params": params, **sc,
                             "edge_t": e["t"], "plausibility": e["plausibility"]})
    rows = pc.deflate(rows)
    proposals = pc.best_per_cell(rows)
    cands = [pc.candidate(
        SOURCE, r["symbol"], "lead_lag", dict(r["params"]),
        mechanism=(f"{r['params']['driver_symbol']} leads {r['symbol']} by "
                   f"{r['params']['lag']} bar(s) ({r['plausibility']}, edge t={r['edge_t']}); "
                   f"trade the laggard in the {r['params']['direction']} direction"),
        title=f"{r['cell']} lag={r['params']['lag']} z>={r['params']['entry_z']}",
        evidence={k: r.get(k) for k in ("n_independent", "gross_per_trade", "net_per_trade",
                                        "cost_frac", "t_gross", "t_deflated_sweep",
                                        "n_tests_sweep", "edge_t")}) for r in proposals]
    rep = {"generated_at": datetime.now(tz=UTC).isoformat(), "symbols_swept": len(syms),
           "pairs": g["n_pairs"], "edges": g["n_edges"],
           "pairs_in_space": len(pairs), "graph_pairs_held": len(whole), "event_chains": len(chains),
           "tests_run": len(rows), "cells_proposed": len(proposals), "skipped": skipped,
           "proposals": proposals}
    REPORT.write_text(json.dumps(rep, indent=1, default=str), "utf-8")
    if cands:
        rep["donated"] = str(pc.donate(SOURCE, cands, len(rows)))
    return rep


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--symbol", action="append", default=None)
    ap.add_argument("--budget-s", type=float, default=900.0)
    a = ap.parse_args()
    r = run(symbols=a.symbol, budget_s=a.budget_s)
    print(f"CROSS-ASSET GRAPH  {r['pairs']} pairs, {r['edges']} edges, {r['event_chains']} "
          f"event chains, {r['tests_run']} tests, {r['cells_proposed']} proposed")
    for p in r["proposals"][:8]:
        print(f"  {p['cell']:36s} lag={p['params']['lag']} t={p['t_gross']:+.2f} "
              f"t_defl={p['t_deflated_sweep']:+.2f} n={p['n_independent']}")
    print(f"written: {GRAPH}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
