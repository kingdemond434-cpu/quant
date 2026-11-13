"""Extreme-value tail index per symbol and per sleeve, and what it does to growth-optimal size.

    GAP_MAP, Max-growth row (2026-11-13): "Per-symbol extreme-value tail index (Hill/POT) as a
    survival-sizing input"

WHY. Every sizing rule that reads only a mean and a standard deviation sizes for the Gaussian
middle. Daily FX, metal and index returns have tail index alpha ~ 3-5 (Gopikrishnan et al. 1999;
Danielsson & de Vries 1997): a 6-sigma day is ~10^4 times likelier than the normal says, and the
log-utility penalty of a loss is unbounded as it approaches the stake. The tail is therefore a
first-order input to growth-optimal size, not a footnote to it -- and it is two-sided: a sleeve
whose losses are thinner-tailed than its standard deviation suggests (a stopped strategy,
truncated losses) is UNDER-sized by the Gaussian rule.

WHAT IT GIVES, per return series (losses and gains separately):

    hill      Hill (1975) estimator of alpha on the k largest losses, k chosen on the most stable
              stretch of the Hill plot (the window of k with the smallest alpha variance, Drees &
              Kaufmann 1998 in spirit), with a bootstrap 90% interval
    pot       Peaks-over-threshold: a generalised Pareto fitted by maximum likelihood to the
              exceedances over the 95th loss percentile (Pickands-Balkema-de Haan), giving shape
              xi (= 1/alpha for xi > 0), scale beta, and the tail's VaR and expected shortfall at
              99% and 99.5% (McNeil & Frey 2000) -- against the Gaussian at the same levels
    kelly     the growth-optimal fraction f* that maximises E[log(1 + f r)] on the SPLICED
              distribution (empirical body, GPD tails beyond the thresholds, simulated so the
              tail is sampled far past the observed worst day), against the Gaussian f = mu/s^2.
              Their ratio is the survival-sizing input: <1 = the tail costs growth, >1 = the
              Gaussian rule was too timid.

Nothing here sizes anything. `research/survival_inputs_lab.py` measures, out of sample, whether
the ratio raises realised log growth before any consumer may read it (GROWTH_GOVERNANCE Rule 1).
"""
from __future__ import annotations

import math
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Any

import numpy as np

#: Below this many observations no tail estimate is published.
MIN_OBS = 250
POT_QUANTILE = 0.95
#: Hill plot search band, as fractions of n. Measured on Student-t(3) and t(5) samples of 3,000
#: (10 seeds): a 2-15% band reads alpha 2.3 / 3.0 (bias from the body leaking in), 1-6% reads
#: 2.75 / 3.8 at a modest variance cost. The tail is what sizing needs right, so the narrow band.
K_LO, K_HI = 0.01, 0.06
BOOT = 200
#: Spliced-distribution simulation size for the growth-optimal fraction.
SIM_N = 200_000


def hill_alpha(losses: np.ndarray, k: int) -> float:
    """Hill estimator on the k largest positive values of `losses`."""
    x = np.sort(losses[losses > 0])[::-1]
    if k < 5 or x.size <= k:
        return float("nan")
    h = float(np.mean(np.log(x[:k] / x[k])))
    return 1.0 / h if h > 0 else float("nan")


def hill_plot(losses: np.ndarray, k_lo: float | None = None, k_hi: float | None = None
              ) -> tuple[np.ndarray, np.ndarray]:
    lo = K_LO if k_lo is None else k_lo
    hi = K_HI if k_hi is None else k_hi
    x = np.sort(losses[losses > 0])[::-1]
    n = x.size
    ks = np.arange(max(10, int(lo * n)), max(11, int(hi * n)) + 1)
    ks = ks[ks < n]
    logs = np.log(x)
    cum = np.cumsum(logs)
    out = np.array([1.0 / (cum[k - 1] / k - logs[k]) if (cum[k - 1] / k - logs[k]) > 0
                    else np.nan for k in ks])
    return ks, out


def stable_k(losses: np.ndarray, window: int = 8) -> int | None:
    """The k at the centre of the window of the Hill plot with the smallest alpha variance."""
    ks, a = hill_plot(losses)
    if ks.size < window + 2:
        return int(ks[ks.size // 2]) if ks.size else None
    best, arg = float("inf"), None
    for i in range(ks.size - window):
        seg = a[i:i + window]
        if not np.isfinite(seg).all():
            continue
        v = float(np.var(seg))
        if v < best:
            best, arg = v, int(ks[i + window // 2])
    return arg


def hill(losses: np.ndarray, rng: np.random.Generator | None = None, boot: int = BOOT
         ) -> dict[str, Any]:
    losses = np.asarray(losses, dtype=float)
    losses = losses[np.isfinite(losses)]
    k = stable_k(losses)
    if k is None:
        return {"alpha": None, "k": None, "ci90": None}
    a = hill_alpha(losses, k)
    rng = rng or np.random.default_rng(0)
    bs = []
    for _ in range(boot):
        s = rng.choice(losses, size=losses.size, replace=True)
        v = hill_alpha(s, k)
        if math.isfinite(v):
            bs.append(v)
    ci = [float(np.quantile(bs, 0.05)), float(np.quantile(bs, 0.95))] if len(bs) >= 20 else None
    return {"alpha": a if math.isfinite(a) else None, "k": k, "ci90": ci}


def pot(losses: np.ndarray, q: float = POT_QUANTILE) -> dict[str, Any]:
    """GPD fit to exceedances over the q-quantile of `losses` (positive = a loss)."""
    from scipy.stats import genpareto

    x = np.asarray(losses, dtype=float)
    x = x[np.isfinite(x)]
    u = float(np.quantile(x, q))
    exc = x[x > u] - u
    if exc.size < 20 or u <= 0:
        return {"xi": None, "beta": None, "u": u, "n_exc": int(exc.size)}
    xi, _loc, beta = genpareto.fit(exc, floc=0.0)
    p_u = exc.size / x.size
    out: dict[str, Any] = {"xi": float(xi), "beta": float(beta), "u": u, "n_exc": int(exc.size),
                           "alpha_from_xi": (1.0 / xi) if xi > 0.01 else None}
    for lvl in (0.99, 0.995):
        if xi != 0:
            var = u + beta / xi * (((1 - lvl) / p_u) ** (-xi) - 1)
        else:
            var = u - beta * math.log((1 - lvl) / p_u)
        es = (var + beta - xi * u) / (1 - xi) if xi < 1 else float("inf")
        out[f"var{int(lvl * 1000)}"] = var
        out[f"es{int(lvl * 1000)}"] = es
    return out


def gaussian_tail(r: np.ndarray) -> dict[str, float]:
    from scipy.stats import norm

    mu, sd = float(np.mean(r)), float(np.std(r, ddof=1))
    out = {}
    for lvl in (0.99, 0.995):
        z = float(norm.ppf(lvl))
        out[f"var{int(lvl * 1000)}"] = -mu + sd * z
        out[f"es{int(lvl * 1000)}"] = -mu + sd * float(norm.pdf(z)) / (1 - lvl)
    return out


def spliced_sample(r: np.ndarray, n: int = SIM_N, rng: np.random.Generator | None = None,
                   q: float = POT_QUANTILE) -> np.ndarray:
    """Empirical body, GPD tails: draw from the data; a draw beyond either threshold is replaced
    by threshold + a GPD exceedance, so the simulated tail extends past the worst observed day."""
    from scipy.stats import genpareto

    rng = rng or np.random.default_rng(0)
    r = np.asarray(r, dtype=float)
    r = r[np.isfinite(r)]
    draw = rng.choice(r, size=n, replace=True)
    for sign in (-1.0, 1.0):
        side = sign * r          # positive = this tail's direction
        u = float(np.quantile(side, q))
        exc = side[side > u] - u
        if exc.size < 20 or u <= 0:
            continue
        xi, _l, beta = genpareto.fit(exc, floc=0.0)
        xi = float(min(xi, 0.9))     # an infinite-mean tail is not a sizing input; clamp it
        mask = sign * draw > u
        m = int(mask.sum())
        if m:
            draw[mask] = sign * (u + genpareto.rvs(xi, scale=beta, size=m, random_state=rng))
    return draw


def growth_optimal_fraction(sample: np.ndarray, f_max: float | None = None) -> float:
    """argmax_f mean(log(1 + f r)) over the admissible f (1 + f r > 0 for every draw), long side;
    golden-section search on the concave objective."""
    s = np.asarray(sample, dtype=float)
    worst = float(s.min())
    hi = (-0.999 / worst) if worst < 0 else (f_max or 1e3)
    if f_max is not None:
        hi = min(hi, f_max)
    if float(s.mean()) <= 0:
        return 0.0

    def g(f: float) -> float:
        return float(np.mean(np.log1p(f * s)))

    a, b = 0.0, hi
    phi = (math.sqrt(5) - 1) / 2
    c, d = b - phi * (b - a), a + phi * (b - a)
    for _ in range(80):
        if g(c) > g(d):
            b, d = d, c
            c = b - phi * (b - a)
        else:
            a, c = c, d
            d = a + phi * (b - a)
    return 0.5 * (a + b)


@dataclass
class TailReading:
    n: int
    loss_hill: dict[str, Any]
    gain_hill: dict[str, Any]
    loss_pot: dict[str, Any]
    gaussian: dict[str, float]
    es995_ratio: float | None
    kelly_gauss: float | None
    kelly_spliced: float | None
    kelly_ratio: float | None

    def as_dict(self) -> dict[str, Any]:
        return {"n": self.n, "loss_hill": self.loss_hill, "gain_hill": self.gain_hill,
                "loss_pot": self.loss_pot, "gaussian": self.gaussian,
                "es995_gpd_over_gauss": self.es995_ratio,
                "kelly_gauss": self.kelly_gauss, "kelly_spliced": self.kelly_spliced,
                "kelly_ratio": self.kelly_ratio}


def kelly_ratio(r: np.ndarray, rng: np.random.Generator | None = None,
                sim_n: int = SIM_N) -> tuple[float | None, float | None, float | None]:
    """(f_gauss, f_spliced, ratio) for a series whose mean is positive; the ratio is None when
    the series has no positive edge (no growth-optimal long fraction to compare)."""
    r = np.asarray(r, dtype=float)
    r = r[np.isfinite(r)]
    mu, var = float(r.mean()), float(r.var(ddof=1))
    if mu <= 0 or var <= 0:
        return None, None, None
    fg = mu / var
    fs = growth_optimal_fraction(spliced_sample(r, sim_n, rng))
    return fg, fs, (fs / fg) if fg > 0 else None


def measure(r: Sequence[float] | np.ndarray, *, rng: np.random.Generator | None = None,
            sim_n: int = SIM_N, boot: int = BOOT) -> TailReading | None:
    r = np.asarray(r, dtype=float)
    r = r[np.isfinite(r)]
    if r.size < MIN_OBS:
        return None
    rng = rng or np.random.default_rng(0)
    lh = hill(-r, rng, boot)
    gh = hill(r, rng, boot)
    lp = pot(-r)
    ga = gaussian_tail(r)
    es = lp.get("es995")
    ratio = (es / ga["es995"]) if es is not None and math.isfinite(es) and ga["es995"] > 0 \
        else None
    fg, fs, kr = kelly_ratio(r, rng, sim_n)
    return TailReading(n=int(r.size), loss_hill=lh, gain_hill=gh, loss_pot=lp, gaussian=ga,
                       es995_ratio=ratio, kelly_gauss=fg, kelly_spliced=fs, kelly_ratio=kr)
