"""Black-Litterman challengers: a CHALLENGER, never primary (mandate 2026-10-06, D15).

    "Black-Litterman: challenger, never primary; robust E[log W] stays sovereign. Challengers:
     A existing allocator; B + BL equilibrium prior; C + confidence-weighted certified strategy
     views; D + Jev/world-state views; E BL only; F MVO baseline; G shuffled-view control."

Jev was dropped (zuck 2026-11-11 10:05Z, "replicated without it"): view D reads the desk's OWN
world-state probabilities instead -- the HMM regime posterior the allocator already sizes against
(`pf_allocator.regime_state`: a label per day and the forward regime mix) and the macro kernel
(`SleeveEvidence.macro_w`: how much each past day's macro state resembled today's).

THE ARITHMETIC, in each sleeve's own unit (R per day, the unit `SleeveEvidence.daily_r` is in):

    Sigma      shrunk sample covariance (`challengers._cov`, the estimator every challenger uses)
    pi         equilibrium prior, reverse-optimised from a REFERENCE book w_ref (the incumbent book,
               equal heat when there is none): pi = delta * Sigma * w_ref, with delta the risk
               aversion that book implies on the sample, delta = max(w'mu, 0) / (w' Sigma w).
               Nothing is chosen: the prior says "the book we hold is efficient".
    tau        1 / T, the textbook "uncertainty of the prior mean scales with the sample".
    views      absolute, one row per sleeve per view family, P = I:
               C  certified-strategy view: Q = sample mean, Omega = var/n x (1 + ln n_trials),
                  so a sleeve selected out of many trials is believed less (selection, not noise).
               D  world-state view: Q = sum_s p(s) mean_i|s over the regime mix; Omega = the
                  variance of that mixture estimate, sum_s p(s)^2 var_i|s / n_i|s. And a macro
                  view: the macro-kernel-weighted mean with Omega = var / n_eff, n_eff the kernel's
                  effective sample (sum w)^2 / sum w^2.
    posterior  mu_BL = [(tau Sigma)^-1 + P' Omega^-1 P]^-1 [(tau Sigma)^-1 pi + P' Omega^-1 Q]

B, C, D hand the robust E[log W] optimiser evidence whose daily returns are LOCATION-SHIFTED so
each sleeve's mean is mu_BL (the distribution's shape, tails and co-movement are untouched): "the
existing allocator plus a BL belief". E is the textbook BL book, (delta Sigma)^-1 mu_BL, long only.
G is D with the views' Q PERMUTED across sleeves (fixed seed): if G scores like D, D's views carry
no information and D earns nothing.

Every book is rescaled to the same total heat by the caller, so the comparison is allocation,
never leverage. This module computes books; it never trades and holds no authority.
"""
from __future__ import annotations

import dataclasses
import math
from collections.abc import Callable, Mapping, Sequence
from typing import Any

import numpy as np

from libs.portfolio.challengers import _cov, _scale, mean_variance

#: The seven arms of D15, in the mandate's order.
ARMS = ("A_allocator", "B_bl_prior", "C_bl_certified_views", "D_bl_world_state_views",
        "E_bl_only", "F_mvo", "G_shuffled_views")
#: Minimum days a regime state needs in a sleeve's history before its conditional mean is a view.
#: DERIVATION: below ~20 observations a sample mean's standard error is over a fifth of the
#: sleeve's daily vol, the same floor `sample_worlds` uses before it trusts a regime pool.
MIN_STATE_DAYS = 20
#: Seed of the shuffled-view control. Fixed so the control is reproducible pass to pass.
SHUFFLE_SEED = 20261006


def _matrix(ev: Sequence[Any]) -> tuple[np.ndarray, list[str], int]:
    obs = min(int(np.asarray(e.daily_r).size) for e in ev)
    m = np.stack([np.nan_to_num(np.asarray(e.daily_r[-obs:], dtype=float), nan=0.0)
                  for e in ev], axis=1)
    return m, [str(e.name) for e in ev], obs


def equilibrium_prior(m: np.ndarray, cov: np.ndarray,
                      w_ref: np.ndarray) -> tuple[np.ndarray, float]:
    """pi = delta Sigma w_ref, with delta implied by the reference book on the sample."""
    w = np.clip(np.nan_to_num(w_ref, nan=0.0), 0.0, None)
    if float(w.sum()) <= 0:
        w = np.ones(m.shape[1])
    w = w / float(w.sum())
    var = float(w @ cov @ w)
    ret = float(m.mean(axis=0) @ w)
    delta = max(ret, 0.0) / var if var > 0 else 0.0
    return delta * (cov @ w), delta


@dataclasses.dataclass(frozen=True)
class Views:
    """Absolute views stacked as rows: P (k x n), Q (k), Omega diagonal (k)."""
    P: np.ndarray
    Q: np.ndarray
    omega: np.ndarray
    names: tuple[str, ...]

    @staticmethod
    def empty(n: int) -> Views:
        return Views(np.zeros((0, n)), np.zeros(0), np.zeros(0), ())

    def stack(self, other: Views) -> Views:
        return Views(np.vstack([self.P, other.P]), np.concatenate([self.Q, other.Q]),
                     np.concatenate([self.omega, other.omega]), self.names + other.names)


def certified_views(ev: Sequence[Any], m: np.ndarray) -> Views:
    """C: each certified sleeve's own mean, believed in proportion to its sample and deflated by
    how many candidates were searched to find it."""
    n_obs, n = m.shape
    var = m.var(axis=0, ddof=1) if n_obs > 1 else np.zeros(n)
    trials = np.array([max(int(getattr(e, "n_trials", 1) or 1), 1) for e in ev], dtype=float)
    omega = var / max(n_obs, 1) * (1.0 + np.log(trials))
    keep = omega > 0
    P = np.eye(n)[keep]
    return Views(P, m.mean(axis=0)[keep], omega[keep],
                 tuple(f"C:{e.name}" for e, k in zip(ev, keep, strict=True) if k))


def regime_views(ev: Sequence[Any], m: np.ndarray, labels: Sequence[str],
                 probs: Mapping[str, float]) -> Views:
    """D (regime half): the sleeve's mean under the desk's forward regime mix."""
    n_obs, n = m.shape
    lab = np.array([str(x) for x in list(labels)[-n_obs:]]) if len(labels) >= n_obs else None
    p = {str(k): float(v) for k, v in (probs or {}).items() if float(v) > 0}
    if lab is None or not p:
        return Views.empty(n)
    tot = sum(p.values())
    p = {k: v / tot for k, v in p.items()}
    rows, qs, oms, nm = [], [], [], []
    for j, e in enumerate(ev):
        q = om = 0.0
        covered = 0.0
        for s, ps in p.items():
            r = m[lab == s, j]
            if r.size < MIN_STATE_DAYS:
                continue
            q += ps * float(r.mean())
            om += ps * ps * float(r.var(ddof=1)) / r.size
            covered += ps
        if covered <= 0 or om <= 0:
            continue
        # Renormalise over the states the sleeve has history in; the uncovered mass widens Omega
        # (a view on part of the mix is believed less), never narrows it.
        rows.append(np.eye(n)[j])
        qs.append(q / covered)
        oms.append(om / covered ** 2 / covered)
        nm.append(f"D:regime:{e.name}")
    if not rows:
        return Views.empty(n)
    return Views(np.array(rows), np.array(qs), np.array(oms), tuple(nm))


def macro_views(ev: Sequence[Any], m: np.ndarray) -> Views:
    """D (macro half): the macro-kernel-weighted mean, believed by the kernel's effective n."""
    n_obs, n = m.shape
    rows, qs, oms, nm = [], [], [], []
    for j, e in enumerate(ev):
        w = np.asarray(getattr(e, "macro_w", ()), dtype=float)
        if w.size < n_obs:
            continue
        w = np.clip(np.nan_to_num(w[-n_obs:], nan=0.0), 0.0, None)
        sw, sw2 = float(w.sum()), float((w * w).sum())
        if sw <= 0 or sw2 <= 0:
            continue
        n_eff = sw * sw / sw2
        if n_eff < MIN_STATE_DAYS:
            continue
        r = m[:, j]
        mu_w = float((w * r).sum() / sw)
        var_w = float((w * (r - mu_w) ** 2).sum() / sw)
        if var_w <= 0:
            continue
        rows.append(np.eye(n)[j])
        qs.append(mu_w)
        oms.append(var_w / n_eff)
        nm.append(f"D:macro:{e.name}")
    if not rows:
        return Views.empty(n)
    return Views(np.array(rows), np.array(qs), np.array(oms), tuple(nm))


def shuffled(v: Views, seed: int = SHUFFLE_SEED) -> Views:
    """G: the same views with Q permuted across rows -- same numbers, information destroyed."""
    if v.Q.size < 2:
        return v
    perm = np.random.default_rng(seed).permutation(v.Q.size)
    return dataclasses.replace(v, Q=v.Q[perm], names=tuple(f"G:{x}" for x in v.names))


def posterior(pi: np.ndarray, cov: np.ndarray, tau: float, views: Views) -> np.ndarray:
    """The BL posterior mean. No views returns the prior unchanged."""
    if views.Q.size == 0:
        return pi.copy()
    ts_inv = np.linalg.inv(tau * cov)
    om_inv = np.diag(1.0 / np.maximum(views.omega, 1e-18))
    a = ts_inv + views.P.T @ om_inv @ views.P
    b = ts_inv @ pi + views.P.T @ om_inv @ views.Q
    out: np.ndarray = np.linalg.solve(a, b)
    return out


def shifted(ev: Sequence[Any], mu: np.ndarray, obs: int) -> list[Any]:
    """Evidence whose mean over the common window is `mu`: a location shift, shape untouched."""
    out = []
    for e, target in zip(ev, mu, strict=True):
        r = np.asarray(e.daily_r, dtype=float)
        cur = float(np.nan_to_num(r[-obs:], nan=0.0).mean())
        out.append(dataclasses.replace(e, daily_r=r + (float(target) - cur)))
    return out


def bl_only_book(mu: np.ndarray, cov: np.ndarray, delta: float, names: list[str],
                 total: float) -> dict[str, float]:
    """E: the textbook BL portfolio (delta Sigma)^-1 mu_BL, long only, at the budget."""
    w = np.linalg.solve(max(delta, 1e-12) * cov, mu)
    return _scale(np.clip(w, 0.0, None), names, total)


@dataclasses.dataclass
class Beliefs:
    """Everything the arms are built from, kept so the report can show its working."""
    names: list[str]
    obs: int
    tau: float
    delta: float
    pi: np.ndarray
    sample_mu: np.ndarray
    mu: dict[str, np.ndarray]
    n_views: dict[str, int]


def beliefs(ev: Sequence[Any], *, w_ref: Mapping[str, float] | None = None,
            regime_labels: Sequence[str] = (), regime_probs: Mapping[str, float] | None = None,
            ) -> Beliefs:
    m, names, obs = _matrix(ev)
    cov = _cov(m)
    ref = np.array([float((w_ref or {}).get(n, 0.0)) for n in names])
    pi, delta = equilibrium_prior(m, cov, ref)
    tau = 1.0 / max(obs, 1)
    c = certified_views(ev, m)
    d = regime_views(ev, m, regime_labels, regime_probs or {}).stack(macro_views(ev, m))
    mu = {"B": pi.copy(), "C": posterior(pi, cov, tau, c),
          "D": posterior(pi, cov, tau, c.stack(d)),
          "G": posterior(pi, cov, tau, c.stack(shuffled(d)))}
    return Beliefs(names, obs, tau, delta, pi, m.mean(axis=0), mu,
                   {"C": int(c.Q.size), "D": int(d.Q.size), "G": int(d.Q.size)})


def arm_books(ev: Sequence[Any], total: float,
              solve: Callable[[Sequence[Any]], Mapping[str, float]], *,
              w_ref: Mapping[str, float] | None = None, regime_labels: Sequence[str] = (),
              regime_probs: Mapping[str, float] | None = None,
              ) -> tuple[dict[str, dict[str, float]], Beliefs]:
    """All seven D15 books at `total` heat. `solve(evidence)` is the desk's allocator (A, and the
    base of B/C/D/G). An arm that cannot be built is left out, never faked."""
    b = beliefs(ev, w_ref=w_ref, regime_labels=regime_labels, regime_probs=regime_probs)
    m, names, _obs = _matrix(ev)
    cov = _cov(m)
    books: dict[str, dict[str, float]] = {}

    def _try(arm: str, fn: Callable[[], Mapping[str, float]]) -> None:
        try:
            book = {str(k): float(v) for k, v in fn().items()}
        except (ValueError, np.linalg.LinAlgError, ZeroDivisionError, FloatingPointError):
            return
        if book and all(math.isfinite(v) for v in book.values()):
            books[arm] = book

    _try("A_allocator", lambda: solve(ev))
    _try("B_bl_prior", lambda: solve(shifted(ev, b.mu["B"], b.obs)))
    _try("C_bl_certified_views", lambda: solve(shifted(ev, b.mu["C"], b.obs)))
    if b.n_views["D"]:
        _try("D_bl_world_state_views", lambda: solve(shifted(ev, b.mu["D"], b.obs)))
        _try("G_shuffled_views", lambda: solve(shifted(ev, b.mu["G"], b.obs)))
    _try("E_bl_only", lambda: bl_only_book(b.mu["D" if b.n_views["D"] else "C"], cov,
                                           b.delta, names, total))
    _try("F_mvo", lambda: mean_variance(ev, total))
    return books, b


# ------------------------------------------------------------------------------- book metrics

def book_metrics(heat: Mapping[str, float], realized: np.ndarray, names: Sequence[str],
                 *, prev: Mapping[str, float] | None = None, cost_r: float = 0.0,
                 alpha: float = 0.10) -> dict[str, float]:
    """The D15 measurement list on a REALISED path: E[log W], Sharpe, max DD, tail, turnover,
    cost, concentration. `realized` is days x sleeves in R (the unit heat multiplies)."""
    h = np.array([float(heat.get(n, 0.0)) for n in names])
    port = np.nan_to_num(realized, nan=0.0) @ h
    ruined = bool(np.any(port <= -1.0))
    lg = np.log1p(np.clip(port, -1 + 1e-12, None))
    eq = np.cumsum(lg)
    peak = np.maximum.accumulate(np.concatenate([[0.0], eq]))[1:]
    dd = float(np.max(peak - eq)) if eq.size else 0.0
    k = max(1, int(alpha * port.size)) if port.size else 1
    tot = float(h.sum())
    turnover = (float(sum(abs(float(heat.get(n, 0.0)) - float((prev or {}).get(n, 0.0)))
                          for n in set(names) | set(prev or {})))
                if prev is not None else float("nan"))
    sd = float(port.std(ddof=1)) if port.size > 1 else 0.0
    return {"log_growth": float("-inf") if ruined else float(lg.sum()),
            "mean_log_growth": float(lg.mean()) if lg.size else 0.0,
            "sharpe_daily": float(port.mean() / sd) if sd > 0 else 0.0,
            "max_drawdown_log": dd,
            "cvar_daily": float(np.sort(port)[:k].mean()) if port.size else 0.0,
            "turnover": turnover,
            "turnover_cost_r": turnover * cost_r if math.isfinite(turnover) else float("nan"),
            "hhi": float(((h / tot) ** 2).sum()) if tot > 0 else 0.0,
            "n_funded": int((h > 1e-9).sum())}
