"""The Reality-Calibrated Market Digital Twin with simulation-based inference (LAWS 5m).

Not an arbitrary agent world. The question the twin answers is INVERSE: given the tape the desk
actually observed, which hidden simulator worlds could have generated it -- and does a strategy
survive across that POSTERIOR rather than on the one history that happened?

Four parts, all pure (numpy/scipy only, no state, no I/O):

(a) `simulate` -- a compact agent-based tape simulator. Every world is a vector of latent
    parameters (`PARAMS`): the participant mix as reaction strengths (market makers, trend
    followers, mean reverters, dealer hedgers, forced liquidators, retail noise, passive scheduled
    flow), order arrivals with a self-exciting (Hawkes) term, cancellation behaviour, a latency
    distribution, a concave impact function, inventory preferences, intraday seasonality and news
    jumps. It produces bars with spreads, ranges, volumes, signed flow, depth and a cancellation
    proxy -- the SAME fields the desk measures on its own tape, so one `summarise` serves both.
(b) `summarise` -- the summary statistics of a tape window (real or simulated): return moments,
    autocorrelations at several lags, tails and jump frequency, volatility clustering, spread and
    range distributions, volume clustering, a depth proxy, signed-flow impact where sided quotes
    exist, a cancellation proxy, intraday seasonality and state-conditioned responses. A field
    the tape does not carry yields NaN, which is UNMEASURED, never zero.
(c) `infer` -- ABC-SMC with a learned summary distance (the semi-automatic projection of
    Fearnhead & Prangle: a ridge regression of parameters on pilot summaries), giving a weighted
    particle POSTERIOR over worlds; `ppc` -- posterior predictive checks per statistic GROUP, so a
    posterior that reproduces returns and nothing else is named RETURNS_ONLY and is not realistic;
    `robustness` -- the distribution of a strategy's outcome across sampled posterior worlds.
(d) `mechanism_plausibility` -- run a hypothesised mechanism inside the posterior worlds and
    report whether it can exist there.

The twin ROUTES research (which candidates deserve the gauntlet's attention, which worlds a rule
dies in). It never sizes capital and never reduces a book: it publishes a robustness
distribution, and the allocator remains the only organ that turns evidence into fractions.
"""
from __future__ import annotations

import math
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass, field
from typing import Any

import numpy as np
from scipy.stats import qmc

EPS = 1e-12
#: Steps of reaction history kept per world (the latency ring buffer).
LAG_RING = 8
#: Robust sigmas (median/MAD of the predictive draws) beyond which an observed statistic is
#: outside the world. See `ppc` for why a per-statistic tail count cannot be the cut.
PPC_Z = 3.5
#: Minimum triggered events before a mechanism's effect in one world is a measurement.
MIN_EVENTS = 20


# ------------------------------------------------------------------------- the latent world

@dataclass(frozen=True)
class ParamSpec:
    name: str
    lo: float
    hi: float
    log: bool
    doc: str


PARAMS: tuple[ParamSpec, ...] = (
    ParamSpec("fundamental_vol", 2e-5, 5e-3, True, "per-step log-vol of the value process"),
    ParamSpec("base_intensity", 2.0, 400.0, True, "mean order arrivals per step"),
    ParamSpec("hawkes_alpha", 0.0, 0.9, False, "self-excitation: branching ratio of arrivals"),
    ParamSpec("hawkes_decay", 0.05, 0.9, False, "per-step decay of the excitation"),
    ParamSpec("cancel_rate", 0.0, 0.8, False, "share of resting depth cancelled per step"),
    ParamSpec("latency_mean", 0.0, 5.0, False, "mean reaction delay, in steps"),
    ParamSpec("latency_cv", 0.1, 1.5, False, "dispersion of the delay across participants"),
    ParamSpec("impact_coef", 0.0, 2.0, False, "mid move per unit standardised flow, vol units"),
    ParamSpec("impact_exponent", 0.3, 1.0, False, "concavity of the impact function"),
    ParamSpec("mm_spread_base", 5e-6, 5e-3, True, "market makers' relative full spread at rest"),
    ParamSpec("mm_depth", 1.0, 500.0, True, "resting depth replenished per step"),
    ParamSpec("mm_inventory_aversion", 0.0, 1.0, False, "quote skew per unit of inventory"),
    ParamSpec("trend_strength", 0.0, 3.0, False, "trend followers' reaction to recent drift"),
    ParamSpec("revert_strength", 0.0, 3.0, False, "mean reverters' reaction to the gap to value"),
    ParamSpec("hedger_gamma", -1.0, 1.0, False, "dealer hedging: <0 chases moves, >0 damps"),
    ParamSpec("liquidator_strength", 0.0, 3.0, False, "forced flow per vol-unit past threshold"),
    ParamSpec("liquidation_threshold", 1.0, 6.0, False, "drawdown (vol units) that forces flow"),
    ParamSpec("retail_noise", 0.0, 3.0, False, "noise-trader flow"),
    ParamSpec("passive_amp", 0.0, 2.0, False, "passive scheduled flow over the day"),
    ParamSpec("season_amp", 0.0, 1.0, False, "intraday amplitude of activity and volatility"),
    ParamSpec("season_phase", 0.0, 1.0, False, "time of day (fraction) of peak activity"),
    ParamSpec("jump_rate", 0.0, 0.05, False, "per-step probability of a news jump"),
    ParamSpec("jump_scale", 2.0, 12.0, False, "jump size in vol units"),
)
PARAM_NAMES: tuple[str, ...] = tuple(p.name for p in PARAMS)
_IDX: dict[str, int] = {p.name: i for i, p in enumerate(PARAMS)}
#: The participant classes whose flow the simulator attributes, in `SimBars.attribution` order.
CLASSES: tuple[str, ...] = ("market_maker", "trend_follower", "mean_reverter", "hedger",
                            "forced_liquidator", "retail", "passive")


def _unit_to_natural(u: np.ndarray) -> np.ndarray:
    """Unit-cube coordinates (N x D) -> natural parameter values."""
    out = np.empty_like(u, dtype=float)
    for i, p in enumerate(PARAMS):
        if p.log:
            out[:, i] = np.exp(math.log(p.lo) + u[:, i] * (math.log(p.hi) - math.log(p.lo)))
        else:
            out[:, i] = p.lo + u[:, i] * (p.hi - p.lo)
    return out


def _natural_to_unit(theta: np.ndarray) -> np.ndarray:
    out = np.empty_like(theta, dtype=float)
    for i, p in enumerate(PARAMS):
        if p.log:
            out[:, i] = (np.log(np.maximum(theta[:, i], EPS)) - math.log(p.lo)) / (
                math.log(p.hi) - math.log(p.lo))
        else:
            out[:, i] = (theta[:, i] - p.lo) / (p.hi - p.lo)
    return np.clip(out, 0.0, 1.0)


# ------------------------------------------------------------------------- the tape objects

@dataclass
class SimBars:
    """A batch of W worlds' bars, every field W x n. NaN where the tape does not carry a field.

    `flow` is signed pressure in standardised units (net order flow in a world; order-flow
    imbalance counted from sided quotes on a real tape); `flicker` is the share of consecutive
    quote changes that reverse the previous one -- the cancellation proxy a quote-only tape can
    measure; `depth` is resting depth (a world) or NaN (a real tape reads depth only through the
    volume-per-range proxy `summarise` derives for both).
    """
    open: np.ndarray
    high: np.ndarray
    low: np.ndarray
    close: np.ndarray
    volume: np.ndarray
    spread: np.ndarray
    flow: np.ndarray
    flicker: np.ndarray
    depth: np.ndarray
    tod: np.ndarray
    steps_per_bar: int = 1
    attribution: np.ndarray | None = None

    @property
    def n_worlds(self) -> int:
        return int(self.close.shape[0])

    @property
    def n_bars(self) -> int:
        return int(self.close.shape[1])

    def world(self, i: int) -> WorldBars:
        return WorldBars(self.open[i], self.high[i], self.low[i], self.close[i], self.volume[i],
                         self.spread[i], self.flow[i], self.tod)


@dataclass(frozen=True)
class WorldBars:
    """One world's bars, 1-D arrays: what a strategy rule or a mechanism trigger reads."""
    open: np.ndarray
    high: np.ndarray
    low: np.ndarray
    close: np.ndarray
    volume: np.ndarray
    spread: np.ndarray
    flow: np.ndarray
    tod: np.ndarray

    @property
    def returns(self) -> np.ndarray:
        lc = np.log(np.maximum(self.close, EPS))
        return np.concatenate([[0.0], np.diff(lc)])


def tape_window(open_: Sequence[float] | np.ndarray, high: Sequence[float] | np.ndarray,
                low: Sequence[float] | np.ndarray, close: Sequence[float] | np.ndarray,
                volume: Sequence[float] | np.ndarray, tod: Sequence[float] | np.ndarray, *,
                spread: Sequence[float] | np.ndarray | None = None,
                flow: Sequence[float] | np.ndarray | None = None,
                flicker: Sequence[float] | np.ndarray | None = None,
                steps_per_bar: int = 1) -> SimBars:
    """A real tape window as a one-world `SimBars`; absent fields are NaN (UNMEASURED)."""
    c = np.asarray(close, dtype=float).reshape(1, -1)
    n = c.shape[1]

    def _f(x: Sequence[float] | np.ndarray | None) -> np.ndarray:
        if x is None:
            return np.full((1, n), np.nan)
        return np.asarray(x, dtype=float).reshape(1, -1)

    return SimBars(_f(open_), _f(high), _f(low), c, _f(volume), _f(spread), _f(flow),
                   _f(flicker), np.full((1, n), np.nan), np.asarray(tod, dtype=float),
                   int(steps_per_bar))


# ------------------------------------------------------------------------- (a) the simulator

def simulate(theta: np.ndarray, n_bars: int, steps_per_bar: int, tod: np.ndarray,
             rng: np.random.Generator, *, attribution: bool = False) -> SimBars:
    """Run W worlds (rows of `theta`, natural units) for `n_bars` bars of `steps_per_bar` steps.

    The state per world is scalar (mid, inventory, depth, excitation, running extremes, EMAs) and
    every participant class is a population with a reaction function of the DELAYED tape, so the
    loop is over steps and every operation is vectorised across worlds: a batch of 256 worlds of
    720 H1 bars at 6 steps costs about a second and a few megabytes.
    """
    th = np.atleast_2d(np.asarray(theta, dtype=float))
    w = th.shape[0]
    g = {name: th[:, i] for i, name in enumerate(PARAM_NAMES)}
    sub = int(steps_per_bar)
    tod_arr = np.asarray(tod, dtype=float)
    if tod_arr.shape[0] != n_bars:
        raise ValueError(f"tod has {tod_arr.shape[0]} entries for {n_bars} bars")

    # latency: one lognormal delay per world, in whole steps, inside the ring
    cv = g["latency_cv"]
    s2 = np.log1p(cv * cv)
    mu = np.log(np.maximum(g["latency_mean"], 1e-3)) - 0.5 * s2
    lag = np.clip(np.rint(np.exp(mu + np.sqrt(s2) * rng.standard_normal(w))), 0, LAG_RING - 1)
    lag = np.where(g["latency_mean"] < 0.5, 0, lag.astype(int))

    base = g["base_intensity"]
    depth_ref = g["mm_depth"] / np.maximum(g["cancel_rate"], 0.02)
    # the Hawkes increment per arrival: branching ratio alpha under an exponential kernel of
    # rate `decay` is alpha*decay per event, so the excitation is stationary for every alpha < 1
    hawkes_inc = g["hawkes_alpha"] * g["hawkes_decay"] / base
    inv_scale = 5.0
    a_fast, a_slow = 1.0 / 12.0, 1.0 / max(24.0 * sub, 24.0)
    a_vol = 1.0 / 20.0
    imp_coef, imp_exp = g["impact_coef"], g["impact_exponent"]
    aversion, cancel_rate = g["mm_inventory_aversion"], g["cancel_rate"]
    liq_k, liq_thr = g["liquidator_strength"], g["liquidation_threshold"]

    logp = np.zeros(w)
    ring = np.zeros((w, LAG_RING))
    ema_fast = np.zeros(w)
    ema_slow = np.zeros(w)
    ewvol = g["fundamental_vol"] * 0.8
    inv = np.zeros(w)
    depth = depth_ref.copy()
    exc = np.zeros(w)
    peak = np.zeros(w)
    trough = np.zeros(w)
    last_d = np.zeros(w)
    # the leveraged pools forced liquidation can sell: finite, depleted by every cascade and
    # rebuilt slowly, which is what stops a cascade in a real book (the longs are gone)
    lev_long = np.ones(w)
    lev_short = np.ones(w)
    widx = np.arange(w)

    o = np.empty((w, n_bars))
    h = np.empty((w, n_bars))
    lo = np.empty((w, n_bars))
    c = np.empty((w, n_bars))
    vol = np.zeros((w, n_bars))
    spr = np.zeros((w, n_bars))
    flw = np.zeros((w, n_bars))
    flk = np.zeros((w, n_bars))
    dep = np.zeros((w, n_bars))
    attr = np.zeros((w, len(CLASSES))) if attribution else None

    for b in range(n_bars):
        phase = 2.0 * math.pi * (tod_arr[b] - g["season_phase"])
        season = 1.0 + g["season_amp"] * np.cos(phase)
        passive = g["passive_amp"] * np.sin(phase)
        sig = g["fundamental_vol"] * season
        sig_e = sig + EPS
        gap_scale = sig * math.sqrt(1.0 / a_slow) + EPS
        bar_hi = np.full(w, -np.inf)
        bar_lo = np.full(w, np.inf)
        o[:, b] = np.exp(logp)
        flips = np.zeros(w)
        # every draw for the bar at once: the call overhead, not the arithmetic, is the cost
        z = rng.standard_normal((sub, w))
        z_retail = rng.standard_normal((sub, w))
        u_jump = rng.random((sub, w))
        z_jump = rng.standard_normal((sub, w))
        u_cancel = rng.random((sub, w))
        for s in range(sub):
            t = b * sub + s
            r_lag = ring[widx, (t - lag) % LAG_RING]
            ema_fast = ema_fast * (1.0 - a_fast) + a_fast * r_lag
            f_trend = g["trend_strength"] * np.tanh(ema_fast / (sig * 0.5 + EPS))
            gap = np.clip((logp - ema_slow) / gap_scale, -3.0, 3.0) / 3.0
            f_revert = -g["revert_strength"] * gap
            f_hedge = g["hedger_gamma"] * np.clip(r_lag / sig_e, -3.0, 3.0) / 3.0
            dd_long = np.clip((peak - logp) / sig_e - liq_thr, 0.0, 3.0) / 3.0
            dd_short = np.clip((logp - trough) / sig_e - liq_thr, 0.0, 3.0) / 3.0
            f_liq = liq_k * (dd_short * lev_short - dd_long * lev_long)
            lev_long = np.minimum(lev_long - 0.2 * dd_long * lev_long + 0.005, 1.0)
            lev_short = np.minimum(lev_short - 0.2 * dd_short * lev_short + 0.005, 1.0)
            n_orders = rng.poisson(base * season * (1.0 + exc))
            act = np.sqrt(np.maximum(n_orders, 1.0) / base)
            f_retail = g["retail_noise"] * z_retail[s]
            net = (f_trend + f_revert + f_hedge + f_liq + f_retail + passive) * act
            exc = exc * (1.0 - g["hawkes_decay"]) + hawkes_inc * n_orders
            thin = np.sqrt(np.clip(depth_ref / np.maximum(depth, EPS), 0.25, 4.0))
            inv_t = np.tanh(inv / inv_scale)
            push = imp_coef * np.sign(net) * np.abs(net) ** imp_exp * thin - aversion * inv_t
            jump = (u_jump[s] < g["jump_rate"]) * z_jump[s] * g["jump_scale"]
            cancel_burst = (u_cancel[s] < cancel_rate).astype(float)
            d = sig * (z[s] + np.clip(push, -10.0, 10.0) + jump) - 0.5 * last_d * cancel_burst
            flips += ((np.sign(d) * np.sign(last_d)) < 0).astype(float)
            logp = np.clip(logp + d, -300.0, 300.0)
            last_d = d
            ring[:, t % LAG_RING] = d
            ema_slow = ema_slow * (1.0 - a_slow) + a_slow * logp
            ewvol = ewvol * (1.0 - a_vol) + a_vol * np.abs(d)
            inv = inv * 0.9 - net
            consumed = np.minimum(depth * 0.5, np.abs(net) * 0.1 * depth_ref)
            depth = np.maximum(depth * (1.0 - cancel_rate) + g["mm_depth"] - consumed, 1.0)
            peak = np.maximum(logp, peak - 0.02 * sig)
            trough = np.minimum(logp, trough + 0.02 * sig)
            spread = (g["mm_spread_base"] * (1.0 + aversion * np.abs(inv_t)) * thin
                      * (0.5 + 0.5 * ewvol / (0.8 * sig_e)))
            p = np.exp(logp)
            bar_hi = np.maximum(bar_hi, p)
            bar_lo = np.minimum(bar_lo, p)
            vol[:, b] += n_orders
            spr[:, b] += spread
            flw[:, b] += net
            dep[:, b] += depth
            if attr is not None:
                for k, part in enumerate((f_trend, f_revert, f_hedge, f_liq, f_retail, passive)):
                    attr[:, k + 1] += (part * act) ** 2
                attr[:, 0] += (aversion * inv_t) ** 2
        c[:, b] = np.exp(logp)
        h[:, b] = np.maximum(bar_hi, np.maximum(o[:, b], c[:, b]))
        lo[:, b] = np.minimum(bar_lo, np.minimum(o[:, b], c[:, b]))
        spr[:, b] /= sub
        dep[:, b] /= sub
        flk[:, b] = flips / max(sub - 1, 1)
    return SimBars(o, h, lo, c, vol, spr, flw, flk, dep, tod_arr, sub, attr)


def participant_mix(bars: SimBars) -> dict[str, float] | None:
    """The share of flow variance each participant class produced (needs attribution=True)."""
    if bars.attribution is None:
        return None
    tot = bars.attribution.sum(axis=0)
    denom = float(tot.sum())
    if denom <= 0:
        return dict.fromkeys(CLASSES, 0.0)
    return {k: round(float(v / denom), 4) for k, v in zip(CLASSES, tot, strict=True)}


# ------------------------------------------------------------------------- (b) the summaries

STATS: tuple[tuple[str, str], ...] = (
    ("ret_vol", "returns"), ("ret_skew", "returns"), ("ret_ac1", "returns"),
    ("ret_ac2", "returns"), ("ret_ac5", "returns"), ("ret_ac10", "returns"),
    ("ret_kurt", "tails"), ("tail_ratio", "tails"), ("jump_freq", "tails"),
    ("absret_ac1", "vol_clustering"), ("absret_ac5", "vol_clustering"),
    ("absret_ac10", "vol_clustering"),
    ("range_ratio", "range"), ("range_cv", "range"), ("range_ac1", "range"),
    ("vol_cv", "volume"), ("vol_ac1", "volume"), ("vol_ac5", "volume"),
    ("vol_absret_corr", "volume"),
    ("depth_disp", "depth"), ("depth_ac1", "depth"), ("range_vol_elasticity", "depth"),
    ("spread_log_mean", "spread"), ("spread_cv", "spread"), ("spread_ac1", "spread"),
    ("spread_absret_corr", "spread"),
    ("flow_ret_corr", "impact"), ("flow_ac1", "impact"), ("flow_lag_ret_corr", "impact"),
    ("absflow_absret_corr", "impact"),
    ("flicker", "cancellation"),
    ("season_absret_amp", "seasonality"), ("season_volume_amp", "seasonality"),
    ("resp_after_up", "state_response"), ("resp_after_down", "state_response"),
    ("vol_after_shock", "state_response"), ("resp_after_high_volume", "state_response"),
)
STAT_NAMES: tuple[str, ...] = tuple(s for s, _ in STATS)
STAT_GROUPS: tuple[str, ...] = tuple(gname for _, gname in STATS)
GROUPS: tuple[str, ...] = tuple(dict.fromkeys(STAT_GROUPS))
#: The groups a returns-only world can pass without being realistic.
RETURNS_GROUPS: frozenset[str] = frozenset({"returns", "tails", "vol_clustering"})


def _acf(x: np.ndarray, k: int) -> np.ndarray:
    if x.shape[1] <= k + 2:
        return np.full(x.shape[0], np.nan)
    xm = x - np.nanmean(x, axis=1, keepdims=True)
    num = np.nanmean(xm[:, :-k] * xm[:, k:], axis=1)
    den = np.nanmean(xm * xm, axis=1)
    with np.errstate(invalid="ignore", divide="ignore"):
        return np.where(den > 0, num / den, np.nan)


def _corr(a: np.ndarray, b: np.ndarray) -> np.ndarray:
    am = a - np.nanmean(a, axis=1, keepdims=True)
    bm = b - np.nanmean(b, axis=1, keepdims=True)
    num = np.nanmean(am * bm, axis=1)
    den = np.sqrt(np.nanmean(am * am, axis=1) * np.nanmean(bm * bm, axis=1))
    with np.errstate(invalid="ignore", divide="ignore"):
        return np.where(den > 0, num / den, np.nan)


def _cv(x: np.ndarray) -> np.ndarray:
    m = np.nanmean(x, axis=1)
    with np.errstate(invalid="ignore", divide="ignore"):
        return np.where(np.abs(m) > 0, np.nanstd(x, axis=1) / np.abs(m), np.nan)


def _masked_mean(x: np.ndarray, mask: np.ndarray, min_n: int = 5) -> np.ndarray:
    n = mask.sum(axis=1)
    with np.errstate(invalid="ignore", divide="ignore"):
        m = np.where(mask, x, 0.0).sum(axis=1) / np.maximum(n, 1)
    return np.where(n >= min_n, m, np.nan)


def _season_amp(x: np.ndarray, tod: np.ndarray, bins: int = 6, min_n: int = 8) -> np.ndarray:
    b = np.minimum((np.asarray(tod) * bins).astype(int), bins - 1)
    means = []
    for k in range(bins):
        mask = np.broadcast_to(b == k, x.shape)
        means.append(_masked_mean(x, mask, min_n))
    m = np.stack(means, axis=1)
    fin = np.isfinite(m)
    n_ok = fin.sum(axis=1)
    hi = np.max(np.where(fin, m, -np.inf), axis=1)
    lo = np.min(np.where(fin, m, np.inf), axis=1)
    mean = np.where(fin, m, 0.0).sum(axis=1) / np.maximum(n_ok, 1)
    with np.errstate(invalid="ignore", divide="ignore"):
        amp = (hi - lo) / mean
    return np.where((n_ok >= 3) & (mean > 0), amp, np.nan)


def _moments(r: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """(skew, excess kurtosis) per row without scipy's precision warnings on a flat row."""
    d = r - r.mean(axis=1, keepdims=True)
    m2 = np.mean(d * d, axis=1)
    m3 = np.mean(d * d * d, axis=1)
    m4 = np.mean(d * d * d * d, axis=1)
    with np.errstate(invalid="ignore", divide="ignore"):
        skew = np.where(m2 > 0, m3 / np.power(m2, 1.5), np.nan)
        kurt = np.where(m2 > 0, m4 / (m2 * m2) - 3.0, np.nan)
    return skew, kurt


def summarise(bars: SimBars) -> np.ndarray:
    """The summary statistics of every world in `bars`: W x len(STATS), NaN = unmeasured."""
    c = np.maximum(bars.close, EPS)
    w, n = c.shape
    out = np.full((w, len(STATS)), np.nan)
    if n < 30:
        return out
    r = np.diff(np.log(c), axis=1)
    sig = np.std(r, axis=1) + EPS
    absr = np.abs(r)
    col = {name: i for i, name in enumerate(STAT_NAMES)}
    with np.errstate(invalid="ignore", divide="ignore", over="ignore"):
        out[:, col["ret_vol"]] = sig
        out[:, col["ret_skew"]], out[:, col["ret_kurt"]] = _moments(r)
        for k in (1, 2, 5, 10):
            out[:, col[f"ret_ac{k}"]] = _acf(r, k)
        q = np.quantile(absr, [0.5, 0.99], axis=1)
        out[:, col["tail_ratio"]] = np.where(q[0] > 0, q[1] / q[0], np.nan)
        mad = np.median(absr, axis=1, keepdims=True) * 1.4826 + EPS
        out[:, col["jump_freq"]] = np.mean(absr > 4.0 * mad, axis=1)
        for k in (1, 5, 10):
            out[:, col[f"absret_ac{k}"]] = _acf(absr, k)
        rng_rel = (bars.high - bars.low) / c
        out[:, col["range_ratio"]] = np.nanmean(rng_rel, axis=1) / sig
        out[:, col["range_cv"]] = _cv(rng_rel)
        out[:, col["range_ac1"]] = _acf(rng_rel, 1)
        lv = np.log1p(np.maximum(bars.volume, 0.0))
        out[:, col["vol_cv"]] = _cv(np.maximum(bars.volume, 0.0))
        out[:, col["vol_ac1"]] = _acf(lv, 1)
        out[:, col["vol_ac5"]] = _acf(lv, 5)
        out[:, col["vol_absret_corr"]] = _corr(lv[:, 1:], absr)
        dp = lv - np.log(rng_rel + 1e-9)
        out[:, col["depth_disp"]] = np.nanstd(dp, axis=1)
        out[:, col["depth_ac1"]] = _acf(dp, 1)
        lr = np.log(rng_rel + 1e-9)
        lvm = lv - np.nanmean(lv, axis=1, keepdims=True)
        var_lv = np.nanmean(lvm * lvm, axis=1)
        cov = np.nanmean(lvm * (lr - np.nanmean(lr, axis=1, keepdims=True)), axis=1)
        out[:, col["range_vol_elasticity"]] = np.where(var_lv > 0, cov / var_lv, np.nan)
        s = bars.spread
        if np.isfinite(s).any():
            out[:, col["spread_log_mean"]] = np.nanmean(np.log(np.maximum(s, EPS)), axis=1)
            out[:, col["spread_cv"]] = _cv(s)
            out[:, col["spread_ac1"]] = _acf(s, 1)
            out[:, col["spread_absret_corr"]] = _corr(s[:, 1:], absr)
        f = bars.flow
        if np.isfinite(f).any():
            fs = (f - np.nanmean(f, axis=1, keepdims=True)) / (np.nanstd(f, axis=1, keepdims=True)
                                                               + EPS)
            out[:, col["flow_ret_corr"]] = _corr(fs[:, 1:], r)
            out[:, col["flow_ac1"]] = _acf(fs, 1)
            out[:, col["flow_lag_ret_corr"]] = _corr(fs[:, 1:-1], r[:, 1:])
            out[:, col["absflow_absret_corr"]] = _corr(np.abs(fs[:, 1:]), absr)
        if np.isfinite(bars.flicker).any():
            out[:, col["flicker"]] = np.nanmean(bars.flicker, axis=1)
        tod = np.asarray(bars.tod, dtype=float)
        if tod.shape[0] == n and np.isfinite(tod).all():
            out[:, col["season_absret_amp"]] = _season_amp(absr / sig[:, None], tod[1:])
            out[:, col["season_volume_amp"]] = _season_amp(np.maximum(bars.volume, 0.0), tod)
        q90 = np.quantile(r, 0.9, axis=1, keepdims=True)
        q10 = np.quantile(r, 0.1, axis=1, keepdims=True)
        nxt = r[:, 1:] / sig[:, None]
        cur = r[:, :-1]
        out[:, col["resp_after_up"]] = _masked_mean(nxt, cur > q90)
        out[:, col["resp_after_down"]] = _masked_mean(nxt, cur < q10)
        qa = np.quantile(absr, 0.9, axis=1, keepdims=True)
        out[:, col["vol_after_shock"]] = _masked_mean(np.abs(nxt), np.abs(cur) > qa) / (
            np.mean(absr, axis=1) / sig)
        qv = np.quantile(bars.volume, 0.9, axis=1, keepdims=True)
        hv = bars.volume[:, 1:-1] > qv
        out[:, col["resp_after_high_volume"]] = _masked_mean(np.sign(cur) * nxt, hv)
    return out


# ------------------------------------------------------------------------- (c) the inference

@dataclass(frozen=True)
class Prior:
    """Uniform on the unit cube of every FREE parameter (log-uniform where the spec says so);
    `fixed` pins a parameter to one natural value, which is how a study narrows the world."""
    fixed: Mapping[str, float] = field(default_factory=dict)

    @property
    def free(self) -> tuple[str, ...]:
        return tuple(n for n in PARAM_NAMES if n not in self.fixed)

    def sample(self, n: int, rng: np.random.Generator) -> np.ndarray:
        """N x D unit-cube coordinates, fixed dims pinned."""
        u = rng.random((n, len(PARAMS)))
        return self.pin(u)

    def pin(self, u: np.ndarray) -> np.ndarray:
        u = np.clip(np.asarray(u, dtype=float), 0.0, 1.0)
        if self.fixed:
            fixed_nat = np.array([[float(self.fixed.get(p.name, p.lo)) for p in PARAMS]])
            fixed_u = _natural_to_unit(fixed_nat)[0]
            for name in self.fixed:
                u[:, _IDX[name]] = fixed_u[_IDX[name]]
        return u


@dataclass
class Posterior:
    """A weighted particle posterior over worlds, in natural units, with what produced it."""
    particles: np.ndarray
    weights: np.ndarray
    observed: np.ndarray
    measurable: np.ndarray
    projection: np.ndarray
    stat_mean: np.ndarray
    stat_scale: np.ndarray
    proj_scale: np.ndarray
    eps_history: list[float]
    acceptance: list[float]
    n_simulations: int
    free: tuple[str, ...]
    n_bars: int
    steps_per_bar: int

    @property
    def n(self) -> int:
        return int(self.particles.shape[0])

    def mean(self) -> dict[str, float]:
        m = self.weights @ self.particles
        return {n: float(v) for n, v in zip(PARAM_NAMES, m, strict=True)}

    def credible_interval(self, name: str, level: float = 0.9) -> tuple[float, float]:
        x = self.particles[:, _IDX[name]]
        a = (1.0 - level) / 2.0
        lo, hi = _wquantile(x, self.weights, np.array([a, 1.0 - a]))
        return float(lo), float(hi)

    def contains(self, name: str, value: float, level: float = 0.9) -> bool:
        lo, hi = self.credible_interval(name, level)
        return bool(lo <= value <= hi)

    def to_dict(self) -> dict[str, Any]:
        return {
            "param_names": list(PARAM_NAMES), "free": list(self.free),
            "particles": np.round(self.particles, 8).tolist(),
            "weights": np.round(self.weights, 8).tolist(),
            "observed": [None if not np.isfinite(v) else float(v) for v in self.observed],
            "stat_names": list(STAT_NAMES), "measurable": self.measurable.astype(int).tolist(),
            "projection": np.round(self.projection, 8).tolist(),
            "stat_mean": self.stat_mean.tolist(), "stat_scale": self.stat_scale.tolist(),
            "proj_scale": self.proj_scale.tolist(),
            "eps_history": self.eps_history, "acceptance": self.acceptance,
            "n_simulations": self.n_simulations, "n_bars": self.n_bars,
            "steps_per_bar": self.steps_per_bar,
            "mean": self.mean(),
            "ci90": {n: list(self.credible_interval(n)) for n in self.free},
        }

    @classmethod
    def from_particles(cls, theta: np.ndarray, *, n_bars: int, steps_per_bar: int,
                       weights: np.ndarray | None = None,
                       observed: np.ndarray | None = None) -> Posterior:
        """A posterior stated directly as worlds (a study's hypothesis, a planted world, a
        stress set): no projection, uniform weights unless given."""
        p = np.atleast_2d(np.asarray(theta, dtype=float))
        w = np.full(p.shape[0], 1.0 / p.shape[0]) if weights is None else np.asarray(weights)
        obs = np.full(len(STATS), np.nan) if observed is None else np.asarray(observed, float)
        n_meas = int(np.isfinite(obs).sum())
        return cls(p, w / w.sum(), obs, np.isfinite(obs), np.zeros((n_meas, 0)),
                   np.zeros(n_meas), np.ones(n_meas), np.ones(0), [], [], 0, PARAM_NAMES,
                   int(n_bars), int(steps_per_bar))

    @classmethod
    def from_dict(cls, d: Mapping[str, Any]) -> Posterior:
        obs = np.array([np.nan if v is None else float(v) for v in d["observed"]])
        arr = np.asarray
        return cls(arr(d["particles"], dtype=float), arr(d["weights"], dtype=float),
                   obs, arr(d["measurable"], dtype=bool), arr(d["projection"], dtype=float),
                   arr(d["stat_mean"], dtype=float), arr(d["stat_scale"], dtype=float),
                   arr(d["proj_scale"], dtype=float), list(d.get("eps_history") or []),
                   list(d.get("acceptance") or []), int(d.get("n_simulations") or 0),
                   tuple(d.get("free") or PARAM_NAMES), int(d.get("n_bars") or 0),
                   int(d.get("steps_per_bar") or 1))


def _wquantile(x: np.ndarray, w: np.ndarray, qs: np.ndarray) -> np.ndarray:
    order = np.argsort(x)
    xs, ws = x[order], w[order]
    cw = np.cumsum(ws)
    cw = cw / cw[-1]
    out: np.ndarray = np.interp(qs, cw - ws / 2.0, xs)
    return out


def _fit_projection(u: np.ndarray, s: np.ndarray, free_idx: np.ndarray, ridge: float = 1.0
                    ) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    """The learned summary distance: ridge-regress the free unit-cube coordinates on the
    standardised summaries (Fearnhead & Prangle's semi-automatic ABC). Returns (W, mean, scale,
    per-projection scale); a projected summary is the pilot's estimate of the posterior mean."""
    mean = np.nanmean(s, axis=0)
    scale = np.nanstd(s, axis=0) + EPS
    z = (s - mean) / scale
    z = np.where(np.isfinite(z), z, 0.0)
    y = u[:, free_idx]
    gram = z.T @ z + ridge * np.eye(z.shape[1])
    w_mat = np.linalg.solve(gram, z.T @ (y - y.mean(axis=0)))
    proj = z @ w_mat
    pscale = np.std(proj, axis=0) + 1e-6
    return w_mat, mean, scale, pscale


def _project(s: np.ndarray, w_mat: np.ndarray, mean: np.ndarray, scale: np.ndarray) -> np.ndarray:
    z = (s - mean) / scale
    z = np.where(np.isfinite(z), z, 0.0)
    out: np.ndarray = z @ w_mat
    return out


def infer(observed: np.ndarray, prior: Prior, *, n_bars: int, steps_per_bar: int,
          tod: np.ndarray, rng: np.random.Generator, n_particles: int = 256, n_rounds: int = 4,
          accept_quantile: float = 0.3, eps_quantile: float = 0.5, max_batches: int = 6,
          deadline: Callable[[], bool] | None = None) -> Posterior:
    """ABC-SMC over the latent worlds against one observed summary vector.

    Round 0 is the pilot: `n_particles` prior draws, simulated and summarised; the projection is
    learned from them and the closest `accept_quantile` share seeds the population. Every later
    round proposes from the weighted population through a Gaussian kernel (twice the weighted
    covariance, reflected into the cube), simulates in batches, keeps proposals under the
    round's epsilon (the `eps_quantile` of the previous population's distances) and importance-
    weights them against the kernel mixture. A `deadline` callable that returns True stops the
    schedule at the last completed round -- a partial posterior is a WIDER posterior, never a
    wrong one.
    """
    obs = np.asarray(observed, dtype=float).reshape(-1)
    if obs.shape[0] != len(STATS):
        raise ValueError(f"observed has {obs.shape[0]} statistics; {len(STATS)} expected")
    measurable = np.isfinite(obs)
    if measurable.sum() < 4:
        raise ValueError("fewer than four measurable statistics; nothing to calibrate on")
    free_idx = np.array([_IDX[n] for n in prior.free], dtype=int)
    n_sims = 0

    def run(u: np.ndarray) -> np.ndarray:
        nonlocal n_sims
        n_sims += u.shape[0]
        return summarise(simulate(_unit_to_natural(u), n_bars, steps_per_bar, tod, rng))

    # the pilot is a scrambled Sobol design over the free dimensions: space-filling where a
    # uniform draw of a few hundred points in twenty dimensions leaves holes
    m = max(1, math.ceil(math.log2(max(n_particles, 2))))
    sob = qmc.Sobol(d=len(PARAMS), scramble=True, seed=rng).random_base2(m)[:n_particles]
    u0 = prior.pin(sob)
    s0 = run(u0)[:, measurable]
    w_mat, mean, scale, pscale = _fit_projection(u0, s0, free_idx)
    p_obs = _project(obs[measurable].reshape(1, -1), w_mat, mean, scale)[0]

    def dist(s: np.ndarray) -> np.ndarray:
        p = _project(s, w_mat, mean, scale)
        d2 = ((p - p_obs) / pscale) ** 2
        out: np.ndarray = np.sqrt(np.mean(d2, axis=1))
        return out

    d0 = dist(s0)
    keep = np.isfinite(d0)
    order = np.argsort(np.where(keep, d0, np.inf))
    n_keep = max(8, round(accept_quantile * n_particles))
    idx = order[:n_keep]
    pop_u, pop_d = u0[idx], d0[idx]
    pop_w = np.full(len(idx), 1.0 / len(idx))
    eps_hist = [float(pop_d.max())]
    acc_hist = [float(len(idx) / n_particles)]

    for _ in range(1, n_rounds + 1):
        if deadline is not None and deadline():
            break
        eps = float(np.quantile(pop_d, eps_quantile))
        cov = np.cov(pop_u[:, free_idx].T, aweights=pop_w) * 2.0
        cov = np.atleast_2d(cov) + 1e-5 * np.eye(len(free_idx))
        chol = np.linalg.cholesky(cov)
        new_u: list[np.ndarray] = []
        new_d: list[np.ndarray] = []
        proposed = 0
        for _batch in range(max_batches):
            if deadline is not None and deadline():
                break
            parents = rng.choice(len(pop_w), size=n_particles, p=pop_w)
            step = rng.standard_normal((n_particles, len(free_idx))) @ chol.T
            cand = pop_u[parents].copy()
            cand[:, free_idx] = _reflect(cand[:, free_idx] + step)
            cand = prior.pin(cand)
            s = run(cand)[:, measurable]
            d = dist(s)
            ok = np.isfinite(d) & (d <= eps)
            proposed += n_particles
            if ok.any():
                new_u.append(cand[ok])
                new_d.append(d[ok])
            if sum(len(x) for x in new_u) >= n_particles:
                break
        if not new_u or sum(len(x) for x in new_u) < max(24, n_particles // 8):
            # too few survivors to be a population: keep the previous round rather than a
            # handful of particles that would make every credible interval a lie
            break
        cu = np.concatenate(new_u)[:n_particles]
        cd = np.concatenate(new_d)[:n_particles]
        # importance weights against the kernel mixture (uniform prior => 1 / mixture density)
        diff = cu[:, None, free_idx] - pop_u[None, :, free_idx]
        sol = np.linalg.solve(chol, diff.reshape(-1, len(free_idx)).T).T
        logk = -0.5 * np.sum(sol * sol, axis=1).reshape(cu.shape[0], pop_u.shape[0])
        mix = (pop_w[None, :] * np.exp(logk - logk.max(axis=1, keepdims=True))).sum(axis=1)
        wts = 1.0 / np.maximum(mix * np.exp(logk.max(axis=1)), 1e-300)
        wts = wts / wts.sum()
        pop_u, pop_d, pop_w = cu, cd, wts
        eps_hist.append(eps)
        acc_hist.append(float(cu.shape[0] / max(proposed, 1)))
        if acc_hist[-1] < 0.02:
            break

    return Posterior(_unit_to_natural(pop_u), pop_w, obs, measurable, w_mat, mean, scale, pscale,
                     eps_hist, acc_hist, n_sims, prior.free, int(n_bars), int(steps_per_bar))


def _reflect(u: np.ndarray) -> np.ndarray:
    """Fold a perturbed unit-cube coordinate back inside [0, 1]."""
    v = np.mod(u, 2.0)
    out: np.ndarray = np.where(v > 1.0, 2.0 - v, v)
    return out


def sample_worlds(posterior: Posterior, n: int, rng: np.random.Generator) -> np.ndarray:
    """n worlds (natural units) drawn from the weighted particles."""
    idx = rng.choice(posterior.n, size=n, p=posterior.weights / posterior.weights.sum())
    out: np.ndarray = posterior.particles[idx]
    return out


@dataclass(frozen=True)
class PPCResult:
    """Posterior predictive checks: per-statistic robust discrepancies, per-group verdicts and
    the one verdict the organ records. `realistic` is True only when EVERY measurable group
    passes; a group the tape could not measure is UNMEASURED and keeps the verdict
    REALISTIC_PARTIAL, never REALISTIC."""
    verdict: str
    realistic: bool
    z_scores: dict[str, float | None]
    groups: dict[str, str]
    failing: list[str]
    unmeasured_groups: list[str]
    n_draws: int

    def to_dict(self) -> dict[str, Any]:
        return {"verdict": self.verdict, "realistic": self.realistic, "z_scores": self.z_scores,
                "groups": self.groups, "failing_statistics": self.failing,
                "unmeasured_groups": self.unmeasured_groups, "n_draws": self.n_draws}


def ppc(posterior: Posterior, observed: np.ndarray, *, tod: np.ndarray,
        rng: np.random.Generator, n_draws: int = 64, z_crit: float = PPC_Z) -> PPCResult:
    """Simulate `n_draws` posterior worlds and ask, statistic by statistic, whether the observed
    value sits inside the posterior predictive distribution.

    The discrepancy is ROBUST (median and MAD of the predictive draws) and the cut is `z_crit`
    rather than a per-statistic tail count: thirty-seven statistics at a 5% tail each would
    fail the TRUE world five times out of six, and a check that cannot pass its own generator
    is not a check. At 3.5 robust sigmas the true world passes all groups ~98% of the time and
    a twenty-fold spread or a different cancellation regime fails by tens of sigmas.
    """
    obs = np.asarray(observed, dtype=float).reshape(-1)
    theta = sample_worlds(posterior, n_draws, rng)
    s = summarise(simulate(theta, posterior.n_bars, posterior.steps_per_bar, tod, rng))
    zs: dict[str, float | None] = {}
    fails: list[str] = []
    group_fail: dict[str, list[str]] = {}
    group_seen: dict[str, int] = dict.fromkeys(GROUPS, 0)
    for k, (name, grp) in enumerate(STATS):
        if not np.isfinite(obs[k]):
            zs[name] = None
            continue
        sims = s[:, k]
        sims = sims[np.isfinite(sims)]
        if sims.size < max(8, n_draws // 4):
            zs[name] = None
            continue
        group_seen[grp] += 1
        med = float(np.median(sims))
        # the floor is the statistic's own resolution: a jump COUNT over a short window moves in
        # steps of one event, and one event's difference is not a different world
        gaps = np.diff(np.unique(sims))
        resolution = float(gaps.min()) if gaps.size else 0.0
        scale = max(1.4826 * float(np.median(np.abs(sims - med))), 0.5 * float(np.std(sims)),
                    1e-6 + 0.01 * abs(med), resolution)
        z = (obs[k] - med) / scale
        zs[name] = round(float(z), 3)
        if abs(z) > z_crit:
            fails.append(name)
            group_fail.setdefault(grp, []).append(name)
    groups: dict[str, str] = {}
    for grp in GROUPS:
        if group_seen[grp] == 0:
            groups[grp] = "UNMEASURED"
        elif grp in group_fail:
            groups[grp] = "FAIL:" + ",".join(group_fail[grp])
        else:
            groups[grp] = "PASS"
    unmeasured = [g for g in GROUPS if groups[g] == "UNMEASURED"]
    measured_fail = [g for g in GROUPS if groups[g].startswith("FAIL")]
    if len(unmeasured) == len(GROUPS):
        verdict = "UNMEASURED"
    elif any(g in RETURNS_GROUPS for g in measured_fail):
        verdict = "FAIL_RETURNS:" + fails[0]
    elif measured_fail:
        verdict = "RETURNS_ONLY:" + fails[0]
    elif unmeasured:
        verdict = "REALISTIC_PARTIAL"
    else:
        verdict = "REALISTIC"
    realistic = verdict.startswith("REALISTIC")
    return PPCResult(verdict, realistic, zs, groups, fails, unmeasured, int(n_draws))


# ------------------------------------------------------------------------- strategies

StrategyRule = Callable[[WorldBars], "np.ndarray | float"]


@dataclass(frozen=True)
class Robustness:
    """The distribution of a strategy's outcome across posterior worlds. `p_positive` is the
    posterior-weighted share of worlds in which the outcome is positive -- the number the
    registry's `posterior_world_robustness` carries."""
    outcomes: np.ndarray
    weights: np.ndarray
    p_positive: float
    mean: float
    quantiles: dict[str, float]
    cvar_10: float
    verdict: str
    n_worlds: int

    def to_dict(self) -> dict[str, Any]:
        return {"p_positive": self.p_positive, "mean": self.mean, "quantiles": self.quantiles,
                "cvar_10": self.cvar_10, "verdict": self.verdict, "n_worlds": self.n_worlds}


def _position_outcome(pos: np.ndarray, world: WorldBars, cost_mult: float) -> float:
    """Net log-return of holding `pos[t-1]` over bar t, paying half the spread per unit traded."""
    p = np.clip(np.asarray(pos, dtype=float), -1.0, 1.0)
    r = world.returns
    gross = float(np.sum(p[:-1] * r[1:]))
    spread = np.where(np.isfinite(world.spread), world.spread, 0.0)
    turn = np.abs(np.diff(np.concatenate([[0.0], p])))
    cost = float(np.sum(turn * spread * 0.5 * cost_mult))
    return gross - cost


def robustness(strategy_rule: StrategyRule, posterior: Posterior, n_worlds: int, *,
               tod: np.ndarray, rng: np.random.Generator, cost_mult: float = 1.0,
               deadline: Callable[[], bool] | None = None) -> Robustness:
    """Run `strategy_rule` in `n_worlds` posterior worlds. A rule returns either a position array
    in [-1, 1] per bar (costed at half the world's spread per unit traded) or, when it has its own
    replay, the outcome itself as a float. Worlds where the rule raises or returns NaN are
    dropped and counted; an empty outcome set is UNMEASURED."""
    theta = sample_worlds(posterior, n_worlds, rng)
    bars = simulate(theta, posterior.n_bars, posterior.steps_per_bar, tod, rng)
    outs: list[float] = []
    for i in range(bars.n_worlds):
        if deadline is not None and deadline():
            break
        world = bars.world(i)
        try:
            res = strategy_rule(world)
        except Exception:
            continue
        if isinstance(res, np.ndarray):
            val = _position_outcome(res, world, cost_mult)
        else:
            val = float(res)
        if math.isfinite(val):
            outs.append(val)
    if not outs:
        return Robustness(np.zeros(0), np.zeros(0), float("nan"), float("nan"), {}, float("nan"),
                          "UNMEASURED", 0)
    x = np.asarray(outs)
    w = np.full(x.size, 1.0 / x.size)
    qs = _wquantile(x, w, np.array([0.05, 0.25, 0.5, 0.75, 0.95]))
    p_pos = float(np.mean(x > 0))
    tail = np.sort(x)[: max(1, math.ceil(0.1 * x.size))]
    if p_pos >= 0.75 and qs[1] > 0:
        verdict = "ROBUST"
    elif p_pos < 0.5:
        verdict = "FRAGILE"
    else:
        verdict = "MIXED"
    return Robustness(x, w, round(p_pos, 4), float(x.mean()),
                      {k: float(v) for k, v in zip(("q05", "q25", "q50", "q75", "q95"), qs,
                                                   strict=True)},
                      float(tail.mean()), verdict, int(x.size))


def mean_reversion_rule(lookback: int = 1) -> StrategyRule:
    """Fade the last `lookback` bars' move: position = -sign(sum of recent returns)."""
    def rule(world: WorldBars) -> np.ndarray:
        r = world.returns
        recent = np.convolve(r, np.ones(lookback), mode="full")[: r.size]
        pos = -np.sign(recent)
        pos[:lookback] = 0.0
        return pos
    return rule


def momentum_rule(lookback: int = 5) -> StrategyRule:
    """Follow the last `lookback` bars' move."""
    def rule(world: WorldBars) -> np.ndarray:
        r = world.returns
        recent = np.convolve(r, np.ones(lookback), mode="full")[: r.size]
        pos = np.sign(recent)
        pos[:lookback] = 0.0
        return pos
    return rule


def breakout_rule(lookback: int = 20) -> StrategyRule:
    """Long above the prior `lookback`-bar high, short below the prior low, flat between."""
    def rule(world: WorldBars) -> np.ndarray:
        n = world.close.size
        pos = np.zeros(n)
        for t in range(lookback, n):
            hi = world.high[t - lookback:t].max()
            lo = world.low[t - lookback:t].min()
            pos[t] = 1.0 if world.close[t] > hi else (-1.0 if world.close[t] < lo else pos[t - 1])
        return pos
    return rule


# ------------------------------------------------------------------------- (d) mechanisms

@dataclass(frozen=True)
class Mechanism:
    """A hypothesised mechanism as a signed trigger: `trigger(world)` returns, per bar, the
    direction (+1/-1) the mechanism predicts for the next `horizon` bars, or 0. Its effect in a
    world is the mean signed forward return over triggered bars, in vol units."""
    name: str
    trigger: Callable[[WorldBars], np.ndarray]
    horizon: int = 1
    min_events: int = MIN_EVENTS


@dataclass(frozen=True)
class Plausibility:
    verdict: str
    p_exists: float
    effects: np.ndarray
    n_measured: int
    n_worlds: int
    mean_effect: float

    def to_dict(self) -> dict[str, Any]:
        return {"verdict": self.verdict, "p_exists": self.p_exists, "n_measured": self.n_measured,
                "n_worlds": self.n_worlds, "mean_effect": self.mean_effect}


def mechanism_plausibility(mechanism: Mechanism, posterior: Posterior, n_worlds: int, *,
                           tod: np.ndarray, rng: np.random.Generator,
                           deadline: Callable[[], bool] | None = None) -> Plausibility:
    """Does the mechanism exist inside the posterior worlds? In each world the effect is measured
    on the triggered bars; it EXISTS there when the signed forward return is positive with a
    one-sided t above 1.64 on at least `min_events` events. CAN_EXIST when the share of worlds
    where it exists is at least a half, MARGINAL above a fifth, CANNOT_EXIST below, UNMEASURED
    when fewer than half the worlds trigger it often enough to say."""
    theta = sample_worlds(posterior, n_worlds, rng)
    bars = simulate(theta, posterior.n_bars, posterior.steps_per_bar, tod, rng)
    h = max(1, int(mechanism.horizon))
    effects: list[float] = []
    exists: list[bool] = []
    for i in range(bars.n_worlds):
        if deadline is not None and deadline():
            break
        world = bars.world(i)
        try:
            trig = np.asarray(mechanism.trigger(world), dtype=float)
        except Exception:
            continue
        lc = np.log(np.maximum(world.close, EPS))
        sig = float(np.std(np.diff(lc))) + EPS
        fwd = (lc[h:] - lc[:-h]) / (sig * math.sqrt(h))
        t = trig[:-h]
        hit = t != 0
        if hit.sum() < mechanism.min_events:
            continue
        e = t[hit] * fwd[hit]
        m = float(e.mean())
        se = float(e.std(ddof=1)) / math.sqrt(e.size) if e.size > 1 else float("inf")
        effects.append(m)
        exists.append(m > 0 and se > 0 and m / se > 1.64)
    n_meas = len(effects)
    if n_meas < max(1, n_worlds // 2):
        return Plausibility("UNMEASURED", float("nan"), np.asarray(effects), n_meas, n_worlds,
                            float(np.mean(effects)) if effects else float("nan"))
    p = float(np.mean(exists))
    verdict = "CAN_EXIST" if p >= 0.5 else ("MARGINAL" if p >= 0.2 else "CANNOT_EXIST")
    return Plausibility(verdict, round(p, 4), np.asarray(effects), n_meas, n_worlds,
                        float(np.mean(effects)))


def _scaled_move(r: np.ndarray, lookback: int) -> np.ndarray:
    """The trailing `lookback`-bar move in vol units, per bar."""
    sig = float(np.std(r)) + EPS
    return np.convolve(r, np.ones(lookback), mode="full")[: r.size] / (sig * math.sqrt(lookback))


def mean_reversion_mechanism(lookback: int = 3, horizon: int = 3, threshold_sigma: float = 1.5
                             ) -> Mechanism:
    """After a move of more than `threshold_sigma` over `lookback` bars, price comes back."""
    def trigger(world: WorldBars) -> np.ndarray:
        move = _scaled_move(world.returns, lookback)
        out = np.where(move > threshold_sigma, -1.0, np.where(move < -threshold_sigma, 1.0, 0.0))
        out[:lookback] = 0.0
        return out
    return Mechanism(f"mean_reversion_{lookback}_{horizon}", trigger, horizon)


def momentum_mechanism(lookback: int = 12, horizon: int = 6, threshold_sigma: float = 1.0
                       ) -> Mechanism:
    """After a move of more than `threshold_sigma` over `lookback` bars, it continues."""
    def trigger(world: WorldBars) -> np.ndarray:
        move = _scaled_move(world.returns, lookback)
        out = np.where(move > threshold_sigma, 1.0, np.where(move < -threshold_sigma, -1.0, 0.0))
        out[:lookback] = 0.0
        return out
    return Mechanism(f"momentum_{lookback}_{horizon}", trigger, horizon)


def liquidation_cascade_mechanism(drawdown_sigma: float = 3.0, window: int = 24, horizon: int = 3
                                  ) -> Mechanism:
    """A drawdown of `drawdown_sigma` from the `window`-bar high forces more selling: continuation
    DOWN over the next `horizon` bars (and the mirror for a run-up against shorts)."""
    def trigger(world: WorldBars) -> np.ndarray:
        lc = np.log(np.maximum(world.close, EPS))
        sig = float(np.std(np.diff(lc))) + EPS
        out = np.zeros(lc.size)
        for t in range(window, lc.size):
            seg = lc[t - window:t + 1]
            if (seg.max() - lc[t]) / sig > drawdown_sigma:
                out[t] = -1.0
            elif (lc[t] - seg.min()) / sig > drawdown_sigma:
                out[t] = 1.0
        return out
    return Mechanism(f"liquidation_cascade_{drawdown_sigma:g}", trigger, horizon)


# ------------------------------------------------------------------------- memory bounds

def capacity(free_bytes: int | None, n_bars: int, steps_per_bar: int, *, share: float = 0.05,
             floor: int = 64, ceiling: int = 512) -> int:
    """Worlds per simulation batch, DERIVED from measured free memory: `share` of it over the
    bytes one world costs (ten bar fields plus the per-step transients), floored so an unreadable
    counter changes nothing and capped so a large box does not spend its hour on one twin."""
    per_world = n_bars * 10 * 8 + steps_per_bar * 64 + 4096
    if free_bytes is None or free_bytes <= 0:
        return floor
    return int(max(floor, min(ceiling, free_bytes * share // per_world)))
