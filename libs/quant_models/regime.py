"""Regime / event-state model (ROMAN-0806): a Markov-switching Gaussian return model built on the
desk's own `libs.regime.hmm.GaussianHMM`, conditioned on its FILTERING posterior
P(state_t | r_1..t) -- never the smoothed one, which would read the future.

Per regime s: daily mean mu_s and variance var_s; the regime path is a Markov chain with the fitted
transition matrix started from the filtered posterior at as_of.

  vol_forecast  the propagated regime mixture: per day k the variance of the mixture under
                p_k = p_now P^k, averaged over the horizon.
  tail_prob     mixture over simulated regime paths of the conditional Gaussian two-sided tail.
  price         Hull-White mixing: E[BS(sigma_bar(path))] over simulated regime paths (exact for
                regime-driven variance independent of the return shocks), risk-neutral drift.
"""
from __future__ import annotations

import math
from dataclasses import dataclass

import numpy as np

from libs.quant_models.base import YEAR_DAYS, MarketData, OptionSpec, StochasticModel
from libs.quant_models.numerics import FArr, bs_price, normals
from libs.regime.hmm import GaussianHMM

TRADING_YEAR = 252.0
SCALE = 100.0   # the HMM is fitted on percent returns: better conditioned EM


@dataclass(frozen=True)
class RegimeParams:
    means: tuple[float, ...] = (0.0, 0.0)            # daily log-return means
    variances: tuple[float, ...] = (5e-5, 4e-4)      # daily variances
    transmat: tuple[tuple[float, ...], ...] = ((0.98, 0.02), (0.05, 0.95))
    posterior: tuple[float, ...] = (0.5, 0.5)        # filtered P(state | data to as_of)
    n_states: int = 2


def fit_hmm(returns: FArr, n_states: int = 2, n_iter: int = 30, seed: int = 0
            ) -> GaussianHMM | None:
    r = np.asarray(returns, dtype=np.float64)
    r = r[np.isfinite(r)]
    if r.size < 120:
        return None
    return GaussianHMM(n_states, n_iter=n_iter, seed=seed).fit(r * SCALE)


def params_from_hmm(hmm: GaussianHMM, r: FArr, window: int = 250) -> RegimeParams:
    """Sort states by variance (state 0 calm) and attach the filtered posterior at the end."""
    order = np.argsort(hmm.vars[:, 0])
    post = hmm.filter_posterior(np.asarray(r[-window:], dtype=np.float64) * SCALE)[-1]
    tm = hmm.transmat[np.ix_(order, order)]
    return RegimeParams(
        means=tuple(float(hmm.means[i, 0]) / SCALE for i in order),
        variances=tuple(float(hmm.vars[i, 0]) / SCALE ** 2 for i in order),
        transmat=tuple(tuple(float(v) for v in row) for row in tm),
        posterior=tuple(float(post[i]) for i in order),
        n_states=hmm.k)


class RegimeHMM(StochasticModel):
    name = "regime_hmm"
    measure = "P"
    params: RegimeParams
    mc_paths = 4000

    def __init__(self, params: RegimeParams | None = None) -> None:
        self.params = params or RegimeParams()
        self._hmm: GaussianHMM | None = None

    def calibrate(self, data: MarketData) -> RegimeHMM:
        r = np.asarray(data.returns, dtype=np.float64)
        hmm = fit_hmm(r)
        if hmm is not None:
            self._hmm = hmm
            self.params = params_from_hmm(hmm, r[np.isfinite(r)])
        return self

    def refilter(self, returns: FArr) -> RegimeHMM:
        """Keep the fitted HMM, update only the filtered posterior (the cheap daily step)."""
        if self._hmm is None:
            return self
        r = np.asarray(returns, dtype=np.float64)
        out = RegimeHMM(params_from_hmm(self._hmm, r[np.isfinite(r)]))
        out._hmm = self._hmm
        return out

    # ---------------------------------------------------------------- regime algebra
    def _arrays(self) -> tuple[FArr, FArr, FArr, FArr]:
        p = self.params
        return (np.asarray(p.means), np.asarray(p.variances), np.asarray(p.transmat),
                np.asarray(p.posterior))

    def regime_probs(self, n_days: int) -> FArr:
        """(n_days, k): P(state at day k+1 | as_of)."""
        _, _, tm, post = self._arrays()
        out = np.empty((n_days, tm.shape[0]))
        q = post
        for i in range(n_days):
            q = q @ tm
            out[i] = q
        return out

    def vol_forecast(self, horizon_days: float) -> float:
        n = max(1, round(horizon_days * TRADING_YEAR / YEAR_DAYS))
        mu, var, _, _ = self._arrays()
        probs = self.regime_probs(n)
        m = probs @ mu
        per_day = probs @ (var + mu * mu) - m * m
        return math.sqrt(float(per_day.mean()) * TRADING_YEAR)

    def regime_paths(self, n_paths: int, n_days: int, seed: int) -> np.ndarray:
        _, _, tm, post = self._arrays()
        rng = np.random.default_rng(seed)
        cum = np.cumsum(tm, axis=1)
        state = rng.choice(tm.shape[0], size=n_paths, p=post / post.sum())
        out = np.empty((n_paths, n_days), dtype=np.int64)
        for i in range(n_days):
            u = rng.random(n_paths)
            state = np.minimum((u[:, None] > cum[state]).sum(axis=1), tm.shape[0] - 1)
            out[:, i] = state
        return out

    def tail_prob(self, threshold_return: float, horizon_days: float) -> float:
        from scipy.special import ndtr
        n = max(1, round(horizon_days * TRADING_YEAR / YEAR_DAYS))
        mu, var, _, _ = self._arrays()
        s = self.regime_paths(self.mc_paths, n, self.seed)
        m, v = mu[s].sum(axis=1), var[s].sum(axis=1)
        sd = np.sqrt(v)
        p = (1.0 - ndtr((threshold_return - m) / sd)) + ndtr((-threshold_return - m) / sd)
        return float(p.mean())

    def price(self, spec: OptionSpec) -> float:
        n = max(1, round(spec.expiry_years * TRADING_YEAR))
        _, var, _, _ = self._arrays()
        s = self.regime_paths(self.mc_paths, n, self.seed)
        vols = np.sqrt(var[s].sum(axis=1) / spec.expiry_years)
        return float(np.mean([bs_price(spec.kind, spec.spot, spec.strike, spec.expiry_years,
                                       spec.rate, spec.div, float(v)) for v in vols]))

    def has_fast_price(self) -> bool:
        return False

    def shift_vol(self, dvol: float) -> RegimeHMM:
        p = self.params
        new = []
        for v in p.variances:
            vol = math.sqrt(v * TRADING_YEAR)
            new.append((max(vol + dvol, 1e-4) ** 2) / TRADING_YEAR)
        return self.copy_with(variances=tuple(new))

    def simulate(self, n_paths: int, n_steps: int, horizon: float, seed: int,
                 spot: float = 1.0, rate: float = 0.0, div: float = 0.0,
                 antithetic: bool = False) -> FArr:
        """Daily regime-switching log returns under the risk-neutral drift, sampled to n_steps."""
        from libs.quant_models.garch import subsample_paths
        n_days = max(1, round(horizon * TRADING_YEAR))
        _, var, _, _ = self._arrays()
        s = self.regime_paths(n_paths, n_days, seed)
        z = normals(np.random.default_rng(seed + 1), n_paths, n_days, antithetic)
        h = var[s]
        daily = (rate - div) / TRADING_YEAR - 0.5 * h + np.sqrt(h) * z
        return subsample_paths(spot, np.asarray(daily, dtype=np.float64), n_steps)
