"""BRAIN HUNTER s31 (2026-08-29) -- the grouping that needs no taxonomy.

THE MECHANISM, extracted from BRAIN's operator set rather than its formulas: `bucket()`
turns a CONTINUOUS attribute into a discrete label (`bucket(rank(x), range="0,1,0.1")`),
and that label is a legal group for group_rank/group_zscore. So a grouping does not require
a sector map, a taxonomy the desk cannot buy, or a clustering whose k six sessions argued
about (s24-s27). It requires ONE POINT-IN-TIME SCALAR PER SYMBOL. That dissolves the
six-session blocker: the desk has had grouping material on its own tape the whole time.

MT5 ANALOGUE (`translate_to_mt5` axis): sector/subindustry -> a bucketed attribute tier
computed from the desk's own bars in year Y-1 and applied in year Y. PIT by construction,
no external data, no licence, no taxonomy.

ARMS (k=24 buckets unless swept, to match the existing ward_k24 / random_k24 arms):
  universe        rank across all symbols with data that day     (what the desk has today)
  bucket_vol      tier by sd of daily log return in Y-1
  bucket_activity tier by count of observed daily bars in Y-1    (trading-intensity proxy)
  bucket_goldbeta tier by OLS beta on XAUUSD daily return in Y-1
  bucket_usdbeta  tier by OLS beta on the equal-weight USD-quoted major basket in Y-1
  ward_k24        the incumbent from s27c/s28, for reference
  random_k24      s27's EXACT control: permute labels AFTER member restriction

=== PREDICTED SIGNS, DECLARED BEFORE THE RUN (s29's rule) ===
P1  bucket_vol beats its exact random control on >=4 of 6 features by gross Sharpe.
    Mechanism: vol tier is the dominant axis of cross-sectional dispersion in raw return
    units, so ranking within a tier removes the mechanical "high-vol names sit at the rank
    extremes every day" artifact that contaminates every return-unit feature.
P2  bucket_vol HURTS lowvol_20 specifically, and this is not a failure but the general rule
    the run is really testing: a bucket grouping built from attribute A neutralises any
    feature that is a function of A. lowvol_20 IS a vol feature; inside a vol tier it is
    close to constant, so its cross-sectional content should collapse toward the control.
P3  bucket_goldbeta does NOT beat its control on the momentum features. There is no reason
    gold-beta is the relevant peer set for a generic momentum ranking; if it wins anyway,
    the grouping axis is not doing what P1 claims and P1's mechanism is wrong.
P4  bucket_activity is the weakest of the four -- bar count is a data-coverage artifact as
    much as a liquidity fact (s23/s24 measured the desk's spread field to be unusable).

NO BAR IS APPLIED (L1.60). This screen sorts and reports EVERY cell tried, winners and
losers, with n beside every number. The ten gates decide.

Run: .venv/bin/python data/brain_hunter_s31_bucket_groupings.py
"""
from __future__ import annotations

import json
import pathlib
import sys
from typing import Any

import numpy as np
import pandas as pd

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from brain_hunter_s27_exact_control import build_panel
from brain_hunter_s28_group_cells import EVAL_YEARS, MIN_NAMES, features, weights

ROOT = pathlib.Path(__file__).resolve().parents[1]
GMAP = ROOT / "data/mt5_grouping_map.json"
OUT = ROOT / "data/brain_hunter_s31_bucket_groupings.json"

K_BUCKETS = 24
K_SWEEP = [4, 8, 24, 48]
SEED = 20260829
RANDOM_DRAWS = 8
MIN_EST_DAYS = 100
USD_MAJORS = ["EURUSD", "GBPUSD", "AUDUSD", "NZDUSD", "USDJPY", "USDCHF", "USDCAD"]


def _bucket(vals: pd.Series, k: int) -> dict[str, str]:
    """BRAIN `bucket(rank(x))`: rank to [0,1], then cut into k equal-count tiers."""
    if len(vals) < k:
        return {}
    pct = vals.rank(pct=True, method="first")
    lab = np.minimum((pct.to_numpy() * k).astype(int), k - 1)
    return {s: f"b{int(v)}" for s, v in zip(vals.index, lab, strict=True)}


def attributes_for_est_year(panel: pd.DataFrame, est_year: int) -> dict[str, pd.Series]:
    """Every attribute is computed on year est_year ONLY and applied in est_year+1."""
    sub = panel[panel.index.year == est_year]
    members = [c for c in sub.columns if sub[c].notna().sum() >= MIN_EST_DAYS]
    if not members:
        return {}
    sub = sub[members]
    out: dict[str, pd.Series] = {
        "vol": sub.std(),
        "activity": sub.notna().sum().astype(float),
    }
    for name, ref_cols in (("goldbeta", ["XAUUSD"]), ("usdbeta", USD_MAJORS)):
        have = [c for c in ref_cols if c in sub.columns]
        if not have:
            continue
        ref = sub[have].mean(axis=1)
        rv = ref.var()
        if not np.isfinite(rv) or rv <= 0:
            continue
        betas = {}
        for c in members:
            both = pd.concat([sub[c], ref], axis=1).dropna()
            if len(both) < MIN_EST_DAYS:
                continue
            v = both.iloc[:, 1].var()
            if v > 0:
                betas[c] = float(both.iloc[:, 0].cov(both.iloc[:, 1]) / v)
        if betas:
            out[name] = pd.Series(betas)
    return out


def build_bucket_maps(panel: pd.DataFrame, k: int) -> dict[str, dict[str, dict[str, str]]]:
    """{attr: {applied_year: {symbol: label}}} -- year Y labelled from year Y-1."""
    maps: dict[str, dict[str, dict[str, str]]] = {}
    years = sorted({int(y) for y in panel.index.year})
    for est in years:
        for attr, vals in attributes_for_est_year(panel, est).items():
            lab = _bucket(vals.dropna(), k)
            if lab:
                maps.setdefault(attr, {})[str(est + 1)] = lab
    return maps


def run_cell(feat: pd.DataFrame, fwd: pd.DataFrame,
             lab_for: Any, rng: np.random.Generator | None) -> dict[str, Any] | None:
    pnl, turn, names, prev = [], [], [], None
    for day, row in feat.iterrows():
        if not (EVAL_YEARS[0] <= day.year <= EVAL_YEARS[1]):
            continue
        w = weights(row, lab_for(day), rng)
        if w is None:
            continue
        nxt = fwd.loc[day].reindex(w.index)
        ok = nxt.notna()
        if ok.sum() < MIN_NAMES:
            continue
        pnl.append(float((w[ok] * nxt[ok]).sum()))
        names.append(int(ok.sum()))
        if prev is not None:
            al = w.reindex(prev.index.union(w.index)).fillna(0.0)
            turn.append(float((al - prev.reindex(al.index).fillna(0.0)).abs().sum()))
        prev = w
    if len(pnl) < 250:
        return None
    p = np.asarray(pnl)
    sd = p.std(ddof=1)
    return {
        "days": len(p), "mean_names": round(float(np.mean(names)), 1),
        "sharpe_gross": round(float(p.mean() / sd * np.sqrt(252)), 3) if sd > 0 else 0.0,
        "t_stat": round(float(p.mean() / sd * np.sqrt(len(p))), 3) if sd > 0 else 0.0,
        "daily_turnover": round(float(np.mean(turn)), 3) if turn else None,
        "bp_per_unit_turnover_to_zero": (
            round(abs(float(p.mean())) / float(np.mean(turn)) * 1e4, 3)
            if turn and np.mean(turn) > 0 else None),
    }


def main() -> None:
    gm = json.loads(GMAP.read_text())
    panel = build_panel()
    fwd = panel.shift(-1)
    feats = features(panel)
    bmaps = build_bucket_maps(panel, K_BUCKETS)
    print("bucket attributes built:", {a: len(v) for a, v in bmaps.items()}, file=sys.stderr)

    def mk(by_year: dict[str, dict[str, str]]) -> Any:
        return lambda d: (dict(by_year[str(d.year)]) if str(d.year) in by_year else None)

    arms: dict[str, Any] = {"universe": (lambda d: None)}
    for attr, by_year in sorted(bmaps.items()):
        arms[f"bucket_{attr}"] = mk(by_year)
    arms["ward_k24"] = mk(gm["ward_cluster_by_year"]["k24"])

    cells: dict[str, Any] = {}
    trials = 0
    for fname, f in feats.items():
        for arm, lab_for in arms.items():
            trials += 1
            r = run_cell(f, fwd, lab_for, None)
            cells[f"{fname}|{arm}"] = r or {"status": "UNMEASURED (too few bars)"}
        # exact size-matched control per grouped arm: permute AFTER restriction (s27)
        for arm, lab_for in arms.items():
            if arm == "universe":
                continue
            ctrl = []
            for i in range(RANDOM_DRAWS):
                trials += 1
                c = run_cell(f, fwd, lab_for, np.random.default_rng(SEED + i))
                if c:
                    ctrl.append(c["sharpe_gross"])
            cells[f"{fname}|{arm}|RANDOM"] = (
                {"draws": len(ctrl), "sharpe_mean": round(float(np.mean(ctrl)), 3),
                 "sharpe_sd": round(float(np.std(ctrl, ddof=1)), 3) if len(ctrl) > 1 else None}
                if ctrl else {"status": "UNMEASURED"})

    # k-sweep on the single best-motivated attribute (s25: a parameter set once is not measured)
    sweep: dict[str, Any] = {}
    for k in K_SWEEP:
        m = build_bucket_maps(panel, k).get("vol")
        if not m:
            continue
        for fname in ("reversal_1", "mom_20"):
            trials += 1
            r = run_cell(feats[fname], fwd, mk(m), None)
            sweep[f"{fname}|bucket_vol_k{k}"] = r or {"status": "UNMEASURED"}

    out = {
        "session": "brain_hunter_s31", "date": "2026-08-29",
        "what": "bucket()-constructed groupings from the desk's own tape; no taxonomy needed",
        "eval_years": list(EVAL_YEARS), "k_buckets": K_BUCKETS, "min_names": MIN_NAMES,
        "trials_run": trials,
        "predictions_declared_before_run": {
            "P1": "bucket_vol beats its exact random control on >=4/6 features",
            "P2": "bucket_vol HURTS lowvol_20 (neutraliser collinear with the feature)",
            "P3": "bucket_goldbeta does NOT beat its control on momentum features",
            "P4": "bucket_activity is the weakest of the four attributes",
        },
        "multiplicity_note": (
            "every cell tried is reported, winners and losers; no bar applied here (L1.60); "
            "trial count is handed to the gauntlet, never screened on locally"),
        "cells": cells, "k_sweep": sweep,
    }
    OUT.write_text(json.dumps(out, indent=2, allow_nan=False) + "\n")
    print(json.dumps({"cells": cells, "k_sweep": sweep}, indent=1))
    print("wrote", OUT)


if __name__ == "__main__":
    main()
