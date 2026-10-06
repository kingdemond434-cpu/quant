"""Shared pricing numerics: the normal law, Black-Scholes closed forms, implied-vol inversion,
characteristic-function pricing (Lewis 2001) and CF tail probabilities, and the Monte Carlo
estimator with control variates and antithetics.

ONE MODULE FOR THE SHARED MATH (the no-second-lane law): every model in `libs.quant_models`
prices through these functions, so a formula defect is fixed once.

SEEDED DEFECTS THIS MODULE IS TESTED AGAINST (card QG-QFIN-005, Q-Fin MIT, ideas only -- no code
was ported): gamma must use the normal PDF, never the CDF; the put must be
K e^{-rT} N(-d2) - S e^{-qT} N(-d1); a Monte Carlo variance step must use sigma^2, never
sqrt(sigma). `tests/research/test_quant_models_invariants.py` fails on each of them.
"""
from __future__ import annotations

import math
from collections.abc import Callable, Sequence
from dataclasses import dataclass

import numpy as np
import numpy.typing as npt
from scipy.special import ndtr

FArr = npt.NDArray[np.float64]
CArr = npt.NDArray[np.complex128]
#: A characteristic function of X_T = ln(S_T / S_0) - (r - q) T (the MARTINGALE log return,
#: E[e^X] = 1), evaluated on a complex array of arguments.
CharFn = Callable[[CArr], CArr]

SQRT_2PI = math.sqrt(2.0 * math.pi)
IV_LO, IV_HI = 1e-4, 5.0


# ============================================================================== the normal law
def norm_pdf(x: float) -> float:
    return math.exp(-0.5 * x * x) / SQRT_2PI


def norm_cdf(x: float) -> float:
    return float(ndtr(x))


# ============================================================================== Black-Scholes
def _d1d2(spot: float, strike: float, t: float, rate: float, div: float,
          vol: float) -> tuple[float, float]:
    sd = vol * math.sqrt(t)
    d1 = (math.log(spot / strike) + (rate - div + 0.5 * vol * vol) * t) / sd
    return d1, d1 - sd


def _intrinsic(kind: str, spot: float, strike: float, t: float, rate: float,
               div: float) -> float:
    fwd_s, df_k = spot * math.exp(-div * t), strike * math.exp(-rate * t)
    return max(fwd_s - df_k, 0.0) if kind == "call" else max(df_k - fwd_s, 0.0)


def bs_price(kind: str, spot: float, strike: float, t: float, rate: float, div: float,
             vol: float) -> float:
    """Black-Scholes-Merton price with continuous dividend yield `div`."""
    if t <= 0 or vol <= 0:
        return _intrinsic(kind, spot, strike, max(t, 0.0), rate, div)
    d1, d2 = _d1d2(spot, strike, t, rate, div, vol)
    dq, dr = math.exp(-div * t), math.exp(-rate * t)
    if kind == "call":
        return spot * dq * norm_cdf(d1) - strike * dr * norm_cdf(d2)
    return strike * dr * norm_cdf(-d2) - spot * dq * norm_cdf(-d1)


def bs_greeks(kind: str, spot: float, strike: float, t: float, rate: float, div: float,
              vol: float) -> dict[str, float]:
    """Closed-form delta, gamma, vega (per unit vol), theta (per year, dV/dt) and rho."""
    d1, d2 = _d1d2(spot, strike, t, rate, div, vol)
    dq, dr = math.exp(-div * t), math.exp(-rate * t)
    pdf1, sq = norm_pdf(d1), math.sqrt(t)
    gamma = dq * pdf1 / (spot * vol * sq)          # the PDF, never the CDF (QG-QFIN-005)
    vega = spot * dq * pdf1 * sq
    common = -spot * dq * pdf1 * vol / (2.0 * sq)
    if kind == "call":
        delta = dq * norm_cdf(d1)
        theta = common + div * spot * dq * norm_cdf(d1) - rate * strike * dr * norm_cdf(d2)
        rho = strike * t * dr * norm_cdf(d2)
    else:
        delta = -dq * norm_cdf(-d1)
        theta = common - div * spot * dq * norm_cdf(-d1) + rate * strike * dr * norm_cdf(-d2)
        rho = -strike * t * dr * norm_cdf(-d2)
    return {"delta": delta, "gamma": gamma, "vega": vega, "theta": theta, "rho": rho}


def implied_vol(price: float, kind: str, spot: float, strike: float, t: float, rate: float,
                div: float) -> float | None:
    """Brent inversion of the BS price on [IV_LO, IV_HI]. None outside the no-arbitrage bounds
    (an unmeasurable IV is None, never a clipped number)."""
    from scipy.optimize import brentq
    if not (t > 0 and math.isfinite(price)):
        return None
    lo_p = _intrinsic(kind, spot, strike, t, rate, div)
    hi_p = spot * math.exp(-div * t) if kind == "call" else strike * math.exp(-rate * t)
    if price <= lo_p + 1e-14 or price >= hi_p:
        return None
    f_lo = bs_price(kind, spot, strike, t, rate, div, IV_LO) - price
    f_hi = bs_price(kind, spot, strike, t, rate, div, IV_HI) - price
    if f_lo > 0 or f_hi < 0:
        return None
    return float(brentq(lambda v: bs_price(kind, spot, strike, t, rate, div, v) - price,
                        IV_LO, IV_HI, xtol=1e-12, rtol=1e-12, maxiter=200))


# ============================================================================== CF pricing
def _gl_grid(upper: float, panel: float = 2.0, order: int = 16) -> tuple[FArr, FArr]:
    """Composite Gauss-Legendre nodes and weights on (0, upper]."""
    x, w = np.polynomial.legendre.leggauss(order)
    n = max(8, math.ceil(upper / panel))
    edges = np.linspace(0.0, upper, n + 1)
    a, b = edges[:-1, None], edges[1:, None]
    nodes = (0.5 * (b - a) * x[None, :] + 0.5 * (a + b)).ravel()
    weights = (0.5 * (b - a) * w[None, :]).ravel()
    return np.asarray(nodes, dtype=np.float64), np.asarray(weights, dtype=np.float64)


def cf_upper(total_var: float) -> float:
    """Truncation point of the Fourier integral: the integrand decays at least like
    exp(-0.5 w u^2) for total variance w, so take u where that is e^-40, bounded."""
    w = max(total_var, 1e-6)
    return float(min(max(math.sqrt(80.0 / w), 60.0), 6000.0))


def cf_upper_adaptive(cf: CharFn, total_var: float, shift: complex = 0.0) -> float:
    """`cf_upper`, then doubled until |phi(u + shift)| < 1e-13 at the cut: a stochastic-vol CF
    decays exponentially rather than like a Gaussian, so the Gaussian guess can be too short."""
    upper = cf_upper(total_var)
    with np.errstate(over="ignore", invalid="ignore", divide="ignore"):
        for _ in range(6):
            tail = np.abs(cf(np.asarray([upper + shift], dtype=np.complex128)))[0]
            if not math.isfinite(float(tail)) or float(tail) < 1e-13 or upper >= 6000.0:
                break
            upper = min(2.0 * upper, 6000.0)
    return upper


def lewis_call(cf: CharFn, spot: float, strikes: FArr, t: float, rate: float, div: float,
               total_var: float) -> FArr:
    """Lewis (2001) call prices for every strike from the martingale log-return CF:

        C = S e^{-qT} - sqrt(S K) e^{-(r+q)T/2} / pi * int_0^inf Re[e^{iu k} phi(u - i/2)]
            / (u^2 + 1/4) du,      k = ln(S/K) + (r - q) T.
    """
    u, w = _gl_grid(cf_upper_adaptive(cf, total_var, -0.5j))
    with np.errstate(over="ignore", invalid="ignore", divide="ignore"):
        phi = cf(np.asarray(u - 0.5j, dtype=np.complex128))
        k = np.log(spot / strikes) + (rate - div) * t
        integrand = np.real(np.exp(1j * np.outer(k, u)) * phi[None, :]) / (u * u + 0.25)
        integrand = np.where(np.isfinite(integrand), integrand, 0.0)
    integral = integrand @ w
    pref = np.sqrt(spot * strikes) * math.exp(-0.5 * (rate + div) * t) / math.pi
    calls = spot * math.exp(-div * t) - pref * integral
    lo = np.maximum(spot * math.exp(-div * t) - strikes * math.exp(-rate * t), 0.0)
    return np.asarray(np.clip(calls, lo, spot * math.exp(-div * t)), dtype=np.float64)


def cf_price(cf: CharFn, kind: str, spot: float, strike: float, t: float, rate: float,
             div: float, total_var: float) -> float:
    call = float(lewis_call(cf, spot, np.asarray([strike], dtype=np.float64), t, rate, div,
                            total_var)[0])
    if kind == "call":
        return call
    return call - spot * math.exp(-div * t) + strike * math.exp(-rate * t)   # parity


def cf_cdf(cf: CharFn, x: FArr, total_var: float) -> FArr:
    """P(X <= x) for the martingale log return X by Gil-Pelaez inversion."""
    u, w = _gl_grid(cf_upper_adaptive(cf, total_var), panel=1.0)
    with np.errstate(over="ignore", invalid="ignore", divide="ignore"):
        phi = cf(np.asarray(u + 0j, dtype=np.complex128))
        integrand = np.imag(np.exp(-1j * np.outer(x, u)) * phi[None, :]) / u
        integrand = np.where(np.isfinite(integrand), integrand, 0.0)
    cdf = 0.5 - (integrand @ w) / math.pi
    return np.asarray(np.clip(cdf, 0.0, 1.0), dtype=np.float64)


def cf_tail_prob(cf: CharFn, threshold: float, drift: float, total_var: float) -> float:
    """P(|ln S_T/S_0| > threshold) where ln S_T/S_0 = drift + X."""
    x = np.asarray([threshold - drift, -threshold - drift], dtype=np.float64)
    c = cf_cdf(cf, x, total_var)
    return float(min(max(1.0 - c[0] + c[1], 0.0), 1.0))


def bs_cf(vol: float, t: float) -> CharFn:
    """CF of the BS martingale log return: exp(-0.5 vol^2 t (iu + u^2))."""
    def phi(u: CArr) -> CArr:
        return np.asarray(np.exp(-0.5 * vol * vol * t * (1j * u + u * u)), dtype=np.complex128)
    return phi


# ============================================================================== Monte Carlo
@dataclass(frozen=True)
class MCResult:
    price: float
    std_error: float
    n: int
    plain_price: float
    plain_std_error: float
    control_betas: tuple[float, ...] = ()

    @property
    def variance_ratio(self) -> float:
        """Estimator variance with variance reduction over plain MC (< 1 is a reduction)."""
        if self.plain_std_error <= 0:
            return 1.0
        return (self.std_error / self.plain_std_error) ** 2


def _pair_mean(x: FArr, antithetic: bool) -> FArr:
    """With antithetic paths (second half mirrors the first) the i.i.d. unit is the pair."""
    if not antithetic:
        return x
    h = x.size // 2
    return np.asarray(0.5 * (x[:h] + x[h:2 * h]), dtype=np.float64)


def mc_estimate(samples: FArr, controls: Sequence[tuple[FArr, float]] = (),
                antithetic: bool = False) -> MCResult:
    """Mean and standard error of discounted payoff `samples`, with optional control variates.

    `controls` holds (control samples, KNOWN mean) pairs; the coefficients are the OLS betas
    (multi-control regression estimator). Antithetic sampling is honoured by averaging the
    mirrored pairs before the variance is taken, so the reported s.e. is not overstated.
    """
    y = _pair_mean(np.asarray(samples, dtype=np.float64), antithetic)
    n = y.size
    plain_se = float(y.std(ddof=1) / math.sqrt(n)) if n > 1 else float("nan")
    if not controls:
        return MCResult(float(y.mean()), plain_se, n, float(y.mean()), plain_se)
    xs = np.column_stack([_pair_mean(np.asarray(c, dtype=np.float64), antithetic) - m
                          for c, m in controls])
    xc = xs - xs.mean(axis=0)
    yc = y - y.mean()
    beta, *_ = np.linalg.lstsq(xc, yc, rcond=None)
    adj = y - xs @ beta
    se = float(adj.std(ddof=1 + len(controls)) / math.sqrt(n)) if n > len(controls) + 1 else plain_se
    return MCResult(float(adj.mean()), se, n, float(y.mean()), plain_se,
                    tuple(float(b) for b in beta))


def normals(rng: np.random.Generator, n_paths: int, n_steps: int,
            antithetic: bool) -> FArr:
    """Standard normals (n_paths, n_steps); with antithetic the second half mirrors the first."""
    if not antithetic:
        return np.asarray(rng.standard_normal((n_paths, n_steps)), dtype=np.float64)
    h = (n_paths + 1) // 2
    z = rng.standard_normal((h, n_steps))
    return np.asarray(np.vstack([z, -z])[:n_paths], dtype=np.float64)


def gbm_paths(spot: float, vol_path: FArr, horizon: float, rate: float, div: float,
              z: FArr) -> FArr:
    """Log-Euler spot paths for per-step variance `vol_path` (n_paths, n_steps) of VOLS.
    The per-step log variance is vol^2 dt (sigma squared -- the Q-Fin sqrt(sigma) defect)."""
    n_steps = z.shape[1]
    dt = horizon / n_steps
    var = vol_path * vol_path
    incr = (rate - div - 0.5 * var) * dt + np.sqrt(var * dt) * z
    logs = np.concatenate([np.zeros((z.shape[0], 1)), np.cumsum(incr, axis=1)], axis=1)
    return np.asarray(spot * np.exp(logs), dtype=np.float64)
