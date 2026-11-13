"""Microstructure-noise ratio and the volatility signature plot, per symbol, from the venue's own
tick tape.

    GAP_MAP, Max-growth (cost) + State-engine row (2026-11-13): "Microstructure-noise ratio /
    signature plot per symbol"

WHY. An observed mid price is the efficient price plus noise (bid-ask bounce, discreteness, stale
quotes): p_obs = p* + e. Realised variance summed at sampling interval D then estimates
IV + 2 n(D) omega^2, so it EXPLODES as D shrinks -- that is the signature plot (Andersen,
Bollerslev, Diebold & Labys 2000). The size of the explosion is the noise variance omega^2, and
its ratio to the integrated variance is how much of what a short-horizon signal "sees" is
the venue's own noise rather than price. A desk that trades M5/M15 scalps and measures their edge
on bar closes needs this number per symbol: below the horizon where noise dominates, edge
measured on closes is partly bounce, and the cost model's spread is not the whole cost.

WHAT IT GIVES, per symbol per day, then pooled over the window:
    signature   RV at sampling intervals 5 s .. 60 min (previous-tick mid on a calendar grid)
    omega2      noise variance, Bandi & Russell (2006): (RV(tick-by-tick) - IV) / (2 n_ticks),
                with the Zhang-Mykland-Ait-Sahalia (2005) TSRV as the noise-robust IV
    nsr         noise-to-signal ratio omega2 / IV_tsrv
    noise_share share of RV(D) that is noise at D = 1, 5, 15 min: 2 n(D) omega2 / RV(D)
    d_opt_s     Bandi-Russell MSE-optimal sampling interval, n* = (IV / (4 omega2^2))^(1/3)
    roll        Roll (1984) effective spread from the first-order autocovariance of tick
                returns, beside the quoted median spread -- the cost model's own number
    min_horizon_s  the shortest interval at which noise is below 10% of RV: the honest floor for
                   any signal measured on closes of that symbol

All are measurements. Consumers: the cost surface and the scalp lane's horizon floor, through the
lab's artifact; nothing here changes an order.
"""
from __future__ import annotations

import math
from collections.abc import Iterable, Sequence
from typing import Any

import numpy as np
import pandas as pd

GRID_S: tuple[int, ...] = (5, 15, 30, 60, 120, 300, 600, 900, 1800, 3600)
#: TSRV slow-scale subsampling K (ticks), the ZMA recommendation n^(2/3) bounded.
TSRV_K_MIN = 5
NOISE_SHARE_TOL = 0.10
MIN_TICKS_DAY = 500


def mid_series(ticks: pd.DataFrame) -> pd.Series:
    """Mid log price on the tick index, one row per distinct timestamp (last quote wins)."""
    df = ticks.dropna(subset=["bid", "ask"])
    df = df[(df["bid"] > 0) & (df["ask"] >= df["bid"])]
    ts = pd.to_datetime(df["ts"], utc=True)
    mid = np.log((df["bid"].to_numpy(float) + df["ask"].to_numpy(float)) / 2.0)
    s = pd.Series(mid, index=ts).sort_index()
    s = s[~s.index.duplicated(keep="last")]
    return s[s.diff().fillna(1.0) != 0.0] if len(s) > 1 else s


def rv_at(mid: pd.Series, step_s: int) -> tuple[float, int]:
    """Realised variance from previous-tick sampling on a calendar grid of `step_s` seconds."""
    if mid.size < 3:
        return float("nan"), 0
    grid = pd.date_range(mid.index[0].ceil(f"{step_s}s"), mid.index[-1], freq=f"{step_s}s")
    if grid.size < 3:
        return float("nan"), 0
    pos = np.searchsorted(mid.index.values, grid.values, side="right") - 1
    pos = pos[pos >= 0]
    p = mid.to_numpy()[pos]
    r = np.diff(p)
    return float((r * r).sum()), int(r.size)


def tsrv(mid: pd.Series, k: int | None = None) -> float:
    """Two-scales realised variance (Zhang, Mykland & Ait-Sahalia 2005), small-sample adjusted."""
    p = mid.to_numpy()
    n = p.size - 1
    if n < 20:
        return float("nan")
    k = k or max(TSRV_K_MIN, round(n ** (2.0 / 3.0) / 2))
    k = min(k, n // 2)
    rv_all = float((np.diff(p) ** 2).sum())
    rv_k = float(sum((np.diff(p[j::k]) ** 2).sum() for j in range(k)) / k)
    nbar = (n - k + 1) / k
    est = float((rv_k - (nbar / n) * rv_all) / (1.0 - nbar / n))
    return est


def roll_spread(mid: pd.Series) -> float | None:
    r = np.diff(mid.to_numpy())
    if r.size < 50:
        return None
    c = float(np.cov(r[1:], r[:-1])[0, 1])
    return 2.0 * math.sqrt(-c) if c < 0 else 0.0


def day_reading(ticks: pd.DataFrame) -> dict[str, Any] | None:
    mid = mid_series(ticks)
    if mid.size < MIN_TICKS_DAY:
        return None
    r_tick = np.diff(mid.to_numpy())
    rv_tick = float((r_tick ** 2).sum())
    n = int(r_tick.size)
    iv = tsrv(mid)
    # Bandi-Russell's RV/(2n) carries the efficient price's own IV/(2n); subtract the TSRV IV so a
    # liquid, quiet symbol is not read as noisy by its own variance (measured: 3x bias without it).
    omega2 = max(rv_tick - (iv if math.isfinite(iv) and iv > 0 else 0.0), 0.0) / (2.0 * n)
    sig = {s: rv_at(mid, s) for s in GRID_S}
    spread_q = (ticks["ask"] - ticks["bid"]) / ((ticks["ask"] + ticks["bid"]) / 2.0)
    return {"n_ticks": n, "rv_tick": rv_tick, "omega2": omega2, "iv_tsrv": iv,
            "signature": {s: v for s, (v, _m) in sig.items()},
            "n_at": {s: m for s, (_v, m) in sig.items()},
            "roll": roll_spread(mid),
            "quoted_spread_rel": float(np.nanmedian(spread_q.to_numpy(float)))}


def pool(days: Iterable[dict[str, Any]]) -> dict[str, Any]:
    """Median-pool day readings into one symbol reading (medians: one news day must not set it)."""
    d = [x for x in days if x]
    if not d:
        return {"status": "UNMEASURED", "why": "no day with enough ticks"}
    def med(k: str) -> float:
        vals = [x[k] for x in d if x[k] is not None]
        return float(np.nanmedian(vals)) if vals else float("nan")

    omega2, iv = med("omega2"), med("iv_tsrv")
    sig = {s: float(np.nanmedian([x["signature"][s] for x in d])) for s in GRID_S}
    n_at = {s: float(np.nanmedian([x["n_at"][s] for x in d])) for s in GRID_S}
    share: dict[int, float | None] = {
        s: (2.0 * n_at[s] * omega2 / sig[s]) if sig[s] > 0 else None for s in GRID_S}
    min_h = next((s for s in GRID_S
                  if (v := share[s]) is not None and v < NOISE_SHARE_TOL), None)
    n_star = (iv / (4.0 * omega2 ** 2)) ** (1.0 / 3.0) if iv > 0 and omega2 > 0 else None
    span = float(np.nanmedian([x["n_at"][GRID_S[0]] for x in d])) * GRID_S[0]
    d_opt = (span / n_star) if n_star else None
    rolls = [x["roll"] for x in d if x["roll"] is not None]
    roll = float(np.median(rolls)) if rolls else None
    q = med("quoted_spread_rel")
    return {"status": "MEASURED", "days": len(d), "omega2": omega2, "iv_tsrv": iv,
            "nsr": (omega2 / iv) if iv > 0 else None,
            "signature": {str(s): v for s, v in sig.items()},
            "noise_share": {str(s): share[s] for s in (60, 300, 900)},
            "d_opt_s": d_opt, "min_horizon_s": min_h,
            "roll_spread_rel": roll, "quoted_spread_rel": q,
            "roll_over_quoted": (roll / q) if roll is not None and q and q > 0 else None,
            "signature_slope": signature_slope(sig)}


def signature_slope(sig: dict[int, float]) -> float | None:
    """d log RV / d log D across the grid: 0 for a noise-free price, toward -1 when noise rules."""
    xs = [math.log(s) for s in sig if sig[s] and sig[s] > 0]
    ys = [math.log(sig[s]) for s in sig if sig[s] and sig[s] > 0]
    if len(xs) < 4:
        return None
    return float(np.polyfit(xs, ys, 1)[0])


def from_bars(closes: Sequence[float]) -> dict[str, Any]:
    """The fallback for a symbol with no tape: Roll and lag-1 autocorrelation from M1 closes. A
    weaker reading and labelled so; never presented as the tick measurement."""
    p = np.log(np.asarray(closes, dtype=float))
    r = np.diff(p[np.isfinite(p)])
    if r.size < 500:
        return {"status": "UNMEASURED", "why": f"{r.size} bar returns < 500"}
    c = float(np.cov(r[1:], r[:-1])[0, 1])
    ac1 = float(np.corrcoef(r[1:], r[:-1])[0, 1])
    return {"status": "BARS_ONLY", "roll_spread_rel": 2.0 * math.sqrt(-c) if c < 0 else 0.0,
            "lag1_autocorr": ac1, "omega2_upper": max(0.0, -c)}
