# -*- coding: utf-8 -*-
"""Pre-registered test of tftrailbreakout + tfatrexitbreakout through the REAL discovery gauntlet.

Faithful to trend_basket_returns conventions: lagged signals (no look-ahead), inverse-vol sizing,
gross-normalized to 1, no-trade band, turnover cost. Canonical params (Turtle 20d breakout, 10%
trail, Chandelier ATR14 x3) -- NOT swept, so the Overfit Prosecutor sees a standard strategy.
Run from repo root with the venv python.
"""
from __future__ import annotations

import importlib.util as u
import numpy as np
import pandas as pd

from libs.research.crossasset import _inv_vol, _hold  # exact sizing/holding-cost helpers
from libs.research.alpha_economics import Idea, ev_score

# import run_discovery as a module (reuse its panels, library, gauntlet wiring; main() is guarded)
spec = u.spec_from_file_location("disc", "scripts/run_discovery.py")
disc = u.module_from_spec(spec); spec.loader.exec_module(disc)


def _backtest_positions(close, pos, cost, *, vol_window=30, band=0.05, min_names=4):
    """Net daily returns for an arbitrary LAGGED position matrix (values in {-1,0,1}).

    pos.iloc[t] is the position held INTO ret[t] (decided from data <= t-1), exactly like
    trend_basket_returns applies its shifted trend to ret.iloc[t]."""
    ret = close.pct_change(fill_method=None)
    inv_vol = _inv_vol(ret, vol_window)
    out = np.zeros(len(close), dtype="float64")
    prev = pd.Series(0.0, index=close.columns)
    for t in range(1, len(close)):
        sig = pos.iloc[t].reindex(close.columns).fillna(0.0)
        valid = close.iloc[t].notna() & ret.iloc[t].notna()
        sig = sig.where(valid, 0.0)
        sig = sig[sig != 0.0]
        if len(sig) < min_names:
            out[t] = float((prev * ret.iloc[t].reindex(prev.index).fillna(0.0)).sum()) - _hold(prev, None)
            continue
        iv = inv_vol.iloc[t].reindex(sig.index).fillna(0.0)
        raw = sig * iv
        gross = raw.abs().sum()
        w = pd.Series(0.0, index=close.columns)
        if gross > 0:
            w[sig.index] = raw / gross
        delta = (w - prev).abs()
        w = w.where(delta > band, prev)
        price_ret = float((w * ret.iloc[t].reindex(w.index).fillna(0.0)).sum())
        turn = float(sum(abs(w[s] - prev[s]) * cost.get(s, 1.0e-3) for s in w.index))
        out[t] = price_ret - turn - _hold(w, None)
        prev = w
    return out


def _donchian_positions_trail(close, *, entry_lb=20, trail=0.10):
    """Long on strict new entry_lb-day high / short on new low; exit to flat on a `trail` % stop
    off the best close since entry. Stateful per name; decision at close[i-1] -> earns ret[i]."""
    up = close > close.rolling(entry_lb).max().shift(1)      # strict new N-day high (bool)
    dn = close < close.rolling(entry_lb).min().shift(1)
    pos = pd.DataFrame(0.0, index=close.index, columns=close.columns)
    for s in close.columns:
        c = close[s].to_numpy(); U = up[s].to_numpy(); D = dn[s].to_numpy()
        col = np.zeros(len(c)); state = 0; anchor = np.nan
        for i in range(1, len(c)):
            p = c[i - 1]
            if not np.isnan(p):
                if state == 0:
                    if U[i - 1]: state, anchor = 1, p
                    elif D[i - 1]: state, anchor = -1, p
                elif state == 1:
                    anchor = p if np.isnan(anchor) else max(anchor, p)
                    if p <= anchor * (1 - trail): state, anchor = 0, np.nan
                elif state == -1:
                    anchor = p if np.isnan(anchor) else min(anchor, p)
                    if p >= anchor * (1 + trail): state, anchor = 0, np.nan
            col[i] = state
        pos[s] = col
    return pos


def _donchian_positions_atr(close, *, entry_lb=20, atr_win=14, atr_k=3.0):
    """Same breakout entry; exit on a Chandelier ATR stop (best close since entry -/+ k*ATR).
    ATR is close-only True Range (|dclose|) since the bronze panel is close-driven."""
    atr = close.diff().abs().rolling(atr_win).mean()          # close-only ATR proxy
    up = close > close.rolling(entry_lb).max().shift(1)
    dn = close < close.rolling(entry_lb).min().shift(1)
    pos = pd.DataFrame(0.0, index=close.index, columns=close.columns)
    for s in close.columns:
        c = close[s].to_numpy(); U = up[s].to_numpy(); D = dn[s].to_numpy(); A = atr[s].to_numpy()
        col = np.zeros(len(c)); state = 0; anchor = np.nan
        for i in range(1, len(c)):
            p = c[i - 1]; a = A[i - 1]
            if not np.isnan(p) and not np.isnan(a):
                if state == 0:
                    if U[i - 1]: state, anchor = 1, p
                    elif D[i - 1]: state, anchor = -1, p
                elif state == 1:
                    anchor = p if np.isnan(anchor) else max(anchor, p)
                    if p <= anchor - atr_k * a: state, anchor = 0, np.nan
                elif state == -1:
                    anchor = p if np.isnan(anchor) else min(anchor, p)
                    if p >= anchor + atr_k * a: state, anchor = 0, np.nan
            col[i] = state
        pos[s] = col
    return pos


def main() -> None:
    close, funding, basis, taker, adv = disc._panels()
    print(f"panel: {close.shape[1]} names x {close.shape[0]} daily bars")
    cost = {s: disc.adv_tier_cost(a) for s, a in adv.items()}
    lib = disc._candidates(close, funding, basis, taker, adv, cost)   # the real book

    lib["tftrailbreakout"] = _backtest_positions(close, _donchian_positions_trail(close), cost)
    lib["tfatrexitbreakout"] = _backtest_positions(close, _donchian_positions_atr(close), cost)
    lib = {k: v for k, v in lib.items() if np.isfinite(v).all()}

    validate, Hypothesis = disc.validate, disc.Hypothesis
    Family, MechanismType, sharpe_ratio = disc.Family, disc.MechanismType, disc.sharpe_ratio

    df = pd.DataFrame(lib, index=close.index)
    corr = df.replace(0.0, np.nan).corr()
    matrix = np.column_stack([lib[k] for k in lib])
    sharpes = np.array([sharpe_ratio(lib[k][lib[k] != 0.0]) for k in lib])
    pbo, rc = disc.campaign_pbo_rc(matrix)

    print(f"\n{'sleeve':20s} {'annSh':>6s} {'gates':>7s} {'maxcorr':>7s} {'orth':>5s}  status")
    new = {}
    for name, r in lib.items():
        active = r[r != 0.0]
        sh = disc._ann(r)
        others = corr[name].drop(labels=[name], errors="ignore").abs()
        max_corr = round(float(others.max()), 2) if not others.empty else 0.0
        orth = max_corr < disc._ORTHO
        v = (validate(active, hypothesis=Hypothesis(
                family=Family.CARRY, subtype=name, symbol="CRYPTO", params={},
                mechanism=MechanismType.RISK_PREMIUM, edge_source=name, failure_modes=disc._FAIL),
                n_trials=len(lib), sharpe_estimates=sharpes, returns_matrix=matrix, pbo=pbo, rc=rc)
             if len(active) >= 250 else None)
        gates = f"{sum(v.gates.values())}/{len(v.gates)}" if v else "n<250"
        survived = bool(v.survived) if v else False
        status = ("DEPLOYABLE" if survived else "SHADOW" if (sh > 0.5 and orth)
                  else "CANDIDATE" if sh > 0.4 else "REJECTED")
        flag = "  <== TEST" if name in ("tftrailbreakout", "tfatrexitbreakout") else ""
        print(f"{name:20s} {sh:6.2f} {gates:>7s} {max_corr:7.2f} {str(orth):>5s}  {status}{flag}")
        if name in ("tftrailbreakout", "tfatrexitbreakout"):
            new[name] = (sh, max_corr, len(active))

    print("\n=== EV gate (pre-registered economics) ===")
    for name, (sh, mc, n) in new.items():
        idea = Idea(name=name, est_sharpe=max(sh, 0.0), breadth=close.shape[1],
                    orthogonality=round(1.0 - mc, 3), effort_h=6.0,
                    tags=["price_only", "crowded_known"])
        print(" ", ev_score(idea))


if __name__ == "__main__":
    main()
