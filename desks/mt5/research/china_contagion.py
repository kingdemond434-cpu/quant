"""CHINA SUPPLY-CHAIN / CREDIT CONTAGION -- GAP_MAP row 31, as one hourly leg.

THE GAP (wired ledger 2026-11-13): "China supply-chain/credit knowledge graph and contagion (CN AI
shops' corporate GNNs)" -- evidence "none; learned gnn_propagation runs on a price-only lead-lag
graph". This leg is the measurement and the proposer; `libs/research/china_graph.py` is the
graph; `research/china_exposure_ingest.py` measures its weights; `libs/models/
learned_propagation` takes the graph as the GNN's `knowledge` adjacency.

EACH PASS:

  1. WEIGHTS. `china_exposure_ingest.refresh()` (weekly; daily while nothing has measured): UN
     Comtrade China export shares and HS-chapter shares for every country node.
  2. GRAPH. Build it, compute each instrument's signed exposure and its channels, write
     data/china_graph.json (nodes, edges with MEASURED/STRUCTURAL status, exposures).
  3. STRESS. The daily China stress index from the markets that price a Chinese shock first
     (USDCNH, CHINAH, HK50, XCUUSD on the desk's own bars), vol-scaled, signed, causal. This is
     a PRICE-SIDE credit proxy. The official default/credit notices (CSRC, SSE, SZSE, ChinaMoney)
     are not fetched: their terms have not been read under this desk's agent, and the Global
     data lane's rule is that an unread term is a refusal -- the report says so by name.
  4. CONTAGION, MEASURED. For every instrument the graph reaches: the contemporaneous beta of its
     vol-scaled daily return on the stress index (leave-one-out for the sources), the next-day
     beta and IC (does the slower market catch up?), stress-day conditional next-day mean
     (|stress| >= 2), and an expanding-window walk-forward OOS IC of the next-day relation.
     Then the graph is SCORED: the rank correlation between the graph's exposures and the
     measured contemporaneous betas -- whether the knowledge graph explains the contagion the
     market actually shows. An unsigned instrument (JPY, CHF, gold) gets its sign MEASURED here.
  5. PROPOSE. Family `china_stress_contagion` on every reached instrument over a declared grid
     (direction x window x entry_z x hold), every configuration charged as a trial whether or not
     it screened; `proposer_common.screen` -> `deflate` -> `best_per_cell` -> `donate`, the door
     every proposer uses. The judge decides; nothing here sizes or promotes.

OUTPUTS: reports/CHINA_CONTAGION.json, data/china_graph.json, data/intelligence/
china_contagion/discoveries_*.json (via donate). Hourly leg `china_contagion`.

    python desks/mt5/research/china_contagion.py [--budget-s 600] [--no-donate]
"""
from __future__ import annotations

import argparse
import json
import math
import os
import sys
import time
from collections.abc import Mapping
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

DESK = Path(__file__).resolve().parents[1]
ROOT = DESK.parents[1]
for _p in (str(ROOT), str(DESK), str(DESK / "research")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from libs.research import china_graph  # noqa: E402
from mt5desk.family_china_contagion import (  # noqa: E402
    daily_close,
    family_china_stress_contagion,
    stress_index,
)

SOURCE = "china_contagion"
FAMILY = "china_stress_contagion"
REPORT = DESK / "reports" / "CHINA_CONTAGION.json"
GRAPH_OUT = DESK / "data" / "china_graph.json"
#: The declared grid, fixed before any result: every point is a trial.
GRID = [{"direction": d, "window": w, "entry_z": z, "hold_bars": h}
        for d in ("same", "opposite") for w in (1, 3) for z in (1.5, 2.0) for h in (24, 72)]
STRESS_DAY_Z = 2.0
MIN_DAYS = 250
OFFICIAL_NOTICE_SOURCES = {
    "CSRC": "REFUSED_TERMS_UNREAD", "SSE": "REFUSED_TERMS_UNREAD",
    "SZSE": "REFUSED_TERMS_UNREAD", "ChinaMoney (CFETS)": "REFUSED_TERMS_UNREAD",
    "HKEX": "REFUSED_ON_TERMS (Global data journal 2026-11-13)"}


def _vol_scaled_daily(df: pd.DataFrame) -> pd.Series:
    dc = daily_close(df)
    r = np.log(dc).diff()
    vol = r.ewm(halflife=20, min_periods=30).std().shift(1)
    return (r / vol).where(vol > 0)


def _beta_ic(x: pd.Series, y: pd.Series) -> dict[str, Any]:
    j = pd.concat([x, y], axis=1).dropna()
    if len(j) < 60:
        return {"status": "UNMEASURED", "n": int(len(j))}
    a, b = j.iloc[:, 0].to_numpy(), j.iloc[:, 1].to_numpy()
    va = float(np.var(a))
    beta = float(np.cov(a, b)[0, 1] / va) if va > 0 else float("nan")
    ic = float(np.corrcoef(a, b)[0, 1])
    t = ic * math.sqrt(max(1, len(j) - 2)) / math.sqrt(max(1e-12, 1 - ic * ic))
    return {"status": "MEASURED", "n": int(len(j)), "beta": round(beta, 4), "ic": round(ic, 4),
            "t": round(t, 2)}


def _oos_ic(x: pd.Series, y: pd.Series, min_train: int = 250, step: int = 21) -> dict[str, Any]:
    """Expanding-window walk-forward: fit beta on [0, k), predict [k, k+step); IC of the
    concatenated out-of-sample predictions against the realised next-day returns."""
    j = pd.concat([x, y], axis=1).dropna()
    if len(j) < min_train + 60:
        return {"status": "UNMEASURED", "n": int(len(j))}
    a, b = j.iloc[:, 0].to_numpy(), j.iloc[:, 1].to_numpy()
    preds, real = [], []
    for k in range(min_train, len(j), step):
        va = float(np.var(a[:k]))
        if va <= 0:
            continue
        beta = float(np.cov(a[:k], b[:k])[0, 1] / va)
        preds.extend((beta * a[k:k + step]).tolist())
        real.extend(b[k:k + step].tolist())
    if len(preds) < 60 or np.std(preds) == 0:
        return {"status": "UNMEASURED", "n": len(preds)}
    ic = float(np.corrcoef(preds, real)[0, 1])
    t = ic * math.sqrt(len(preds) - 2) / math.sqrt(max(1e-12, 1 - ic * ic))
    return {"status": "MEASURED", "n_oos": len(preds), "oos_ic": round(ic, 4), "t": round(t, 2)}


def measure(bars: Mapping[str, pd.DataFrame], ex: Mapping[str, Mapping[str, Any]]
            ) -> dict[str, Any]:
    signs = china_graph.stress_sources()
    out: dict[str, Any] = {}
    for inst, e in sorted(ex.items()):
        df = bars.get(inst)
        if df is None:
            out[inst] = {"status": "UNMEASURED_NO_BARS"}
            continue
        st = stress_index({s: bars[s] for s in signs if s in bars}, signs, exclude=inst)
        if st["stress"].notna().sum() < MIN_DAYS:
            out[inst] = {"status": "UNMEASURED_STRESS_HISTORY",
                         "stress_days": int(st["stress"].notna().sum())}
            continue
        y = _vol_scaled_daily(df)
        s = st["stress"]
        nxt = y.shift(-1)
        same_day = _beta_ic(s, y)
        next_day = _beta_ic(s, nxt)
        j = pd.concat([s, nxt], axis=1).dropna()
        hot = j[j.iloc[:, 0].abs() >= STRESS_DAY_Z]
        cond = ({"n": int(len(hot)),
                 "mean_signed_next": round(float((np.sign(hot.iloc[:, 0]) * hot.iloc[:, 1])
                                                 .mean()), 4)}
                if len(hot) >= 10 else {"n": int(len(hot)), "status": "UNMEASURED"})
        rec = {"status": "MEASURED", "graph_exposure": e.get("exposure"),
               "graph_sign": e.get("sign"), "same_day": same_day, "next_day": next_day,
               "stress_day_next": cond, "walk_forward": _oos_ic(s, nxt)}
        if not e.get("sign") and same_day.get("status") == "MEASURED":
            rec["measured_sign"] = int(np.sign(same_day["beta"])) if abs(same_day["t"]) >= 2 \
                else 0
        if e.get("sign") and same_day.get("status") == "MEASURED":
            rec["sign_agrees"] = bool(np.sign(same_day["beta"]) == np.sign(e["sign"]))
        out[inst] = rec
    pairs = [(float(v["graph_exposure"]), float(v["same_day"]["beta"]))
             for v in out.values() if v.get("status") == "MEASURED" and v.get("graph_sign")
             and v["same_day"].get("status") == "MEASURED"]
    score: dict[str, Any] = {"n": len(pairs)}
    if len(pairs) >= 5:
        g, m = np.array(pairs).T
        rg, rm = pd.Series(g).rank().to_numpy(), pd.Series(m).rank().to_numpy()
        score.update(status="MEASURED", spearman=round(float(np.corrcoef(rg, rm)[0, 1]), 4),
                     sign_agreement=round(float(np.mean(np.sign(g) == np.sign(m))), 3))
    else:
        score["status"] = "UNMEASURED_FEW_INSTRUMENTS"
    return {"instruments": out, "graph_vs_market": score}


def propose(bars: Mapping[str, pd.DataFrame], reached: Mapping[str, int], *,
            budget_s: float, donate: bool = True) -> dict[str, Any]:
    from research import proposer_common as pc
    meta = pc.universe_meta()
    signs = china_graph.stress_sources()
    t0 = time.monotonic()
    rows: list[dict[str, Any]] = []
    attempted = 0
    skipped: dict[str, str] = {}
    for inst, sgn in sorted(reached.items()):
        t = bars.get(inst)
        if t is None:
            skipped[inst] = "no bars"
            continue
        if time.monotonic() - t0 > budget_s:
            skipped[inst] = "budget exhausted"
            continue
        cost = pc.cost_frac(inst, meta, t["close"])
        if cost is None:
            skipped[inst] = "no contract terms"
            continue
        unf = pc.artifact_hours(t)
        srcs = {s: bars[s] for s in signs if s in bars and s != inst}
        for g in GRID:
            attempted += 1
            params = {"exposure_sign": int(sgn), **g}
            sig = family_china_stress_contagion(t, symbol=inst, sources=srcs, **params)
            sc = pc.screen(t, sig, cost, unf)
            if sc is None:
                continue
            rows.append({"cell": f"{inst}.{FAMILY}.{g['direction']}", "symbol": inst,
                         "params": params, **sc})
    rows = pc.deflate(rows)
    # charge the ATTEMPTED count, not the screened one: a configuration that never fired was
    # still a trial the sweep ran
    from research.multiplicity import deflate_t
    for r in rows:
        r["n_tests_attempted"] = attempted
        r["t_deflated_attempted"] = round(deflate_t(float(r["t_gross"]), max(1, attempted)), 3)
        r["proposed"] = bool(r["proposed"] and r["t_deflated_attempted"] > pc.PROPOSE_T)
    best = pc.best_per_cell(rows)
    cands = [pc.candidate(
        SOURCE, r["symbol"], FAMILY, dict(r["params"]),
        mechanism=(f"China stress reaches {r['symbol']} through the knowledge graph (exposure "
                   f"sign {r['params']['exposure_sign']:+d}); "
                   + ("the slower market catches up the next day" if r["params"]["direction"]
                      == "same" else "the first day over-prices the shock and it reverts")),
        title=f"{r['cell']} w={r['params']['window']} z>={r['params']['entry_z']} "
              f"hold={r['params']['hold_bars']}",
        evidence={k: r.get(k) for k in ("n_independent", "gross_per_trade", "net_per_trade",
                                        "cost_frac", "t_gross", "t_deflated_sweep",
                                        "t_deflated_attempted", "n_tests_attempted")})
        for r in best]
    out: dict[str, Any] = {"tests_attempted": attempted, "tests_screened": len(rows),
                           "cells_proposed": len(best), "skipped": skipped,
                           "proposals": [{k: v for k, v in r.items() if k not in ("pnl",
                                                                                   "entry_pos")}
                                         for r in best[:20]]}
    if donate and cands:
        out["donated"] = str(pc.donate(SOURCE, cands, attempted))
        out["donation"] = dict(pc.donation_counts())
    return out


def load_bars(symbols: list[str]) -> dict[str, pd.DataFrame]:
    from mt5desk.family_learned_propagation import load_peer
    out = {}
    for s in symbols:
        df = load_peer(s)
        if df is not None and len(df) >= 500:
            out[s] = df
    return out


def run(*, budget_s: float = 600.0, donate: bool = True, write: bool = True,
        bars: Mapping[str, pd.DataFrame] | None = None, refresh_weights: bool = True,
        now: datetime | None = None) -> dict[str, Any]:
    now = now or datetime.now(UTC)
    t0 = time.monotonic()
    weights: dict[str, Any] = {}
    if refresh_weights:
        try:
            from research import china_exposure_ingest as ing
            w = ing.refresh(now=now)
            weights = {"refreshed": w.get("refreshed"), "year": w.get("year"),
                       "n_measured": w.get("n_measured"), "attempts": w.get("attempts")}
        except Exception as exc:  # noqa: BLE001 -- the graph falls back to labelled priors
            weights = {"error": f"{type(exc).__name__}: {str(exc)[:200]}"}
    g = china_graph.build()
    ex = china_graph.exposures(g)
    reached = china_graph.reached(g)
    universe = sorted(set(china_graph.instruments(g)) | set(china_graph.stress_sources()))
    b = dict(bars) if bars is not None else load_bars(universe)
    meas = measure(b, ex)
    # an unsigned instrument whose sign the market measured joins the proposal set
    for inst, rec in meas["instruments"].items():
        if inst not in reached and rec.get("measured_sign"):
            reached[inst] = int(rec["measured_sign"])
    remaining = max(0.0, budget_s - (time.monotonic() - t0))
    signs = china_graph.stress_sources()
    n_src = sum(1 for s in signs if s in b)
    if n_src < 2:
        # no index can be formed: every family call would refuse, so no trial is charged
        prop: dict[str, Any] = {"status": "UNMEASURED_NO_STRESS_SOURCES", "sources_with_bars":
                                n_src, "tests_attempted": 0, "cells_proposed": 0}
    else:
        prop = propose(b, reached, budget_s=remaining * 0.9, donate=donate)
    st = stress_index({s: b[s] for s in signs if s in b}, signs)
    latest = st.dropna().tail(1)
    doc_graph = {"generated_at": now.isoformat(timespec="seconds"), **g.to_doc(),
                 "exposures": ex}
    report = {
        "generated_at": now.isoformat(timespec="seconds"),
        "organ": "desks/mt5/research/china_contagion.py", "gap_row": "GAP_MAP 31",
        "weights": weights,
        "graph": {k: doc_graph[k] for k in ("measured_year", "n_measured_edges",
                                            "n_structural_edges")},
        "instruments_reached": len(reached), "bars_available": sorted(b),
        "stress_sources": signs,
        "stress_latest": ({"date": str(latest.index[-1].date()),
                           "stress": round(float(latest["stress"].iloc[-1]), 3),
                           "n_sources": int(latest["n_sources"].iloc[-1])}
                          if len(latest) else "UNMEASURED"),
        "credit_proxy": "PRICE_SIDE (CNH, H-shares, Hang Seng, copper on the desk's own bars)",
        "official_notice_sources": OFFICIAL_NOTICE_SOURCES,
        "contagion": meas, "proposer": prop,
        "gnn_hook": "libs.models.learned_propagation adjacency kind 'knowledge' / "
                    "'knowledge_lead_lag' (gnn_propagation family, learned_miners grid)",
        "status": ("OK" if n_src >= 2 else "UNMEASURED_NO_STRESS_SOURCES") if b
        else "UNMEASURED_NO_BARS",
        "elapsed_s": round(time.monotonic() - t0, 1)}
    if write:
        for path, doc in ((GRAPH_OUT, doc_graph), (REPORT, report)):
            path.parent.mkdir(parents=True, exist_ok=True)
            tmp = path.with_suffix(".json.tmp")
            tmp.write_text(json.dumps(doc, indent=1, default=str), encoding="utf-8")
            os.replace(tmp, path)
    return report


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n", 1)[0])
    ap.add_argument("--budget-s", type=float, default=600.0)
    ap.add_argument("--no-donate", action="store_true")
    a = ap.parse_args(argv)
    r = run(budget_s=a.budget_s, donate=not a.no_donate)
    gv = r["contagion"]["graph_vs_market"]
    p = r["proposer"]
    print(f"china_contagion: status={r['status']} reached={r['instruments_reached']} "
          f"bars={len(r['bars_available'])} graph_vs_market={gv.get('spearman', gv['status'])} "
          f"tests={p.get('tests_attempted')} proposed={p.get('cells_proposed')} "
          f"weights_measured={r['weights'].get('n_measured')} elapsed={r['elapsed_s']}s")
    return 0


if __name__ == "__main__":
    sys.exit(main())
