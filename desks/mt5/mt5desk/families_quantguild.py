"""TWO MECHANISMS FROM THE QUANT GUILD LECTURES THE DESK COULD NOT EXPRESS (2026-10-06).

Translated from Roman Paolucci's Quant Guild Library (github.com/romanmichaelpaolucci/
Quant-Guild-Library, 2026 lectures). The repository carries NO licence, so nothing here is
copied: both rules are re-derived from the published mechanism (cards QG26-01 and QG26-03 in
`/mnt/project-files/mining/quant_guild/cards_2026.json`) and written causally for MT5 bars.

    kalman_ou_level   An OU fair value tracked by a one-dimensional Kalman filter. Every `refit`
                      bars an AR(1) on the trailing `window` log closes (past only) gives phi, the
                      long-run mean mu and the residual variance; the filter's transition is the
                      OU step and its observation the log close, with R = r_mult x residual
                      variance; a window that cannot reject a unit root (Dickey-Fuller 5%)
                      is not fitted. The filtered level's distance from mu in stationary standard
                      deviations is z; fade |z| >= entry_z towards mu, out by 3 half-lives. The
                      desk's Kalman code works on returns and model scores, never on the level.
    hawkes_jump_switch  Jumps cluster: a self-exciting (exponential Hawkes) intensity, refit on
                      the trailing `window` bars every `refit` bars, says whether a jump arrives
                      inside a cluster (intensity >= hi x baseline -> follow it) or alone (below
                      lo x baseline -> fade it). `family_jump` uses one fixed mode for every jump;
                      `source_civilizations` fits a static branching ratio and trades nothing.

Both are price-only. Signals fire at a bar's close and the engine fills at the next open.
"""
from __future__ import annotations

import math

import numpy as np
import pandas as pd

from mt5desk.engine import Signal
from mt5desk.families import _atr, _h1


#: Dickey-Fuller 5% critical value (constant, no trend). A window whose AR(1) cannot reject a unit
#: root has no mean to revert to: on a trending walk the biased phi < 1 puts "fair value" far off.
DF_CRIT = -2.86


def _ar1(y: np.ndarray) -> tuple[float, float, float] | None:
    """phi, mu, residual variance of y[t] = c + phi y[t-1] + e, by least squares; None unless
    the Dickey-Fuller statistic rejects a unit root."""
    x, z = y[:-1], y[1:]
    xm, zm = x.mean(), z.mean()
    vx = float(((x - xm) ** 2).sum())
    if vx <= 0:
        return None
    phi = float(((x - xm) * (z - zm)).sum() / vx)
    if not 0.0 < phi < 1.0:
        return None
    c = zm - phi * xm
    resid = z - c - phi * x
    var = float(resid.var(ddof=2))
    if not (var > 0 and math.isfinite(var)):
        return None
    if (phi - 1.0) / math.sqrt(var / vx) > DF_CRIT:
        return None
    return phi, c / (1.0 - phi), var


def family_kalman_ou_level(df: pd.DataFrame, *, window: int = 720, refit: int = 24,
                           r_mult: float = 1.0, entry_z: float = 1.5, atr_n: int = 20,
                           stop_atr: float = 2.5, max_ttl: int = 240) -> list[Signal]:
    """Fade the Kalman-filtered OU level's stretch from its long-run mean, back towards it."""
    h = _h1(df)
    if len(h) < window + refit + 2:
        return []
    c = h["close"].to_numpy(dtype=float)
    if not np.all(c > 0):
        return []
    y = np.log(c)
    atr = _atr(h, atr_n).to_numpy()
    out: list[Signal] = []
    fit: tuple[float, float, float] | None = None
    x, p = y[window - 1], 0.0
    busy_until = -1
    for i in range(window, len(y) - 1):
        if (i - window) % refit == 0:
            fit = _ar1(y[i - window:i + 1])
            if fit is not None:
                x, p = y[i - 1], fit[2]
        if fit is None:
            continue
        phi, mu, q = fit
        r = r_mult * q
        xp = phi * x + (1.0 - phi) * mu                       # OU step
        pp = phi * phi * p + q
        k = pp / (pp + r)
        x = xp + k * (y[i] - xp)
        p = (1.0 - k) * pp
        if i <= busy_until:
            continue
        sd = math.sqrt(q / (1.0 - phi * phi))
        zk = (x - mu) / sd
        if abs(zk) < entry_z:
            continue
        a = float(atr[i])
        if not (math.isfinite(a) and a > 0):
            continue
        side = -1 if zk > 0 else 1
        half = -math.log(2.0) / math.log(phi)
        ttl = int(min(max_ttl, max(4, round(3 * half))))
        fair = float(math.exp(mu))
        if (fair - c[i]) * side <= 0:                         # the price already crossed back
            continue
        out.append(Signal(time=h.index[i], side=side, stop=c[i] - side * stop_atr * a,
                          target=fair, ttl_bars=ttl,
                          tag=f"kalman_ou_level:{window}:{entry_z:g}"))
        busy_until = i + ttl
    return out


def _hawkes_fit(t: np.ndarray, span: float) -> tuple[float, float, float] | None:
    """MLE of an exponential Hawkes process (mu, alpha, beta) on event times t in [0, span]."""
    from scipy.optimize import minimize

    if len(t) < 2:
        return None

    def nll(v: np.ndarray) -> float:
        mu, a, b = np.exp(v)
        if a >= b:                                            # non-stationary
            return 1e12
        lam = np.empty(len(t))
        s = 0.0
        for j in range(len(t)):
            if j:
                s = math.exp(-b * (t[j] - t[j - 1])) * (1.0 + s)
            lam[j] = mu + a * s
        comp = mu * span + (a / b) * float(np.sum(1.0 - np.exp(-b * (span - t))))
        return comp - float(np.sum(np.log(lam)))

    n = len(t)
    res = minimize(nll, np.log([0.5 * n / span, 0.3, 0.6]), method="Nelder-Mead",
                   options={"maxiter": 300, "xatol": 1e-3, "fatol": 1e-3})
    if not res.success and res.fun >= 1e11:
        return None
    mu, a, b = (float(v) for v in np.exp(res.x))
    return (mu, a, b) if a < b else None


def family_hawkes_jump_switch(df: pd.DataFrame, *, jump_k: float = 2.5, sigma_n: int = 120,
                              window: int = 4000, refit: int = 120, min_events: int = 80,
                              hi: float = 3.0, lo: float = 1.5, atr_n: int = 20,
                              stop_atr: float = 1.5, rr: float = 1.5,
                              ttl_bars: int = 8) -> list[Signal]:
    """Follow a jump inside a self-exciting cluster, fade a jump that arrives alone."""
    h = _h1(df)
    if len(h) < window + refit + sigma_n:
        return []
    c = h["close"].to_numpy(dtype=float)
    if not np.all(c > 0):
        return []
    r = np.diff(np.log(c), prepend=np.nan)
    ab = np.abs(r)
    bip = pd.Series(ab * np.roll(ab, 1)).rolling(sigma_n).mean().shift(1).to_numpy()
    sigma = np.sqrt(math.pi / 2.0 * bip)
    jump = (ab > jump_k * sigma) & np.isfinite(sigma) & (sigma > 0)
    ev = np.flatnonzero(jump)
    atr = _atr(h, atr_n).to_numpy()
    out: list[Signal] = []
    fit: tuple[float, float, float] | None = None
    busy_until = -1
    next_refit = window
    for i in ev:
        if i < window or i >= len(c) - 1:
            continue
        while next_refit <= i:
            lo_i = next_refit - window
            past = ev[(ev >= lo_i) & (ev < next_refit)]
            fit = (_hawkes_fit((past - lo_i).astype(float), float(window))
                   if len(past) >= min_events else None)
            next_refit += refit
        if fit is None or i <= busy_until:
            continue
        mu, a, b = fit
        prior = ev[(ev < i) & (ev >= i - 10 * ttl_bars / max(b, 1e-6))]
        lam = mu + a * float(np.sum(np.exp(-b * (i - prior)))) if len(prior) else mu
        ratio = lam / mu
        if lo <= ratio < hi:
            continue
        side = int(np.sign(r[i])) * (1 if ratio >= hi else -1)
        at = float(atr[i])
        if side == 0 or not (math.isfinite(at) and at > 0):
            continue
        stop = c[i] - side * stop_atr * at
        out.append(Signal(time=h.index[i], side=side, stop=stop,
                          target=c[i] + side * stop_atr * at * rr, ttl_bars=ttl_bars,
                          tag=f"hawkes_jump_switch:{jump_k:g}:{'follow' if side * r[i] > 0 else 'fade'}"))
        busy_until = i + ttl_bars
    return out


QUANTGUILD_FAMILIES = {
    "kalman_ou_level": family_kalman_ou_level,
    "hawkes_jump_switch": family_hawkes_jump_switch,
}

PARAM_GRID: dict[str, dict[str, list]] = {
    "kalman_ou_level": {"window": [480, 720], "entry_z": [1.5, 2.0]},
    "hawkes_jump_switch": {"jump_k": [2.5, 3.0]},
}

_QG = {"source_culture": "US/en", "participant_structure": "retail_education",
       "crowding_prior": "medium"}
CULTURE: dict[str, dict[str, str]] = {
    "kalman_ou_level": {**_QG, "failure_mode_hypothesis": (
        "fails when the cross's long-run mean itself moves (a policy regime change, a peg "
        "break), which a trailing AR(1) learns only after the loss")},
    "hawkes_jump_switch": {**_QG, "crowding_prior": "low", "failure_mode_hypothesis": (
        "fails when jumps are scheduled releases rather than self-exciting flow, so the "
        "intensity reads a calendar instead of a cascade")},
}
