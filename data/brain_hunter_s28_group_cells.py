"""BRAIN HUNTER s28 (2026-08-29) -- the conversion six sessions have owed.

s11 built a grouping map. s24-s27 argued about which arm to use and finally held the
population and settled it (ward k24, data/brain_hunter_s27c_common_population.json).
NOTHING HAS EVER CONSUMED ANY ARM: `grep -rl mt5_grouping_map libs desks scripts` returns
operators.py, wq_operators.py and build_bars.py -- the operator definitions and a bar
builder. Zero hypotheses. The independence gain was measured only on the RULER, never on a
signal, so the desk has six sessions of evidence about a ruler and none about money.

This runs the cross-sectional cells the ruler was always a proxy for. Every cell is a
(feature x neutralization) pair on daily MT5 closes, PIT throughout:

  feature       reversal_1, mom_5, mom_20, mom_60, accel (mom_5 - mom_20), lowvol_20
  neutraliser   universe   -- rank across ALL symbols with data that day (what the desk has)
                ward_k24   -- group_rank within the PIT cluster (Y from Y-1)
                asset_class, currency_quote  -- the two static arms, for reference
                random_k24 -- labels permuted AFTER member restriction (s27's exact control)

Weights are rank-demeaned and gross-normalised to 1.0, held one day, applied to the NEXT
day's log return. Dollar-neutral by construction within each ranking population.

NO BAR IS APPLIED HERE (L1.60). This is a screen: it sorts and reports, and reports EVERY
cell tried including the losers, with n printed beside every number (the s25-s27 habit).
The ten gates decide; nothing here is a promotion or a rejection.

Run: .venv/bin/python data/brain_hunter_s28_group_cells.py
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

ROOT = pathlib.Path(__file__).resolve().parents[1]
GMAP = ROOT / "data/mt5_grouping_map.json"
OUT = ROOT / "data/brain_hunter_s28_group_cells.json"
OUT_VOID = ROOT / "data/brain_hunter_s28_group_cells_VOID_calendar_bug.json"

EVAL_YEARS = (2019, 2026)   # inclusive range of traded years
MIN_NAMES = 8               # a cross-sectional bar needs a cross-section
SEED = 20260829
RANDOM_DRAWS = 8


def _roll(panel: pd.DataFrame, w: int, how: str) -> pd.DataFrame:
    """Rolling window over each symbol's OWN VALID OBSERVATIONS, then reindexed.

    THE BUG THIS FIXES, and it is the reason the first s28 run is void for 5 of 6 features:
    a naive `panel.rolling(w)` needs w CONSECUTIVE non-NaN rows in the shared calendar. The
    panel's index is the union of every symbol's days, so a weekend, a holiday, or any symbol
    with a different trading calendar inserts a NaN that annihilates the window for EVERYONE.
    Measured: mean cross-section fell from 140.6 names (no rolling) to ~12.7 (any rolling) --
    an 89% silent loss of the cross-section, on a run that otherwise reported clean numbers.
    `mean_names` printed beside every score is what caught it (the s25-s27 habit, fourth turn).
    """
    out = {}
    for c in panel.columns:
        s = panel[c].dropna()
        r = s.rolling(w, min_periods=w)
        out[c] = (r.sum() if how == "sum" else r.std()).reindex(panel.index)
    return pd.DataFrame(out, index=panel.index)


def features(panel: pd.DataFrame) -> dict[str, pd.DataFrame]:
    """All PIT: every value at date t uses returns up to and including t, and is applied to
    t+1's return by the caller. No feature reads its own forward bar."""
    r = panel
    return {
        "reversal_1": -r,
        "mom_5": _roll(r, 5, "sum"),
        "mom_20": _roll(r, 20, "sum"),
        "mom_60": _roll(r, 60, "sum"),
        "accel": _roll(r, 5, "sum") - _roll(r, 20, "sum"),
        "lowvol_20": -_roll(r, 20, "std"),
    }


def labels_for_day(day: pd.Timestamp, arm: str,
                   gm: dict[str, Any]) -> dict[str, str] | None:
    if arm == "universe":
        return None
    if arm in ("asset_class", "currency_quote"):
        return dict(gm[arm])
    by = gm["ward_cluster_by_year"]["k24"]
    got = by.get(str(day.year))
    return dict(got) if got else None


def weights(row: pd.Series, lab: dict[str, str] | None,
            rng: np.random.Generator | None) -> pd.Series | None:
    """Rank-demeaned, gross-normalised cross-sectional weights for one bar."""
    x = row.dropna()
    if len(x) < MIN_NAMES:
        return None
    if lab is None:
        pct = x.rank(pct=True)
        w = pct - pct.mean()
    else:
        members = [s for s in x.index if s in lab]
        if len(members) < MIN_NAMES:
            return None
        vals = [lab[s] for s in members]
        if rng is not None:
            rng.shuffle(vals)                       # s27 ordering: restrict first, then permute
        lb = pd.Series(vals, index=members)
        keep = lb.map(lb.value_counts()) >= 2
        members = [s for s in members if keep[s]]
        if len(members) < MIN_NAMES:
            return None
        x, lb = x[members], lb[members]
        pct = x.groupby(lb).rank(pct=True)
        w = pct - pct.groupby(lb).transform("mean")  # neutral WITHIN each peer group
    g = w.abs().sum()
    if g <= 0:
        return None
    return w / g


def run_cell(feat: pd.DataFrame, fwd: pd.DataFrame, arm: str, gm: dict[str, Any],
             rng: np.random.Generator | None) -> dict[str, Any] | None:
    pnl, turn, names, prev = [], [], [], None
    for day, row in feat.iterrows():
        if not (EVAL_YEARS[0] <= day.year <= EVAL_YEARS[1]):
            continue
        w = weights(row, labels_for_day(day, arm, gm), rng)
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
            pl = prev.reindex(al.index).fillna(0.0)
            turn.append(float((al - pl).abs().sum()))
        prev = w
    if len(pnl) < 250:
        return None
    p = np.asarray(pnl)
    sd = p.std(ddof=1)
    sharpe = float(p.mean() / sd * np.sqrt(252)) if sd > 0 else 0.0
    return {
        "days": len(p), "mean_names": round(float(np.mean(names)), 1),
        "sharpe_gross": round(sharpe, 3),
        "t_stat": round(float(p.mean() / sd * np.sqrt(len(p))), 3) if sd > 0 else 0.0,
        "ann_return": round(float(p.mean() * 252), 5),
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
    arms = ["universe", "ward_k24", "asset_class", "currency_quote"]
    cells, trials = {}, 0
    for fname, f in feats.items():
        for arm in arms:
            trials += 1
            res = run_cell(f, fwd, arm, gm, None)
            cells[f"{fname}|{arm}"] = res if res else {"status": "UNMEASURED (too few bars)"}
        # exact size-matched control, averaged over draws
        ctrl = []
        for i in range(RANDOM_DRAWS):
            trials += 1
            r = run_cell(f, fwd, "ward_k24", gm, np.random.default_rng(SEED + i))
            if r:
                ctrl.append(r["sharpe_gross"])
        cells[f"{fname}|random_k24"] = (
            {"draws": len(ctrl), "sharpe_mean": round(float(np.mean(ctrl)), 3),
             "sharpe_sd": round(float(np.std(ctrl, ddof=1)), 3) if len(ctrl) > 1 else None}
            if ctrl else {"status": "UNMEASURED"})
    out = {
        "session": "brain_hunter_s28", "date": "2026-08-29",
        "what": "first consumption of mt5_grouping_map by a SIGNAL rather than a ruler",
        "eval_years": list(EVAL_YEARS), "min_names": MIN_NAMES,
        "trials_run": trials,
        "multiplicity_note": (
            "every cell tried is reported, winners and losers; no bar applied here (L1.60) -- "
            "trial count is handed to the gauntlet, never screened on locally"),
        "costs_note": (
            "sharpe_gross is BEFORE costs. bp_per_unit_turnover_to_zero is the round-trip cost "
            "in bp that takes the cell to zero; compare against the symbol's real spread."),
        "cells": cells,
    }
    OUT.write_text(json.dumps(out, indent=2, allow_nan=False) + "\n")
    print(json.dumps(cells, indent=1))
    print("wrote", OUT)


if __name__ == "__main__":
    main()
