"""The cross-asset information graph: X_t -> Y_{t+h}, with lag, state, stability and value.

Edges are INFERRED, never asserted: for every (driver, target) pair the module measures, on
H1 bars, whether the driver's past return carries information about the target's next return:

    lag             the h in 1..MAX_LAG with the largest |t| of the regression of y_{t+h} on x_t
    t_stat          that regression's t (HAC-lite: non-overlapping targets at horizon h)
    state_dep       |t| on high-volatility bars minus |t| on calm bars (does the edge live in a
                    state?)
    stability       sign agreement of the coefficient across four quarters of the history
    incremental     out-of-sample log-likelihood gain of a sign forecast using x over the base
                    rate -- the number that says the edge is FORECAST value, not a correlation
    plausibility    from `economic_drivers.ROLES`: a declared causal role (USD, RATES, RISK,
                    GOLD, OIL, GROWTH) makes an edge plausible; an undeclared pair is labelled
                    STATISTICAL and must clear a higher bar

EVENT PROPAGATION. After a scheduled high-impact release the chain leader -> laggard is measured
the same way but conditioned on event bars: the second-order trade is the laggard's move after
an abnormal leader reaction, and `event_propagation` reports the lag and value of each chain.

`graph()` returns the edges; `desks/mt5/research/cross_asset_graph.py` turns the strong ones
into `lead_lag` cells for the gauntlet.
"""
from __future__ import annotations

import math
from typing import Any

import numpy as np
import pandas as pd

MAX_LAG = 6
MIN_OBS = 500


def _align(driver: pd.DataFrame, target: pd.DataFrame) -> tuple[np.ndarray, np.ndarray, pd.Index]:
    d = driver["close"].astype(float)
    t = target["close"].astype(float)
    d.index = pd.DatetimeIndex(pd.to_datetime(d.index, utc=True, errors="coerce"))
    t.index = pd.DatetimeIndex(pd.to_datetime(t.index, utc=True, errors="coerce"))
    d = d[~d.index.duplicated(keep="last")].sort_index()
    t = t[~t.index.duplicated(keep="last")].sort_index()
    j = pd.concat([np.log(d).diff().rename("x"), np.log(t).diff().rename("y")], axis=1,
                  join="inner").dropna()
    return j["x"].to_numpy(), j["y"].to_numpy(), j.index


def _t_reg(x: np.ndarray, y: np.ndarray) -> tuple[float, float]:
    if x.size < 30 or x.std() == 0 or y.std() == 0:
        return 0.0, 0.0
    xc = x - x.mean()
    beta = float(xc @ (y - y.mean()) / (xc @ xc))
    resid = y - y.mean() - beta * xc
    se = math.sqrt(float(resid @ resid) / max(x.size - 2, 1) / float(xc @ xc))
    return beta, (beta / se if se > 0 else 0.0)


def _oos_gain(x: np.ndarray, y: np.ndarray) -> float:
    """Walk-forward log-score gain of a logistic sign forecast over the base rate (nats)."""
    n = x.size
    if n < 200:
        return 0.0
    cut = n // 2
    xs = (x - x[:cut].mean()) / max(x[:cut].std(), 1e-12)
    yb = (y > 0).astype(float)
    p0 = yb[:cut].mean()
    w = 0.0
    for _ in range(200):                                     # 1-d logistic, gradient steps
        p = 1 / (1 + np.exp(-(w * xs[:cut] + math.log(p0 / (1 - p0) + 1e-12))))
        w -= 0.5 * float(((p - yb[:cut]) * xs[:cut]).mean() + 1e-3 * w)
    p_te = 1 / (1 + np.exp(-(w * xs[cut:] + math.log(p0 / (1 - p0) + 1e-12))))
    p_te = np.clip(p_te, 1e-6, 1 - 1e-6)
    ll = float(np.mean(yb[cut:] * np.log(p_te) + (1 - yb[cut:]) * np.log(1 - p_te)))
    base = float(np.mean(yb[cut:] * np.log(p0) + (1 - yb[cut:]) * np.log(1 - p0)))
    return ll - base


def edge(driver: pd.DataFrame, target: pd.DataFrame, *, plausible_role: str | None = None,
         max_lag: int = MAX_LAG) -> dict[str, Any]:
    x, y, _idx = _align(driver, target)
    if x.size < MIN_OBS:
        return {"verdict": "UNMEASURED", "n": int(x.size)}
    best: dict[str, Any] = {"lag": 0, "t": 0.0, "beta": 0.0}
    for h in range(1, max_lag + 1):
        xs, ys = x[:-h], np.array([y[i + 1:i + 1 + h].sum() for i in range(x.size - h)])
        xs, ys = xs[::h], ys[::h]                            # non-overlapping targets
        beta, t = _t_reg(xs, ys)
        if abs(t) > abs(best["t"]):
            best = {"lag": h, "t": round(t, 2), "beta": round(beta, 6)}
    h = int(best["lag"]) or 1
    xs = x[:-h][::h]
    ys = np.array([y[i + 1:i + 1 + h].sum() for i in range(x.size - h)])[::h]
    vol = pd.Series(y).rolling(48, min_periods=24).std().to_numpy()[:-h][::h]
    hi = np.isfinite(vol) & (vol > np.nanmedian(vol))
    t_hi = _t_reg(xs[hi], ys[hi])[1] if hi.sum() > 30 else 0.0
    t_lo = _t_reg(xs[~hi], ys[~hi])[1] if (~hi).sum() > 30 else 0.0
    q = max(1, xs.size // 4)
    signs = [np.sign(_t_reg(xs[i * q:(i + 1) * q], ys[i * q:(i + 1) * q])[0]) for i in range(4)]
    stability = float(np.mean([s == np.sign(best["beta"]) for s in signs if s != 0] or [0.0]))
    gain = _oos_gain(xs, ys)
    plaus = "CAUSAL_ROLE" if plausible_role else "STATISTICAL"
    bar = 3.0 if plaus == "CAUSAL_ROLE" else 4.0
    strong = abs(best["t"]) >= bar and stability >= 0.75 and gain > 0
    return {"verdict": "EDGE" if strong else "NO_EDGE", **best, "n": int(xs.size),
            "state_dep": round(abs(t_hi) - abs(t_lo), 2), "t_high_vol": round(t_hi, 2),
            "t_low_vol": round(t_lo, 2), "stability": round(stability, 2),
            "incremental_logscore": round(gain, 6), "plausibility": plaus,
            "role": plausible_role, "t_bar": bar,
            "direction": ("same" if best["beta"] > 0 else "opposite")}


def event_propagation(leader: pd.DataFrame, laggard: pd.DataFrame, event_times: list[Any],
                      *, react_bars: int = 2, follow_bars: int = 6,
                      abnormal_z: float = 1.5) -> dict[str, Any]:
    """After an event, does an ABNORMAL leader reaction predict the laggard's follow-through?"""
    x, y, idx = _align(leader, laggard)
    if x.size < MIN_OBS or not event_times:
        return {"verdict": "UNMEASURED", "n_events": len(event_times)}
    pos = {ts: i for i, ts in enumerate(idx)}
    sd = float(np.std(x)) or 1e-9
    xs, ys = [], []
    for ev in event_times:
        try:
            t0 = pd.Timestamp(ev)
            t0 = t0.tz_localize("UTC") if t0.tzinfo is None else t0.tz_convert("UTC")
        except (TypeError, ValueError):
            continue
        i = pos.get(idx[idx.searchsorted(t0)] if idx.searchsorted(t0) < len(idx) else None)
        if i is None or i + react_bars + follow_bars >= x.size:
            continue
        react = float(x[i:i + react_bars].sum())
        if abs(react) / (sd * math.sqrt(react_bars)) < abnormal_z:
            continue
        xs.append(react)
        ys.append(float(y[i + react_bars:i + react_bars + follow_bars].sum()))
    if len(xs) < 20:
        return {"verdict": "UNMEASURED", "n_abnormal": len(xs)}
    beta, t = _t_reg(np.asarray(xs), np.asarray(ys))
    return {"verdict": "CHAIN" if abs(t) >= 2.5 else "NO_CHAIN", "n_abnormal": len(xs),
            "beta": round(beta, 6), "t": round(t, 2), "react_bars": react_bars,
            "follow_bars": follow_bars,
            "direction": "same" if beta > 0 else "opposite"}


def graph(bars: dict[str, pd.DataFrame], pairs: list[tuple[str, str, str | None]]
          ) -> dict[str, Any]:
    """All requested (driver, target, role) edges; the strong ones first."""
    edges = []
    for d, t, role in pairs:
        if d not in bars or t not in bars or d == t:
            continue
        e = edge(bars[d], bars[t], plausible_role=role)
        edges.append({"driver": d, "target": t, **e})
    edges.sort(key=lambda e: -abs(float(e.get("t", 0.0))))
    return {"n_pairs": len(edges), "n_edges": sum(1 for e in edges if e.get("verdict") == "EDGE"),
            "edges": edges}
