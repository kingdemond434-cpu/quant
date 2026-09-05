"""The complete multi-period POSTERIOR E[log W] optimiser: size on what the desk knows, not on
what it happened to measure.

    maximise   E_posterior[ log(1 + sum_i h_i R_i - C(h, h_prev)) ]   summed over T periods
    subject to P(ruin) < eps_ruin,   P(stop-out) < eps_stop,
               floor <= sum_i h_i <= ceiling,   0 <= h_i <= cap_i

THE TWO RULES THIS SERVES, verbatim from docs/GROWTH_GOVERNANCE.md (principal, 2026-09-04;
`RULES` carries the same text unwrapped, and every certificate repeats it):

    "Every risk reduction mechanism must prove that it increases robust forward E[log W]."
    "Every strong opportunity must be allowed to increase capital above normal when the
     evidence supports it."

WHAT THE POSTERIOR IS. `robust_elog` draws worlds around a point estimate and scores a book on
its robust functional. This module goes one level up: the expectation is taken over a POSTERIOR
on the sleeves' joint mean and covariance, so a sleeve whose edge is precisely measured and one
whose edge is a hopeful forty days are different objects to the optimiser even when their
sample means agree. Three sources of doubt are drawn jointly, per path:

  1. PARAMETER UNCERTAINTY -- Normal-Inverse-Wishart on (mu, Sigma), or a Bayesian bootstrap
     (Dirichlet weights over days). The NIW prior mean is NO EDGE with `K_SLEEVE` pseudo-
     observations, which makes its posterior mean exactly `n / (n + 60)` of the sample mean --
     the same shrinkage `robust_elog._posterior_mu` applies, restated as the prior it always
     was. The same module's winner's-curse deflation is applied before the shrinkage: a sleeve
     is in the matrix BECAUSE it measured well, and `n_trials` says how many candidates it
     was picked from. Sizing on the undeflated mean is how the biggest position ends up in
     the luckiest backtest, and no sample size cures that bias.
  2. THE DESK'S OWN WORLDS -- when a `WorldConfig` or a drawn `Worlds` is supplied, the paths
     are T-day blocks cut from that population, so regime mixture, crisis overlay, edge decay
     and execution-cost uncertainty enter exactly as the rest of the desk already models them.
     The bootstrap across worlds is the covariance posterior in that case.
  3. THE REAL TAILS -- innovations are the sleeves' own residual days, whitened by the sample
     covariance and recoloured by each path's posterior covariance draw. A Gaussian innovation
     would sample a world in which the -60R day never happened; this one keeps it, which is
     what the ruin constraint has to be measured against.

WHAT MULTI-PERIOD BUYS. The decision is the first-step book h_1; the desk re-solves before h_2
ever arrives (a receding horizon), so the plan for later steps is to HOLD h_1. That is not a
simplification of the problem, it is the problem: a move paid for now earns its growth for the
T periods until the next re-solve, and ruin and stop-out are properties of the wealth PATH over
those periods, not of one day's return. Both constraints and the turnover cost are therefore
measured on the same M x T sample paths the growth is.

HOW IT IS SOLVED. Sample-average approximation: draw M paths of length T, evaluate the T-period
log wealth for a candidate book, ascend. Projected proximal gradient: the L1 turnover cost is a
proximal (soft-threshold toward h_prev) step, so the no-trade region is exact rather than
oscillated around; the heat band and per-sleeve caps are a projection onto the capped simplex
(`robust_elog.project_capped_simplex`); the stop-out constraint is a hinge penalty on each
path's worst log wealth, tightened until the estimated probability sits under `eps_stop`. The
floor is FLAT -- never scaled by readiness or confidence -- and growth is free above it to the
ceiling: when growth wants less than the floor the book is filled to the floor by the sleeves
with the highest marginal growth (the projection does exactly that), and when it wants more it
is clipped at the ceiling. The ruin guard is the ONLY mechanism permitted to take the book
below the floor, and it names itself: `binding == "ruin_guard"`.

WHAT IT REPORTS. `PosteriorBook.certificate()` carries the first-step book, the posterior mean
growth and its 10th percentile across paths (the robust number), P(ruin), P(stop-out), the
turnover it paid, which constraint decided the total, and the posterior's shrinkage summary --
so the reader can see how much of the measured edge the optimiser actually believed.
`compare()` scores two books on the SAME paths with a paired bootstrap, which is the contest
semantics `allocator_proof` uses: a challenger beats the incumbent only when dE[log W] > 0 with
a confidence interval that excludes zero.
"""
from __future__ import annotations

import math
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass, field
from typing import Any

import numpy as np

from libs.portfolio.robust_elog import (
    SleeveEvidence,
    WorldConfig,
    Worlds,
    project_capped_simplex,
    sample_worlds,
)

__all__ = [
    "BINDINGS",
    "DEFAULT_HORIZON",
    "DEFAULT_N_PATHS",
    "EPS_RUIN",
    "EPS_STOP",
    "K_SLEEVE",
    "RULES",
    "STOPOUT_DD",
    "TURNOVER_COST",
    "PathOutcome",
    "PosteriorBook",
    "PosteriorMoments",
    "PosteriorPaths",
    "compare",
    "posterior_moments",
    "sample_paths",
    "simulate",
    "solve",
]

RULE_1 = "Every risk reduction mechanism must prove that it increases robust forward E[log W]."
RULE_2 = ("Every strong opportunity must be allowed to increase capital above normal when the "
          "evidence supports it.")
#: The two governance rules, unwrapped, for certificates and fences to carry verbatim.
RULES: tuple[str, str] = (RULE_1, RULE_2)

#: Pseudo-observations of the no-edge prior. THE SAME 60 AS `robust_elog._posterior_mu`'s
#: `k_sleeve`, on purpose: the desk has one belief about how many days it takes to start
#: trusting a mean, and a second allocator with a second number would let the two disagree
#: about the same sleeve. Forward and live days weigh 4x and 12x for the same reason.
K_SLEEVE = 60.0
FORWARD_WEIGHT = 4.0
LIVE_WEIGHT = 12.0
#: Out-of-sample day scale over which the winner's-curse deflation is relieved (robust_elog).
OOS_SCALE = 250.0

DEFAULT_N_PATHS = 400
DEFAULT_HORIZON = 5
#: Round-trip price of a unit of heat moved, in account fraction -- `pf_allocator.TURNOVER_COST_R`.
TURNOVER_COST = 0.06
#: P(ruin) must sit strictly under this. At M=400 paths that is "no path is wiped out", which is
#: the same statement `rails.ruin_guard` makes: a book wiped out in a sampled world is not a book.
EPS_RUIN = 1e-3
#: P(stop-out) bound and the drawdown that counts as a stop-out. 35% is MAX_DRAWDOWN_TOLERANCE,
#: the principal's stated pain limit (mt5desk.gateway_config_fallback); it is restated here
#: because libs/ may not import the desk, and a certificate reports the number it used.
EPS_STOP = 0.05
STOPOUT_DD = 0.35
#: Below this one-day wealth multiple the log is continued by its tangent parabola. A log that
#: goes to -inf cannot be ascended off; a quadratic continuation keeps a gradient pointing away
#: from ruin, and the hard P(ruin) count afterwards decides whether the book actually survived.
SOFT_LOG_DELTA = 0.25

BINDINGS: tuple[str, ...] = ("growth", "floor", "ceiling", "cap", "stopout_guard", "ruin_guard")


# ------------------------------------------------------------------------------ the posterior
@dataclass(frozen=True)
class PosteriorMoments:
    """Per-sleeve posterior on the mean, and the common-window covariance the paths recolour.

    Means use each sleeve's OWN history (a sleeve with 500 days is measured on 500 days even when
    its neighbour has 100); the covariance and the residual rows use the window every sleeve
    shares, because a covariance needs the days to be the same days.
    """

    names: tuple[str, ...]
    sample_mean: np.ndarray
    sample_sd: np.ndarray
    n_obs: np.ndarray
    n_eff: np.ndarray
    n_trials: np.ndarray
    #: Winner's-curse deflation in Sharpe units, already relieved by out-of-sample evidence.
    deflation: np.ndarray
    deflated_mean: np.ndarray
    #: n_eff / (n_eff + K_SLEEVE): the share of the deflated mean the posterior keeps.
    lam: np.ndarray
    post_mean: np.ndarray
    #: NIW precision weight on the mean, n_eff + K_SLEEVE.
    kappa: np.ndarray
    cov: np.ndarray
    #: Residual rows on the common window, whitened by the sample covariance's Cholesky factor.
    whitened: np.ndarray
    chol: np.ndarray
    obs: int
    cost_r: np.ndarray

    def summary(self) -> dict[str, Any]:
        per: dict[str, dict[str, float]] = {}
        for i, n in enumerate(self.names):
            sm = float(self.sample_mean[i])
            per[n] = {
                "n_obs": float(self.n_obs[i]), "n_eff": float(self.n_eff[i]),
                "n_trials": float(self.n_trials[i]),
                "sample_mean": round(sm, 8), "deflation_sr": round(float(self.deflation[i]), 6),
                "deflated_mean": round(float(self.deflated_mean[i]), 8),
                "posterior_mean": round(float(self.post_mean[i]), 8),
                "lam": round(float(self.lam[i]), 6),
                "shrink": round(float(self.post_mean[i] / sm) if abs(sm) > 1e-15 else 1.0, 6),
            }
        shrinks = np.array([v["shrink"] for v in per.values()]) if per else np.zeros(0)
        return {"k_sleeve": K_SLEEVE, "common_window_days": self.obs,
                "mean_shrink": round(float(shrinks.mean()), 6) if shrinks.size else 1.0,
                "min_shrink": round(float(shrinks.min()), 6) if shrinks.size else 1.0,
                "sleeves": per}


def posterior_moments(ev: Sequence[SleeveEvidence]) -> PosteriorMoments:
    """Deflate for selection, shrink for precision -- the desk's notion, restated as a NIW.

    TWO CORRECTIONS, EACH ONCE, exactly as `robust_elog._posterior_mu` argues: the BIAS limb is
    the trial deflation (half the expected maximum of `n_trials` null Sharpes, because the gate
    has already charged the other half), relieved by the out-of-sample days the sleeve could not
    have been selected on; the PRECISION limb is the `n / (n + K_SLEEVE)` shrinkage toward no
    edge, which is what a Normal prior with `K_SLEEVE` pseudo-observations at zero produces.
    """
    if not ev:
        raise ValueError("no sleeves to build a posterior over")
    n = len(ev)
    obs = min(int(e.daily_r.size) for e in ev)
    if obs < 2:
        raise ValueError("a sleeve has fewer than 2 observations; refusing to fabricate a path")
    m = np.array([float(e.daily_r.mean()) for e in ev])
    s = np.array([float(e.daily_r.std(ddof=1)) if e.daily_r.size > 1 else 0.0 for e in ev])
    n_obs = np.array([float(e.daily_r.size) for e in ev])
    fwd = np.array([float(e.forward_days) for e in ev])
    live = np.array([float(e.live_days) for e in ev])
    n_eff = n_obs + FORWARD_WEIGHT * fwd + LIVE_WEIGHT * live
    trials = np.array([max(float(e.n_trials), 1.0) for e in ev])

    sr0 = np.where(trials > 1.0,
                   0.5 * np.sqrt(2.0 * np.log(np.maximum(trials, 1.0000001)))
                   / np.sqrt(np.maximum(n_obs, 1.0)), 0.0)
    oos = FORWARD_WEIGHT * fwd + LIVE_WEIGHT * live
    sr0 = sr0 * (1.0 - oos / (oos + OOS_SCALE))
    sharpe = np.divide(m, s, out=np.zeros_like(m), where=s > 0)
    deflated = np.sign(sharpe) * np.maximum(np.abs(sharpe) - sr0, 0.0) * s
    lam = n_eff / (n_eff + K_SLEEVE)
    post = lam * deflated
    kappa = n_eff + K_SLEEVE

    hist = np.stack([np.asarray(e.daily_r[-obs:], dtype=float) for e in ev], axis=1)
    resid = hist - hist.mean(axis=0)
    cov = np.atleast_2d(np.cov(hist, rowvar=False))
    # A dead sleeve (zero variance) would make the factor singular; a whisper of variance keeps
    # the algebra alive and gives that sleeve no return to be sized on.
    cov = cov + 1e-12 * np.eye(n)
    chol = np.linalg.cholesky(cov)
    whitened = np.linalg.solve(chol, resid.T).T
    return PosteriorMoments(
        names=tuple(e.name for e in ev), sample_mean=m, sample_sd=s, n_obs=n_obs, n_eff=n_eff,
        n_trials=trials, deflation=sr0, deflated_mean=deflated, lam=lam, post_mean=post,
        kappa=kappa, cov=cov, whitened=whitened, chol=chol, obs=obs,
        cost_r=np.array([abs(float(e.cost_r)) for e in ev]),
    )


# ------------------------------------------------------------------------------ the paths
@dataclass(frozen=True)
class PosteriorPaths:
    """M sample paths of T days over N sleeves, drawn from the posterior, plus their provenance.

    `r` is (n_paths, horizon, n_sleeves) daily R-multiples. Everything the optimiser and the
    comparison do is arithmetic on this tensor, which is what makes a comparison fair: two books
    scored on the same `PosteriorPaths` saw the same futures.
    """

    r: np.ndarray
    names: tuple[str, ...]
    cost_r: np.ndarray
    mu_draws: np.ndarray
    shrinkage: dict[str, Any] = field(default_factory=dict)
    source: str = "niw"
    seed: int = 0
    note: str = ""

    @property
    def n_paths(self) -> int:
        return int(self.r.shape[0])

    @property
    def horizon(self) -> int:
        return int(self.r.shape[1])

    @property
    def n_sleeves(self) -> int:
        return int(self.r.shape[2])


def _inverse_wishart_chol(scale: np.ndarray, df: float, n_draws: int,
                          rng: np.random.Generator) -> np.ndarray:
    """Cholesky factors of `n_draws` draws from IW(df, scale), by the Bartlett decomposition.

    Sigma^-1 ~ Wishart(df, scale^-1) = B B' with B = L A, L L' = scale^-1 and A the Bartlett
    triangle. Inverting and re-factoring gives the Cholesky of Sigma itself rather than some
    other square root, and that matters: the paths recolour WHITENED REAL RESIDUALS, so a draw
    equal to the sample covariance must reproduce the real residual exactly, tails and all.
    """
    n = scale.shape[0]
    l_inv = np.linalg.cholesky(np.linalg.inv(scale))
    a = np.zeros((n_draws, n, n))
    idx = np.tril_indices(n, -1)
    a[:, idx[0], idx[1]] = rng.standard_normal((n_draws, idx[0].size))
    for i in range(n):
        a[:, i, i] = np.sqrt(rng.chisquare(df - i, size=n_draws))
    b = l_inv[None, :, :] @ a
    prec = b @ np.swapaxes(b, 1, 2)
    sigma = np.linalg.inv(prec)
    sigma = 0.5 * (sigma + np.swapaxes(sigma, 1, 2)) + 1e-12 * np.eye(n)[None, :, :]
    out: np.ndarray = np.linalg.cholesky(sigma)
    return out


def _worlds_paths(w: Worlds, n_paths: int, horizon: int, rng: np.random.Generator,
                  ) -> tuple[np.ndarray, np.ndarray, str]:
    """T-day blocks cut from the desk's world population: regime mix, crisis, decay included."""
    n_w, n_rows, _ = w.r.shape
    t = max(1, min(horizon, n_rows))
    widx = rng.integers(0, n_w, size=n_paths)
    start = rng.integers(0, n_rows - t + 1, size=n_paths)
    rows = start[:, None] + np.arange(t)[None, :]
    r = w.r[widx[:, None], rows, :].astype(np.float64)
    note = (f"paths cut from {n_w} worlds x {n_rows} rows; crisis share "
            f"{float(w.crisis[widx].mean()):.3f}")
    if t < horizon:
        note += f"; horizon trimmed to {t} rows"
    return r, w.mu_draws[widx], note


def sample_paths(ev: Sequence[SleeveEvidence] | None, *, n_paths: int = DEFAULT_N_PATHS,
                 horizon: int = DEFAULT_HORIZON, method: str = "niw",
                 cfg: WorldConfig | None = None, worlds: Worlds | None = None,
                 seed: int = 0) -> PosteriorPaths:
    """Draw the M x T x N path tensor the optimiser and the comparison are evaluated on.

    With `worlds` (or a `cfg` to draw them from) the paths are blocks of the desk's own world
    population, so the regime mixture and the crisis overlay are the ones the rest of the desk
    sizes against, and `ev` is needed only for costs and the shrinkage summary. Without them the
    posterior is drawn here: `method="niw"` for Normal-Inverse-Wishart, `"bayesian_bootstrap"`
    for Dirichlet-weighted days. Either way each path is ONE joint draw of (mu, Sigma) followed
    by T days of real residuals under it -- the parameter doubt and the day-to-day noise are
    never averaged separately.
    """
    if n_paths < 2 or horizon < 1:
        raise ValueError("need at least 2 paths and a horizon of at least 1 day")
    rng = np.random.default_rng(seed)
    pm = posterior_moments(ev) if ev else None

    if worlds is not None or cfg is not None:
        if worlds is None:
            if not ev:
                raise ValueError("a WorldConfig needs evidence to draw worlds from")
            worlds = sample_worlds(ev, cfg)
        if pm is not None and tuple(pm.names) != tuple(worlds.names):
            raise ValueError("evidence and worlds name different sleeves")
        r, mu, note = _worlds_paths(worlds, n_paths, horizon, rng)
        names = tuple(worlds.names)
        cost = pm.cost_r if pm is not None else np.zeros(len(names))
        shrink = (pm.summary() if pm is not None else
                  {"source": "worlds", "posterior_mean": {
                      n: round(float(worlds.mu_draws[:, i].mean()), 8)
                      for i, n in enumerate(names)}})
        shrink["source"] = "worlds" + (f"+{method}" if pm is not None else "")
        return PosteriorPaths(r=r, names=names, cost_r=cost, mu_draws=mu, shrinkage=shrink,
                              source="worlds", seed=seed, note=note)

    if pm is None:
        raise ValueError("no evidence and no worlds: nothing to draw paths from")
    n, obs = len(pm.names), pm.obs
    # Innovations: T consecutive real residual days per path, circular over the window. A block
    # keeps the runs a crisis week has; scattering the days would diversify it away.
    start = rng.integers(0, obs, size=n_paths)
    rows = (start[:, None] + np.arange(horizon)[None, :]) % obs
    z = pm.whitened[rows]                                               # (M, T, N)

    if method == "niw":
        # E[Sigma] = S under IW(df, S * (df - N - 1)); df grows with the window, so the
        # covariance is doubted in proportion to how few days measured it.
        df = float(obs + n + 2)
        chol = _inverse_wishart_chol(pm.cov * (df - n - 1.0), df, n_paths, rng)
        # mu | Sigma ~ N(post_mean, Sigma / kappa), widened by (2 - lam): pulling an estimate
        # toward zero does not make it more certain (robust_elog's own widening).
        scale = (2.0 - pm.lam) / np.sqrt(pm.kappa)
        mu = pm.post_mean[None, :] + scale[None, :] * np.einsum(
            "mij,mj->mi", chol, rng.standard_normal((n_paths, n)))
    elif method == "bayesian_bootstrap":
        # Dirichlet(1, ..., 1) weights over the window's days: every path is a posterior draw of
        # the empirical distribution itself. The replicate mean is deflated and shrunk by the
        # same arithmetic as the NIW mean, so the two methods disagree only about SHAPE.
        hist = pm.whitened @ pm.chol.T + pm.sample_mean[None, :]
        hist_mean_window = hist.mean(axis=0)
        wts = rng.dirichlet(np.ones(obs), size=n_paths)                   # (M, obs)
        m_w = wts @ hist                                                  # (M, N)
        centred = hist[None, :, :] - m_w[:, None, :]
        cov_w = np.einsum("mt,mti,mtj->mij", wts, centred, centred) * (obs / (obs - 1.0))
        cov_w = cov_w + 1e-12 * np.eye(n)[None, :, :]
        chol = np.linalg.cholesky(cov_w)
        sd_w = np.sqrt(np.einsum("mii->mi", cov_w))
        # The replicate carries the sleeve's own-history mean offset, so a sleeve measured on
        # more days than the window keeps that evidence in its centre.
        m_rep = m_w + (pm.sample_mean - hist_mean_window)[None, :]
        sr = np.divide(m_rep, sd_w, out=np.zeros_like(m_rep), where=sd_w > 0)
        defl = np.sign(sr) * np.maximum(np.abs(sr) - pm.deflation[None, :], 0.0) * sd_w
        mu = pm.lam[None, :] * defl
    else:
        raise ValueError(f"unknown posterior method {method!r}")

    r = mu[:, None, :] + np.einsum("mij,mtj->mti", chol, z)
    shrink = pm.summary()
    shrink["source"] = method
    return PosteriorPaths(r=r, names=pm.names, cost_r=pm.cost_r, mu_draws=mu, shrinkage=shrink,
                          source=method, seed=seed,
                          note=f"{method}: {n_paths} paths x {horizon} days on a "
                               f"{obs}-day common window")


# ------------------------------------------------------------------------------ the arithmetic
def _soft_log(x: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """log(x) above SOFT_LOG_DELTA, its C1 quadratic continuation below. Concave everywhere."""
    d = SOFT_LOG_DELTA
    safe = np.maximum(x, d)
    val = np.log(safe)
    der = 1.0 / safe
    below = x < d
    if below.any():
        u = (x[below] - d) / d
        val[below] = math.log(d) + u - 0.5 * u * u
        der[below] = (1.0 - u) / d
    return val, der


def _vec(book: Mapping[str, float] | None, names: Sequence[str]) -> np.ndarray:
    return np.array([max(float(book.get(k, 0.0)), 0.0) if book else 0.0 for k in names])


def _cost_vec(paths: PosteriorPaths, turnover_cost: float) -> np.ndarray:
    """Price of moving a unit of heat in each sleeve: the desk's turnover price plus the
    sleeve's own round trip. Charged once, at the first step -- the receding horizon holds the
    book until the next re-solve, so no later move is planned and none is billed."""
    out: np.ndarray = float(turnover_cost) + np.abs(paths.cost_r)
    return out


@dataclass(frozen=True)
class PathOutcome:
    """What a schedule did on every path: the numbers the constraints and the report read."""

    logw: np.ndarray
    ruined: np.ndarray
    stopped: np.ndarray
    turnover_l1: float
    turnover_cost: float
    horizon: int

    @property
    def per_day(self) -> np.ndarray:
        out: np.ndarray = self.logw / float(self.horizon)
        return out

    @property
    def p_ruin(self) -> float:
        return float(self.ruined.mean())

    @property
    def p_stopout(self) -> float:
        return float(self.stopped.mean())

    @property
    def elogw_per_day(self) -> float:
        fin = self.per_day[np.isfinite(self.per_day)]
        return float(fin.mean()) if fin.size else float("-inf")

    def quantile_per_day(self, q: float) -> float:
        """Quantile of per-day growth with ruined paths counted at -inf, not dropped."""
        pd_ = self.per_day
        ruined = ~np.isfinite(pd_)
        p_r = float(ruined.mean())
        if p_r >= q:
            return float("-inf")
        fin = pd_[~ruined]
        if fin.size == 0:
            return float("-inf")
        q_adj = (q - p_r) / (1.0 - p_r)
        return float(np.quantile(fin, min(max(q_adj, 0.0), 1.0)))


def simulate(paths: PosteriorPaths, schedule: Mapping[str, float] | Sequence[Mapping[str, float]]
             | np.ndarray, h_prev: Mapping[str, float] | None = None, *,
             turnover_cost: float = TURNOVER_COST, stopout_dd: float = STOPOUT_DD,
             ) -> PathOutcome:
    """Exact T-period log wealth of a schedule on every path, with ruin and stop-out flags.

    `schedule` is one book (held for the horizon) or one book per step. Ruin is a day on which
    the book's return reaches -100% of the account; a stop-out is the wealth path falling
    `stopout_dd` below its start at any step. Costs are charged as a fraction of wealth at the
    step the move is made, so log W_T = sum_t log(1 + h_t . R_t) - C.
    """
    names = paths.names
    t_n, n = paths.horizon, paths.n_sleeves
    if isinstance(schedule, np.ndarray):
        hs = np.asarray(schedule, dtype=float)
        hs = np.broadcast_to(hs, (t_n, n)).copy() if hs.ndim == 1 else hs
    elif isinstance(schedule, Mapping):
        hs = np.broadcast_to(_vec(schedule, names), (t_n, n)).copy()
    else:
        hs = np.stack([_vec(b, names) for b in schedule])
    if hs.shape != (t_n, n):
        raise ValueError(f"schedule shape {hs.shape} does not match paths {(t_n, n)}")
    prev = _vec(h_prev, names)
    cvec = _cost_vec(paths, turnover_cost)
    moves = np.abs(np.diff(np.vstack([prev[None, :], hs]), axis=0))          # (T, N)
    l1 = float(moves.sum())
    cost = float((moves @ cvec).sum())
    port = np.einsum("mtn,tn->mt", paths.r, hs)
    x = 1.0 + port
    ruined = np.any(x <= 1e-12, axis=1)
    logs = np.log(np.where(x > 1e-12, x, 1.0))
    cum = np.cumsum(logs, axis=1) - cost
    stopped = ruined | (cum.min(axis=1) <= math.log(1.0 - stopout_dd))
    logw = np.where(ruined, -np.inf, cum[:, -1])
    return PathOutcome(logw=logw, ruined=ruined, stopped=stopped, turnover_l1=l1,
                       turnover_cost=cost, horizon=t_n)


def _soft_logw(r: np.ndarray, h: np.ndarray, cost: float) -> np.ndarray:
    """Per-path T-period soft log wealth of a held book -- the optimiser's own currency."""
    val, _ = _soft_log(1.0 + r @ h)
    out: np.ndarray = val.sum(axis=1) - cost
    return out


def _smooth_objective(r: np.ndarray, h: np.ndarray, cost: float, lam_stop: float,
                      l_stop: float) -> tuple[float, np.ndarray]:
    """Mean soft log wealth minus the stop-out hinge, and its gradient; the L1 cost is not here
    because the proximal step owns it."""
    m = r.shape[0]
    val, der = _soft_log(1.0 + r @ h)                                       # (M, T)
    cum = np.cumsum(val, axis=1) - cost
    growth = float(cum[:, -1].mean())
    grad = np.einsum("mt,mtn->n", der, r) / m
    tmin = np.argmin(cum, axis=1)
    short = np.maximum(l_stop - cum[np.arange(m), tmin], 0.0)
    pen = lam_stop * float(short.mean())
    if pen > 0.0:
        # d(-pen)/dh = lam/M * sum over breaching paths of d(min cum)/dh, and the minimum's
        # derivative is the sum of the day derivatives up to the day it occurs.
        mask = (np.arange(r.shape[1])[None, :] <= tmin[:, None]) & (short > 0.0)[:, None]
        grad = grad + lam_stop * np.einsum("mt,mtn->n", der * mask, r) / m
    return growth - pen, grad


def _ascend(r: np.ndarray, h0: np.ndarray, *, cap: float, exact: bool, ub: np.ndarray,
            h_prev: np.ndarray, cvec: np.ndarray, lam_stop: float, l_stop: float,
            iterations: int, step: float) -> tuple[np.ndarray, float, np.ndarray, int, bool]:
    """Projected proximal gradient ascent on the SAA objective.

    Each step soft-thresholds the gradient move toward `h_prev` by the per-sleeve turnover price
    (the proximal operator of the L1 cost), then projects onto the heat set. Accepted only when
    the full objective -- growth, penalty and cost -- improves, so the composition of the two
    operators can at worst stall, never drift. The objective is concave on the feasible set
    (a concave function of an affine map, minus convex terms), so the stationary point it finds
    is the optimum and there is no restart strategy to get wrong.
    """
    def full(h: np.ndarray) -> tuple[float, np.ndarray]:
        cost = float(cvec @ np.abs(h - h_prev))
        v, g = _smooth_objective(r, h, cost, lam_stop, l_stop)
        return v - cost, g

    h = project_capped_simplex(h0, cap, exact=exact, upper=ub)
    obj, grad = full(h)
    lr, converged, done = step, False, 0
    for i in range(iterations):
        done = i + 1
        d = h + lr * grad - h_prev
        d = np.sign(d) * np.maximum(np.abs(d) - lr * cvec, 0.0)
        cand = project_capped_simplex(h_prev + d, cap, exact=exact, upper=ub)
        c_obj, c_grad = full(cand)
        if c_obj > obj:
            moved = float(np.abs(cand - h).sum())
            h, obj, grad = cand, c_obj, c_grad
            lr *= 1.1
            if moved < 1e-9:
                converged = True
                break
        else:
            lr *= 0.5
            if lr < 1e-10:
                converged = True
                break
    return h, obj, grad, done, converged


def _largest_scale(ok: Callable[[float], bool], lo: float, hi: float) -> float:
    """Largest s in [lo, hi] with ok(s), for a monotone `ok`; `lo` when even that fails."""
    if ok(hi):
        return hi
    if not ok(lo):
        return lo
    for _ in range(40):
        mid = 0.5 * (lo + hi)
        if ok(mid):
            lo = mid
        else:
            hi = mid
    return lo


# ------------------------------------------------------------------------------ the book
@dataclass(frozen=True)
class PosteriorBook:
    """The solved first-step book and everything a reader needs to trust or refuse it."""

    h: dict[str, float]
    total_heat: float
    #: Posterior mean log growth per day, and its 10th percentile across paths -- the robust
    #: number, the one a book has to keep positive in the futures it did not choose.
    elogw_per_day: float
    elogw_p10: float
    elogw_total: float
    p_ruin: float
    p_stopout: float
    turnover_l1: float
    turnover_cost: float
    #: Which constraint decided the total: one of `BINDINGS`.
    binding: str
    n_worlds: int
    T: int
    floor: float
    ceiling: float
    #: What growth wanted before the band was applied -- the number the floor fill and the
    #: ceiling clip are measured against, and what the missed-growth ledger bills.
    free_total_heat: float
    guard_scale: float = 1.0
    stopout_breached_at_floor: bool = False
    marginal: dict[str, float] = field(default_factory=dict)
    shrinkage: dict[str, Any] = field(default_factory=dict)
    h_prev: dict[str, float] = field(default_factory=dict)
    eps_ruin: float = EPS_RUIN
    eps_stop: float = EPS_STOP
    stopout_dd: float = STOPOUT_DD
    method: str = "niw"
    iterations: int = 0
    converged: bool = False
    note: str = ""

    def certificate(self) -> dict[str, Any]:
        """Everything above as a JSON-ready record, with the governance rules it answers to."""
        def _f(x: float) -> float | None:
            return float(x) if math.isfinite(x) else None
        return {
            "h": {k: round(v, 6) for k, v in self.h.items()},
            "total_heat": round(self.total_heat, 6),
            "elogw_per_day": _f(self.elogw_per_day), "elogw_p10": _f(self.elogw_p10),
            "elogw_total": _f(self.elogw_total),
            "annual_growth_pct": (round((math.exp(self.elogw_per_day * 252.0) - 1.0) * 100.0, 2)
                                  if math.isfinite(self.elogw_per_day) else None),
            "p_ruin": round(self.p_ruin, 6), "p_stopout": round(self.p_stopout, 6),
            "eps_ruin": self.eps_ruin, "eps_stop": self.eps_stop, "stopout_dd": self.stopout_dd,
            "turnover_l1": round(self.turnover_l1, 6),
            "turnover_cost": round(self.turnover_cost, 8),
            "binding": self.binding, "n_worlds": self.n_worlds, "T": self.T,
            "floor": self.floor, "ceiling": self.ceiling,
            "free_total_heat": round(self.free_total_heat, 6),
            "guard_scale": round(self.guard_scale, 6),
            "stopout_breached_at_floor": self.stopout_breached_at_floor,
            "marginal": {k: round(v, 8) for k, v in self.marginal.items()},
            "shrinkage": self.shrinkage, "h_prev": {k: round(v, 6) for k, v in self.h_prev.items()},
            "method": self.method, "iterations": self.iterations, "converged": self.converged,
            "note": self.note, "governance": list(RULES),
        }


def solve(ev: Sequence[SleeveEvidence] | None = None, *, h_prev: Mapping[str, float] | None = None,
          paths: PosteriorPaths | None = None, floor: float = 0.20, ceiling: float = 0.30,
          caps: Mapping[str, float] | float | None = None,
          turnover_cost: float = TURNOVER_COST, eps_ruin: float = EPS_RUIN,
          eps_stop: float = EPS_STOP, stopout_dd: float = STOPOUT_DD,
          n_paths: int = DEFAULT_N_PATHS, horizon: int = DEFAULT_HORIZON, method: str = "niw",
          cfg: WorldConfig | None = None, worlds: Worlds | None = None, seed: int = 0,
          iterations: int = 300, step: float = 0.05) -> PosteriorBook:
    """Solve for the first-step book. See the module docstring for what is being maximised.

    THE ORDER OF OPERATIONS IS THE POLICY. First the FREE solve under the ceiling alone, which
    is what growth wants and the number every later adjustment is billed against. Then the
    band: below the floor the book is filled to it along the marginal-growth ranking, above the
    ceiling it is clipped. Then the stop-out guard, which may bring a book down toward the
    floor but never through it -- if the floor itself breaches the stop-out bound that is
    reported, not silently fixed, because only the catastrophe layer may decide to run less
    than the mandate. Last the ruin guard, the one mechanism allowed below the floor, which
    names itself in `binding` when it acts.
    """
    if not (0.0 <= floor <= ceiling):
        raise ValueError(f"need 0 <= floor <= ceiling, got {floor} <= {ceiling}")
    if paths is None:
        paths = sample_paths(ev, n_paths=n_paths, horizon=horizon, method=method, cfg=cfg,
                             worlds=worlds, seed=seed)
    names = list(paths.names)
    n = len(names)
    r = paths.r
    prev = _vec(h_prev, names)
    if isinstance(caps, Mapping):
        ub = np.array([min(float(caps.get(k, ceiling)), ceiling) for k in names])
    elif caps is not None:
        ub = np.full(n, min(float(caps), ceiling))
    else:
        ub = np.full(n, ceiling)
    ub = np.maximum(ub, 0.0)
    cvec = _cost_vec(paths, turnover_cost)
    l_stop = math.log(1.0 - stopout_dd)

    def outcome(h: np.ndarray) -> PathOutcome:
        return simulate(paths, h, h_prev, turnover_cost=turnover_cost, stopout_dd=stopout_dd)

    # 1. FREE: what growth wants under the ceiling. The stop-out hinge is tightened until the
    #    hard count agrees with the smooth penalty, so the free optimum is already feasible in
    #    the stop-out sense wherever that is achievable by composition rather than by scale.
    start = prev.copy() if prev.sum() > 0 else np.full(n, max(floor, 1e-3) / n)
    lam_stop, notes, iters = 1.0, [], 0
    h_free, _, grad, it, conv = _ascend(r, start, cap=ceiling, exact=False, ub=ub, h_prev=prev,
                                        cvec=cvec, lam_stop=lam_stop, l_stop=l_stop,
                                        iterations=iterations, step=step)
    iters += it
    for _round in range(3):
        if outcome(h_free).p_stopout < eps_stop:
            break
        lam_stop *= 4.0
        h_free, _, grad, it, conv = _ascend(r, h_free, cap=ceiling, exact=False, ub=ub,
                                            h_prev=prev, cvec=cvec, lam_stop=lam_stop,
                                            l_stop=l_stop, iterations=iterations, step=step)
        iters += it
    free_total = float(h_free.sum())
    h = h_free

    # 2. THE BAND. Filled to the floor by marginal growth, clipped at the ceiling.
    if free_total < floor - 1e-9:
        if float(ub.sum()) < floor - 1e-12:
            h, binding = np.minimum(ub, ub), "cap"
            notes.append(f"per-sleeve caps total {float(ub.sum()):.4f}, cannot fund the floor "
                         f"{floor:.4f}")
        else:
            h, _, grad, it, conv = _ascend(r, h_free, cap=floor, exact=True, ub=ub, h_prev=prev,
                                           cvec=cvec, lam_stop=lam_stop, l_stop=l_stop,
                                           iterations=iterations, step=step)
            iters += it
            binding = "floor"
            notes.append(f"growth wanted {free_total:.4f}; filled to the flat floor {floor:.4f}")
    elif free_total >= ceiling - 1e-9:
        binding = "ceiling"
    elif bool(np.any(h_free >= ub - 1e-9)):
        binding = "cap"
    else:
        binding = "growth"

    # 3. THE STOP-OUT GUARD, inside the band only.
    guard_scale, breached = 1.0, False
    total = float(h.sum())
    if total > 0 and outcome(h).p_stopout >= eps_stop:
        s_lo = min(1.0, floor / total)
        s = _largest_scale(lambda s: outcome(s * h).p_stopout < eps_stop, s_lo, 1.0)
        if outcome(s * h).p_stopout >= eps_stop:
            breached = True
            notes.append(f"stop-out bound {eps_stop} breached at the floor "
                         f"(P={outcome(s * h).p_stopout:.4f}); the floor is held and reported")
        if s < 1.0 - 1e-12:
            h, guard_scale = s * h, s
            if not breached:
                binding = "stopout_guard"
                notes.append(f"stop-out guard scaled the book by {s:.4f}")

    # 4. THE RUIN GUARD -- the only mechanism allowed below the floor, and it says so.
    if outcome(h).p_ruin >= eps_ruin:
        s = _largest_scale(lambda s: outcome(s * h).p_ruin < eps_ruin, 0.0, 1.0)
        h, guard_scale, binding = s * h, guard_scale * s, "ruin_guard"
        notes.append(f"RUIN GUARD: P(ruin) >= {eps_ruin} at the mandated book; scaled by "
                     f"{s:.4f} to {float(h.sum()):.4f} total heat")

    out = outcome(h)
    cost = float(cvec @ np.abs(h - prev))
    _, grad = _smooth_objective(r, h, cost, lam_stop, l_stop)
    return PosteriorBook(
        h={k: float(v) for k, v in zip(names, h, strict=True)}, total_heat=float(h.sum()),
        elogw_per_day=out.elogw_per_day, elogw_p10=out.quantile_per_day(0.10),
        elogw_total=(out.elogw_per_day * out.horizon if math.isfinite(out.elogw_per_day)
                     else float("-inf")),
        p_ruin=out.p_ruin, p_stopout=out.p_stopout, turnover_l1=out.turnover_l1,
        turnover_cost=out.turnover_cost, binding=binding, n_worlds=paths.n_paths,
        T=paths.horizon, floor=floor, ceiling=ceiling, free_total_heat=free_total,
        guard_scale=guard_scale, stopout_breached_at_floor=breached,
        marginal={k: float(g) for k, g in sorted(zip(names, grad, strict=True),
                                                  key=lambda kv: -float(kv[1]))},
        shrinkage=dict(paths.shrinkage), h_prev={k: float(v) for k, v in
                                                 zip(names, prev, strict=True) if v > 0},
        eps_ruin=eps_ruin, eps_stop=eps_stop, stopout_dd=stopout_dd, method=paths.source,
        iterations=iters, converged=conv, note="; ".join([paths.note, *notes]).strip("; "),
    )


# ------------------------------------------------------------------------------ the contest
def compare(book_a: PosteriorBook | Mapping[str, float],
            book_b: PosteriorBook | Mapping[str, float], paths: PosteriorPaths, *,
            h_prev: Mapping[str, float] | None = None, turnover_cost: float = TURNOVER_COST,
            n_boot: int = 2000, ci: float = 0.95, seed: int = 0) -> dict[str, Any]:
    """dE[log W] per day of A over B on the SAME paths, with a paired bootstrap interval.

    PAIRED, BECAUSE THE PATHS ARE SHARED. Both books see the same futures, so the per-path
    difference is the estimator and its bootstrap is the interval; scoring the two on
    independently drawn paths would put the sampling noise of the worlds into the verdict. A
    wiped-out path is scored at the optimiser's own barrier value rather than at -inf, so the
    interval is computable, and the ruin counts are reported beside it so nobody mistakes a
    finite number for a survivable book. `beats` is `allocator_proof`'s contest semantics: the
    challenger must win by dE[log W] > 0 with the interval excluding zero.
    """
    names = paths.names
    prev = _vec(h_prev, names)
    cvec = _cost_vec(paths, turnover_cost)

    def _book(b: PosteriorBook | Mapping[str, float]) -> tuple[np.ndarray, float]:
        if isinstance(b, PosteriorBook):
            h = _vec(b.h, names)
            return h, float(b.turnover_cost)
        h = _vec(b, names)
        return h, float(cvec @ np.abs(h - prev))

    ha, ca = _book(book_a)
    hb, cb = _book(book_b)
    t_n = paths.horizon
    d = (_soft_logw(paths.r, ha, ca) - _soft_logw(paths.r, hb, cb)) / t_n
    delta = float(d.mean())
    rng = np.random.default_rng(seed)
    idx = rng.integers(0, d.size, size=(n_boot, d.size))
    means = d[idx].mean(axis=1)
    lo, hi = np.quantile(means, [(1.0 - ci) / 2.0, 1.0 - (1.0 - ci) / 2.0])
    out_a = simulate(paths, ha, h_prev, turnover_cost=turnover_cost)
    out_b = simulate(paths, hb, h_prev, turnover_cost=turnover_cost)
    return {
        "delta_elogw_per_day": delta, "ci_lo": float(lo), "ci_hi": float(hi), "ci": ci,
        "beats": bool(delta > 0.0 and lo > 0.0),
        "p_a_better": float((d > 0.0).mean()), "n_paths": int(d.size), "n_boot": int(n_boot),
        "elogw_a": out_a.elogw_per_day, "elogw_b": out_b.elogw_per_day,
        "p_ruin_a": out_a.p_ruin, "p_ruin_b": out_b.p_ruin,
        "total_heat_a": float(ha.sum()), "total_heat_b": float(hb.sum()),
    }
