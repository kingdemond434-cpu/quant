"""CONTROL VARIATES for the validation Monte Carlos (ROMAN-0972, Quant Guild directive item 30).

THE IDEA. A Monte Carlo estimate ``mean(Y)`` gets cheaper to make precise if each draw also
yields a statistic ``C`` whose expectation ``mu`` is KNOWN EXACTLY and which is correlated with
``Y``. Then ``mean(Y) - beta * (mean(C) - mu)`` has the same expectation and, at the optimal
``beta = Cov(Y, C) / Var(C)``, variance ``(1 - rho^2)`` times smaller. Nothing is assumed about
``Y``'s distribution; the only thing that must be true is ``E[C] = mu``, and every control built
here has that expectation by an identity of the resampling scheme, not by an approximation.

WHERE IT APPLIES IN THE GAUNTLET (the audit, 2026-10-06). Of everything the validation path
simulates, only RESAMPLING P-VALUES are Monte Carlo estimators of a fixed quantity:

    hansen_spa / whites_reality_check   stationary bootstrap, 1,000 draws -> APPLIES
    random_baseline.monkey_test         exposure-matched permutation, 500 draws -> APPLIES
    bar_permutation                     permutes returns: every moment is INVARIANT under it, so
                                        a moment control has zero variance -> does NOT apply
    pbo / cpcv                          exhaustive combinatorial splits, not sampled -> no MC
    stress_costs / dsr / lockbox        closed form -> no MC
    tier_s / libs.tiers.traps           seeded generators of planted cases; the estimand is the
                                        decision on each case, not a mean over draws -> no MC

THE TWO KNOWN-EXPECTATION CONTROLS.

* Stationary bootstrap (Politis & Romano 1994). Every resampled index is marginally uniform on
  the sample, so ``E*[mean(x*)] = mean(x)`` exactly; and two resampled points ``i`` apart share a
  block with probability ``q^i`` (``q = 1 - 1/mean_block``), otherwise the later one is a fresh
  uniform draw, so ``Var*(mean(x*)) = (1/T) [c(0) + 2 sum_{i>=1} (1 - i/T) q^i c(i)]`` with
  ``c`` the CIRCULAR autocovariance. Both the standardized resample mean and its square
  therefore have exactly known expectations. The test pins the formula against 40,000 draws.
* Exposure-matched permutation. ``mean(p_pi * r)`` has expectation ``mean(p) mean(r)`` and
  variance ``S_pp S_rr / (n^2 (n - 1))``; ``mean(p_pi^2 r^2)`` has ``mean(p^2) mean(r^2)``.

UNBIASED BY CONSTRUCTION, NOT ASYMPTOTICALLY. ``beta`` fitted on the same draws it corrects
makes the estimator biased by O(1/B). It is CROSS-FITTED here instead: the draws are split into
folds and each fold is corrected with the ``beta`` fitted on the others. Draws are independent,
so that ``beta`` is independent of the fold's controls and ``E[beta (C - mu)] = 0`` exactly.

THE BAR IS NEVER LOOSENED (the directive's hard rule, enforced here, not by the caller's
goodwill). ``CVEstimate.value`` is the controlled number only when its measured variance is
lower than the raw estimator's; otherwise it is the raw number. And a gate never reads it alone:
``guarded_decision`` keeps the UNCONTROLLED decision unless the controlled one is STRICTER, and
records every disagreement, so a control variate can turn a pass into a fail but never a fail
into a pass.
"""
from __future__ import annotations

import json
import os
from collections.abc import Callable, Sequence
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import numpy as np
import numpy.typing as npt

from libs.validation.bootstrap import stationary_block_indices
from libs.validation.errors import ValidationError

F = npt.NDArray[np.float64]

#: Cross-fitting folds. Two keeps each beta fitted on half the draws, which at 500-1,000 draws
#: and <= 16 controls is ample data for the regression.
DEFAULT_FOLDS = 2

#: How many of the best-looking strategies contribute controls (u and u^2 each) to a bootstrap
#: max-statistic. MEASURED, not chosen: on 8 planted strategies x 30 bootstrap seeds the true
#: variance ratio was 0.84 with the top 1, 0.77-0.91 with the top 3 and 0.66 with all 8 -- the
#: max is attained by any of them, so each one's control carries information. Beyond ~8 the
#: beta regression (2 controls per strategy, fitted on half the draws) starts to cost more noise
#: than it removes, and the measured-variance guard in `CVEstimate.used` falls back to raw.
TOP_STRATEGIES = 8

#: Where the hourly planted-truth measurement lands (written by the `evaluator_lab` leg).
REPORT_PATH = (Path(__file__).resolve().parents[2] / "desks" / "mt5" / "reports"
               / "CONTROL_VARIATES.json")


@dataclass(frozen=True)
class CVEstimate:
    """A Monte Carlo mean, raw and control-variate corrected, with both variances measured."""

    raw: float
    controlled: float
    raw_var: float           # Var(mean(Y)) estimated from the draws
    controlled_var: float    # Var of the cross-fitted corrected mean, estimated the same way
    n: int
    n_controls: int
    folds: int
    beta: tuple[float, ...]  # full-sample beta, reported only; the estimate uses cross-fitted ones

    @property
    def variance_ratio(self) -> float | None:
        """controlled_var / raw_var: below 1 means the control bought precision."""
        if not np.isfinite(self.raw_var) or self.raw_var <= 0.0:
            return None
        return float(self.controlled_var / self.raw_var)

    @property
    def used(self) -> bool:
        """The controlled number is used only where its variance is MEASURED lower."""
        r = self.variance_ratio
        return r is not None and r < 1.0 and bool(np.isfinite(self.controlled))

    @property
    def value(self) -> float:
        return self.controlled if self.used else self.raw

    def as_dict(self) -> dict[str, Any]:
        d = asdict(self)
        d["beta"] = list(self.beta)
        d.update(variance_ratio=self.variance_ratio, used=self.used, value=self.value)
        return d


def control_variate_mean(y: npt.ArrayLike, controls: npt.ArrayLike, known_means: npt.ArrayLike,
                         *, folds: int = DEFAULT_FOLDS) -> CVEstimate:
    """Cross-fitted, unbiased control-variate estimate of ``E[Y]``.

    ``y`` is ``(B,)``; ``controls`` is ``(B, k)`` (or ``(B,)`` for one control); ``known_means``
    the exact ``E[C_j]``. Draws must be i.i.d. across ``B`` (Monte Carlo draws are).
    """
    yy = np.asarray(y, dtype="float64").reshape(-1)
    cc = np.asarray(controls, dtype="float64")
    if cc.ndim == 1:
        cc = cc[:, None]
    mu = np.asarray(known_means, dtype="float64").reshape(-1)
    b = yy.size
    if cc.shape[0] != b or cc.shape[1] != mu.size:
        raise ValidationError(f"controls {cc.shape} do not match y ({b},) and means ({mu.size},)")
    if folds < 2:
        raise ValidationError("folds must be >= 2: an in-sample beta is biased")
    if not (np.all(np.isfinite(yy)) and np.all(np.isfinite(cc)) and np.all(np.isfinite(mu))):
        raise ValidationError("non-finite draw, control or known mean")
    raw = float(yy.mean())
    raw_var = float(yy.var(ddof=1) / b) if b > 1 else float("nan")
    k = cc.shape[1]
    if b < folds * (k + 2):
        nan = float("nan")
        return CVEstimate(raw, nan, raw_var, nan, b, k, folds, tuple([nan] * k))

    dev = cc - mu
    fold_of = np.arange(b) * folds // b          # contiguous folds; draws are i.i.d.
    adjusted = np.empty(b, dtype="float64")
    for f in range(folds):
        test = fold_of == f
        adjusted[test] = yy[test] - dev[test] @ _beta(yy[~test], cc[~test])
    full_beta = _beta(yy, cc)
    return CVEstimate(raw=raw, controlled=float(adjusted.mean()), raw_var=raw_var,
                      controlled_var=float(adjusted.var(ddof=1) / b), n=b, n_controls=k,
                      folds=folds, beta=tuple(float(x) for x in full_beta))


def _beta(y: F, c: F) -> F:
    """OLS slope of y on centered controls (minimum-norm when a control is degenerate)."""
    cx = c - c.mean(axis=0)
    beta, *_ = np.linalg.lstsq(cx, y - y.mean(), rcond=None)
    return np.asarray(beta, dtype="float64")


def guarded_decision(raw_pass: bool, controlled_pass: bool | None) -> dict[str, Any]:
    """The gate decision a control variate is allowed to produce: never a loosened one.

    Agreement -> that decision. Disagreement -> FAIL (the stricter side), recorded as a change in
    the direction it went. ``controlled_pass=None`` (no usable controlled estimate) -> raw.
    """
    if controlled_pass is None or controlled_pass == raw_pass:
        return {"passed": bool(raw_pass), "changed": False, "direction": None}
    if raw_pass and not controlled_pass:
        return {"passed": False, "changed": True, "direction": "stricter"}
    return {"passed": bool(raw_pass), "changed": False, "direction": "would_loosen_refused"}


# ----------------------------------------------------------------------------------------------
# Stationary-bootstrap controls (SPA / White's Reality Check)
# ----------------------------------------------------------------------------------------------

def stationary_bootstrap_mean_variance(x: Sequence[float] | F, mean_block: float) -> float:
    """EXACT ``Var*(mean(x*))`` under `bootstrap.stationary_block_indices` (circular, geometric).

    ``(1/T) [c(0) + 2 sum_{i=1}^{T-1} (1 - i/T) q^i c(i)]``, ``c`` the circular autocovariance,
    ``q = 1 - 1/mean_block``. Exact for this index process, not a large-T approximation.
    """
    a = np.asarray(x, dtype="float64").reshape(-1)
    t = a.size
    if t < 1:
        raise ValidationError("empty series")
    if mean_block < 1:
        raise ValueError("mean_block must be >= 1")
    d = a - a.mean()
    spec = np.fft.rfft(d, n=t)
    c = np.fft.irfft(spec * np.conj(spec), n=t) / t        # circular autocovariance, lags 0..T-1
    q = 1.0 - 1.0 / float(mean_block)
    if t == 1:
        return float(c[0])
    i = np.arange(1, t, dtype="float64")
    w = (1.0 - i / t) * np.power(q, i)
    return float((c[0] + 2.0 * np.sum(w * c[1:])) / t)


@dataclass(frozen=True)
class BootstrapPValue:
    method: str
    statistic: float
    p_raw: float                       # bit-identical to libs.validation.reality_check
    estimate: CVEstimate | None        # None when no strategy can carry a control
    control_strategies: tuple[int, ...]

    @property
    def p_controlled(self) -> float | None:
        if self.estimate is None or not self.estimate.used:
            return None
        return float(min(1.0, max(0.0, self.estimate.controlled)))

    def decision(self, alpha: float) -> dict[str, Any]:
        raw_pass = self.p_raw < alpha
        pc = self.p_controlled
        out = guarded_decision(raw_pass, None if pc is None else pc < alpha)
        out.update(p_raw=self.p_raw, p_controlled=pc, alpha=alpha)
        return out

    def as_dict(self) -> dict[str, Any]:
        return {"method": self.method, "statistic": self.statistic, "p_raw": self.p_raw,
                "p_controlled": self.p_controlled,
                "estimate": None if self.estimate is None else self.estimate.as_dict(),
                "control_strategies": list(self.control_strategies)}


def bootstrap_pvalue_cv(performance: F | Sequence[Sequence[float]], *, method: str = "spa",
                        n_boot: int = 1000, mean_block: float = 10, seed: int = 0,
                        top: int = TOP_STRATEGIES, folds: int = DEFAULT_FOLDS,
                        index_fn: Callable[[int, float, np.random.Generator], npt.NDArray[Any]]
                        = stationary_block_indices) -> BootstrapPValue:
    """`hansen_spa` (``method="spa"``) or `whites_reality_check` (``"white"``) with controls.

    Draws, statistic and raw p-value reproduce `libs.validation.reality_check` bit for bit (same
    RNG stream, same arithmetic order). Each draw additionally records, for the ``top`` strategies
    with the largest observed statistic, ``u = sqrt(T) (mean(f*_k) - mean(f_k)) / s_k`` and
    ``u^2``: ``E*[u] = 0`` and ``E*[u^2] = T Var*(mean(f*_k)) / s_k^2`` exactly.
    """
    f = np.asarray(performance, dtype="float64")
    if f.ndim != 2 or f.shape[1] < 1:
        raise ValidationError("performance must be a 2-D (T x N) array")
    if method not in ("spa", "white"):
        raise ValidationError(f"unknown method {method!r}")
    t_obs, _n = f.shape
    d_bar = f.mean(axis=0)
    if method == "spa":
        omega = f.std(axis=0, ddof=1)
        omega = np.where(omega <= 0, np.inf, omega)
        statistic = float(max(0.0, np.max(np.sqrt(t_obs) * d_bar / omega)))
        loglog = max(np.log(np.log(t_obs)) if t_obs > np.e else 1.0, 1e-6)
        threshold = -np.sqrt((omega**2 / t_obs) * 2.0 * loglog)
        keep = d_bar >= threshold
        observed = np.sqrt(t_obs) * d_bar / omega
        scale = omega
    else:
        statistic = float(np.sqrt(t_obs) * d_bar.max())
        observed = d_bar
        sd = f.std(axis=0, ddof=1)
        scale = np.where(sd > 0, sd, np.inf)

    usable = [int(k) for k in np.argsort(-observed, kind="stable") if np.isfinite(scale[k])]
    ks = np.asarray(usable[:max(0, int(top))], dtype=int)

    rng = np.random.default_rng(seed)
    boot_max = np.empty(n_boot, dtype="float64")
    u = np.empty((n_boot, ks.size), dtype="float64")
    resampled = np.empty_like(f)
    for b in range(n_boot):
        idx = index_fn(t_obs, mean_block, rng)
        if idx.max() >= t_obs or idx.min() < 0:
            raise ValidationError("bootstrap produced an out-of-range row index")
        np.take(f, idx, axis=0, out=resampled, mode="clip")
        f_star = resampled.mean(axis=0)
        if method == "spa":
            z = np.sqrt(t_obs) * (f_star - d_bar * keep) / omega
            boot_max[b] = max(0.0, float(z.max()))
        else:
            boot_max[b] = np.sqrt(t_obs) * (f_star - d_bar).max()
        if ks.size:
            u[b] = np.sqrt(t_obs) * (f_star[ks] - d_bar[ks]) / scale[ks]
    hits = (boot_max >= statistic).astype("float64")
    p_raw = float(np.mean(boot_max >= statistic))
    if not ks.size:
        return BootstrapPValue(method, statistic, p_raw, None, ())
    second = np.array([t_obs * stationary_bootstrap_mean_variance(f[:, k], mean_block)
                       / scale[k] ** 2 for k in ks])
    controls = np.hstack([u, u ** 2])
    means = np.concatenate([np.zeros(ks.size), second])
    est = control_variate_mean(hits, controls, means, folds=folds)
    return BootstrapPValue(method, statistic, p_raw, est, tuple(int(k) for k in ks))


# ----------------------------------------------------------------------------------------------
# Exposure-matched permutation controls (random_baseline.monkey_test)
# ----------------------------------------------------------------------------------------------

def permutation_control_moments(positions: Sequence[float] | F, returns: Sequence[float] | F
                                ) -> tuple[float, float, float]:
    """Exact ``E[m1]``, ``E[m1^2]``, ``E[m2]`` for ``m1 = mean(p_pi r)``, ``m2 = mean(p_pi^2 r^2)``
    over a uniform random permutation ``pi`` of ``p`` (``r`` fixed)."""
    p = np.asarray(positions, dtype="float64")
    r = np.asarray(returns, dtype="float64")
    n = p.size
    if n < 2 or r.size != n:
        raise ValidationError("need two equal-length series of at least 2 points")
    e1 = float(p.mean() * r.mean())
    var1 = float(np.sum((p - p.mean()) ** 2) * np.sum((r - r.mean()) ** 2) / (n * n * (n - 1)))
    e2 = float(np.mean(p * p) * np.mean(r * r))
    return e1, var1 + e1 * e1, e2


@dataclass(frozen=True)
class MonkeyPValue:
    real_statistic: float
    p_raw: float               # (#{draw >= real} + 1) / (N + 1), as monkey_test reports it
    estimate: CVEstimate       # of the exceedance PROBABILITY (no +1)
    n_baselines: int

    @property
    def p_controlled(self) -> float | None:
        if not self.estimate.used:
            return None
        pc = min(1.0, max(0.0, self.estimate.controlled))
        return float((pc * self.n_baselines + 1.0) / (self.n_baselines + 1.0))

    def as_dict(self) -> dict[str, Any]:
        return {"real_statistic": self.real_statistic, "p_raw": self.p_raw,
                "p_controlled": self.p_controlled, "n_baselines": self.n_baselines,
                "estimate": self.estimate.as_dict()}


def monkey_pvalue_cv(positions: Sequence[float] | F, market_returns: Sequence[float] | F, *,
                     rng: np.random.Generator, n_baselines: int = 1000,
                     folds: int = DEFAULT_FOLDS) -> MonkeyPValue | None:
    """`random_baseline.monkey_test`'s p-value (default Sharpe statistic) with controls.

    Consumes the RNG exactly as `monkey_test` does, so with the same seed the raw p-value is the
    one `monkey_test` reports. Returns None where `monkey_test` would be unmeasurable (non-finite
    inputs or a non-finite statistic): no control variate is offered where the raw is not.
    """
    from libs.validation.random_baseline import _sharpe, matched_random_positions

    p = np.asarray(positions, dtype="float64")
    r = np.asarray(market_returns, dtype="float64")
    if p.size != r.size or not (np.all(np.isfinite(p)) and np.all(np.isfinite(r))):
        return None
    real = float(_sharpe(p * r))
    if not np.isfinite(real):
        return None
    draws = np.empty(n_baselines, dtype="float64")
    m1 = np.empty(n_baselines, dtype="float64")
    m2 = np.empty(n_baselines, dtype="float64")
    for b in range(n_baselines):
        pp = matched_random_positions(p, rng=rng)
        x = pp * r
        draws[b] = _sharpe(x)
        m1[b] = x.mean()
        m2[b] = np.mean(x * x)
    if not np.all(np.isfinite(draws)):
        return None
    e1, e11, e2 = permutation_control_moments(p, r)
    hits = (draws >= real).astype("float64")
    est = control_variate_mean(hits, np.column_stack([m1, m1 * m1, m2]), [e1, e11, e2],
                               folds=folds)
    p_raw = float((hits.sum() + 1.0) / (n_baselines + 1.0))
    return MonkeyPValue(real, p_raw, est, n_baselines)


# ----------------------------------------------------------------------------------------------
# Planted-truth measurement (published hourly by the `evaluator_lab` leg)
# ----------------------------------------------------------------------------------------------
#
# WHAT IS MEASURED AND AGAINST WHAT. Two truths are planted and both are checked.
#   * The MONTE CARLO truth: for one data set the resampling p-value is a fixed number, and the
#     raw estimator (a mean of i.i.d. indicators) is unbiased for it by definition. Re-running
#     the SAME data under many bootstrap/permutation seeds measures each estimator's actual
#     variance, and the paired difference controlled - raw (same draws) measures the controlled
#     estimator's bias directly: its mean must be zero within its standard error.
#   * The PLANTED-EDGE truth: the data sets are simulated with a known effect (zero = null), so
#     every gate decision is known to be right or wrong. The report counts what the guarded
#     decision did against the raw one: it may only ever be stricter.

SPA_EFFECTS = (0.0, 0.15, 0.25)       # per-bar mean of the planted strategy, in noise sd
MONKEY_SKILLS = (0.0, 0.04, 0.08)     # share of bars on which the planted rule sees the sign
GATE_ALPHA = 0.05


def _planted_matrix(seed: int, effect: float, t_obs: int, n_strat: int, ar: float = 0.2) -> F:
    g = np.random.default_rng(seed)
    e = g.normal(0.0, 1.0, (t_obs, n_strat))
    f = np.empty_like(e)
    f[0] = e[0]
    for t in range(1, t_obs):
        f[t] = ar * f[t - 1] + e[t]
    f /= f.std(axis=0, ddof=1)
    f[:, 0] += effect
    return f


def _planted_monkey(seed: int, skill: float, n: int) -> tuple[F, F]:
    g = np.random.default_rng(seed)
    r = g.normal(0.0002, 0.01, n)
    pos = (g.random(n) < 0.6).astype("float64")
    sees = g.random(n) < skill
    return np.where(sees, (r > 0).astype("float64"), pos), r


def _cell(raw: list[float], ctl: list[float], used: list[bool], decisions: list[dict[str, Any]],
          truth_positive: bool) -> dict[str, Any]:
    a, c = np.asarray(raw), np.asarray(ctl)
    var_raw, var_ctl = float(a.var(ddof=1)), float(c.var(ddof=1))
    diff = c - a
    se = float(diff.std(ddof=1) / np.sqrt(diff.size)) if diff.size > 1 else float("nan")
    mean_diff = float(diff.mean())
    raw_pass = sum(bool(d["p_raw"] < d["alpha"]) for d in decisions)
    guarded = sum(bool(d["passed"]) for d in decisions)
    return {
        "truth": "genuine" if truth_positive else "null",
        "runs": int(a.size), "p_raw_mean": round(float(a.mean()), 5),
        "p_controlled_mean": round(float(c.mean()), 5),
        "mc_var_raw": var_raw, "mc_var_controlled": var_ctl,
        "variance_ratio": (round(var_ctl / var_raw, 4) if var_raw > 0 else None),
        "bias": {"mean_controlled_minus_raw": mean_diff, "se": se,
                 "t": (round(mean_diff / se, 3) if se > 0 else None)},
        "controlled_used_share": round(float(np.mean(used)), 3),
        "gate": {"raw_pass": raw_pass, "guarded_pass": guarded,
                 "changed_stricter": sum(d["direction"] == "stricter" for d in decisions),
                 "loosening_refused": sum(d["direction"] == "would_loosen_refused"
                                          for d in decisions),
                 "correct_raw": raw_pass if truth_positive else len(decisions) - raw_pass,
                 "correct_guarded": guarded if truth_positive else len(decisions) - guarded},
    }


def measure_spa(*, data_seeds: int = 4, boot_seeds: int = 10, t_obs: int = 300, n_strat: int = 8,
                n_boot: int = 400, mean_block: float = 10, base_seed: int = 9720
                ) -> dict[str, Any]:
    cells: dict[str, Any] = {}
    for effect in SPA_EFFECTS:
        for d in range(data_seeds):
            f = _planted_matrix(base_seed + 1000 * d, effect, t_obs, n_strat)
            raw, ctl, used, dec = [], [], [], []
            for s in range(boot_seeds):
                bp = bootstrap_pvalue_cv(f, n_boot=n_boot, mean_block=mean_block, seed=s)
                est = bp.estimate
                raw.append(bp.p_raw)
                ctl.append(est.controlled if est is not None and np.isfinite(est.controlled)
                           else bp.p_raw)
                used.append(bool(est is not None and est.used))
                dec.append(bp.decision(GATE_ALPHA))
            cells[f"effect={effect}|data={d}"] = _cell(raw, ctl, used, dec, effect > 0)
    return {"estimator": "hansen_spa p-value (stationary bootstrap)", "t_obs": t_obs,
            "n_strategies": n_strat, "n_boot": n_boot, "mean_block": mean_block,
            "controls": "u_k and u_k^2 for the top strategies (exact E* by the bootstrap identity)",
            "cells": cells, "summary": _summary(cells)}


def measure_monkey(*, data_seeds: int = 4, perm_seeds: int = 10, n_days: int = 750,
                   n_baselines: int = 500, base_seed: int = 9721) -> dict[str, Any]:
    cells: dict[str, Any] = {}
    for skill in MONKEY_SKILLS:
        for d in range(data_seeds):
            pos, r = _planted_monkey(base_seed + 1000 * d, skill, n_days)
            raw, ctl, used, dec = [], [], [], []
            for s in range(perm_seeds):
                m = monkey_pvalue_cv(pos, r, rng=np.random.default_rng(s),
                                     n_baselines=n_baselines)
                if m is None:
                    continue
                pc = m.p_controlled
                # the controlled exceedance probability on monkey_test's (k+1)/(N+1) scale,
                # whether or not it was used, so the bias check sees every draw
                ctl.append(float((m.estimate.controlled * n_baselines + 1.0)
                                 / (n_baselines + 1.0)))
                raw.append(m.p_raw)
                used.append(m.estimate.used)
                g = guarded_decision(m.p_raw < GATE_ALPHA, None if pc is None else pc < GATE_ALPHA)
                g.update(p_raw=m.p_raw, p_controlled=pc, alpha=GATE_ALPHA)
                dec.append(g)
            if len(raw) > 1:
                cells[f"skill={skill}|data={d}"] = _cell(raw, ctl, used, dec, skill > 0)
    return {"estimator": "monkey_test p-value (exposure-matched permutation, Sharpe)",
            "n_days": n_days, "n_baselines": n_baselines,
            "controls": "mean(p r), mean(p r)^2, mean(p^2 r^2) (exact permutation moments)",
            "cells": cells, "summary": _summary(cells)}


def _summary(cells: dict[str, Any]) -> dict[str, Any]:
    rows = [c for c in cells.values() if c["mc_var_raw"] > 0]
    vr = sum(c["mc_var_raw"] for c in rows)
    vc = sum(c["mc_var_controlled"] for c in rows)
    ts = [abs(c["bias"]["t"]) for c in cells.values() if c["bias"]["t"] is not None]
    gates = [c["gate"] for c in cells.values()]
    ratio = (vc / vr) if vr > 0 else None
    return {
        "pooled_variance_ratio": None if ratio is None else round(ratio, 4),
        "equivalent_draw_multiplier": None if not ratio else round(1.0 / ratio, 3),
        "cells_with_lower_variance": sum(1 for c in rows if c["mc_var_controlled"]
                                         < c["mc_var_raw"]),
        "cells_measurable": len(rows),
        "max_abs_bias_t": round(max(ts), 3) if ts else None,
        "gate_changed_stricter": sum(g["changed_stricter"] for g in gates),
        "gate_loosening_refused": sum(g["loosening_refused"] for g in gates),
        "correct_raw": sum(g["correct_raw"] for g in gates),
        "correct_guarded": sum(g["correct_guarded"] for g in gates),
        "runs": sum(c["runs"] for c in cells.values()),
    }


def planted_truth_report(*, quick: bool = False) -> dict[str, Any]:
    """Both arms, with a verdict per arm: ADOPTABLE only if variance is lower and bias is nil."""
    kw: dict[str, Any] = {"data_seeds": 2, "boot_seeds": 6} if quick else {}
    spa = measure_spa(**kw)
    monkey = measure_monkey(**({"data_seeds": 2, "perm_seeds": 6} if quick else {}))
    for arm in (spa, monkey):
        s = arm["summary"]
        lower = s["pooled_variance_ratio"] is not None and s["pooled_variance_ratio"] < 1.0
        # |t| < 4 over a dozen cells: a real bias of the size that matters shows as t >> 4 at
        # these run counts; the cross-fit makes the expectation exactly zero, so this is a
        # regression alarm for a wrong known-mean, not a tuning knob.
        unbiased = s["max_abs_bias_t"] is not None and s["max_abs_bias_t"] < 4.0
        arm["verdict"] = ("ADOPTABLE: variance measured lower, no detectable bias, never looser"
                          if lower and unbiased
                          else "NOT ADOPTABLE: " + ("variance not lower" if not lower
                                                    else "bias detected"))
    return {
        "generated_at": datetime.now(UTC).isoformat(timespec="seconds"),
        "row": "ROMAN-0972", "module": "libs/validation/control_variates.py",
        "rule": ("controlled estimates are used only where unbiased (cross-fitted beta) and "
                 "measured lower-variance; a gate keeps the raw decision unless the controlled "
                 "one is stricter (guarded_decision)"),
        "gate_alpha": GATE_ALPHA, "quick": quick,
        "audit": {
            "hansen_spa / whites_reality_check": "APPLIES (measured below: spa)",
            "random_baseline.monkey_test": "APPLIES (measured below: monkey)",
            "bar_permutation": "N/A: permuted returns keep every moment, a moment control "
                               "has zero variance",
            "pbo / cpcv": "N/A: exhaustive combinatorial splits, no sampling",
            "dsr / lockbox / stress_costs": "N/A: closed form",
            "tier_s trap suite": "N/A: seeded planted cases judged one by one, no MC mean",
        },
        "spa": spa, "monkey": monkey,
    }


def write_report(path: Path | None = None, *, quick: bool = False) -> dict[str, Any]:
    out = path or REPORT_PATH
    doc = planted_truth_report(quick=quick)
    out.parent.mkdir(parents=True, exist_ok=True)
    tmp = out.with_suffix(out.suffix + f".tmp{os.getpid()}")
    tmp.write_text(json.dumps(doc, indent=1, default=str), "utf-8")
    os.replace(tmp, out)
    return doc
