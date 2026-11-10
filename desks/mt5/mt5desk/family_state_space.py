"""Five quant-framework families: GARCH, Kalman (trend and pair), copula pair, OU half-life.

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


def garch_sigma_path(r: pd.Series, window: int, refit: int) -> tuple[pd.Series, pd.Series]:
    """Walk-forward conditional sigma_{t|t-1} and the variance ratio sigma^2_{t+1|t} / long-run.

    The block [k, k+refit) is labelled with parameters fitted on r[k-window:k] -- returns the fit
    never saw are the only ones it labels. The recursion is warmed up over that same trailing
    window, so each block's first forecast is not an arbitrary initial value.
    """
    x = r.to_numpy(dtype=float)
    n = x.size
    sig = np.full(n, np.nan)
    ratio = np.full(n, np.nan)
    k = window
    while k < n:
        hist = x[k - window:k]
        fit = fit_gjr_garch(hist)
        end = min(n, k + refit)
        if fit is not None:
            om, a, g, b = fit
            pers = a + b + 0.5 * g
            lr = om / (1.0 - pers) if pers < 1 else np.nan
            seg = np.nan_to_num(x[k - window:end] - np.nanmean(hist))
            v = _gjr_var_path(seg, om, a, g, b, float(np.nanvar(hist)))
            off = window
            sig[k:end] = np.sqrt(v[off:off + (end - k)])
            if math.isfinite(lr) and lr > 0:
                ratio[k:end] = v[off + 1:off + 1 + (end - k)] / lr
        k = end
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
    window: int = 2000,
    refit: int = 500,
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
    if len(d) < window + refit:
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
    if len(d) < warmup + 100:
        return []
    y = _log_close(d)
    slope, sd = kalman_trend_path(y, q_level, q_slope)
    with np.errstate(divide="ignore", invalid="ignore"):
        tstat = slope / sd
    tstat[:warmup] = np.nan
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


def _peer_frame(family: str, d: pd.DataFrame, peer: pd.DataFrame | None,
                peer_symbol: str | None) -> pd.DataFrame | None:
    """The peer's bars on THIS cell's stamps: the handed-over frame, else the bar store's.

    THE SEALED GAUNTLET LOADS PEERS ONLY FOR THE FAMILIES IT NAMES (`relative_value`,
    `correlation_regime`), so for these two `peer_symbol` reaches the family as an ordinary
    parameter. The family then reads the peer's H1 closes itself, through the class books' own
    loader -- the precedent `families_specialist` set for `risk_symbol` -- matched to this cell's
    stamps EXACTLY (no as-of carry), so a missing peer bar drops the bar instead of pairing a
    fresh close with a stale one. Only on an hourly chart: the store holds peers at H1, and an H1
    close joined onto an M5 cell would be the chart mismatch `family_inputs` documents. Anything
    else with a named peer and no frame RAISES, so the judge files it as a build failure by name.
    """
    if peer is not None and not getattr(peer, "empty", True):
        return _h1(peer)
    if not peer_symbol:
        return None
    step = pd.Series(d.index).diff().median()
    if step != pd.Timedelta(hours=1):
        raise ValueError(f"{family}: peer_symbol={peer_symbol!r} named on a {step} chart with no "
                         "peer frame handed over; only H1 peers are loaded from the store")
    from mt5desk.families_specialist import asof_close
    # The store's stamps are UTC nanoseconds; a frame read at another unit (pandas 3 keeps the
    # parquet's, often microseconds) would match nothing, so the unit is stated, not assumed.
    idx = d.index if d.index.tz is None else d.index.tz_convert(None)
    stamps = idx.as_unit("ns").asi8
    closes = asof_close(np.asarray(stamps, dtype="int64"), str(peer_symbol), max_stale_h=0.0)
    if not np.isfinite(closes).any():
        raise ValueError(f"{family}: no H1 bars in the store for peer {peer_symbol!r}")
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
    peer: pd.DataFrame | None = None,
    peer_symbol: str | None = None,
    delta: float = 1e-4,
    entry_z: float = 2.0,
    target_frac: float = 1.0,
    warmup: int = 500,
    atr_n: int = 20,
    stop_atr: float = 2.5,
    ttl_bars: int = 48,
) -> list[Signal]:
    """Fade this leg when its Kalman-hedged spread innovation is `entry_z` deviations rich/cheap.

    Single-leg proxy, exactly as `relative_value` states for itself: the engine holds one
    position, so the signal trades THIS instrument against the dislocation. The target is the
    price at which `target_frac` of the innovation has closed; the stop is ATR-based.
    """
    if not (0 < delta < 1):
        return []
    d = _h1(df)
    p = _peer_frame("kalman_pair", d, peer, peer_symbol)
    if p is None:
        return []
    j = d[["close"]].join(p[["close"]], how="inner", rsuffix="_peer").dropna()
    if len(j) < warmup + 100:
        return []
    a = np.log(j["close"].astype(float).to_numpy())
    b = np.log(j["close_peer"].astype(float).to_numpy())
    e, Q = kalman_hedge_path(a, b, delta)
    with np.errstate(divide="ignore", invalid="ignore"):
        z = e / np.sqrt(Q)
    z[:warmup] = np.nan
    atr = _atr(d, atr_n).reindex(j.index).to_numpy()
    close = j["close"].astype(float).to_numpy()
    out: list[Signal] = []
    for mask in (_edges(np.isfinite(z) & (z >= entry_z)), _edges(np.isfinite(z) & (z <= -entry_z))):
        for i in np.flatnonzero(mask):
            if i >= len(j) - 1 or not (np.isfinite(atr[i]) and atr[i] > 0):
                continue
            side = -1 if z[i] > 0 else 1
            px = float(close[i])
            out.append(Signal(time=j.index[i], side=side, stop=px - side * stop_atr * atr[i],
                              target=px * math.exp(-target_frac * float(e[i])),
                              ttl_bars=ttl_bars, tag="kalman_pair", trigger=None, wait_bars=1))
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
    one = np.sqrt(1 - rho * rho)
    if kind == "t":
        scale = np.sqrt((nu + xb * xb) * (1 - rho * rho) / (nu + 1))
        h = pd.Series(stats.t.cdf((xa - rho * xb) / scale, nu + 1), index=ra.index)
    else:
        h = pd.Series(stats.norm.cdf((xa - rho * xb) / one), index=ra.index)
    h = h.where(np.isfinite(rho))
    m = (h - 0.5).rolling(int(cum_bars), min_periods=int(cum_bars)).sum()
    return m, rho


def family_copula_pair(
    df: pd.DataFrame,
    *,
    peer: pd.DataFrame | None = None,
    peer_symbol: str | None = None,
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
    p = _peer_frame("copula_pair", d, peer, peer_symbol)
    if p is None:
        return []
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
            out.append(Signal(time=d.index[i], side=side, stop=px - side * stop_atr * atr[i],
                              target=px * math.exp(-target_frac * (xv[i] - mv[i])),
                              ttl_bars=ttl, tag="ou_reversion", trigger=None, wait_bars=1))
    out.sort(key=lambda s: s.time)
    return out


FAMILIES = {
    "garch_shock": family_garch_shock,
    "kalman_trend": family_kalman_trend,
    "kalman_pair": family_kalman_pair,
    "copula_pair": family_copula_pair,
    "ou_reversion": family_ou_reversion,
}
#: Families with a second leg. A caller that has the peer frame passes it as `peer`; one that
#: does not (the sealed gauntlet) passes `peer_symbol` and the family reads the store itself.
PEER_FAMILIES = frozenset({"kalman_pair", "copula_pair"})
