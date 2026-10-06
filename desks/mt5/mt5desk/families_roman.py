"""THE ROMAN ROWS ON MT5 BARS: KALMAN RESIDUALS AND HAWKES FLOW STATES (2026-10-06).

The principal's Roman blueprint (rows 0819-0843, Quant Guild clusters 3 and 4) asks for Hawkes
intensities of order-flow events and state-space residuals mined as gauntlet cells. MT5 has no
exchange tape, so every event here is read off the bars the desk already holds, each as a named
proxy, and every filter comes from the shared modules `libs/research/state_space.py` and
`libs/research/point_process.py` (World sensor imports the same ones for its news and macro
states). Nothing is copied from the lectures (no licence).

KALMAN (rows 0833-0843):
    kalman_hedge_spread   Dynamic hedge ratio (0834) or dynamic spread mean (0836) between this
                          leg and `pair_symbol`, read from the bar store as of each bar; fade the
                          spread's standardized one-step surprise. An optional gate on the filtered
                          return correlation (0837) trades only while the pair still co-moves.
    kalman_beta_residual  Dynamic beta of this leg's returns on `pair_symbol`'s (0835); fade the
                          sum of the last `horizon` standardized residual returns.
    kalman_trend          Local linear trend (0838): follow the filtered slope when it crosses
                          `entry_k` trailing return sd per bar.
    kalman_vol_residual   Filtered log-variance level (0843): a vol surprise of `entry_z` arriving
                          in a calm filtered regime is a lone shock and is faded.
    (0833 dynamic fair value is `families_quantguild.kalman_ou_level`; 0842 futures/spot basis has
    no expiring contract on MT5 and is reported NOT_BUILDABLE by the thread, not faked.)

HAWKES (rows 0819-0831), events on the cell's own bars:
    buy / sell      an up / down bar whose tick_volume is above its trailing 80th percentile
                    (signed activity: the bar-level proxy for market buys and sells)
    large           tick_volume above its trailing 95th percentile (large prints)
    depletion       the bar's recorded spread above its trailing 90th percentile (liquidity
                    depletion; MT5 has no book, so cancellations are not observable and are not
                    proxied)
    hawkes_flow     mode `accel_depletion` (0828): signed-flow intensity accelerating while the
                    depletion intensity is excited -> follow the flow. Mode `sell_cascade_skew`
                    (0829): sell intensity excited while trailing skew is negative -> short.
                    Mode `arrival_breakout` (0831): a 20-bar breakout taken only while
                    large-print arrivals cluster.

Every threshold is read strictly before the bar it classifies, every intensity counts events at
or before the decision bar, and the engine fills at the next open.
"""
from __future__ import annotations

import math

import numpy as np
import pandas as pd

from libs.research import path_representations as pr
from libs.research import point_process as pp
from libs.research import state_space as ss
from mt5desk import families_cross_sectional as xs
from mt5desk.engine import Signal
from mt5desk.families import _atr, _h1


def _sig(h: pd.DataFrame, i: int, side: int, stop_dist: float, rr: float, ttl: int,
         tag: str) -> Signal | None:
    px = float(h["close"].iloc[i])
    if not (math.isfinite(px) and math.isfinite(stop_dist) and stop_dist > 0 and side):
        return None
    return Signal(time=h.index[i], side=int(side), stop=px - side * stop_dist,
                  target=px + side * stop_dist * rr, ttl_bars=int(ttl), tag=tag)


def _peer_log(h: pd.DataFrame, pair_symbol: str, max_stale_h: float) -> np.ndarray | None:
    """The peer's log close as of each of this frame's bars; NaN where stale or absent."""
    got = xs._load_series(str(pair_symbol))
    if got is None:
        return None
    t, c = got
    stamps = h.index.asi8
    j = np.searchsorted(t, stamps, side="right") - 1
    out = np.full(stamps.size, np.nan)
    has = j >= 0
    jj = np.where(has, j, 0)
    fresh = has & ((stamps - t[jj]) <= max_stale_h * 3_600_000_000_000)
    out[fresh] = np.log(c[jj[fresh]].astype(float))
    return out


def _r_scale(y: np.ndarray, warm: int) -> float:
    d = np.diff(y[:warm])
    d = d[np.isfinite(d)]
    return float(d.var()) if d.size > 10 else float("nan")


# ------------------------------------------------------------------------------ Kalman --------
def family_kalman_hedge_spread(df: pd.DataFrame, *, pair_symbol: str = "", mode: str = "beta",
                               delta: float = 1e-5, entry_z: float = 2.0, corr_min: float = 0.0,
                               warm: int = 500, atr_n: int = 20, stop_atr: float = 2.5,
                               rr: float = 1.5, ttl_bars: int = 48,
                               max_stale_h: float = 2.0) -> list[Signal]:
    """Fade this leg's spread surprise against `pair_symbol`: a dynamic hedge ratio (`beta`) or a
    static trailing hedge with a filtered spread mean (`mean`)."""
    if not pair_symbol or mode not in ("beta", "mean"):
        return []
    h = _h1(df)
    if len(h) < warm + 50:
        return []
    y = np.log(h["close"].to_numpy(dtype=float))
    x = _peer_log(h, pair_symbol, max_stale_h)
    if x is None or np.isfinite(x).sum() < warm:
        return []
    r = _r_scale(y, warm)
    if not (math.isfinite(r) and r > 0):
        return []
    if mode == "beta":
        z = ss.dynamic_regression(y, x, delta=delta, r=r).innov
    else:
        # hedge ratio from the trailing `warm` bars, refit every `warm // 5` bars, past only
        b = np.full(y.size, np.nan)
        step = max(24, warm // 5)
        for s in range(warm, y.size, step):
            yy, xx = y[s - warm:s], x[s - warm:s]
            ok = np.isfinite(yy) & np.isfinite(xx)
            if ok.sum() > warm // 2 and np.var(xx[ok]) > 0:
                b[s:s + step] = np.polyfit(xx[ok], yy[ok], 1)[0]
        z = ss.local_level(y - b * x, r * 0.01, r).innov
    if corr_min > 0:
        rho = ss.dynamic_correlation(np.diff(y, prepend=np.nan), np.diff(x, prepend=np.nan))
        z = np.where(rho >= corr_min, z, np.nan)
    atr = _atr(h, atr_n).to_numpy()
    out: list[Signal] = []
    busy = -1
    for i in range(warm, len(h) - 1):
        if i <= busy or not (math.isfinite(z[i]) and abs(z[i]) >= entry_z):
            continue
        sig = _sig(h, i, -int(np.sign(z[i])), stop_atr * float(atr[i]), rr, ttl_bars,
                   f"kalman_hedge_spread:{pair_symbol}:{mode}")
        if sig:
            out.append(sig)
            busy = i + ttl_bars
    return out


def family_kalman_beta_residual(df: pd.DataFrame, *, pair_symbol: str = "US500",
                                delta: float = 1e-4, horizon: int = 12, entry_z: float = 2.5,
                                warm: int = 500, atr_n: int = 20, stop_atr: float = 2.0,
                                rr: float = 1.5, ttl_bars: int = 24,
                                max_stale_h: float = 2.0) -> list[Signal]:
    """Fade this leg's return unexplained by its dynamic beta on `pair_symbol`, summed over the
    last `horizon` bars."""
    if not pair_symbol:
        return []
    h = _h1(df)
    if len(h) < warm + horizon + 50:
        return []
    y = np.log(h["close"].to_numpy(dtype=float))
    x = _peer_log(h, pair_symbol, max_stale_h)
    if x is None:
        return []
    ry, rx = np.diff(y, prepend=np.nan), np.diff(x, prepend=np.nan)
    # the observation noise is the residual variance of a static beta on the warm-up bars only
    a, b = ry[:warm], rx[:warm]
    ok = np.isfinite(a) & np.isfinite(b)
    if ok.sum() < warm // 2 or not np.var(b[ok]) > 0:
        return []
    r = float(np.var(a[ok] - np.polyfit(b[ok], a[ok], 1)[0] * b[ok]))
    if not (math.isfinite(r) and r > 0):
        return []
    e = ss.dynamic_regression(ry, rx, delta=delta, r=r).innov
    cum = pd.Series(e).rolling(horizon, min_periods=horizon).sum().to_numpy() / math.sqrt(horizon)
    atr = _atr(h, atr_n).to_numpy()
    out: list[Signal] = []
    busy = -1
    for i in range(warm, len(h) - 1):
        if i <= busy or not (math.isfinite(cum[i]) and abs(cum[i]) >= entry_z):
            continue
        sig = _sig(h, i, -int(np.sign(cum[i])), stop_atr * float(atr[i]), rr, ttl_bars,
                   f"kalman_beta_residual:{pair_symbol}")
        if sig:
            out.append(sig)
            busy = i + ttl_bars
    return out


def family_kalman_trend(df: pd.DataFrame, *, slope_ratio: float = 1e-3, entry_k: float = 0.05,
                        warm: int = 500, atr_n: int = 20, stop_atr: float = 2.5, rr: float = 2.0,
                        ttl_bars: int = 48) -> list[Signal]:
    """Follow the local linear trend's filtered slope when it crosses `entry_k` trailing return
    sd per bar; `slope_ratio` is the slope's process variance relative to the level's."""
    h = _h1(df)
    if len(h) < warm + 50:
        return []
    y = np.log(h["close"].to_numpy(dtype=float))
    q = _r_scale(y, warm)
    if not (math.isfinite(q) and q > 0):
        return []
    slope = ss.local_linear_trend(y, q, q * slope_ratio, q * 0.1).filt[:, 1]
    sd = pd.Series(np.diff(y, prepend=np.nan)).rolling(warm, min_periods=warm // 2).std()
    k = slope / sd.to_numpy()
    prev = np.r_[np.nan, k[:-1]]
    atr = _atr(h, atr_n).to_numpy()
    out: list[Signal] = []
    busy = -1
    for i in range(warm, len(h) - 1):
        if i <= busy or not (math.isfinite(k[i]) and math.isfinite(prev[i])):
            continue
        side = 1 if (k[i] >= entry_k > prev[i]) else (-1 if k[i] <= -entry_k < prev[i] else 0)
        if side == 0:
            continue
        sig = _sig(h, i, side, stop_atr * float(atr[i]), rr, ttl_bars,
                   f"kalman_trend:{entry_k:g}")
        if sig:
            out.append(sig)
            busy = i + ttl_bars
    return out


def family_kalman_vol_residual(df: pd.DataFrame, *, q: float = 0.01, entry_z: float = 2.0,
                               calm_window: int = 500, atr_n: int = 20, stop_atr: float = 1.5,
                               rr: float = 1.5, ttl_bars: int = 6) -> list[Signal]:
    """Fade a bar whose squared return surprises the filtered log variance by `entry_z` while the
    filtered level sits below its own trailing median: a lone shock in a calm regime."""
    h = _h1(df)
    if len(h) < calm_window + 50:
        return []
    c = h["close"].to_numpy(dtype=float)
    r = np.diff(np.log(c), prepend=np.nan)
    f = ss.log_variance_level(r, q)
    level = f.filt[:, 0]
    # the level before this bar updated it, against its trailing median read before the bar
    before = np.r_[np.nan, level[:-1]]
    med = pd.Series(before).rolling(calm_window, min_periods=calm_window // 2).median().to_numpy()
    atr = _atr(h, atr_n).to_numpy()
    out: list[Signal] = []
    busy = -1
    for i in range(calm_window, len(h) - 1):
        if i <= busy or not (math.isfinite(f.innov[i]) and f.innov[i] >= entry_z):
            continue
        if not (before[i] < med[i]) or r[i] == 0:
            continue
        sig = _sig(h, i, -int(np.sign(r[i])), stop_atr * float(atr[i]), rr, ttl_bars,
                   f"kalman_vol_residual:{entry_z:g}")
        if sig:
            out.append(sig)
            busy = i + ttl_bars
    return out


# ------------------------------------------------------------------------------ Hawkes --------
def bar_events(h: pd.DataFrame, *, window: int = 500) -> dict[str, np.ndarray]:
    """Boolean event masks per bar, each threshold from the trailing `window` bars before it."""
    c = h["close"].to_numpy(dtype=float)
    o = h["open"].to_numpy(dtype=float)
    out: dict[str, np.ndarray] = {}
    if "tick_volume" in h.columns:
        v = h["tick_volume"].astype(float)
        q80 = v.rolling(window, min_periods=window // 2).quantile(0.80).shift(1).to_numpy()
        q95 = v.rolling(window, min_periods=window // 2).quantile(0.95).shift(1).to_numpy()
        vv = v.to_numpy()
        out["buy"] = (vv > q80) & (c > o)
        out["sell"] = (vv > q80) & (c < o)
        out["large"] = vv > q95
    if "spread" in h.columns:
        s = h["spread"].astype(float)
        q90 = s.rolling(window, min_periods=window // 2).quantile(0.90).shift(1).to_numpy()
        out["depletion"] = s.to_numpy() > q90
    return out


def _ratios(masks: list[np.ndarray], n: int, window: int, refit: int,
            min_events: int) -> np.ndarray:
    """(n, d) intensity / baseline per bar for a d-type process refit on the trailing window."""
    out = np.full((n, len(masks)), np.nan)
    ev = [np.flatnonzero(m) for m in masks]
    for start in range(window, n, refit):
        lo = start - window
        times = np.concatenate([e[(e >= lo) & (e < start)] for e in ev]).astype(float) - lo
        types = np.concatenate([np.full(((e >= lo) & (e < start)).sum(), k)
                                for k, e in enumerate(ev)])
        if times.size < min_events:
            continue
        f = pp.fit(times, types, d=len(masks), span=float(window), max_events=1500)
        if f is None:
            continue
        stop = min(n, start + refit)
        # intensity through the refit block, counting the block's own events as they arrive
        lo2 = start - window
        t_all = np.concatenate([e[(e >= lo2) & (e < stop)] for e in ev]).astype(float) - lo2
        k_all = np.concatenate([np.full(((e >= lo2) & (e < stop)).sum(), k)
                                for k, e in enumerate(ev)])
        grid = np.arange(start, stop, dtype=float) - lo2
        lam = pp.intensity_at(grid, t_all, k_all, f)
        out[start:stop] = lam / np.where(f.mu > 0, f.mu, np.nan)
    return out


def family_hawkes_flow(df: pd.DataFrame, *, mode: str = "accel_depletion", hi: float = 2.0,
                       window: int = 3000, refit: int = 240, min_events: int = 100,
                       skew_n: int = 120, breakout_n: int = 20, atr_n: int = 20,
                       stop_atr: float = 1.5, rr: float = 1.5, ttl_bars: int = 8) -> list[Signal]:
    """Trade a bar-event Hawkes state: flow acceleration under depletion, a sell cascade under
    negative skew, or a breakout under clustered large-print arrivals."""
    if mode not in ("accel_depletion", "sell_cascade_skew", "arrival_breakout"):
        return []
    h = _h1(df)
    if len(h) < window + refit + 10:
        return []
    ev = bar_events(h)
    c = h["close"].to_numpy(dtype=float)
    n = len(c)
    atr = _atr(h, atr_n).to_numpy()
    side = np.zeros(n, dtype=int)
    if mode == "accel_depletion":
        if not {"buy", "sell", "depletion"} <= set(ev):
            return []
        q = _ratios([ev["buy"], ev["sell"], ev["depletion"]], n, window, refit, min_events)
        acc_b = q[:, 0] - np.r_[np.full(3, np.nan), q[:-3, 0]]
        acc_s = q[:, 1] - np.r_[np.full(3, np.nan), q[:-3, 1]]
        dep = q[:, 2] >= hi
        side[(q[:, 0] >= hi) & (acc_b > 0) & dep & ~(q[:, 1] >= hi)] = 1
        side[(q[:, 1] >= hi) & (acc_s > 0) & dep & ~(q[:, 0] >= hi)] = -1
    elif mode == "sell_cascade_skew":
        if "sell" not in ev:
            return []
        q = _ratios([ev["sell"]], n, window, refit, min_events)
        r = pd.Series(np.diff(np.log(c), prepend=np.nan))
        skew = r.rolling(skew_n, min_periods=skew_n).skew().to_numpy()
        side[(q[:, 0] >= hi) & (skew < 0)] = -1
    else:
        if "large" not in ev:
            return []
        q = _ratios([ev["large"]], n, window, refit, min_events)
        hh = h["high"].rolling(breakout_n).max().shift(1).to_numpy()
        ll = h["low"].rolling(breakout_n).min().shift(1).to_numpy()
        hot = q[:, 0] >= hi
        side[hot & (c > hh)] = 1
        side[hot & (c < ll)] = -1
    out: list[Signal] = []
    busy = -1
    for i in np.flatnonzero(side):
        if i <= busy or i >= n - 1:
            continue
        sig = _sig(h, int(i), int(side[i]), stop_atr * float(atr[i]), rr, ttl_bars,
                   f"hawkes_flow:{mode}")
        if sig:
            out.append(sig)
            busy = int(i) + ttl_bars
    return out


# ------------------------------------------------------------------- path shape --------------
def family_path_state(df: pd.DataFrame, *, rep: str = "hurst", window: int = 240,
                      hi: float = 0.55, lo: float = 0.45, momentum_n: int = 24,
                      bridge_n: int = 48, bridge_max: float = 0.35, jump_k: float = 2.5,
                      atr_n: int = 20, stop_atr: float = 2.0, rr: float = 1.5,
                      ttl_bars: int = 24) -> list[Signal]:
    """Trade the path's shape (rows 1000 and 0743): `hurst` follows the last `momentum_n` bars
    when the trailing path is persistent (H > hi) and fades them when anti-persistent (H < lo);
    `bridge` follows a path that hugs its own straight line (bridge excursion < bridge_max);
    `rough_vol` follows a jump when log vol is smoother than usual (H_vol above its trailing
    median: vol persists) and fades it when rougher (vol reverts)."""
    if rep not in ("hurst", "bridge", "rough_vol"):
        return []
    h = _h1(df)
    if len(h) < window + 120:
        return []
    c = h["close"].to_numpy(dtype=float)
    if not np.all(c > 0):
        return []
    x = np.log(c)
    r = np.diff(x, prepend=np.nan)
    n = len(c)
    side = np.zeros(n, dtype=int)
    mom = np.sign(x - np.r_[np.full(momentum_n, np.nan), x[:-momentum_n]])
    if rep == "hurst":
        H = pr.rolling_hurst(x, window, step=6)
        prev = np.r_[np.nan, H[:-1]]
        side[(H > hi) & ~(prev > hi)] = 1
        side[(H < lo) & ~(prev < lo)] = -1
        side = side * np.nan_to_num(mom).astype(int)
    elif rep == "bridge":
        b = np.full(n, np.nan)
        for t in range(bridge_n, n):
            b[t] = pr.bridge_excursion(x[t - bridge_n:t + 1])
        prev = np.r_[np.nan, b[:-1]]
        hug = (b < bridge_max) & ~(prev < bridge_max)
        trend = np.sign(x - np.r_[np.full(bridge_n, np.nan), x[:-bridge_n]])
        side[hug] = np.nan_to_num(trend[hug]).astype(int)
    else:
        ab = np.abs(r)
        bip = pd.Series(ab * np.roll(ab, 1)).rolling(120).mean().shift(1).to_numpy()
        sigma = np.sqrt(np.pi / 2.0 * bip)
        jump = (ab > jump_k * sigma) & np.isfinite(sigma) & (sigma > 0)
        hv = np.full(n, np.nan)
        for t in range(window * 6, n, 24):
            hv[t] = pr.rough_vol_hurst(r[t - window * 6 + 1:t + 1])
        hv = pd.Series(hv).ffill(limit=23).to_numpy()
        med = pd.Series(hv).shift(1).rolling(24 * 60, min_periods=24 * 10).median().to_numpy()
        follow = hv > med
        fade = hv < med
        sgn = np.sign(np.nan_to_num(r)).astype(int)
        side[jump & follow] = sgn[jump & follow]
        side[jump & fade] = -sgn[jump & fade]
    atr = _atr(h, atr_n).to_numpy()
    out: list[Signal] = []
    busy = -1
    for i in np.flatnonzero(side):
        if i <= busy or i >= n - 1 or not math.isfinite(float(atr[i])):
            continue
        sig = _sig(h, int(i), int(side[i]), stop_atr * float(atr[i]), rr, ttl_bars,
                   f"path_state:{rep}")
        if sig:
            out.append(sig)
            busy = int(i) + ttl_bars
    return out


ROMAN_FAMILIES = {
    "kalman_hedge_spread": family_kalman_hedge_spread,
    "kalman_beta_residual": family_kalman_beta_residual,
    "kalman_trend": family_kalman_trend,
    "kalman_vol_residual": family_kalman_vol_residual,
    "hawkes_flow": family_hawkes_flow,
    "path_state": family_path_state,
}

#: The Roman row each family closes, for the thread's assignment table.
ROWS = {"kalman_hedge_spread": ["ROMAN-0834", "ROMAN-0836", "ROMAN-0837"],
        "kalman_beta_residual": ["ROMAN-0835"], "kalman_trend": ["ROMAN-0838"],
        "kalman_vol_residual": ["ROMAN-0843"], "path_state": ["ROMAN-1000", "ROMAN-0743"],
        "hawkes_flow": ["ROMAN-0819", "ROMAN-0820", "ROMAN-0821", "ROMAN-0823", "ROMAN-0828",
                        "ROMAN-0829", "ROMAN-0831"]}

#: Families that read a second leg keyed by `pair_symbol` from the bar store. NOT `peer_symbol`:
#: that is a gauntlet identity key (`family_inputs.IDENTITY_KEYS`), stripped before the call and
#: loaded only for the families the sealed gauntlet knows, so these would be called leg-less.
PEER_KEYED = frozenset({"kalman_hedge_spread", "kalman_beta_residual"})

#: The pairs the hedge and beta cells are screened on: the paperswithbacktest pairs and each
#: leg's natural driver. Cells are (symbol, peer) with the peer named in the params.
PAIRS = {"XBRUSD": "XTIUSD", "XAGUSD": "XAUUSD", "XPTUSD": "XPDUSD", "XCUUSD": "XALUSD",
         "AUDUSD": "NZDUSD", "EURUSD": "GBPUSD", "NAS100": "US500", "GER40": "EUSTX50",
         "US30": "US500", "EURCHF": "EURUSD"}

PARAM_GRID: dict[str, dict[str, list]] = {
    "kalman_hedge_spread": {"mode": ["beta", "mean"]},
    "kalman_beta_residual": {"horizon": [12]},
    "kalman_trend": {"entry_k": [0.05, 0.1]},
    "kalman_vol_residual": {"entry_z": [2.0]},
    "hawkes_flow": {"mode": ["accel_depletion", "sell_cascade_skew", "arrival_breakout"]},
    "path_state": {"rep": ["hurst", "bridge", "rough_vol"]},
}

_RM = {"source_culture": "US/en", "participant_structure": "retail_education",
       "crowding_prior": "low"}
CULTURE: dict[str, dict[str, str]] = {
    "kalman_hedge_spread": {**_RM, "crowding_prior": "medium", "failure_mode_hypothesis": (
        "fails when the pair's relation breaks for a reason (a supply shock to one leg), which "
        "the filter reads as a surprise to fade")},
    "kalman_beta_residual": {**_RM, "failure_mode_hypothesis": (
        "fails when the residual is the leg's own news, which drifts rather than reverts")},
    "kalman_trend": {**_RM, "crowding_prior": "medium", "failure_mode_hypothesis": (
        "fails in a ranging market where the filtered slope crosses and recrosses its line")},
    "kalman_vol_residual": {**_RM, "failure_mode_hypothesis": (
        "fails when the first shock of a calm regime is the start of a repricing")},
    "path_state": {**_RM, "failure_mode_hypothesis": (
        "fails because a roughness estimate on a few hundred bars is noisy enough that the state "
        "flips on sampling error rather than on a change in who is trading")},
    "hawkes_flow": {**_RM, "failure_mode_hypothesis": (
        "fails because bar tick_volume is a quote count, not signed trades, so the 'flow' may "
        "be quoting activity rather than aggression")},
}
