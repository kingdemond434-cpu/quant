"""THE WORLD MODEL'S NON-PRICE NODES: RATES, CREDIT, VOLATILITY, DOLLAR, INFLATION, LIQUIDITY,
CARRY AND POSITIONING (Tier S layer 3, scope gap closed 2026-09-30).

`world_edges` classified edges between PRICE series only, so the world model could never say
"a rise in real yields leads gold" or "crowded speculative length precedes a fall" -- the
relationships the desk's macro and carry sleeves actually trade. This module adds the desk's own
non-price series as nodes, at DAILY resolution, and classifies every (macro node -> MT5 target)
edge with the same life-cycle test (`world_edges.classify_edge`, Bonferroni over every edge
examined here).

THE NODES ARE THE FIELDS THE EXPRESSION FACTORY CAN BIND. They are read through
`libs.research.alpha_dsl.FieldCatalogue` over `desks/mt5/data/axes/` -- the same catalogue, the
same availability rules and the same forward-filled causal join the factory uses. So an edge
found here names a field the factory can put on a bar, and its hypothesis is a grammar
expression pinned to that field (`bind`), never a claim about a series nothing downstream reads.

CAUSALITY. A node's value on day d is the value the catalogue says was KNOWN by the end of day d
(its availability rule: a FRED/ECB print one day after its period, a COT report on its
`knowable_at`). The target is the MT5 symbol's return over day d+1. Nothing reads the future.

  global node (rates, credit, vol, dollar, inflation, liquidity)  -> its daily CHANGE drives
  per-symbol node (positioning, carry)                             -> its LEVEL drives

COVERAGE IS REPORTED PER KIND. A kind with no series on this host (credit when the FRED pull
failed, flows because the desk holds no flow dataset) is UNMEASURED with the reason -- never a
silent zero.
"""
from __future__ import annotations

import math
from collections.abc import Mapping
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from libs.tiers import world_edges

KINDS = ("rates", "credit", "vol", "dollar", "inflation", "liquidity", "carry", "positioning",
         "flows")
#: fewer common days than this and an edge is not examined (a year of trading days)
MIN_DAYS = 250
#: the expression factory's window for one trading day of H1 bars / a positioning z-score
DAY_BARS, Z_BARS = 24, 240
#: the grammar's external terminals a non-price field can bind (BIS policy rates bind
#: `fundamental`, the COT report `positioning`, FRED / ECB series `macro`)
TERMINALS = ("macro", "positioning", "fundamental", "flow")
#: an edge the Bonferroni bar rejects but the single-test bar does not is still a HYPOTHESIS:
#: research is anti-timid, and the gauntlet charges the trial when it judges the cell
NOMINAL_T = 1.96


def kind_of(name: str, semantic: str) -> str:
    """The world-model kind of one catalogue field, from its own name and semantic."""
    n = name.lower()
    col = n.split(".", 1)[-1]
    if semantic == "positioning" or n.startswith("cot."):
        return "positioning"
    if semantic == "flow":
        return "flows"
    if "carry" in col:
        return "carry"
    if col.startswith("baml") or "oas" in col or "credit" in col or col.startswith("baa"):
        return "credit"
    if col.startswith("vix") or "vol" in col:
        return "vol"
    if col.startswith("t5yie") or col.startswith("t10yie") or "breakeven" in col or \
            "inflation" in col:
        return "inflation"
    if col.startswith("dtwex") or col.endswith("_ref") or "dollar" in col:
        return "dollar"
    if col in ("walcl", "m2sl") or "liquidity" in col or "balance_sheet" in col:
        return "liquidity"
    if semantic == "rate" or col.startswith(("dgs", "dfii", "t10y2y", "dff", "sofr", "tb3")) \
            or "yield" in col or "_aaa_" in col or "rate" in col:
        return "rates"
    return "rates" if semantic == "macro_level" else "other"


def _day_index(days: pd.DatetimeIndex) -> pd.DatetimeIndex:
    """End of each day, UTC: the instant a daily node's value must already be known."""
    return days + pd.Timedelta(hours=23, minutes=59, seconds=59)


def daily_returns(closes: Mapping[str, pd.Series]) -> dict[str, pd.Series]:
    """Daily log returns (indexed by the UTC calendar day) from intraday close series."""
    out: dict[str, pd.Series] = {}
    for sym, c in closes.items():
        if not isinstance(c.index, pd.DatetimeIndex) or c.empty:
            continue
        idx = c.index.tz_localize("UTC") if c.index.tz is None else c.index.tz_convert("UTC")
        d = pd.Series(c.to_numpy(dtype=float), index=idx).resample("1D").last().dropna()
        d = d[d > 0]
        if len(d) >= MIN_DAYS:
            r = np.log(d).diff().dropna()
            r.index = r.index.normalize()
            out[sym] = r
    return out


def nodes(catalogue: Any, days: pd.DatetimeIndex, symbols: set[str]
          ) -> list[tuple[Any, str, pd.Series]]:
    """(field, kind, daily series) for every causal non-price field, known by each day's end."""
    out: list[tuple[Any, str, pd.Series]] = []
    at = _day_index(days)
    for f in getattr(catalogue, "fields", ()):
        if f.source == "bars" or f.source.startswith("driver:") or not f.causal():
            continue
        if f.terminal not in TERMINALS:
            continue
        if f.symbol and f.symbol not in symbols:
            continue
        try:
            s = catalogue.series(f, at)
        except Exception:
            s = None
        if s is None:
            continue
        s = pd.Series(s.to_numpy(dtype=float), index=days)
        if int(s.notna().sum()) < MIN_DAYS:
            continue
        out.append((f, kind_of(f.name, f.semantic), s))
    return out


def classify(rets: Mapping[str, pd.Series], node_rows: list[tuple[Any, str, pd.Series]],
             targets: set[str] | None = None) -> list[dict[str, Any]]:
    """Every (node -> target) edge at a one-day lag, classified by `world_edges`."""
    pairs: list[tuple[Any, str, pd.Series, str]] = []
    for f, kind, s in node_rows:
        for sym in sorted(rets):
            if targets is not None and sym not in targets:
                continue
            if f.symbol and f.symbol != sym:
                continue
            pairs.append((f, kind, s, sym))
    out: list[dict[str, Any]] = []
    for f, kind, s, sym in pairs:
        driver = s if f.symbol else s.diff()          # a level per symbol, a change globally
        y = rets[sym]
        df = pd.concat({"x": driver, "y": y}, axis=1, join="inner").dropna()
        if len(df) < MIN_DAYS or float(df["x"].std()) == 0.0:
            continue
        x_arr = df["x"].to_numpy(dtype=float)
        x_arr = (x_arr - x_arr.mean()) / (x_arr.std() or 1.0)
        res = world_edges.classify_edge(x_arr, df["y"].to_numpy(dtype=float), 1,
                                        n_tests=len(pairs))
        out.append({"driver": f.name, "kind": kind, "target": sym, "lag_days": 1,
                    "terminal": f.terminal, "per_symbol": bool(f.symbol), "n_days": len(df),
                    **res})
    return out


def census(edges: list[dict[str, Any]], node_rows: list[tuple[Any, str, pd.Series]],
           catalogue: Any) -> dict[str, Any]:
    """Per kind: nodes read, edges examined, edges by class -- or UNMEASURED with the reason."""
    declared: dict[str, int] = {}
    for f in getattr(catalogue, "fields", ()):
        if f.terminal in TERMINALS and f.source != "bars":
            k = kind_of(f.name, f.semantic)
            declared[k] = declared.get(k, 0) + 1
    out: dict[str, Any] = {}
    for k in KINDS:
        nd = [(f.name, f.symbol) for f, kind, _s in node_rows if kind == k]
        es = [e for e in edges if e["kind"] == k]
        if not nd:
            why = ("no field of this kind in the catalogue on this host" if not declared.get(k) else
                   f"{declared[k]} declared field(s), none with {MIN_DAYS}+ causal days here")
            out[k] = {"status": "UNMEASURED", "why": why}
            continue
        by: dict[str, int] = {}
        for e in es:
            by[str(e["class"])] = by.get(str(e["class"]), 0) + 1
        out[k] = {"status": "MEASURED", "nodes": len(set(nd)), "edges": len(es), **by}
    return out


def expression(edge: Mapping[str, Any]) -> str:
    """The edge as a grammar expression on the target's H1 bars, signed by its beta."""
    term = str(edge.get("terminal") or "macro")
    base = (f"zscore({term}, {Z_BARS})" if edge.get("per_symbol")
            else f"delta({term}, {DAY_BARS})")
    return base if float(edge.get("beta") or 0.0) > 0 else f"neg({base})"


def hypotheses(edges: list[dict[str, Any]], at: str, may: Any = None,
               vocab: set[str] | None = None) -> tuple[list[dict[str, Any]],
                                                       list[dict[str, Any]]]:
    """(compiler rows, pinned expression-queue rows) for every live or nominal edge.

    Every live edge becomes a grammar expression pinned to its field (`bind`), which the
    expression factory binds first when it loads the target. A positioning edge whose sign
    matches a registered COT family is ALSO a compiler row for that family."""
    rows: list[dict[str, Any]] = []
    exprs: list[dict[str, Any]] = []
    for e in edges:
        cls = str(e.get("class"))
        if cls == "FALSE" and abs(float(e.get("t") or 0.0)) < NOMINAL_T:
            continue
        cls = "NOMINAL_ONLY" if cls == "FALSE" else cls
        sym = str(e["target"])
        if may is not None and not may(sym):
            continue
        claim = (f"{e['driver']} ({e['kind']}) leads {sym} by one day: {cls} edge, "
                 f"beta {float(e['beta']):+.5f} per sd, t {float(e['t']):+.2f} against a "
                 f"Bonferroni bar of {float(e['bar']):.2f}")
        exprs.append({"symbol": sym, "expr": expression(e),
                      "bind": {str(e.get("terminal") or "macro"): str(e["driver"])},
                      "lab": "macro_world", "generator": "cross_science:macro_world",
                      "claim": claim, "edge_class": cls, "kind": e["kind"],
                      "falsifier": "the pinned field's change does not predict the target's "
                                   "next-day return beyond the lifetime online-FDR level",
                      "at": at})
        if e["kind"] == "positioning" and vocab:
            col = str(e["driver"]).split(".", 1)[-1]
            spec = col in ("net_pct_oi", "net_noncommercial")
            comm = col in ("comm_pct_oi", "net_commercial")
            fam = ("cot_net_fade" if spec and float(e["beta"]) < 0 else
                   "cot_comm_follow" if comm and float(e["beta"]) > 0 else "")
            if fam in vocab:
                rows.append({"kind": "hypothesis", "family": fam, "symbols": [sym],
                             "mechanism": "positioning_leads_price", "text": claim,
                             "edge_class": cls, "driver": e["driver"]})
    return rows, exprs


def run(catalogue: Any, closes: Mapping[str, pd.Series], at: str, may: Any = None,
        vocab: set[str] | None = None) -> dict[str, Any]:
    rets = daily_returns(closes)
    if not rets:
        return {"status": "UNMEASURED", "why": "no MT5 series with a year of daily closes",
                "census": {k: {"status": "UNMEASURED", "why": "no targets"} for k in KINDS},
                "edges": [], "rows": [], "exprs": []}
    days = pd.DatetimeIndex(sorted(set().union(*[set(r.index) for r in rets.values()])))
    node_rows = nodes(catalogue, days, set(rets))
    edges = classify(rets, node_rows)
    rows, exprs = hypotheses(edges, at, may, vocab)
    cen = census(edges, node_rows, catalogue)
    live = [e for e in edges if e["class"] != "FALSE"]
    return {"status": "MEASURED" if node_rows else "UNMEASURED",
            "why": None if node_rows else "no causal non-price field with a year of history",
            "census": cen, "n_nodes": len(node_rows), "n_edges": len(edges),
            "live_edges": sorted(live, key=lambda e: -abs(float(e["t"])))[:40],
            "kinds_measured": sum(1 for v in cen.values() if v["status"] == "MEASURED"),
            "edges": edges, "rows": rows, "exprs": exprs}


def bars_closes(universe: Path, symbols: list[str]) -> dict[str, pd.Series]:
    out: dict[str, pd.Series] = {}
    for s in symbols:
        p = universe / f"{s}_H1.parquet"
        try:
            df = pd.read_parquet(p, columns=["close"])
        except Exception:
            continue
        c = df["close"].astype(float)
        if isinstance(c.index, pd.DatetimeIndex) and len(c) and math.isfinite(float(c.iloc[-1])):
            out[s] = c
    return out
