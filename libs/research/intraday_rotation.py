"""Intraday rotation/continuation engine — built to FALSIFY the XAUUSD-derived hypothesis.

Pre-registered in docs/research/INTRADAY_ROTATION_PREREGISTRATION.md (2026-08-04, before any
data). Everything here follows that file; where an implementation choice remained, the
conservative side was taken and is commented at the site.

DESIGN. Candidate bars are detected vectorised; each candidate is then resolved by a bounded
forward scan (max `time_stop` bars), which keeps the whole 540-config grid tractable without a
per-bar Python loop over 300k bars. Lookahead discipline: every quantity used to ADMIT a bar-t
entry is computed from data ending at bar t (boundaries exclude bar t itself: shifted rolling
extrema), and fills happen at bar t's close (rotation, taker) or at a later bar's limit touch
(continuation, maker). The self-test in tests/ shuffles future bars and demands the entry set
not change — the Part-3 "watch for" made mechanical.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import numpy as np

TAKER_BPS = 4.0 + 1.0        # taker fee + 1bp slippage on market legs (entries, stop exits)
MAKER_BPS = 2.0              # limit fills: continuation entries, boundary targets
ER_RANGE = 0.25              # efficiency-ratio ceiling for RANGE
ER_TREND = 0.45              # floor for TREND
ER_WINDOW = 48
ATR_WINDOW = 20
STOP_ATR_BUFFER = 0.25
LOCATION_MIN_RR = 2.0        # opposing boundary must be >= 2x the stop distance away
PARTIAL_R = 0.75             # variant (c): take half at 0.75R
BREAKOUT_ATR_MULT = 1.5

N_GRID = (24, 48, 96)
K_GRID = (6, 12, 24)
M_GRID = (24, 48, 96)
EXIT_VARIANTS = ("r1.5", "r2", "r3", "boundary", "mimic")


@dataclass
class Trade:
    entry_i: int
    exit_i: int
    side: int                # +1 long, -1 short
    entry_px: float
    exit_px: float
    stop_px: float
    r_multiple: float        # net of fees/funding, in R units
    net_ret: float           # net fractional return on notional
    regime: str
    exit_reason: str
    hour_utc: int
    partial: bool = False


@dataclass
class ConfigResult:
    symbol: str
    strategy: str            # rotation | continuation
    n: int
    k: int                  # 0 for rotation
    m: int
    exit_variant: str
    trades: list[Trade] = field(default_factory=list)
    n_unfilled: int = 0      # continuation limits cancelled after K bars

    def r_series(self) -> np.ndarray:
        return np.asarray([t.r_multiple for t in self.trades], dtype="float64")


def atr(high: np.ndarray, low: np.ndarray, close: np.ndarray, window: int = ATR_WINDOW
        ) -> np.ndarray:
    prev = np.concatenate([[close[0]], close[:-1]])
    tr = np.maximum(high - low, np.maximum(np.abs(high - prev), np.abs(low - prev)))
    out = np.full_like(tr, np.nan)
    if len(tr) >= window:
        c = np.cumsum(tr)
        out[window - 1:] = (c[window - 1:] - np.concatenate([[0.0], c[:-window]])) / window
    return np.asarray(out)


def efficiency_ratio(close: np.ndarray, window: int = ER_WINDOW) -> np.ndarray:
    d = np.abs(np.diff(close, prepend=close[0]))
    cd = np.cumsum(d)
    denom = np.full_like(close, np.nan)
    denom[window:] = cd[window:] - cd[:-window]
    num = np.full_like(close, np.nan)
    num[window:] = np.abs(close[window:] - close[:-window])
    with np.errstate(invalid="ignore", divide="ignore"):
        return np.where(denom > 0, num / denom, 0.0)


def regimes(close: np.ndarray) -> np.ndarray:
    """0 = RANGE, 1 = TREND, 2 = TRANSITION (and warmup NaN -> TRANSITION, which trades nothing)."""
    er = efficiency_ratio(close)
    out = np.full(len(close), 2, dtype=np.int8)
    out[er < ER_RANGE] = 0
    out[er > ER_TREND] = 1
    out[np.isnan(er)] = 2
    return out


def _shifted_extrema(high: np.ndarray, low: np.ndarray, n: int) -> tuple[np.ndarray, np.ndarray]:
    """Rolling N-bar high/low EXCLUDING the current bar — the boundary a bar-t decision may see.

    Including bar t is the classic rotation-backtest lookahead: the bar that tags the boundary
    also defines it, so every touch is 'at the boundary' by construction. sliding_window_view
    over [t-n, t) keeps this honest.
    """
    from numpy.lib.stride_tricks import sliding_window_view
    hi = np.full(len(high), np.nan)
    lo = np.full(len(low), np.nan)
    if len(high) > n:
        hi[n:] = sliding_window_view(high, n)[:-1].max(axis=1)
        lo[n:] = sliding_window_view(low, n)[:-1].min(axis=1)
    return hi, lo


def _funding_cost(times_ms: np.ndarray, i0: int, i1: int, side: int,
                  f_time: np.ndarray, f_rate: np.ndarray) -> float:
    """Sum of funding paid while open across settlements in (t_entry, t_exit]. Long pays +rate."""
    if len(f_time) == 0:
        return 0.0
    a = np.searchsorted(f_time, times_ms[i0], side="right")
    b = np.searchsorted(f_time, times_ms[i1], side="right")
    if b <= a:
        return 0.0
    return float(side * np.sum(f_rate[a:b]))


def _resolve(side: int, entry_i: int, entry_px: float, stop_px: float,
             high: np.ndarray, low: np.ndarray, close: np.ndarray,
             opp_boundary: float, variant: str, m: int,
             times_ms: np.ndarray, f_time: np.ndarray, f_rate: np.ndarray,
             regime: str, entry_bps: float) -> Trade | None:
    """Forward-scan one entry to its exit. Conservative tie-break: when stop and target are both
    inside one bar's range, the STOP fills — intrabar path is unknown and the pessimistic order
    is the one that cannot flatter the result."""
    risk = abs(entry_px - stop_px)
    if risk <= 0:
        return None
    if variant.startswith("r"):
        target = entry_px + side * float(variant[1:]) * risk
    elif variant == "boundary":
        target = opp_boundary
    else:                                     # mimic: partial at 0.75R then swing-trail
        target = entry_px + side * PARTIAL_R * risk
    n_bars = len(close)
    end = min(entry_i + m, n_bars - 1)
    partial_done = False
    realised = 0.0                            # fraction of position already banked (mimic)
    trail = stop_px
    exit_i, exit_px, reason = end, close[end], "time"
    exit_bps = TAKER_BPS                      # time exits go at market
    for j in range(entry_i + 1, end + 1):
        hit_stop = low[j] <= trail if side > 0 else high[j] >= trail
        hit_tgt = high[j] >= target if side > 0 else low[j] <= target
        if hit_stop:                          # pessimistic order: stop first
            exit_i, exit_px, reason, exit_bps = j, trail, "stop", TAKER_BPS
            break
        if hit_tgt:
            if variant == "mimic" and not partial_done:
                realised = 0.5 * PARTIAL_R    # half the position banked at 0.75R (maker)
                partial_done = True
                trail = entry_px              # remainder now risk-free to entry
                target = entry_px + side * 1e12   # no fixed target; trail owns the rest
                continue
            exit_i, exit_px, reason = j, target, "target"
            exit_bps = MAKER_BPS
            break
        if variant == "mimic" and partial_done and j - entry_i >= 3:
            # swing-trail on 5m: ratchet to the extreme of the last 3 bars, never backwards
            swing = low[j - 3:j].min() if side > 0 else high[j - 3:j].max()
            trail = max(trail, swing) if side > 0 else min(trail, swing)
    gross_r = side * (exit_px - entry_px) / risk
    cost_frac = (entry_bps + exit_bps) / 1e4
    funding = _funding_cost(times_ms, entry_i, exit_i, side, f_time, f_rate)
    net_ret = side * (exit_px - entry_px) / entry_px
    if variant == "mimic" and partial_done:
        net_ret = 0.5 * (PARTIAL_R * risk / entry_px) + 0.5 * net_ret
        gross_r = realised + 0.5 * gross_r
    net_ret -= cost_frac + funding
    r_net = gross_r - (cost_frac + funding) * entry_px / risk
    hour = int((times_ms[entry_i] // 3_600_000) % 24)
    return Trade(entry_i, exit_i, side, entry_px, exit_px, stop_px, float(r_net),
                 float(net_ret), regime, reason, hour, partial_done)


def run_config(data: dict[str, np.ndarray], *, symbol: str, strategy: str, n: int, k: int,
               m: int, variant: str, lo_q: float = 0.25, start: int = 0,
               stop: int | None = None) -> ConfigResult:
    """One (strategy, N, K, M, exit) pass over [start, stop) — the walk-forward window seam."""
    high, low, close = data["high"], data["low"], data["close"]
    opn = data["open"]
    times = data["open_time"]
    f_time = data.get("funding_time", np.empty(0))
    f_rate = data.get("funding_rate", np.empty(0))
    a = atr(high, low, close)
    reg = regimes(close)
    hi_n, lo_n = _shifted_extrema(high, low, n)
    stop = len(close) if stop is None else stop
    res = ConfigResult(symbol, strategy, n, k, m, variant)
    width = hi_n - lo_n
    lo_i = max(start, n + ER_WINDOW + 1)
    hi_i = min(stop, len(close) - 2)
    if hi_i <= lo_i:
        return res
    # CANDIDATE DETECTION IS VECTORISED; only candidates are visited. Semantics are identical
    # to the original per-bar walk (verified by the no-lookahead and conservatism tests): the
    # one-position-at-a-time rule is applied while iterating candidates in time order.
    idx = np.arange(len(close))
    in_window = (idx >= lo_i) & (idx < hi_i)
    valid = in_window & np.isfinite(width) & (width > 0) & np.isfinite(a)
    bar_rng = high - low
    if strategy == "rotation":
        with np.errstate(invalid="ignore", divide="ignore"):
            pos_rng = np.where(width > 0, (close - lo_n) / width, np.nan)
            pos_bar = np.where(bar_rng > 0, (close - low) / bar_rng, np.nan)
        long_m = valid & (reg == 0) & (pos_rng <= lo_q) & (pos_bar >= 2.0 / 3.0)
        short_m = valid & (reg == 0) & (pos_rng >= 1.0 - lo_q) & (pos_bar <= 1.0 / 3.0)
        stop_l = low - STOP_ATR_BUFFER * a
        stop_s = high + STOP_ATR_BUFFER * a
        risk_l = close - stop_l
        risk_s = stop_s - close
        long_m &= (risk_l > 0) & ((hi_n - close) >= LOCATION_MIN_RR * risk_l)
        short_m &= (risk_s > 0) & ((close - lo_n) >= LOCATION_MIN_RR * risk_s)
        cands = np.flatnonzero(long_m | short_m)
        sides = np.where(long_m[cands], 1, -1)
        last_exit = lo_i
        for i, side in zip(cands.tolist(), sides.tolist(), strict=True):
            if i < last_exit:
                continue
            stop_px = float(stop_l[i] if side > 0 else stop_s[i])
            opp = float(hi_n[i] if side > 0 else lo_n[i])
            t = _resolve(side, i, float(close[i]), stop_px, high, low, close, opp,
                         variant, m, times, f_time, f_rate, "RANGE", TAKER_BPS)
            if t is not None:
                res.trades.append(t)
                last_exit = t.exit_i + 1
    else:
        brk_l = valid & (reg == 1) & (close > hi_n) & (bar_rng > BREAKOUT_ATR_MULT * a)
        brk_s = valid & (reg == 1) & (close < lo_n) & (bar_rng > BREAKOUT_ATR_MULT * a)
        cands = np.flatnonzero(brk_l | brk_s)
        sides = np.where(brk_l[cands], 1, -1)
        last_exit = lo_i
        for i, side in zip(cands.tolist(), sides.tolist(), strict=True):
            if i < last_exit:
                continue
            level = float(hi_n[i] if side > 0 else lo_n[i])
            filled = None
            for j in range(i + 1, min(i + 1 + k, len(close) - 1)):
                touched = low[j] <= level if side > 0 else high[j] >= level
                if touched:
                    # limit at the broken boundary; when the bar gaps through it, the OPEN is
                    # what a resting limit would actually have got (taking the worse of
                    # level/open would penalise gaps twice; taking close would be fiction).
                    px = float(min(level, opn[j]) if side > 0 else max(level, opn[j]))
                    filled = (j, px)
                    break
            if filled is None:
                res.n_unfilled += 1
                continue
            j, px = filled
            stop_px = (px - (a[i] * STOP_ATR_BUFFER + bar_rng[i]) if side > 0
                       else px + (a[i] * STOP_ATR_BUFFER + bar_rng[i]))
            opp = px + side * 3.0 * abs(px - stop_px)      # boundary target n/a post-break
            t = _resolve(side, j, px, float(stop_px), high, low, close, opp,
                         variant, m, times, f_time, f_rate, "TREND", MAKER_BPS)
            if t is not None:
                res.trades.append(t)
                last_exit = t.exit_i + 1
    return res


# ------------------------------------------------------------------ evaluation helpers

def expectancy(r: np.ndarray) -> dict[str, float]:
    if len(r) == 0:
        return {"n": 0, "exp_r": 0.0, "win": 0.0, "sharpe_r": 0.0}
    win = float(np.mean(r > 0))
    sd = float(np.std(r, ddof=1)) if len(r) > 1 else 0.0
    return {"n": len(r), "exp_r": float(np.mean(r)), "win": win,
            "sharpe_r": float(np.mean(r) / sd) if sd > 0 else 0.0}


def wilson_ci(wins: int, n: int, z: float = 1.96) -> tuple[float, float]:
    if n == 0:
        return (0.0, 1.0)
    p = wins / n
    d = 1 + z * z / n
    c = (p + z * z / (2 * n)) / d
    h = z * np.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return (float(c - h), float(c + h))


def bootstrap_sizing(r: np.ndarray, *, risk_fracs: tuple[float, ...],
                     n_paths: int = 2000, block: int = 10, seed: int = 7,
                     ruin_level: float = 0.20) -> list[dict[str, Any]]:
    """Stationary-block bootstrap of the OOS R-sequence, compounded at each risk fraction.

    Equity multiplies by (1 + f * r_i) per trade — the R-multiple already carries costs. Block
    resampling preserves streakiness, which is exactly what fixed-fraction sizing is sensitive
    to and what an iid bootstrap would understate.
    """
    rng = np.random.default_rng(seed)
    n = len(r)
    out: list[dict[str, Any]] = []
    if n < 20:
        return out
    paths = np.empty((n_paths, n))
    for p in range(n_paths):
        seq: list[float] = []
        while len(seq) < n:
            s = int(rng.integers(0, n))
            ln = int(rng.geometric(1.0 / block))
            seq.extend(r[(s + np.arange(ln)) % n])
        paths[p] = np.asarray(seq[:n])
    # longest losing streak on the REAL sequence
    streak = best = 0
    for x in r:
        streak = streak + 1 if x < 0 else 0
        best = max(best, streak)
    for f in risk_fracs:
        eq = np.cumprod(1.0 + f * paths, axis=1)
        peak = np.maximum.accumulate(eq, axis=1)
        dd = 1.0 - eq / peak
        maxdd = dd.max(axis=1)
        term = eq[:, -1]
        out.append({
            "risk_frac": f,
            "median_terminal": float(np.median(term)),
            "median_max_dd": float(np.median(maxdd)),
            "p95_max_dd": float(np.percentile(maxdd, 95)),
            "p_dd_over_50": float(np.mean(maxdd > 0.50)),
            "p_ruin": float(np.mean(eq.min(axis=1) < ruin_level)),
            "longest_loss_streak_real": int(best),
            "streak_implied_dd": float(1.0 - (1.0 - f) ** best),
        })
    return out


def half_kelly(r: np.ndarray, *, n_boot: int = 2000, seed: int = 11
               ) -> dict[str, float]:
    """Half of the R-space Kelly fraction f* = E[r]/E[r^2] (quadratic approximation), with a
    bootstrap CI. Stated in the same risk-per-trade units as the sizing sweep."""
    if len(r) < 20 or float(np.mean(r)) <= 0:
        return {"half_kelly": 0.0, "lo": 0.0, "hi": 0.0}
    rng = np.random.default_rng(seed)
    f = 0.5 * float(np.mean(r) / np.mean(r * r))
    bs = []
    for _ in range(n_boot):
        s = r[rng.integers(0, len(r), len(r))]
        m2 = float(np.mean(s * s))
        if m2 > 0:
            bs.append(0.5 * float(np.mean(s) / m2))
    return {"half_kelly": f, "lo": float(np.percentile(bs, 2.5)),
            "hi": float(np.percentile(bs, 97.5))}


def deflated_sharpe(sr: float, n_obs: int, n_configs: int, *, skew: float = 0.0,
                    kurt: float = 3.0) -> float:
    """PSR against the expected-max-Sharpe benchmark over n_configs (Bailey & Lopez de Prado)."""
    from scipy.stats import norm
    if n_obs < 2 or n_configs < 1:
        return 0.0
    e = np.euler_gamma
    var_sr = 1.0 / n_obs
    sr0 = np.sqrt(var_sr) * ((1 - e) * norm.ppf(1 - 1.0 / n_configs)
                             + e * norm.ppf(1 - 1.0 / (n_configs * np.e)))
    denom = np.sqrt(max(1e-12, 1 - skew * sr + (kurt - 1) / 4.0 * sr * sr))
    z = (sr - sr0) * np.sqrt(n_obs - 1) / denom
    return float(norm.cdf(z))
