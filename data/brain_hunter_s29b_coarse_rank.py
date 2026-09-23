"""BRAIN HUNTER s29b (2026-08-29) -- the platform's OWN rank operator is coarse, and the
desk's cross-sectional cells die on turnover. Those two facts belong together.

SOURCE (mined as TEXT, GPL-3.0, nothing installed/vendored):
efJerryYang/worldquant-brain-simulator `src/alpha_pool/expression.py:154`, which quotes the
platform's own operator description verbatim:

    "The Rank operator ranks the value of the input data x for the given stock among all
     instruments, and returns float numbers equally distributed between 0.0 and 1.0.
     When rate is set to 0, the sorting is done precisely. The default value of rate is 2."

So the platform's DEFAULT rank is deliberately IMPRECISE, and every desk implementation
(`x.rank(pct=True)`) is the rate=0 precise case. The simulator itself accepts `rate` and
then ignores it -- the semantic is in the docstring and in nothing else.

WHY IT MATTERS HERE AND NOT AS TRIVIA. s28's best cell (`reversal_1|ward_k24`) has gross
t=2.33 and dies at a break-even of 1.60 bp per unit turnover on 147% DAILY turnover. The
binding constraint on this whole family is TURNOVER, not signal. A coarser rank makes the
weight vector piecewise-constant, so a name that drifts within its bucket generates no
trade at all.

THE FALSIFIABLE CLAIM, declared before the run:
    coarsening the rank into B buckets reduces daily turnover FASTER than it reduces gross
    mean return, so BREAK-EVEN BP PER UNIT TURNOVER RISES MONOTONICALLY as B falls.
    Refuted if break-even does not rise at any coarsening step, or is non-monotone.

NO BAR IS APPLIED (L1.60). Screen only; every B tried is reported. The ten gates decide.

Run: .venv/bin/python data/brain_hunter_s29b_coarse_rank.py
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
from brain_hunter_s28_group_cells import _roll, labels_for_day, EVAL_YEARS, MIN_NAMES

ROOT = pathlib.Path(__file__).resolve().parents[1]
GMAP = ROOT / "data/mt5_grouping_map.json"
OUT = ROOT / "data/brain_hunter_s29b_coarse_rank.json"

BUCKETS = [0, 50, 20, 10, 5, 3]   # 0 = precise (rate=0), the desk's current behaviour


def _coarsen(pct: pd.Series, b: int) -> pd.Series:
    """Bucketed rank: the rate>0 semantic. b=0 leaves the precise rank untouched."""
    if b <= 0:
        return pct
    return np.ceil(pct * b) / b


def weights(row: pd.Series, lab: dict[str, str] | None, b: int) -> pd.Series | None:
    x = row.dropna()
    if len(x) < MIN_NAMES:
        return None
    if lab is None:
        pct = _coarsen(x.rank(pct=True), b)
        w = pct - pct.mean()
    else:
        members = [s for s in x.index if s in lab]
        if len(members) < MIN_NAMES:
            return None
        lb = pd.Series({s: lab[s] for s in members})
        keep = lb.map(lb.value_counts()) >= 2
        members = [s for s in members if keep[s]]
        if len(members) < MIN_NAMES:
            return None
        x, lb = x[members], lb[members]
        pct = _coarsen(x.groupby(lb).rank(pct=True), b)
        w = pct - pct.groupby(lb).transform("mean")
    g = w.abs().sum()
    return None if g <= 0 else w / g


def run(feat: pd.DataFrame, fwd: pd.DataFrame, arm: str, gm: dict[str, Any],
        b: int) -> dict[str, Any] | None:
    pnl, turn, names, prev = [], [], [], None
    for day, r in feat.iterrows():
        if not (EVAL_YEARS[0] <= day.year <= EVAL_YEARS[1]):
            continue
        w = weights(r, labels_for_day(day, arm, gm), b)
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
    tv = float(np.mean(turn)) if turn else None
    return {
        "buckets": ("precise" if b <= 0 else b),
        "days": len(p), "mean_names": round(float(np.mean(names)), 1),
        "sharpe_gross": round(float(p.mean() / sd * np.sqrt(252)), 3) if sd > 0 else 0.0,
        "t_stat": round(float(p.mean() / sd * np.sqrt(len(p))), 3) if sd > 0 else 0.0,
        "ann_return": round(float(p.mean() * 252), 5),
        "daily_turnover": round(tv, 3) if tv else None,
        "bp_per_unit_turnover_to_zero": (
            round(abs(float(p.mean())) / tv * 1e4, 3) if tv and tv > 0 else None),
    }


def main() -> None:
    gm = json.loads(GMAP.read_text())
    panel = build_panel()
    fwd = panel.shift(-1)
    cells = {
        "reversal_1|ward_k24": (-panel, "ward_k24"),
        "reversal_1|universe": (-panel, "universe"),
        "lowvol_20|ward_k24": (-_roll(panel, 20, "std"), "ward_k24"),
    }
    out_cells: dict[str, Any] = {}
    trials = 0
    for name, (feat, arm) in cells.items():
        rows = []
        for b in BUCKETS:
            trials += 1
            r = run(feat, fwd, arm, gm, b)
            rows.append(r if r else {"buckets": b, "status": "UNMEASURED"})
        out_cells[name] = rows
        be = [(r.get("buckets"), r.get("bp_per_unit_turnover_to_zero")) for r in rows
              if isinstance(r, dict) and r.get("bp_per_unit_turnover_to_zero") is not None]
        vals = [v for _, v in be]
        out_cells[name + "|__verdict"] = {
            "break_even_bp_by_bucket": be,
            "rises_from_precise": (len(vals) > 1 and max(vals[1:]) > vals[0]),
            "monotone_rising": all(b_ > a for a, b_ in zip(vals, vals[1:])) if len(vals) > 1 else None,
        }
    out = {
        "session": "brain_hunter_s29b", "date": "2026-08-29",
        "source": ("efJerryYang/worldquant-brain-simulator src/alpha_pool/expression.py:154 "
                   "(GPL-3.0, mined as TEXT; nothing installed, executed or vendored)"),
        "claim": ("coarsening the cross-sectional rank cuts turnover faster than gross return, "
                  "so break-even bp per unit turnover rises monotonically as buckets fall"),
        "falsifier": "refuted if break-even does not rise at any coarsening, or is non-monotone",
        "buckets_tried": BUCKETS, "trials_run": trials,
        "eval_years": list(EVAL_YEARS), "min_names": MIN_NAMES,
        "multiplicity_note": ("every bucket tried is reported; no bar applied here (L1.60) -- "
                              "the trial count is handed to the gauntlet"),
        "cells": out_cells,
    }
    OUT.write_text(json.dumps(out, indent=2, allow_nan=False) + "\n")
    print(json.dumps(out_cells, indent=1))


if __name__ == "__main__":
    main()
