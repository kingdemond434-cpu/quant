"""THE STATE-ENGINE ENSEMBLE: six causal volatility-state engines, fused by prequential score.

WHAT IT IS FOR (principal, 2026-10-13, thread "State-engine ensemble for allocator"). The
allocator conditions its worlds on ONE regime reading -- a 3-state Gaussian HMM on gold's daily
closes (`pf_allocator.regime_state`). One model is one opinion. This module builds the others the
literature names -- an explicit-duration HSMM, GJR-GARCH, stochastic volatility by Kalman QML and
by a particle filter, and a Hawkes process on high-volatility days -- forecasts the SAME target
with every one of them, and fuses them by how well each has forecast it so far. Each one is a
different answer to "what state is this market in, and how sure are we", and where they disagree
is itself a state (`split`).

THE ONE TARGET EVERY ENGINE FORECASTS. Tomorrow's volatility TIER: |r_{t+1}| against the terciles
of the trailing year of |r| known at the close of t (low / mid / high). It is observable, it is
the axis the incumbent HMM's labels sort on (`engine._characterise` ranks states by vol), and a
shared target is what makes the engines comparable at all: a log score on the same outcome is the
only honest way to say one state model is better than another.

POINT-IN-TIME BY CONSTRUCTION, AND THE TESTS PIN IT.
  * Every engine is refit every REFIT_EVERY days on returns STRICTLY BEFORE the refit day, and
    between refits it only FILTERS (forward recursions with fixed parameters), so the forecast
    made at the close of t reads r_0..r_t and nothing later.
  * The fusion weight of each engine at t is its discounted log score on outcomes up to y_t,
    every one of which is known at the close of t.
  * `test_state_ensemble.py` truncates the series at random t and asserts the forecast at t is
    bit-identical with and without the future attached. That is the lookahead test; nothing here
    is trusted without it.

THE ENGINES (each degrades to the base rate, never to a guess, when it cannot forecast):
  climatology  the trailing year's tier frequencies -- the PLAIN input every engine must beat
  garch        GJR-GARCH(1,1) through `arch` (hand-rolled GARCH is banned on this desk:
               libs/research/stationarity.py). `arch` is the optional [stats] extra; where it is
               absent the engine is UNMEASURED and named so in every artifact, never imitated.
  sv_kalman    log-squared-return stochastic volatility, Harvey-Ruiz-Shephard QML Kalman filter,
               (phi, q) by a vectorised likelihood grid
  particle     the same SV law with a jump mixture in the measurement, bootstrap particle filter,
               seeded so a re-run (the gauntlet's re-execution) is bit-identical
  hsmm         two volatility regimes with NEGATIVE-BINOMIAL (explicit) durations by the
               expanded-state construction; emissions and mean durations moment-fitted on the
               training window, forward-filtered. Stated plainly: moment-fitted, not EM.
  hawkes       an exponential-kernel Hawkes process on the high-tier days, fitted by
               `libs.models.classical_baselines.HawkesIntensity` (extended, not rebuilt)
  The trend axis is a seventh, separate reading: a local-level Kalman filter on returns whose
  drift z-score labels the day `trend` or `range` (the vocabulary of `libs.regime.control_room`).

WHAT THIS MODULE IS NOT. It sizes nothing and is imported by no money-path file. Its consumers
are `desks/mt5/research/state_ensemble_run.py` (the published artifact, the walk-forward
calibration and allocation contract, and the near-miss re-test) and the opt-in `labeler=
"ensemble"` of `families_orthogonal.family_regime_split`, which is how a regime-conditioned cell
reaches the canonical gauntlet and is re-executed there exactly.
"""

from __future__ import annotations

import math
import warnings
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

import numpy as np
import pandas as pd
from scipy.special import ndtr

__all__ = [
    "ENGINES",
    "TIERS",
    "EnsembleResult",
    "available_engines",
    "calibration",
    "common_mask",
    "compare",
    "fit_ensemble",
    "gauss_tiers",
    "hmm_tier_forecast",
    "label_days",
    "label_days_cached",
    "tier_outcomes",
]

TIERS: tuple[str, ...] = ("low", "mid", "high")
ENGINES: tuple[str, ...] = ("climatology", "garch", "sv_kalman", "particle", "hsmm", "hawkes")
RANK_WIN = 252
FIT_WIN = 750
MIN_FIT = 300
REFIT_EVERY = 63
#: Discount on past log scores in the fusion: an engine's last ~100 forecasts carry most weight.
FORGET = 0.99
P_FLOOR = 1e-4
#: A day is `split` when the engines' disagreement is in the top quarter of its trailing year.
SPLIT_Q = 0.75
TREND_Z = 1.0
#: Local-level drift: state noise as a share of observation noise (signal-to-noise prior).
DRIFT_KAPPA = 1.0 / 250.0
N_PARTICLES = 400
JUMP_P, JUMP_SCALE = 0.02, 3.0
HSMM_STAGES = 4
_LOG_CHI2_MEAN = -1.2704
_LOG_CHI2_VAR = math.pi ** 2 / 2.0

Arr = np.ndarray


def available_engines() -> tuple[str, ...]:
    """The engines this host can run. `garch` needs `arch`; its absence is reported, not hidden."""
    try:
        import arch  # noqa: F401
    except Exception:
        return tuple(e for e in ENGINES if e != "garch")
    return ENGINES


# ------------------------------------------------------------------------------- the target
def tier_outcomes(r: Arr) -> tuple[Arr, Arr, Arr]:
    """(y, q1, q2). q1[t], q2[t]: terciles of |r| over the trailing RANK_WIN days ending AT t.
    y[t]: tier (0/1/2) of |r_t| against q[t-1] -- NaN until a full year precedes it."""
    a = pd.Series(np.abs(np.asarray(r, dtype=float)))
    q1 = a.rolling(RANK_WIN).quantile(1.0 / 3.0).to_numpy()
    q2 = a.rolling(RANK_WIN).quantile(2.0 / 3.0).to_numpy()
    y = np.full(a.size, np.nan)
    av = a.to_numpy()
    p1, p2 = np.roll(q1, 1), np.roll(q2, 1)
    p1[0] = p2[0] = np.nan
    ok = np.isfinite(p1) & np.isfinite(p2) & np.isfinite(av)
    y[ok] = np.where(av[ok] < p1[ok], 0.0, np.where(av[ok] < p2[ok], 1.0, 2.0))
    return y, q1, q2


def gauss_tiers(sigma: Arr, q1: Arr, q2: Arr) -> Arr:
    """Tier probabilities of a zero-mean normal return with sd `sigma` (broadcasts)."""
    s = np.maximum(np.asarray(sigma, dtype=float), 1e-12)
    c1 = 2.0 * ndtr(np.asarray(q1, dtype=float) / s) - 1.0
    c2 = 2.0 * ndtr(np.asarray(q2, dtype=float) / s) - 1.0
    c2 = np.maximum(c2, c1)
    out = np.stack([c1, c2 - c1, 1.0 - c2], axis=-1)
    return np.asarray(out)


def _norm(p: Arr) -> Arr:
    p = np.clip(p, P_FLOOR, None)
    return np.asarray(p / p.sum(axis=-1, keepdims=True))


# ------------------------------------------------------------------------------ walk-forward
Fit = Callable[[Arr, int], Any]
Filt = Callable[[Arr, Any, int], Arr]


def _walk(r: Arr, fit: Fit, filt: Filt) -> Arr:
    """Refit every REFIT_EVERY days on r[<t0], filter forward with those params to t1.

    Row t of the result is the forecast made at the close of t for day t+1. `fit(train, start)`
    and `filt(segment, params, start)` both receive the absolute index of their first element so
    an engine can line its inputs (thresholds, outcomes) up without seeing anything later."""
    n = r.size
    out = np.full((n, 3), np.nan)
    for t0 in range(MIN_FIT, n, REFIT_EVERY):
        t1 = min(n, t0 + REFIT_EVERY)
        lo = max(0, t0 - FIT_WIN)
        try:
            params = fit(r[lo:t0], lo)
        except Exception:
            params = None
        if params is None:
            continue
        try:
            got = filt(r[lo:t1], params, lo)
        except Exception:
            continue
        out[t0:t1] = got[t0 - lo:t1 - lo]
    return out


def _climatology(y: Arr) -> Arr:
    n = y.size
    out = np.full((n, 3), np.nan)
    for k in range(3):
        hit = pd.Series(np.where(np.isfinite(y), (y == k).astype(float), np.nan))
        out[:, k] = (hit.rolling(RANK_WIN, min_periods=60).sum() + 1.0).to_numpy()
    cnt = pd.Series(np.isfinite(y).astype(float)).rolling(RANK_WIN, min_periods=60).sum()
    return np.asarray(out / (cnt.to_numpy()[:, None] + 3.0))


# ---------------------------------------------------------------------------------- engines
def _garch(r: Arr, q1: Arr, q2: Arr) -> Arr:
    from arch import arch_model

    def fit(train: Arr, _lo: int) -> Any:
        if train.size < 200:
            return None
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            res = arch_model(train * 100.0, mean="Zero", vol="GARCH", p=1, o=1, q=1,
                             dist="normal", rescale=False).fit(disp="off", show_warning=False)
        return np.asarray(res.params, dtype=float)

    def filt(seg: Arr, params: Any, lo: int) -> Arr:
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            fixed = arch_model(seg * 100.0, mean="Zero", vol="GARCH", p=1, o=1, q=1,
                               dist="normal", rescale=False).fix(params)
            var = np.asarray(fixed.forecast(horizon=1, start=0, reindex=False).variance,
                             dtype=float)[:, 0]
        sig = np.sqrt(np.maximum(var, 1e-12)) / 100.0
        return gauss_tiers(sig, q1[lo:lo + seg.size], q2[lo:lo + seg.size])

    return _walk(r, fit, filt)


@dataclass(frozen=True)
class _SV:
    mu: float
    phi: float
    q: float
    c: float


_PHI_GRID = np.array([0.90, 0.95, 0.98, 0.995])
_Q_GRID = np.array([0.005, 0.02, 0.05, 0.1, 0.2])


def _sv_y(seg: Arr, c: float) -> Arr:
    return np.asarray(np.log(seg * seg + c))


def _sv_fit(train: Arr, _lo: int) -> _SV | None:
    if train.size < 200:
        return None
    c = 0.01 * float(np.median(train * train)) + 1e-14
    y = _sv_y(train, c)
    mu = float(y.mean()) - _LOG_CHI2_MEAN
    phi, q = np.meshgrid(_PHI_GRID, _Q_GRID, indexing="ij")
    phi, q = phi.ravel(), q.ravel()
    m = np.full(phi.size, mu)
    p = q / (1.0 - phi ** 2)
    ll = np.zeros(phi.size)
    for yt in y:
        f = p + _LOG_CHI2_VAR
        v = yt - (m + _LOG_CHI2_MEAN)
        ll += -0.5 * (np.log(2 * math.pi * f) + v * v / f)
        k = p / f
        m = m + k * v
        p = (1.0 - k) * p
        m = mu + phi * (m - mu)
        p = phi * phi * p + q
    j = int(np.argmax(ll))
    return _SV(mu=mu, phi=float(phi[j]), q=float(q[j]), c=c)


_GH_X, _GH_W = np.polynomial.hermite_e.hermegauss(7)
_GH_W = _GH_W / _GH_W.sum()


def _sv_kalman(r: Arr, q1: Arr, q2: Arr) -> Arr:
    def filt(seg: Arr, par: Any, lo: int) -> Arr:
        sv: _SV = par
        y = _sv_y(seg, sv.c)
        m, p = sv.mu, sv.q / (1.0 - sv.phi ** 2)
        mp, pp = np.empty(seg.size), np.empty(seg.size)
        for t, yt in enumerate(y):
            f = p + _LOG_CHI2_VAR
            k = p / f
            m = m + k * (yt - (m + _LOG_CHI2_MEAN))
            p = (1.0 - k) * p
            m = sv.mu + sv.phi * (m - sv.mu)
            p = sv.phi * sv.phi * p + sv.q
            mp[t], pp[t] = m, p
        h = mp[:, None] + np.sqrt(pp)[:, None] * _GH_X[None, :]
        sig = np.exp(h / 2.0)
        a1, a2 = q1[lo:lo + seg.size, None], q2[lo:lo + seg.size, None]
        tiers = gauss_tiers(sig, a1, a2)
        return np.asarray((tiers * _GH_W[None, :, None]).sum(axis=1))

    return _walk(r, _sv_fit, filt)


def _particle(r: Arr, q1: Arr, q2: Arr) -> Arr:
    def filt(seg: Arr, par: Any, lo: int) -> Arr:
        sv: _SV = par
        rng = np.random.default_rng(1_000_003 + lo)
        n = N_PARTICLES
        h = sv.mu + math.sqrt(sv.q / (1.0 - sv.phi ** 2)) * rng.standard_normal(n)
        out = np.empty((seg.size, 3))
        sd_q = math.sqrt(sv.q)
        for t, rt in enumerate(seg):
            var = np.exp(h)
            lik = ((1.0 - JUMP_P) * np.exp(-0.5 * rt * rt / var) / np.sqrt(var)
                   + JUMP_P * np.exp(-0.5 * rt * rt / (var * JUMP_SCALE ** 2))
                   / (np.sqrt(var) * JUMP_SCALE))
            w = lik / lik.sum() if np.isfinite(lik.sum()) and lik.sum() > 0 else np.full(n, 1 / n)
            pos = (rng.random() + np.arange(n)) / n
            h = h[np.minimum(np.searchsorted(np.cumsum(w), pos), n - 1)]
            h = sv.mu + sv.phi * (h - sv.mu) + sd_q * rng.standard_normal(n)
            s = np.exp(h / 2.0)
            a1, a2 = q1[lo + t], q2[lo + t]
            out[t] = ((1.0 - JUMP_P) * gauss_tiers(s, a1, a2)
                      + JUMP_P * gauss_tiers(s * JUMP_SCALE, a1, a2)).mean(axis=0)
        return out

    return _walk(r, _sv_fit, filt)


@dataclass(frozen=True)
class _HSMM:
    sig: tuple[float, float]
    trans: Arr = field(repr=False)
    regime: Arr = field(repr=False)


def _hsmm_fit(train: Arr, _lo: int) -> _HSMM | None:
    if train.size < 200:
        return None
    rv = pd.Series(train).rolling(10, min_periods=5).std().to_numpy()
    ok = np.isfinite(rv)
    lab = (rv > np.nanmedian(rv)).astype(int)
    lab, x = lab[ok], train[ok]
    sig = tuple(float(np.std(x[lab == k])) if (lab == k).sum() > 10 else float(np.std(x))
                for k in (0, 1))
    if not sig[0] > 0 or not sig[1] > 0:
        return None
    runs: dict[int, list[int]] = {0: [], 1: []}
    cur, ln = int(lab[0]), 1
    for v in lab[1:]:
        if int(v) == cur:
            ln += 1
        else:
            runs[cur].append(ln)
            cur, ln = int(v), 1
    runs[cur].append(ln)
    stages, stay = [], []
    for k in (0, 1):
        d = max(2.0, float(np.mean(runs[k])) if runs[k] else 10.0)
        m = int(min(HSMM_STAGES, max(1, d // 2)))
        stages.append(m)
        stay.append(1.0 - m / d)
    size = sum(stages)
    trans = np.zeros((size, size))
    regime = np.zeros(size, dtype=int)
    first = [0, stages[0]]
    for k in (0, 1):
        for i in range(stages[k]):
            s = first[k] + i
            regime[s] = k
            trans[s, s] = stay[k]
            nxt = s + 1 if i < stages[k] - 1 else first[1 - k]
            trans[s, nxt] += 1.0 - stay[k]
    return _HSMM(sig=(sig[0], sig[1]), trans=trans, regime=regime)


def _hsmm(r: Arr, q1: Arr, q2: Arr) -> Arr:
    def filt(seg: Arr, par: Any, lo: int) -> Arr:
        hs: _HSMM = par
        sd = np.array([hs.sig[k] for k in hs.regime])
        a = np.full(hs.regime.size, 1.0 / hs.regime.size)
        out = np.empty((seg.size, 3))
        tier_k = np.stack([gauss_tiers(np.full(seg.size, hs.sig[k]), q1[lo:lo + seg.size],
                                       q2[lo:lo + seg.size]) for k in (0, 1)], axis=1)
        for t, rt in enumerate(seg):
            e = np.exp(-0.5 * (rt / sd) ** 2) / sd
            a = a * e
            z = a.sum()
            a = a / z if np.isfinite(z) and z > 0 else np.full(a.size, 1.0 / a.size)
            a = a @ hs.trans
            pk = np.array([a[hs.regime == k].sum() for k in (0, 1)])
            out[t] = pk @ tier_k[t]
        return out

    return _walk(r, _hsmm_fit, filt)


def _hawkes(r: Arr, y: Arr) -> Arr:
    from libs.models.classical_baselines import HawkesIntensity

    ev = np.where(np.isfinite(y), (y == 2).astype(float), 0.0)

    def fit(train: Arr, lo: int) -> Any:
        idx = lo + np.arange(train.size)
        yy = y[idx]
        times = idx[np.isfinite(yy) & (yy == 2)].astype(float)
        st = HawkesIntensity().fit(list(times)).state
        if not st.get("fitted"):
            return None
        rest = yy[np.isfinite(yy) & (yy < 2)]
        low = float(((rest == 0).sum() + 1.0) / (rest.size + 2.0))
        return (float(st["mu"]), float(st["alpha"]), float(st["beta"]), low)

    def filt(seg: Arr, par: Any, lo: int) -> Arr:
        mu, alpha, beta, low = par
        dec = math.exp(-beta)
        s = 0.0
        out = np.empty((seg.size, 3))
        for t in range(seg.size):
            s = s * dec + ev[lo + t]
            lam = mu + alpha * dec * s
            ph = min(0.98, max(0.02, 1.0 - math.exp(-lam)))
            out[t] = (low * (1 - ph), (1 - low) * (1 - ph), ph)
        return out

    return _walk(r, fit, filt)


def _drift_z(r: Arr) -> Arr:
    """Local-level Kalman drift on returns; z = filtered drift / its sd, causal."""
    var = pd.Series(r).rolling(60, min_periods=20).var().to_numpy()
    z = np.full(r.size, np.nan)
    m, p = 0.0, np.nan
    for t, rt in enumerate(r):
        rv = var[t]
        if not np.isfinite(rv) or rv <= 0:
            continue
        q = DRIFT_KAPPA * rv
        if not np.isfinite(p):
            p = rv
        p = p + q
        k = p / (p + rv)
        m = m + k * (rt - m)
        p = (1.0 - k) * p
        z[t] = m / math.sqrt(p)
    return z


# ------------------------------------------------------------------------------------ fusion
@dataclass
class EnsembleResult:
    """Everything one symbol's ensemble pass measured, indexed on the RETURN days."""

    days: list[str]
    y: Arr
    engines: dict[str, Arr]
    fused: Arr
    weights: Arr
    disagreement: Arr
    labels: pd.DataFrame
    unavailable: dict[str, str]

    def current(self) -> dict[str, Any]:
        lab = self.labels[self.labels["vol"] != ""]
        if lab.empty:
            return {"status": "UNMEASURED", "why": "no labelled day yet"}
        day = str(lab.index[-1])
        i = self.days.index(day)
        names = list(self.engines)
        return {"status": "MEASURED", "asof": day, "vol": str(lab["vol"].iloc[-1]),
                "trend": str(lab["trend"].iloc[-1]), "split": bool(lab["split"].iloc[-1]),
                "state": f"{lab['vol'].iloc[-1]}_{lab['trend'].iloc[-1]}"
                         f"|{'split' if lab['split'].iloc[-1] else 'agree'}",
                "p_next_tier": dict(zip(TIERS, (round(float(v), 4) for v in self.fused[i]),
                                        strict=True)),
                "disagreement": round(float(self.disagreement[i]), 4),
                "drift_z": round(float(lab["drift_z"].iloc[-1]), 3),
                "weights": {n: round(float(w), 4) for n, w in zip(names, self.weights[i],
                                                                   strict=True)},
                "engine_p_high": {n: round(float(self.engines[n][i, 2]), 4) for n in names}}


def _entropy(p: Arr) -> Arr:
    q = np.clip(p, 1e-12, 1.0)
    return np.asarray(-(q * np.log(q)).sum(axis=-1))


def _trailing_rank(x: Arr, win: int = RANK_WIN) -> Arr:
    s = pd.Series(x)
    return np.asarray(s.rolling(win, min_periods=60).rank(pct=True).to_numpy())


def fit_ensemble(close: pd.Series, engines: tuple[str, ...] | None = None) -> EnsembleResult:
    """Run every available engine on one symbol's daily closes and fuse them, point-in-time."""
    close = close.astype(float).dropna()
    lr = np.diff(np.log(close.to_numpy()))
    days = [str(d) for d in close.index[1:]]
    y, q1, q2 = tier_outcomes(lr)
    clim = _climatology(y)
    want = engines or available_engines()
    unavailable = {e: "the optional `arch` package ([stats] extra) is not installed on this host"
                   for e in ENGINES if e not in want and e == "garch"}
    runners: dict[str, Callable[[], Arr]] = {
        "climatology": lambda: clim,
        "garch": lambda: _garch(lr, q1, q2),
        "sv_kalman": lambda: _sv_kalman(lr, q1, q2),
        "particle": lambda: _particle(lr, q1, q2),
        "hsmm": lambda: _hsmm(lr, q1, q2),
        "hawkes": lambda: _hawkes(lr, y),
    }
    out: dict[str, Arr] = {}
    for name in ENGINES:
        if name not in want:
            continue
        try:
            p = runners[name]()
        except Exception as exc:
            unavailable[name] = f"{type(exc).__name__}: {str(exc)[:160]}"
            continue
        # AN ENGINE THAT CANNOT FORECAST YET FORECASTS THE BASE RATE, never a guess: so the
        # fusion compares like with like on every day, and an engine earns weight only on the
        # days it actually forecast.
        bad = ~np.isfinite(p).all(axis=1)
        p = p.copy()
        p[bad] = clim[bad]
        out[name] = _norm(np.where(np.isfinite(p), p, 1.0 / 3.0))
    names = list(out)
    stack = np.stack([out[n] for n in names], axis=1)                        # (n, k, 3)
    n = lr.size
    score = np.zeros(len(names))
    weights = np.full((n, len(names)), 1.0 / len(names))
    live = np.isfinite(clim).all(axis=1)
    for t in range(n):
        if t > 0 and np.isfinite(y[t]) and live[t - 1]:
            score = FORGET * score + np.log(stack[t - 1, :, int(y[t])])
        z = score - score.max()
        w = np.exp(z)
        weights[t] = w / w.sum()
    fused = _norm(np.einsum("nk,nkc->nc", weights, stack))
    js = (_entropy(fused) - np.einsum("nk,nk->n", weights, _entropy(stack))) / math.log(3.0)
    js = np.where(live, np.maximum(js, 0.0), np.nan)
    fused = np.where(live[:, None], fused, np.nan)
    e_tier = fused @ np.array([0.0, 1.0, 2.0])
    rank = _trailing_rank(np.where(live, e_tier, np.nan))
    dis_rank = _trailing_rank(js)
    vol = np.where(~np.isfinite(rank), "", np.where(rank <= 1 / 3, "low",
                                                    np.where(rank <= 2 / 3, "mid", "high")))
    dz = _drift_z(lr)
    trend = np.where(np.isfinite(dz) & (np.abs(dz) > TREND_Z), "trend", "range")
    labels = pd.DataFrame({"vol": vol, "trend": np.where(vol == "", "", trend),
                           "split": np.isfinite(dis_rank) & (dis_rank > SPLIT_Q),
                           "drift_z": dz, "e_tier": e_tier, "disagreement": js}, index=days)
    return EnsembleResult(days=days, y=y, engines=out, fused=fused, weights=weights,
                          disagreement=js, labels=labels, unavailable=unavailable)


def label_days(daily: pd.DataFrame, engines: tuple[str, ...] | None = None) -> pd.DataFrame:
    """`control_room.label_days`' shape for the ensemble: index = day, columns vol / trend / liq.

    The label of day d is read at the close of d. `family_regime_split(labeler="ensemble")` gates
    a signal on the label of the last completed day before it, exactly as it does the control
    room's, so the gauntlet re-executes the miner's cell with the same states."""
    res = fit_ensemble(daily["close"], engines)
    lab = res.labels[["vol", "trend"]].copy()
    lab["liq"] = ""
    lab["split"] = res.labels["split"]
    return lab


_LABEL_CACHE: dict[tuple[Any, ...], pd.DataFrame] = {}
_LABEL_CACHE_MAX = 64


def label_days_cached(daily: pd.DataFrame) -> pd.DataFrame:
    """`label_days`, memoised on the frame's identity (length, ends, close checksum).

    The gauntlet builds one `regime_split(labeler="ensemble")` cell per regime bucket on the same
    bars; without this every bucket would refit all six engines. The key is the DATA, so two
    different frames can never share labels."""
    c = daily["close"].astype(float)
    key = (len(c), str(c.index[0]) if len(c) else "", str(c.index[-1]) if len(c) else "",
           round(float(c.sum()), 8) if len(c) else 0.0, available_engines())
    got = _LABEL_CACHE.get(key)
    if got is None:
        got = label_days(daily)
        if len(_LABEL_CACHE) >= _LABEL_CACHE_MAX:
            _LABEL_CACHE.pop(next(iter(_LABEL_CACHE)))
        _LABEL_CACHE[key] = got
    return got.copy()


# -------------------------------------------------------------------- the incumbent, honestly
def hmm_tier_forecast(close: pd.Series) -> Arr:
    """THE ALLOCATOR'S CURRENT INPUT, walk-forward: a 3-state Gaussian HMM on the engine's own
    features, refit on the same schedule, standardised with TRAINING statistics only, filtered
    forward, and mapped to tomorrow's tier by the training window's own state->outcome table."""
    from libs.regime.features import raw_regime_features, standardise
    from libs.regime.hmm import GaussianHMM

    close = close.astype(float).dropna()
    raw = raw_regime_features(close)[1:]                 # row t <-> return t
    lr = np.diff(np.log(close.to_numpy()))
    y, _q1, _q2 = tier_outcomes(lr)

    def fit(train: Arr, lo: int) -> Any:
        x = raw[lo:lo + train.size]
        mu, sd = x.mean(axis=0), x.std(axis=0) + 1e-9
        hmm = GaussianHMM(n_states=3, seed=0).fit(standardise(x, mu, sd))
        post = hmm.filter_posterior(standardise(x, mu, sd))
        yy = y[lo:lo + train.size]
        m = np.ones((3, 3))
        for t in range(train.size - 1):
            if np.isfinite(yy[t + 1]):
                m[:, int(yy[t + 1])] += post[t]
        return hmm, mu, sd, m / m.sum(axis=1, keepdims=True)

    def filt(seg: Arr, par: Any, lo: int) -> Arr:
        hmm, mu, sd, m = par
        post = hmm.filter_posterior(standardise(raw[lo:lo + seg.size], mu, sd))
        return np.asarray(post @ m)

    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        got = _walk(lr, fit, filt)
    ok = np.isfinite(got).all(axis=1)
    out = np.full_like(got, np.nan)
    out[ok] = _norm(got[ok])
    return out


# ------------------------------------------------------------------------------- calibration
def _block_ci(x: Arr, block: int = 10, reps: int = 1000, alpha: float = 0.10,
              seed: int = 11) -> tuple[float, float]:
    """Moving-block bootstrap interval for a mean (vectorised)."""
    n = x.size
    if n < 2 * block:
        return float("nan"), float("nan")
    rng = np.random.default_rng(seed)
    nb = math.ceil(n / block)
    starts = rng.integers(0, n - block + 1, size=(reps, nb))
    idx = (starts[:, :, None] + np.arange(block)[None, None, :]).reshape(reps, -1)[:, :n]
    means = x[idx].mean(axis=1)
    lo, hi = np.quantile(means, [alpha / 2, 1 - alpha / 2])
    return float(lo), float(hi)


def calibration(p: Arr, y: Arr, keep: Arr | None = None) -> dict[str, Any]:
    """Log score, Brier and high-tier ECE of forecasts p[t] for outcomes y[t+1].

    `keep[t]` selects the forecast days; pass the SAME mask to every side of a comparison so the
    two are scored on identical days (`common_mask`)."""
    sel = common_mask(y, p) if keep is None else np.asarray(keep, dtype=bool)
    sel = sel.copy()
    sel[-1] = False
    t = np.flatnonzero(sel)
    pp, yy = p[t], y[t + 1]
    if not (np.isfinite(yy).all() and np.isfinite(pp).all()):
        return {"status": "UNMEASURED", "n": 0, "why": "the mask admits an unscored day"}
    yy = yy.astype(int)
    if yy.size < 60:
        return {"status": "UNMEASURED", "n": int(yy.size), "why": "under 60 scored forecasts"}
    ls = np.log(np.clip(pp[np.arange(yy.size), yy], P_FLOOR, 1.0))
    onehot = np.eye(3)[yy]
    brier = ((pp - onehot) ** 2).sum(axis=1)
    bins = np.clip((pp[:, 2] * 10).astype(int), 0, 9)
    ece = 0.0
    for b in range(10):
        m = bins == b
        if m.any():
            ece += float(m.mean()) * abs(float(pp[m, 2].mean()) - float((yy[m] == 2).mean()))
    return {"status": "MEASURED", "n": int(yy.size), "log_score": round(float(ls.mean()), 5),
            "brier": round(float(brier.mean()), 5), "ece_high": round(ece, 5),
            "_ls": ls}


def common_mask(y: Arr, *forecasts: Arr) -> Arr:
    """Days t on which EVERY forecast is finite and the outcome y[t+1] is known."""
    nxt = np.append(np.isfinite(y[1:]), False)
    keep = nxt.copy()
    for f in forecasts:
        keep &= np.isfinite(f).all(axis=1)
    return keep


def compare(a: dict[str, Any], b: dict[str, Any]) -> dict[str, Any]:
    """a minus b on per-day log score, same days; WIN iff the 90% block interval is above 0."""
    if a.get("status") != "MEASURED" or b.get("status") != "MEASURED":
        return {"status": "UNMEASURED", "why": "one side has no scored forecasts"}
    la, lb = a["_ls"], b["_ls"]
    if la.size != lb.size:
        return {"status": "UNMEASURED", "why": "the two sides scored different days"}
    d = la - lb
    lo, hi = _block_ci(d)
    verdict = ("WIN" if lo > 0 else "LOSS" if hi < 0 else "INCONCLUSIVE")
    return {"status": "MEASURED", "verdict": verdict, "n": int(d.size),
            "mean_log_score_gain": round(float(d.mean()), 6), "ci90": [round(lo, 6),
                                                                      round(hi, 6)]}
