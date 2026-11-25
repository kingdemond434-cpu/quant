"""COINTEGRATION PAIRS: an Engle-Granger tested pair, traded only while the test holds.

WHY THIS IS NOT `relative_value`. `families_orthogonal.family_relative_value` fades the rolling
z-score of `log(a) - log(b)`: a hedge ratio of one and no test that the spread is stationary at
all. Two trending instruments with a drifting ratio give it extreme z-scores forever, and it
fades every one. This family is the textbook statistical-arbitrage construction instead:

    1. on a trailing `lookback` window, OLS `log a = alpha + beta * log b`  (the hedge ratio)
    2. an Engle-Granger ADF regression on that residual,
           d e_t = c + gamma * e_{t-1} + sum_i phi_i * d e_{t-i} + eps,
       with the pair called cointegrated only when the t-statistic of gamma is below `adf_crit`
       (default -3.37: the 5% Engle-Granger critical value for two variables at a few hundred
       observations, MacKinnon's response surface; fixed, never fitted)
    3. the half-life of mean reversion from an AR(1) on the residual, `-ln 2 / ln rho`, and the
       pair traded only while that half-life lies inside [hl_min, hl_max] bars
    4. entry when |z| >= entry_z (z = the residual against the window's own mean and spread),
       re-armed only after |z| has come back inside exit_z; the target is the A-leg price at
       which z would be back at exit_z, the time stop `hl_mult` half-lives.

A SINGLE-LEG PROXY, exactly as relative_value is: it trades THIS instrument against its peer's
residual, because the engine does not hold paired positions. The limitation is stated, not hidden:
the target assumes the peer leg stands still.

NO LOOKAHEAD. The fit that decides bars [t0, t0 + refit) uses joined rows t0 - lookback .. t0 - 1
only: the hedge ratio, the test, the half-life and the z normalisation are all read off bars at or
before t - 1 for a signal at t, and the refit grid is anchored at a fixed row so it never moves as
history grows. `test_gen_methods` perturbs future bars and asserts past signals do not change.

THE PEER, by relative_value's convention: the cell names it as `peer_symbol` (an identity key) and
the frame is loaded on this cell's own chart. The sealed gauntlet passes `peer_symbol` through to
the family, which reads the bars itself (`family_inputs.bars_named`, as lead_lag and triangle do);
the forward engine strips identity keys and hands the frame in as `peer_bars`
(`family_inputs.resolve`). Nothing here has authority: proposed, charged, judged.
"""
from __future__ import annotations

import math
from typing import Any

import numpy as np
import pandas as pd
from mt5desk.families import Signal, _atr, _h1, register_family

#: The 5% Engle-Granger critical value, two variables, constant, a few hundred observations.
ADF_CRIT_5PCT_2VAR = -3.37


def ols_hedge(a: np.ndarray, b: np.ndarray) -> tuple[float, float]:
    """(alpha, beta) of a = alpha + beta * b by least squares."""
    bm, am = b.mean(), a.mean()
    vb = float(((b - bm) ** 2).sum())
    if vb <= 0:
        return float(am), 0.0
    beta = float(((b - bm) * (a - am)).sum() / vb)
    return float(am - beta * bm), beta


def adf_tstat(e: np.ndarray, lags: int = 1) -> float:
    """t-statistic of gamma in d e_t = c + gamma e_{t-1} + sum phi_i d e_{t-i} (numpy only)."""
    e = np.asarray(e, dtype=float)
    lags = max(0, int(lags))
    de = np.diff(e)
    n = len(de) - lags
    if n < 20:
        return float("nan")
    y = de[lags:]
    cols = [np.ones(n), e[lags:-1]]
    cols += [de[lags - i:len(de) - i] for i in range(1, lags + 1)]
    x = np.column_stack(cols)
    xtx = x.T @ x
    try:
        inv = np.linalg.inv(xtx)
    except np.linalg.LinAlgError:
        return float("nan")
    coef = inv @ (x.T @ y)
    resid = y - x @ coef
    dof = n - x.shape[1]
    if dof <= 0:
        return float("nan")
    s2 = float(resid @ resid) / dof
    se = math.sqrt(max(s2 * float(inv[1, 1]), 0.0))
    return float(coef[1] / se) if se > 0 else float("nan")


def half_life(e: np.ndarray) -> float:
    """AR(1) half-life in bars, `-ln 2 / ln rho`; inf when the residual does not revert."""
    e = np.asarray(e, dtype=float)
    x, y = e[:-1], e[1:]
    xm = x - x.mean()
    vx = float(xm @ xm)
    if vx <= 0:
        return float("inf")
    rho = float(xm @ (y - y.mean())) / vx
    if not 0.0 < rho < 1.0:
        return float("inf")
    return float(-math.log(2.0) / math.log(rho))


def coint_state(la: np.ndarray, lb: np.ndarray, lookback: int, refit: int, adf_lags: int,
                adf_crit: float) -> dict[str, np.ndarray]:
    """Per joined row: z, residual sd, half-life, and whether the pair was cointegrated, every
    quantity fitted on rows strictly before the row it describes."""
    n = len(la)
    z = np.full(n, np.nan)
    sd_out = np.full(n, np.nan)
    hl_out = np.full(n, np.inf)
    coint = np.zeros(n, dtype=bool)
    lookback, refit = max(60, int(lookback)), max(1, int(refit))
    for t0 in range(lookback, n, refit):
        a, b = la[t0 - lookback:t0], lb[t0 - lookback:t0]
        if not (np.isfinite(a).all() and np.isfinite(b).all()):
            continue
        alpha, beta = ols_hedge(a, b)
        e = a - alpha - beta * b
        mu, sd = float(e.mean()), float(e.std(ddof=1))
        if not np.isfinite(sd) or sd <= 0:
            continue
        stat = adf_tstat(e, adf_lags)
        hl = half_life(e)
        t1 = min(n, t0 + refit)
        z[t0:t1] = (la[t0:t1] - alpha - beta * lb[t0:t1] - mu) / sd
        sd_out[t0:t1] = sd
        hl_out[t0:t1] = hl
        coint[t0:t1] = bool(np.isfinite(stat) and stat < adf_crit)
    return {"z": z, "sd": sd_out, "hl": hl_out, "coint": coint}


@register_family(param_grid={"lookback": [250, 500, 1000], "entry_z": [1.5, 2.0, 2.5]},
                 tags=["cointegration", "pairs", "stat_arb", "generated", "relative_value"])
def family_coint_pairs(df: pd.DataFrame, *, peer_symbol: str = "",
                       peer_bars: pd.DataFrame | None = None, lookback: int = 500,
                       refit: int = 24, entry_z: float = 2.0, exit_z: float = 0.5,
                       hl_min: float = 2.0, hl_max: float = 120.0,
                       adf_crit: float = ADF_CRIT_5PCT_2VAR, adf_lags: int = 1,
                       hl_mult: float = 2.0, max_hold: int = 480, stop_atr: float = 2.5,
                       atr_n: int = 20) -> list[Signal]:
    peer = peer_bars
    if peer is None and peer_symbol:
        from mt5desk.family_inputs import bars_named
        peer = bars_named(str(peer_symbol), df)
    if peer is None or getattr(peer, "empty", True) or "close" not in peer.columns:
        return []
    d, p = _h1(df), _h1(peer)
    joined = d[["close"]].join(p[["close"]], how="inner", rsuffix="_peer").dropna()
    if len(joined) < int(lookback) * 2:
        return []
    ca = joined["close"].to_numpy(dtype=float)
    cb = joined["close_peer"].to_numpy(dtype=float)
    if (ca <= 0).any() or (cb <= 0).any():
        return []
    if np.allclose(ca, cb):
        return []                                         # the peer is this instrument
    st = coint_state(np.log(ca), np.log(cb), lookback, refit, adf_lags, adf_crit)
    atr = _atr(d, atr_n).reindex(joined.index).ffill().to_numpy(dtype=float)
    z, sd, hl, coint = st["z"], st["sd"], st["hl"], st["coint"]
    idx = joined.index
    out: list[Signal] = []
    armed = True
    busy_until = -1
    entry_z, exit_z = float(entry_z), max(0.0, float(exit_z))
    for i in range(int(lookback), len(joined) - 1):
        zi = z[i]
        if not np.isfinite(zi):
            continue
        if abs(zi) <= exit_z:
            armed = True
        if i <= busy_until or not armed or abs(zi) < entry_z or not coint[i]:
            continue
        if not hl_min <= hl[i] <= hl_max:
            continue
        av = atr[i]
        if not np.isfinite(av) or av <= 0:
            continue
        side = -1 if zi > 0 else 1                        # rich -> short this leg; cheap -> long
        px = float(ca[i])
        ttl = int(min(max(2, round(float(hl_mult) * hl[i])), int(max_hold)))
        out.append(Signal(time=idx[i], side=side, stop=px - side * stop_atr * av,
                          target=px * math.exp(side * (abs(zi) - exit_z) * sd[i]),
                          ttl_bars=ttl, tag="coint_pairs", trigger=None, wait_bars=1))
        armed = False
        busy_until = i + ttl
    return out


def coint_report(df: pd.DataFrame, peer: pd.DataFrame, lookback: int = 500,
                 adf_lags: int = 1) -> dict[str, Any]:
    """The test on the LAST full window, for a human: hedge ratio, ADF t, half-life."""
    d, p = _h1(df), _h1(peer)
    j = d[["close"]].join(p[["close"]], how="inner", rsuffix="_peer").dropna().iloc[-lookback:]
    a, b = np.log(j["close"].to_numpy(float)), np.log(j["close_peer"].to_numpy(float))
    alpha, beta = ols_hedge(a, b)
    e = a - alpha - beta * b
    return {"beta": beta, "adf_t": adf_tstat(e, adf_lags), "half_life": half_life(e),
            "cointegrated_5pct": bool(adf_tstat(e, adf_lags) < ADF_CRIT_5PCT_2VAR)}
