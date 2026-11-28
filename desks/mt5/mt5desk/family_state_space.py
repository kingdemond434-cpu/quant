"""Quant-framework families: GARCH, Kalman (trend, pair), copula pair, OU, particle filter, GP.

WHY THESE EXIST (2026-11-10). The framework audit of the live tree (PASS_COVERAGE.md,
"Quant-framework coverage", items 52, 53, 56 and 57) found the desk ran Gaussian HMMs, Bayesian
E[log W] sizing, Hawkes and change-points, but had GARCH only as an EWMA stand-in, Kalman only
inside a macro dynamic-factor model, copulas untested and an OU half-life nowhere. Each family
below is one of those frameworks expressed as a MECHANISM the gauntlet can judge, not a
forecast that is admired and never traded:

    garch_shock    GJR-GARCH(1,1), walk-forward QMLE. A return measured in its own conditional
                   sigma is a shock; whether shocks continue or revert depends on whether the
                   variance is above or below its long-run level. Both claims are tested.
    kalman_trend   local-linear-trend Kalman filter on log price. Trades the filtered SLOPE when
                   its own posterior t-statistic crosses a threshold -- a trend whose noise is
                   estimated rather than assumed, which a moving-average cross cannot say.
    kalman_pair    Kalman time-varying hedge ratio (alpha_t, beta_t as random walks) between this
                   instrument and a peer; fades the standardised innovation of the spread. The
                   hedge ratio a rolling OLS would lag by half its window is tracked bar by bar.
    copula_pair    Gaussian or Student-t copula on trailing rank-transformed returns; trades the
                   cumulative conditional-probability mispricing index (Liew-Wu 2013, Xie et al.
                   2016). Dependence in the ranks, so a fat-tailed pair is not judged by a
                   correlation that its tails break.
    ou_reversion   rolling AR(1) = discretised Ornstein-Uhlenbeck on log price. Enters only when
                   the fitted half-life lies inside [hl_min, hl_max] bars and holds for a multiple
                   of that half-life -- item 57's rule (a mean-reversion trade whose half-life is
                   longer than its hold is a trend bet) built into the family rather than bolted
                   on after certification.

ITEM 58 (added after the five above, same conventions):

    particle_regime  Rao-Blackwellised bootstrap particle filter on a latent drift with
                     stochastic volatility; trades the posterior P(drift > 0) crossing a
                     threshold. The joint drift-and-variance posterior is not Gaussian, which is
                     the case a Kalman filter cannot state and a particle filter can.
    gp_forecast      Gaussian-process regression (RBF + noise) of the drift on a trailing window,
                     length-scale chosen per calendar block by marginal likelihood; trades the
                     forecast drift measured in its own posterior sd.

HOW THE TWO ITEM-58 DEFAULTS WERE SET, ON THE RECORD. `particle_regime`'s `drift_vol` and
`gp_forecast`'s `amp` were first written as 0.1. A first smoke on EURUSD H1 (54,205 bars) gave 37
and 81 signals in eight years, too few for the judge's 60-day observations gate, and both were
moved to 0.2 (251 and 416 signals on the first cut). The choice was made on SIGNAL COUNT, with
no return, R or Sharpe looked at -- but it was made after seeing data, and is written here so
nobody reads the defaults as priors that were fixed blind. Both remain on the sweep grid.

EVERY ESTIMATE IS CAUSAL. Parameters are fitted on a trailing window that ends at the bar being
labelled (GARCH refits on blocks it could not see; the rolling statistics end at bar i), the
signal at bar i uses only bar i's close, and the engine fills at the next bar's open
(`wait_bars=1`, `trigger=None`). Bracket anchors are bar i's own close and ATR, read by position
in the same frame -- the stale-anchor defect fixed in `cross_asset_residual` (2026-11-06) is not
repeated here.

EDGE-TRIGGERED. Each family fires on the bar its condition BECOMES true, not on every bar it stays
true, so a cell's trade count is the number of distinct episodes rather than a measure of how
long one episode lasted.

REFUSES rather than degrades: too little history, a fit that does not converge, a peer that
cannot be found. A pair family whose named peer has no bars RAISES, so the gauntlet files a named
build failure instead of a cell that "never fires" (see `_peer_frame` for how the peer is read).
"""
from __future__ import annotations

import math

import numpy as np
import pandas as pd
from mt5desk.build_memo import Memo, args_key, frame_fingerprint
from mt5desk.families import Signal, _atr, _h1

#: Per-worker LRU of GARCH conditional-sigma paths: cells that differ only in entry threshold,
#: side or bracket share one set of walk-forward fits.
_GARCH_MEMO = Memo()

#: A return in units of its own GARCH sigma; the floor on the variance keeps a flat market from
#: producing an infinite shock out of a one-tick move.
_VAR_FLOOR = 1e-12


def _log_close(d: pd.DataFrame) -> np.ndarray:
    c = d["close"].astype(float).to_numpy()
    with np.errstate(divide="ignore", invalid="ignore"):
        return np.log(np.where(c > 0, c, np.nan))


def _edges(cond: np.ndarray) -> np.ndarray:
    """True where `cond` becomes true (and was false or undefined on the bar before)."""
    cond = np.asarray(cond, dtype=bool)
    prev = np.concatenate(([False], cond[:-1]))
    return cond & ~prev


def _bracket(px: float, side: int, atr: float, stop_atr: float, rr: float) -> tuple[float, float]:
    dist = stop_atr * atr
    return px - side * dist, px + side * rr * dist


# ---------------------------------------------------------------------------------------------
# GARCH (item 52)
# ---------------------------------------------------------------------------------------------

def _gjr_var_path(r: np.ndarray, omega: float, alpha: float, gamma: float, beta: float,
                  v0: float) -> np.ndarray:
    """sigma^2_{t|t-1} for t = 0..n (n+1 values: the last one is the next-bar forecast).

    The recursion v_{t+1} = omega + (alpha + gamma*1[r_t<0]) r_t^2 + beta v_t is LINEAR in v, so
    it is one first-order IIR filter (`lfilter`) rather than a Python loop -- the QMLE evaluates
    it a few hundred times per fit, and the loop made one symbol's walk-forward cost ~80s.
    """
    from scipy.signal import lfilter

    r = np.asarray(r, dtype=float)
    drive = omega + (alpha + gamma * (r < 0)) * r * r
    v = np.empty(r.size + 1)
    v[0] = max(v0, _VAR_FLOOR)
    if r.size:
        v[1:], _ = lfilter([1.0], [1.0, -beta], drive, zi=[beta * v[0]])
    return np.maximum(v, _VAR_FLOOR)


def fit_gjr_garch(r: np.ndarray) -> tuple[float, float, float, float] | None:
    """Gaussian QMLE of a zero-mean GJR-GARCH(1,1). None when the optimiser does not converge.

    Written here rather than imported from `arch` on purpose: the box's interpreter and this
    container's disagree on whether `arch` is installed (the audit found an EWMA fallback written
    because it "was not installed" while requirements pin 7.3.0). A family whose model silently
    changes with the environment certifies one thing and trades another. scipy is pinned on both.
    """
    from scipy.optimize import minimize

    r = np.asarray(r, dtype=float)
    r = r[np.isfinite(r)]
    if r.size < 250:
        return None
    r = r - r.mean()
    s = float(r.std())
    if not math.isfinite(s) or s <= 0:
        return None
    x = r / s                                    # unit variance: the optimiser sees O(1) numbers
    v0 = 1.0

    def nll(p: np.ndarray) -> float:
        om, a, g, b = p
        if om <= 0 or a < 0 or g < 0 or b < 0 or a + b + 0.5 * g >= 0.999:
            return 1e10
        v = _gjr_var_path(x, om, a, g, b, v0)[:-1]
        return float(0.5 * np.sum(np.log(v) + x * x / v))

    best = None
    for start in ((0.05, 0.05, 0.05, 0.85), (0.02, 0.08, 0.02, 0.9)):
        try:
            res = minimize(nll, np.array(start), method="Nelder-Mead",
                           options={"maxiter": 600, "xatol": 1e-5, "fatol": 1e-4})
        except (ValueError, FloatingPointError):
            continue
        if res.fun < 1e9 and (best is None or res.fun < best.fun):
            best = res
    if best is None:
        return None
    om, a, g, b = (float(z) for z in best.x)
    return om * s * s, a, g, b


def _refit_starts(index: pd.DatetimeIndex, window: int, refit: int) -> np.ndarray:
    """Bar positions where a new fit begins, anchored to the CALENDAR, not to the frame's start.

    A block boundary is the first bar of each period of `refit` bar-steps counted from the epoch,
    so the gauntlet's frame and a forward clock's shorter frame cut the same blocks and a
    certificate trades the rule it was judged on. Anchoring at the frame's first bar (`k = window,
    window + refit, ...`) was prefix-invariant but moved every fit when the frame started one bar
    later. Only boundaries with a full trailing `window` behind them are used.
    """
    n = len(index)
    if n < 2:
        return np.array([], dtype=int)
    idx = index if index.tz is None else index.tz_convert(None)
    ns = idx.as_unit("ns").asi8
    step = int(np.median(np.diff(ns)))
    if step <= 0:
        return np.array([], dtype=int)
    period = ns // (step * int(refit))
    starts = np.flatnonzero(np.diff(period, prepend=period[0]) != 0)
    return starts[starts >= window]


#: How many of this cell's newest bars may lack a peer close before the peer store is called
#: stale (see `_peer_frame`). Six hourly bars covers differing session hours, not a dead feed.
MAX_PEER_LAG_BARS = 6

#: Bars per calendar block for the Kalman families (see `_blocked`).
KALMAN_BLOCK = 500


def _blocked(index: pd.DatetimeIndex, warmup: int, block: int, n_out: int,
             run) -> list[np.ndarray]:
    """Run a recursive filter per CALENDAR block, each from `warmup` bars before the block.

    A Kalman filter has infinite memory, so run once from the frame's first bar it is not the same
    rule on a frame that starts later -- the difference decays but never reaches zero, and a
    certificate judged on eight years would trade a slightly different number on a forward
    clock's 400 days. Restarting the filter `warmup` bars before each calendar-anchored block
    (`_refit_starts`) makes every labelled bar a function of at most `warmup + block` bars before
    it, whatever the frame's first bar is. `run(lo, hi)` returns `n_out` arrays over [lo, hi).
    """
    n = len(index)
    outs = [np.full(n, np.nan) for _ in range(n_out)]
    starts = _refit_starts(index, int(warmup), int(block))
    for j, k in enumerate(starts):
        end = int(starts[j + 1]) if j + 1 < len(starts) else n
        lo = int(k) - int(warmup)
        for o, part in zip(outs, run(lo, end), strict=True):
            o[k:end] = part[k - lo:]
    return outs


def garch_sigma_path(r: pd.Series, window: int, refit: int) -> tuple[pd.Series, pd.Series]:
    """Walk-forward conditional sigma_{t|t-1} and the variance ratio sigma^2_{t+1|t} / long-run.

    Each block (see `_refit_starts`) is labelled with parameters fitted on the `window` returns
    before its first bar -- returns the fit never saw are the only ones it labels. The recursion
    is warmed up over that same trailing window from its sample variance, so a block's forecasts
    depend on nothing earlier than `window` bars before it: the path is the same whatever bar the
    frame happens to start on.
    """
    x = r.to_numpy(dtype=float)
    n = x.size
    sig = np.full(n, np.nan)
    ratio = np.full(n, np.nan)
    starts = _refit_starts(pd.DatetimeIndex(r.index), int(window), int(refit))
    for j, k in enumerate(starts):
        end = int(starts[j + 1]) if j + 1 < len(starts) else n
        hist = x[k - window:k]
        fit = fit_gjr_garch(hist)
        if fit is None:
            continue
        om, a, g, b = fit
        pers = a + b + 0.5 * g
        lr = om / (1.0 - pers) if pers < 1 else np.nan
        seg = np.nan_to_num(x[k - window:end] - np.nanmean(hist))
        v = _gjr_var_path(seg, om, a, g, b, float(np.nanvar(hist)))
        sig[k:end] = np.sqrt(v[window:window + (end - k)])
        if math.isfinite(lr) and lr > 0:
            ratio[k:end] = v[window + 1:window + 1 + (end - k)] / lr
    return pd.Series(sig, index=r.index), pd.Series(ratio, index=r.index)


def qlike_vs_ewma(r: pd.Series, window: int = 2000, refit: int = 500,
                  lam: float = 0.94) -> dict[str, float | int] | None:
    """Out-of-sample QLIKE of the walk-forward GJR-GARCH against the EWMA it would replace.

    QLIKE = mean(log s2 + r2 / s2) is the loss under which variance-forecast rankings are robust
    to noise in the r2 proxy (Patton 2011). Lower is better. Scored only on bars both forecasts
    exist for, so neither is credited with an easier sample.
    """
    rr = r.astype(float)
    sig, _ = garch_sigma_path(rr, window, refit)
    x = rr.to_numpy()
    ew = np.full(x.size, np.nan)
    acc = np.nan
    for t in range(x.size):
        ew[t] = acc                              # forecast for t uses returns up to t-1
        if math.isfinite(x[t]):
            acc = x[t] * x[t] if not math.isfinite(acc) else lam * acc + (1 - lam) * x[t] * x[t]
    g2 = sig.to_numpy() ** 2
    ok = np.isfinite(g2) & np.isfinite(ew) & np.isfinite(x) & (g2 > 0) & (ew > 0)
    if ok.sum() < 200:
        return None
    r2 = x[ok] ** 2
    q_g = float(np.mean(np.log(g2[ok]) + r2 / g2[ok]))
    q_e = float(np.mean(np.log(ew[ok]) + r2 / ew[ok]))
    return {"n": int(ok.sum()), "qlike_garch": q_g, "qlike_ewma": q_e,
            "garch_better": bool(q_g < q_e)}


def family_garch_shock(
    df: pd.DataFrame,
    *,
    window: int = 1000,
    refit: int = 250,
    entry_z: float = 2.5,
    vol_state: str = "any",
    side_mode: str = "fade",
    atr_n: int = 20,
    stop_atr: float = 1.5,
    rr: float = 1.5,
    ttl_bars: int = 24,
) -> list[Signal]:
    """Trade a return of `entry_z` GARCH sigmas or more, faded or followed.

    `vol_state` conditions on sigma^2_{t+1|t} relative to the fitted long-run variance:
    `calm` (below it) is where a large shock is news, `stressed` (above it) is where it is noise
    in a market already moving. The claim is that the two behave differently; `any` is the
    unconditional control.
    """
    if side_mode not in {"fade", "follow"} or vol_state not in {"any", "calm", "stressed"}:
        return []
    d = _h1(df)
    if len(d) < window + 2:
        return []
    lc = pd.Series(_log_close(d), index=d.index)
    r = lc.diff()
    sig, ratio = _GARCH_MEMO.get_or_compute(
        (frame_fingerprint(d[["close"]]), args_key(window, refit)),
        lambda: garch_sigma_path(r, window, refit))
    s = sig.to_numpy()
    rv = r.to_numpy()
    with np.errstate(divide="ignore", invalid="ignore"):
        z = rv / s
    cond = np.isfinite(z) & (np.abs(z) >= entry_z)
    q = ratio.to_numpy()
    if vol_state == "calm":
        cond &= np.isfinite(q) & (q < 1.0)
    elif vol_state == "stressed":
        cond &= np.isfinite(q) & (q >= 1.0)
    atr = _atr(d, atr_n).to_numpy()
    close = d["close"].astype(float).to_numpy()
    out: list[Signal] = []
    for i in np.flatnonzero(_edges(cond)):
        if i >= len(d) - 1 or not (np.isfinite(atr[i]) and atr[i] > 0):
            continue
        direction = 1 if rv[i] > 0 else -1
        side = -direction if side_mode == "fade" else direction
        stop, target = _bracket(float(close[i]), side, float(atr[i]), stop_atr, rr)
        out.append(Signal(time=d.index[i], side=side, stop=stop, target=target,
                          ttl_bars=ttl_bars, tag=f"garch_shock.{side_mode}.{vol_state}",
                          trigger=None, wait_bars=1))
    return out


# ---------------------------------------------------------------------------------------------
# Kalman (item 53)
# ---------------------------------------------------------------------------------------------

def _ewma_var(r: np.ndarray, lam: float) -> np.ndarray:
    """Variance known BEFORE bar t (uses returns through t-1)."""
    out = np.full(r.size, np.nan)
    acc = np.nan
    for t in range(r.size):
        out[t] = acc
        x = r[t]
        if math.isfinite(x):
            acc = x * x if not math.isfinite(acc) else lam * acc + (1 - lam) * x * x
    return out


def kalman_trend_path(y: np.ndarray, q_level: float, q_slope: float,
                      lam: float = 0.97) -> tuple[np.ndarray, np.ndarray]:
    """Filtered slope and its posterior standard deviation for a local-linear-trend model.

    level_t = level_{t-1} + slope_{t-1} + w1,  slope_t = slope_{t-1} + w2,  y_t = level_t + e.
    The observation variance is the EWMA of one-bar returns known before t, and both state
    noises are stated as multiples of it, so the filter's notion of "a big move" scales with the
    market's own -- the t-statistic is then comparable across instruments and decades.
    """
    n = y.size
    slope = np.full(n, np.nan)
    sd = np.full(n, np.nan)
    rv = _ewma_var(np.diff(y, prepend=np.nan), lam)
    x = None
    P = None
    for t in range(n):
        yt = y[t]
        R = rv[t]
        if not (math.isfinite(yt) and math.isfinite(R) and R > 0):
            continue
        if x is None:
            x = np.array([yt, 0.0])
            P = np.diag([R, R])
            continue
        Q = np.diag([q_level * R, q_slope * R])
        xp = np.array([x[0] + x[1], x[1]])
        Pp = np.array([[P[0, 0] + 2 * P[0, 1] + P[1, 1], P[0, 1] + P[1, 1]],
                       [P[0, 1] + P[1, 1], P[1, 1]]]) + Q
        S = Pp[0, 0] + R
        K = Pp[:, 0] / S
        x = xp + K * (yt - xp[0])
        P = Pp - np.outer(K, Pp[0, :])
        slope[t] = x[1]
        sd[t] = math.sqrt(max(P[1, 1], 0.0))
    return slope, sd


def family_kalman_trend(
    df: pd.DataFrame,
    *,
    q_level: float = 0.1,
    q_slope: float = 1e-3,
    entry_t: float = 2.0,
    side_mode: str = "follow",
    warmup: int = 500,
    atr_n: int = 20,
    stop_atr: float = 2.0,
    rr: float = 2.0,
    ttl_bars: int = 48,
) -> list[Signal]:
    """Enter when the filtered slope's t-statistic crosses +/- `entry_t`.

    `follow` is the trend claim; `fade` is the claim that a slope the filter is suddenly sure of
    is an overshoot. Both are tested, neither is chosen after the fact.
    """
    if side_mode not in {"follow", "fade"} or q_slope <= 0 or q_level < 0:
        return []
    d = _h1(df)
    if len(d) < warmup + 2:
        return []
    y = _log_close(d)
    slope, sd = _blocked(d.index, warmup, KALMAN_BLOCK, 2,
                         lambda lo, hi: kalman_trend_path(y[lo:hi], q_level, q_slope))
    with np.errstate(divide="ignore", invalid="ignore"):
        tstat = slope / sd
    up = np.isfinite(tstat) & (tstat >= entry_t)
    dn = np.isfinite(tstat) & (tstat <= -entry_t)
    atr = _atr(d, atr_n).to_numpy()
    close = d["close"].astype(float).to_numpy()
    out: list[Signal] = []
    for direction, mask in ((1, _edges(up)), (-1, _edges(dn))):
        for i in np.flatnonzero(mask):
            if i >= len(d) - 1 or not (np.isfinite(atr[i]) and atr[i] > 0):
                continue
            side = direction if side_mode == "follow" else -direction
            stop, target = _bracket(float(close[i]), side, float(atr[i]), stop_atr, rr)
            out.append(Signal(time=d.index[i], side=side, stop=stop, target=target,
                              ttl_bars=ttl_bars, tag=f"kalman_trend.{side_mode}",
                              trigger=None, wait_bars=1))
    out.sort(key=lambda s: s.time)
    return out


def _peer_frame(family: str, d: pd.DataFrame, pair_symbol: str) -> pd.DataFrame:
    """The peer's H1 closes on THIS cell's stamps, read from the bar store by `pair_symbol`.

    THE FAMILY LOADS ITS OWN SECOND LEG, the class books' and `families_specialist`'s contract
    (`risk_symbol`, `cond_symbol`): the sealed gauntlet loads a `peer` frame only for the two
    families it names, so a `peer` argument here would be called with None and every cell would
    build with zero signals (`gauntlet_buildability` says so by name). The cell carries the peer
    by value instead. `pair_symbol`, NOT `peer_symbol`: that one is an identity key the forward
    clock strips before the call, which would leave the family peerless exactly where forward
    evidence accrues.

    Matched to this cell's stamps EXACTLY (no as-of carry), so a missing peer bar drops the bar
    instead of pairing a fresh close with a stale one. H1 only, declared in `FAMILY_TIMEFRAMES`:
    the store holds the peer at H1, and an H1 close joined onto an M5 cell is the chart mismatch
    `family_inputs` documents. A named peer that cannot be read RAISES, so the judge files a
    build failure by name rather than a cell that "never fires". `pair_symbol` is a REQUIRED
    keyword on both families for the same reason: a cell that names no second leg is a failed
    build (TypeError), and the orthogonal sweep files it as unsuppliable instead of calling it.
    """
    if not pair_symbol:
        raise ValueError(f"{family}: no pair_symbol on the cell")
    step = pd.Series(d.index).diff().median()
    if step != pd.Timedelta(hours=1):
        raise ValueError(f"{family}: pair_symbol={pair_symbol!r} on a {step} chart; the peer is "
                         "read from the H1 store, so this family runs on H1 only")
    from mt5desk.families_specialist import asof_close
    # The store's stamps are UTC nanoseconds; a frame read at another unit (pandas 3 keeps the
    # parquet's, often microseconds) would match nothing, so the unit is stated, not assumed.
    idx = d.index if d.index.tz is None else d.index.tz_convert(None)
    stamps = idx.as_unit("ns").asi8
    closes = asof_close(np.asarray(stamps, dtype="int64"), str(pair_symbol), max_stale_h=0.0)
    if not np.isfinite(closes).any():
        raise ValueError(f"{family}: no H1 bars in the store for pair_symbol {pair_symbol!r}")
    # A PEER STORE THAT HAS FALLEN BEHIND IS A NAMED FAILURE, NOT A QUIET CLOCK. With exact-stamp
    # matching, a peer whose newest bar is older than this cell's simply drops the newest bars
    # from the join and the family fires nothing -- on a forward clock that reads exactly like a
    # calm market. A short gap is normal (the two instruments keep different hours around the
    # weekend and the daily break); beyond `MAX_PEER_LAG_BARS` the store is stale and says so.
    last = np.flatnonzero(np.isfinite(closes))[-1]
    if len(closes) - 1 - last > MAX_PEER_LAG_BARS:
        raise ValueError(f"{family}: the H1 store for pair_symbol {pair_symbol!r} ends "
                         f"{len(closes) - 1 - last} bars before this cell's last bar")
    return pd.DataFrame({"close": closes}, index=d.index).dropna()


def kalman_hedge_path(a: np.ndarray, b: np.ndarray, delta: float, lam: float = 0.97
                      ) -> tuple[np.ndarray, np.ndarray]:
    """Innovation e_t and its predicted variance for a = alpha_t + beta_t * b + noise.

    alpha and beta are random walks whose covariance is `delta` times the measurement variance
    (Chan 2013 states it as delta/(1-delta) against a FIXED Ve; a fixed Ve is a price-scale
    constant, which on hourly log prices made the hedge adapt fully every bar and the innovation
    vanish -- zero signals on EURUSD/GBPUSD). The measurement variance is an EWMA of past squared
    innovations -- known before t -- so the standardised innovation is not scaled by its own bar.
    """
    n = a.size
    e = np.full(n, np.nan)
    Q = np.full(n, np.nan)
    th = np.zeros(2)
    P = np.eye(2)
    Ve = np.nan
    started = False
    for t in range(n):
        at, bt = a[t], b[t]
        if not (math.isfinite(at) and math.isfinite(bt)):
            continue
        h = np.array([1.0, bt])
        if not started:
            th = np.array([at - bt, 1.0])
            P = np.eye(2)
            started = True
            continue
        et = at - float(h @ th)
        ve = Ve if math.isfinite(Ve) else et * et + 1e-12
        Pp = P + delta * ve * np.eye(2)
        Qt = float(h @ Pp @ h) + ve
        e[t] = et
        Q[t] = Qt
        K = Pp @ h / Qt
        th = th + K * et
        P = Pp - np.outer(K, h) @ Pp
        Ve = lam * ve + (1 - lam) * et * et
    return e, Q


def family_kalman_pair(
    df: pd.DataFrame,
    *,
    pair_symbol: str,
    delta: float = 1e-4,
    entry_z: float = 2.0,
    target_frac: float = 1.0,
    min_target_atr: float = 0.5,
    warmup: int = 1000,
    atr_n: int = 20,
    stop_atr: float = 2.5,
    ttl_bars: int = 48,
) -> list[Signal]:
    """Fade this leg when its Kalman-hedged spread innovation is `entry_z` deviations rich/cheap.

    Single-leg proxy, exactly as `relative_value` states for itself: the engine holds one
    position, so the signal trades THIS instrument against the dislocation. The target is the
    price at which `target_frac` of the innovation has closed; the stop is ATR-based.

    `min_target_atr` refuses a dislocation too small to trade: z can be large only because the
    predicted variance is small, and a target a fraction of the spread away is a cost, not an
    edge. The filter is restarted `warmup` bars before each calendar block (`_blocked`), so the
    gauntlet's frame and a forward clock's shorter one trade exactly the same rule; `warmup` is
    long because the hedge ratio needs ~1/sqrt(delta) bars to settle.
    """
    if not (0 < delta < 1):
        return []
    d = _h1(df)
    p = _peer_frame("kalman_pair", d, pair_symbol)
    j = d[["close"]].join(p[["close"]], how="inner", rsuffix="_peer").dropna()
    if len(j) < warmup + 2:
        return []
    a = np.log(j["close"].astype(float).to_numpy())
    b = np.log(j["close_peer"].astype(float).to_numpy())
    e, Q = _blocked(j.index, warmup, KALMAN_BLOCK, 2,
                    lambda lo, hi: kalman_hedge_path(a[lo:hi], b[lo:hi], delta))
    with np.errstate(divide="ignore", invalid="ignore"):
        z = e / np.sqrt(Q)
    atr = _atr(d, atr_n).reindex(j.index).to_numpy()
    close = j["close"].astype(float).to_numpy()
    out: list[Signal] = []
    for mask in (_edges(np.isfinite(z) & (z >= entry_z)), _edges(np.isfinite(z) & (z <= -entry_z))):
        for i in np.flatnonzero(mask):
            if i >= len(j) - 1 or not (np.isfinite(atr[i]) and atr[i] > 0):
                continue
            side = -1 if z[i] > 0 else 1
            px = float(close[i])
            target = px * math.exp(-target_frac * float(e[i]))
            if abs(target - px) < min_target_atr * atr[i]:
                continue
            out.append(Signal(time=j.index[i], side=side, stop=px - side * stop_atr * atr[i],
                              target=target, ttl_bars=ttl_bars, tag="kalman_pair",
                              trigger=None, wait_bars=1))
    out.sort(key=lambda s: s.time)
    return out


# ---------------------------------------------------------------------------------------------
# Copula (item 56)
# ---------------------------------------------------------------------------------------------

def copula_mispricing(ra: pd.Series, rb: pd.Series, window: int, kind: str, nu: float,
                      cum_bars: int) -> tuple[pd.Series, pd.Series]:
    """Cumulative mispricing index M_t = sum over `cum_bars` of (h(u_a | u_b) - 0.5), and rho.

    u is the trailing-window percentile rank (ending at t), so the marginal CDFs are empirical
    and causal. h is the copula's conditional CDF: P(U_a <= u_a | U_b = u_b). M > 0 means this
    leg has repeatedly closed higher than its peer's move made likely.
    """
    from scipy import stats

    n = int(window)
    ua = ra.rolling(n, min_periods=n).rank(pct=True) * n / (n + 1)
    ub = rb.rolling(n, min_periods=n).rank(pct=True) * n / (n + 1)
    if kind == "t":
        xa = pd.Series(stats.t.ppf(ua, nu), index=ra.index)
        xb = pd.Series(stats.t.ppf(ub, nu), index=ra.index)
    else:
        xa = pd.Series(stats.norm.ppf(ua), index=ra.index)
        xb = pd.Series(stats.norm.ppf(ub), index=ra.index)
    rho = xa.rolling(n, min_periods=n).corr(xb).clip(-0.995, 0.995)
    if kind == "t":
        scale = np.sqrt((nu + xb * xb) * (1 - rho * rho) / (nu + 1))
        h = pd.Series(stats.t.cdf((xa - rho * xb) / scale, nu + 1), index=ra.index)
    else:
        h = pd.Series(stats.norm.cdf((xa - rho * xb) / np.sqrt(1 - rho * rho)), index=ra.index)
    h = h.where(np.isfinite(rho))
    m = (h - 0.5).rolling(int(cum_bars), min_periods=int(cum_bars)).sum()
    return m, rho


def family_copula_pair(
    df: pd.DataFrame,
    *,
    pair_symbol: str,
    window: int = 500,
    kind: str = "t",
    nu: float = 4.0,
    cum_bars: int = 12,
    entry_m: float = 2.0,
    min_rho: float = 0.3,
    atr_n: int = 20,
    stop_atr: float = 2.0,
    rr: float = 1.5,
    ttl_bars: int = 24,
) -> list[Signal]:
    """Fade this leg when its copula mispricing index crosses +/- `entry_m` against its peer.

    `min_rho` refuses a pair whose rank dependence has dissolved on the trailing window: without
    dependence the conditional probability is just the leg's own percentile, and the cell would be
    a disguised single-instrument reversal.
    """
    if kind not in {"gauss", "t"} or nu <= 2:
        return []
    d = _h1(df)
    p = _peer_frame("copula_pair", d, pair_symbol)
    j = d[["close"]].join(p[["close"]], how="inner", rsuffix="_peer").dropna()
    if len(j) < 2 * window + cum_bars:
        return []
    ra = np.log(j["close"].astype(float)).diff()
    rb = np.log(j["close_peer"].astype(float)).diff()
    m, rho = copula_mispricing(ra, rb, window, kind, nu, cum_bars)
    mv = m.to_numpy()
    dep = np.isfinite(rho.to_numpy()) & (np.abs(rho.to_numpy()) >= min_rho)
    atr = _atr(d, atr_n).reindex(j.index).to_numpy()
    close = j["close"].astype(float).to_numpy()
    out: list[Signal] = []
    for mask in (_edges(dep & np.isfinite(mv) & (mv >= entry_m)),
                 _edges(dep & np.isfinite(mv) & (mv <= -entry_m))):
        for i in np.flatnonzero(mask):
            if i >= len(j) - 1 or not (np.isfinite(atr[i]) and atr[i] > 0):
                continue
            side = -1 if mv[i] > 0 else 1
            stop, target = _bracket(float(close[i]), side, float(atr[i]), stop_atr, rr)
            out.append(Signal(time=j.index[i], side=side, stop=stop, target=target,
                              ttl_bars=ttl_bars, tag=f"copula_pair.{kind}",
                              trigger=None, wait_bars=1))
    out.sort(key=lambda s: s.time)
    return out


# ---------------------------------------------------------------------------------------------
# OU half-life (item 57)
# ---------------------------------------------------------------------------------------------

def ou_path(x: pd.Series, window: int) -> tuple[pd.Series, pd.Series, pd.Series]:
    """Rolling AR(1) on log price: (half-life in bars, equilibrium mu, stationary sigma).

    x_t = a + b x_{t-1} + e over the trailing `window` ending at t. Half-life = -ln 2 / ln b,
    defined only for 0 < b < 1 -- anything else is not mean-reverting on this window and is NaN.
    """
    lag = x.shift(1)
    w = int(window)
    mx = x.rolling(w, min_periods=w).mean()
    ml = lag.rolling(w, min_periods=w).mean()
    cov = x.rolling(w, min_periods=w).cov(lag)
    vl = lag.rolling(w, min_periods=w).var()
    vx = x.rolling(w, min_periods=w).var()
    b = cov / vl
    a = mx - b * ml
    ev = (vx - b * b * vl).clip(lower=0)
    ok = (b > 0) & (b < 1)
    with np.errstate(divide="ignore", invalid="ignore"):
        hl = (-math.log(2) / np.log(b)).where(ok)
        mu = (a / (1 - b)).where(ok)
        s_eq = np.sqrt(ev / (1 - b * b)).where(ok)
    return hl, mu, s_eq


def family_ou_reversion(
    df: pd.DataFrame,
    *,
    window: int = 500,
    entry_z: float = 2.0,
    hl_min: float = 4.0,
    hl_max: float = 96.0,
    hold_mult: float = 2.0,
    target_frac: float = 0.5,
    min_target_atr: float = 0.5,
    atr_n: int = 20,
    stop_atr: float = 2.5,
    max_ttl: int = 240,
) -> list[Signal]:
    """Fade a log-price `entry_z` stationary sigmas from its OU equilibrium, half-life permitting.

    The hold is `hold_mult` half-lives (capped at `max_ttl`), so a cell can never hold for less
    than the reversion it claims takes; `hl_max` refuses a 'reversion' slower than any hold this
    desk would run. The target is `target_frac` of the distance back to mu.
    """
    if not (0 < hl_min < hl_max) or hold_mult < 1 or not (0 < target_frac <= 1):
        return []
    d = _h1(df)
    if len(d) < 2 * window:
        return []
    x = pd.Series(_log_close(d), index=d.index)
    hl, mu, s_eq = ou_path(x, window)
    xv, hv, mv, sv = x.to_numpy(), hl.to_numpy(), mu.to_numpy(), s_eq.to_numpy()
    with np.errstate(divide="ignore", invalid="ignore"):
        z = (xv - mv) / sv
    inside = np.isfinite(hv) & (hv >= hl_min) & (hv <= hl_max) & np.isfinite(z)
    atr = _atr(d, atr_n).to_numpy()
    close = d["close"].astype(float).to_numpy()
    out: list[Signal] = []
    for mask in (_edges(inside & (z >= entry_z)), _edges(inside & (z <= -entry_z))):
        for i in np.flatnonzero(mask):
            if i >= len(d) - 1 or not (np.isfinite(atr[i]) and atr[i] > 0):
                continue
            side = -1 if z[i] > 0 else 1
            px = float(close[i])
            ttl = int(min(max_ttl, math.ceil(hold_mult * hv[i])))
            target = px * math.exp(-target_frac * (xv[i] - mv[i]))
            if abs(target - px) < min_target_atr * atr[i]:
                continue                         # a reversion smaller than its own cost
            out.append(Signal(time=d.index[i], side=side, stop=px - side * stop_atr * atr[i],
                              target=target, ttl_bars=ttl, tag="ou_reversion",
                              trigger=None, wait_bars=1))
    out.sort(key=lambda s: s.time)
    return out

# ---------------------------------------------------------------------------------------------
# Particle filter and Gaussian process (item 58)
# ---------------------------------------------------------------------------------------------

#: Bars per calendar block for the particle filter (see `_refit_starts`), and the stream its
#: random numbers are drawn from. The seed is a CONSTANT, not a cell parameter: a seed on the
#: recipe would let one rule be judged many times under different noise and the best draw kept.
PARTICLE_BLOCK = 500
PARTICLE_SEED = 20261110
#: Log-variance dynamics of the particle model, in units of the block's own warm-up variance.
_SV_PHI = 0.97
_SV_SIGMA = 0.2


def particle_drift_path(r: pd.Series, warmup: int, drift_vol: float, drift_hl: float,
                        n_particles: int = 128) -> tuple[pd.Series, pd.Series]:
    """Filtered P(drift_t > 0 | returns to t) and the filtered return sigma, bar by bar.

    THE MODEL: x_t = m_t + exp(h_t / 2) e_t, with a latent drift m (AR(1), half-life `drift_hl`
    bars, stationary sd `drift_vol` in units of one bar's sd) and a latent log-variance h (AR(1)).
    Drift and variance are unknown together, so the posterior is not Gaussian and a Kalman filter
    cannot state it; a bootstrap particle filter over h does, with the drift carried exactly per
    particle (Rao-Blackwellised: given h the drift is linear-Gaussian, so each particle holds a
    Kalman mean and variance rather than a sampled drift, which is the same posterior with less
    Monte-Carlo noise). Systematic resampling every bar.

    CAUSAL AND THE SAME ON ANY FRAME. Each calendar block (`_refit_starts`) is filtered from
    `warmup` bars before its first bar; returns are scaled by the sd of those warm-up bars only;
    and the block's random numbers come from a generator seeded by `PARTICLE_SEED` and the
    block's first timestamp, drawn in bar order. So a labelled bar is a function of at most
    `warmup + block` bars before it and of nothing after it, whatever bar the frame starts or ends
    on. All blocks are filtered together (one array row per block), which is what makes ~40k bars
    cost about a second instead of a Python loop of that length times the particle count.
    """
    from scipy.special import ndtr

    x = r.to_numpy(dtype=float)
    n = x.size
    p_up = np.full(n, np.nan)
    sig = np.full(n, np.nan)
    index = pd.DatetimeIndex(r.index)
    # `warmup + 1`: bar 0's return is undefined on every frame, so no block may warm up over it.
    starts = _refit_starts(index, int(warmup) + 1, PARTICLE_BLOCK)
    if not len(starts) or drift_vol <= 0 or drift_hl <= 0 or n_particles < 8:
        return pd.Series(p_up, index=r.index), pd.Series(sig, index=r.index)
    ends = np.append(starts[1:], n)
    w, npart, nb = int(warmup), int(n_particles), len(starts)
    steps = w + int((ends - starts).max())
    idx = index if index.tz is None else index.tz_convert(None)
    stamp = idx.as_unit("ns").asi8
    obs = np.full((nb, steps), np.nan)
    scale = np.full(nb, np.nan)
    noise = np.zeros((nb, steps + 1, npart), dtype=np.float32)
    unif = np.zeros((nb, steps))
    for b, (k, e) in enumerate(zip(starts, ends, strict=True)):
        seg = x[k - w:e]
        s0 = float(np.nanstd(seg[:w]))
        if not (math.isfinite(s0) and s0 > 0):
            continue
        scale[b] = s0
        obs[b, :seg.size] = seg / s0
        key = [PARTICLE_SEED, int(stamp[k] // 3_600_000_000_000)]
        noise[b, :seg.size + 1] = np.random.default_rng([*key, 0]).standard_normal(
            (seg.size + 1, npart), dtype=np.float32)
        unif[b, :seg.size] = np.random.default_rng([*key, 1]).random(seg.size)
    phi_m = 0.5 ** (1.0 / float(drift_hl))
    q_m = float(drift_vol) ** 2 * (1.0 - phi_m * phi_m)
    var_h = _SV_SIGMA ** 2 / (1.0 - _SV_PHI ** 2)
    mu_h = -0.5 * var_h                          # E[exp(h)] = 1: the warm-up variance
    h = mu_h + math.sqrt(var_h) * noise[:, 0, :].astype(float)
    mm = np.zeros((nb, npart))
    pp = np.full((nb, npart), float(drift_vol) ** 2)
    rows = np.arange(nb)[:, None]
    out_p = np.full((nb, steps), np.nan)
    out_v = np.full((nb, steps), np.nan)
    for t in range(steps):
        h = mu_h + _SV_PHI * (h - mu_h) + _SV_SIGMA * noise[:, t + 1, :]
        mp = phi_m * mm
        pq = phi_m * phi_m * pp + q_m
        o = obs[:, t]
        ok = np.isfinite(o)[:, None]
        rv = np.exp(h)
        s = pq + rv
        innov = np.where(ok, o[:, None] - mp, 0.0)
        gain = pq / s
        mm = np.where(ok, mp + gain * innov, mp)
        pp = np.where(ok, (1.0 - gain) * pq, pq)
        logw = np.where(ok, -0.5 * (np.log(s) + innov * innov / s), 0.0)
        wt = np.exp(logw - logw.max(axis=1, keepdims=True))
        wt /= wt.sum(axis=1, keepdims=True)
        out_p[:, t] = (wt * ndtr(mm / np.sqrt(pp))).sum(axis=1)
        out_v[:, t] = (wt * rv).sum(axis=1)
        # systematic resampling, every row at once: one uniform per block per bar
        cs = np.cumsum(wt, axis=1)
        cs[:, -1] = 1.0
        pos = (unif[:, t][:, None] + np.arange(npart)) / npart
        pick = np.minimum((cs[:, None, :] < pos[:, :, None]).sum(axis=2), npart - 1)
        h, mm, pp = h[rows, pick], mm[rows, pick], pp[rows, pick]
    for b, (k, e) in enumerate(zip(starts, ends, strict=True)):
        if math.isfinite(scale[b]):
            p_up[k:e] = out_p[b, w:w + (e - k)]
            sig[k:e] = np.sqrt(out_v[b, w:w + (e - k)]) * scale[b]
    bad = ~np.isfinite(x)
    p_up[bad] = np.nan
    return pd.Series(p_up, index=r.index), pd.Series(sig, index=r.index)


def family_particle_regime(
    df: pd.DataFrame,
    *,
    drift_vol: float = 0.2,
    drift_hl: float = 48.0,
    entry_p: float = 0.9,
    side_mode: str = "follow",
    warmup: int = 250,
    n_particles: int = 128,
    atr_n: int = 20,
    stop_atr: float = 2.0,
    rr: float = 2.0,
    ttl_bars: int = 48,
) -> list[Signal]:
    """Enter when the particle posterior P(drift > 0) crosses `entry_p` (long) or 1 - `entry_p`.

    `follow` is the claim that a drift regime the filter has become sure of persists; `fade` that
    such certainty marks its end. `drift_vol` is the PRIOR size of a drift regime in units of one
    bar's sd and `drift_hl` how long one lasts -- both are the claim under test, on the recipe,
    never fitted.
    """
    if side_mode not in {"follow", "fade"} or not (0.5 < entry_p < 1.0):
        return []
    d = _h1(df)
    if len(d) < warmup + 3:
        return []
    r = pd.Series(_log_close(d), index=d.index).diff()
    p, _sig = particle_drift_path(r, warmup, drift_vol, drift_hl, n_particles)
    pv = p.to_numpy()
    up = np.isfinite(pv) & (pv >= entry_p)
    dn = np.isfinite(pv) & (pv <= 1.0 - entry_p)
    atr = _atr(d, atr_n).to_numpy()
    close = d["close"].astype(float).to_numpy()
    out: list[Signal] = []
    for direction, mask in ((1, _edges(up)), (-1, _edges(dn))):
        for i in np.flatnonzero(mask):
            if i >= len(d) - 1 or not (np.isfinite(atr[i]) and atr[i] > 0):
                continue
            side = direction if side_mode == "follow" else -direction
            stop, target = _bracket(float(close[i]), side, float(atr[i]), stop_atr, rr)
            out.append(Signal(time=d.index[i], side=side, stop=stop, target=target,
                              ttl_bars=ttl_bars, tag=f"particle_regime.{side_mode}",
                              trigger=None, wait_bars=1))
    out.sort(key=lambda s: s.time)
    return out


#: Length-scales (bars) the GP's marginal likelihood chooses between at each calendar block, and
#: the block length. A grid, not an optimiser: four Cholesky factorisations a block, no
#: convergence to fail, and the same answer on every machine.
GP_LENGTHS = (6.0, 12.0, 24.0, 48.0)
GP_BLOCK = 500


def _gp_weights(window: int, horizon: int, amp: float, ell: float
                ) -> tuple[np.ndarray, float, np.ndarray]:
    """FIR weights, posterior sd and the Cholesky factor for one (amp, ell) on a regular grid.

    Observations y_j = f(j) + e_j over j = 0..window-1 with f ~ GP(0, amp^2 RBF(ell)) and unit
    noise; the target is g = f(window) + ... + f(window - 1 + horizon), the drift summed over the
    next `horizon` bars. On equally spaced bars the posterior mean is one fixed linear filter of
    the window, so a whole block is a single matrix product.
    """
    from scipy.linalg import cho_factor, cho_solve

    j = np.arange(window, dtype=float)
    fut = window + np.arange(horizon, dtype=float)
    a2 = amp * amp
    kxx = a2 * np.exp(-0.5 * ((j[:, None] - j[None, :]) / ell) ** 2) + np.eye(window)
    c = (a2 * np.exp(-0.5 * ((fut[:, None] - j[None, :]) / ell) ** 2)).sum(axis=0)
    kff = float((a2 * np.exp(-0.5 * ((fut[:, None] - fut[None, :]) / ell) ** 2)).sum())
    cf = cho_factor(kxx, lower=True)
    wts = cho_solve(cf, c)
    var = max(kff - float(c @ wts), 1e-18)
    return wts, math.sqrt(var), cf[0]


def gp_forecast_path(r: pd.Series, window: int, horizon: int, amp: float
                     ) -> tuple[pd.Series, pd.Series]:
    """t-statistic of the GP forecast of the next `horizon` bars' drift, and the length-scale used.

    Returns are divided by their own trailing-`window` sd (ending at the bar), so `amp` -- the
    prior sd of the drift in units of one bar's sd -- means the same on every instrument. At each
    calendar block (`_refit_starts`) the RBF length-scale is the one in `GP_LENGTHS` with the
    highest marginal likelihood on the `window` standardised returns BEFORE the block; the block's
    bars are then forecast with that length-scale from their own trailing window. Nothing after a
    bar enters its forecast, and nothing earlier than `2 * window + block` bars before it.
    """
    from numpy.lib.stride_tricks import sliding_window_view
    from scipy.linalg import solve_triangular

    w, k = int(window), int(horizon)
    x = r.to_numpy(dtype=float)
    n = x.size
    tstat = np.full(n, np.nan)
    used = np.full(n, np.nan)
    sd = r.rolling(w, min_periods=w).std().to_numpy()
    with np.errstate(divide="ignore", invalid="ignore"):
        z = np.where(sd > 0, x / sd, np.nan)     # each bar in the sd of the window ending at it
    # `2w + 1`: the fit window's standardised returns each need their own full trailing window.
    starts = _refit_starts(pd.DatetimeIndex(r.index), 2 * w + 1, GP_BLOCK)
    if not len(starts) or amp <= 0 or k < 1 or n < w:
        return pd.Series(tstat, index=r.index), pd.Series(used, index=r.index)
    models = [_gp_weights(w, k, float(amp), ell) for ell in GP_LENGTHS]
    # THE FORECAST READS WHAT THE LENGTH-SCALE WAS CHOSEN ON: z, each bar over the sd of the
    # window ending at it. The first cut forecast from raw returns over the END bar's sd while
    # the marginal likelihood was scored on z -- two standardisations of one model (audit
    # should-fix 2026-11-10). One series now feeds both.
    view = sliding_window_view(z, w)             # view[i - w + 1] = z[i - w + 1 .. i]
    ends = np.append(starts[1:], n)
    for s0, e in zip(starts, ends, strict=True):
        y = z[s0 - w:s0]
        if not np.isfinite(y).all():
            continue
        best, best_ll = 0, -np.inf
        for m, (_wts, _psd, chol) in enumerate(models):
            a = solve_triangular(chol, y, lower=True)
            ll = -0.5 * float(a @ a) - float(np.log(np.diag(chol)).sum())
            if ll > best_ll:
                best, best_ll = m, ll
        wts, psd, _ = models[best]
        with np.errstate(invalid="ignore"):
            mean = view[s0 - w + 1:e - w + 1] @ wts     # NaN where the window holds an undefined z
        tstat[s0:e] = mean / psd
        used[s0:e] = GP_LENGTHS[best]
    return pd.Series(tstat, index=r.index), pd.Series(used, index=r.index)


def family_gp_forecast(
    df: pd.DataFrame,
    *,
    window: int = 240,
    horizon: int = 8,
    amp: float = 0.2,
    entry_t: float = 1.0,
    side_mode: str = "follow",
    atr_n: int = 20,
    stop_atr: float = 2.0,
    rr: float = 1.5,
    ttl_bars: int = 24,
) -> list[Signal]:
    """Enter when the GP's forecast drift over `horizon` bars is `entry_t` posterior sds from zero.

    The t-statistic is posterior mean over posterior sd of the LATENT drift, so it is small by
    construction when the window says nothing (posterior = prior, mean ~ 0): the threshold is in
    units of what the model itself claims to know. `amp` is the prior and is on the recipe.
    """
    if side_mode not in {"follow", "fade"} or window < 60 or horizon < 1 or amp <= 0:
        return []
    d = _h1(df)
    if len(d) < 2 * window + 3:
        return []
    r = pd.Series(_log_close(d), index=d.index).diff()
    t, _ell = gp_forecast_path(r, window, horizon, amp)
    tv = t.to_numpy()
    up = np.isfinite(tv) & (tv >= entry_t)
    dn = np.isfinite(tv) & (tv <= -entry_t)
    atr = _atr(d, atr_n).to_numpy()
    close = d["close"].astype(float).to_numpy()
    out: list[Signal] = []
    for direction, mask in ((1, _edges(up)), (-1, _edges(dn))):
        for i in np.flatnonzero(mask):
            if i >= len(d) - 1 or not (np.isfinite(atr[i]) and atr[i] > 0):
                continue
            side = direction if side_mode == "follow" else -direction
            stop, target = _bracket(float(close[i]), side, float(atr[i]), stop_atr, rr)
            out.append(Signal(time=d.index[i], side=side, stop=stop, target=target,
                              ttl_bars=ttl_bars, tag=f"gp_forecast.{side_mode}",
                              trigger=None, wait_bars=1))
    out.sort(key=lambda s: s.time)
    return out


FAMILIES = {
    "garch_shock": family_garch_shock,
    "kalman_trend": family_kalman_trend,
    "kalman_pair": family_kalman_pair,
    "copula_pair": family_copula_pair,
    "ou_reversion": family_ou_reversion,
    "particle_regime": family_particle_regime,
    "gp_forecast": family_gp_forecast,
}
#: Families with a second leg, named on the cell as `pair_symbol` and read by the family itself.
PEER_FAMILIES = frozenset({"kalman_pair", "copula_pair"})
