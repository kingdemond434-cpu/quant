"""How many observations a claim needs before it may be made. The gate, not the model.

WHY THIS FILE EXISTS AT ALL. Two of the things the principal asked for -- a conditional model of
which execution style is best, and a meta-labeler that sizes an otherwise-valid signal -- are
estimators of a DIFFERENCE IN MEANS on a sample the desk does not yet have. The failure mode is
not that such a model is hard to fit; it is that it fits perfectly well on forty rows, produces
a confident ranking, and the ranking is noise. A desk that sizes on that ranking has not added
edge, it has added a random number generator with a decimal point.

So the sample size is computed FIRST, from the effect the desk actually needs to detect, and the
model is refused until the corpus reaches it. `required_n` is the whole discipline in one
function: give it the per-observation dispersion and the smallest difference worth acting on and
it returns the observations per arm. Give it the number of cells the search will try and it
charges the multiplicity, because a table of 180 conditioning cells scanned at 5% produces nine
significant cells from pure noise and the desk has paid for exactly that error before.

THE NUMBERS THIS DESK CARES ABOUT. The principal's own target is recovering 0.04R of execution
cost. At a per-trade dispersion of sigma R, detecting a 0.04R difference between two execution
styles at 5% two-sided and 80% power needs

    n per arm = 2 (z_{alpha/2} + z_{beta})^2 (sigma / delta)^2  ~= 15.7 (sigma / 0.04)^2

which is a large number for any plausible sigma, and saying so plainly is the point. Nothing
here estimates sigma: it is measured off the corpus when the corpus has rows, and until then the
caller must pass a REFERENCE sigma and the verdict says it was a reference.

CONVENTIONS. Two-sided alpha, per-arm n (a two-arm comparison needs 2n observations total),
equal variances, equal allocation. Unequal allocation and paired designs are cheaper and this
module deliberately does not model them: the cheaper design is a reason to re-run the number,
not a reason to trust a thinner sample than the plain one supports.
"""
from __future__ import annotations

import math
from collections.abc import Iterable
from dataclasses import dataclass, field
from typing import Any

__all__ = [
    "DEFAULT_ALPHA",
    "DEFAULT_POWER",
    "MEASURED",
    "UNMEASURED",
    "PowerVerdict",
    "detectable_delta",
    "norm_ppf",
    "required_n",
    "sigma_of",
]

MEASURED = "MEASURED"
UNMEASURED = "UNMEASURED"

#: Two-sided significance and power the desk's other gates already use.
DEFAULT_ALPHA = 0.05
DEFAULT_POWER = 0.80


def norm_ppf(p: float) -> float:
    """The standard-normal quantile, to about 1e-9, without scipy.

    Acklam's rational approximation with one Halley refinement. This desk's research containers
    do not all carry scipy and a power calculation that cannot run is a power calculation nobody
    performs, which is how a model gets fitted on forty rows.
    """
    if not (0.0 < p < 1.0):
        raise ValueError(f"norm_ppf needs 0 < p < 1, got {p!r}")
    a = (-3.969683028665376e+01, 2.209460984245205e+02, -2.759285104469687e+02,
         1.383577518672690e+02, -3.066479806614716e+01, 2.506628277459239e+00)
    b = (-5.447609879822406e+01, 1.615858368580409e+02, -1.556989798598866e+02,
         6.680131188771972e+01, -1.328068155288572e+01)
    c = (-7.784894002430293e-03, -3.223964580411365e-01, -2.400758277161838e+00,
         -2.549732539343734e+00, 4.374664141464968e+00, 2.938163982698783e+00)
    d = (7.784695709041462e-03, 3.224671290700398e-01, 2.445134137142996e+00,
         3.754408661907416e+00)
    plow, phigh = 0.02425, 1.0 - 0.02425
    if p < plow:
        q = math.sqrt(-2.0 * math.log(p))
        x = ((((((c[0] * q + c[1]) * q + c[2]) * q + c[3]) * q + c[4]) * q + c[5]) /
             ((((d[0] * q + d[1]) * q + d[2]) * q + d[3]) * q + 1.0))
    elif p > phigh:
        q = math.sqrt(-2.0 * math.log(1.0 - p))
        x = -((((((c[0] * q + c[1]) * q + c[2]) * q + c[3]) * q + c[4]) * q + c[5]) /
              ((((d[0] * q + d[1]) * q + d[2]) * q + d[3]) * q + 1.0))
    else:
        q = p - 0.5
        r = q * q
        x = ((((((a[0] * r + a[1]) * r + a[2]) * r + a[3]) * r + a[4]) * r + a[5]) * q /
             (((((b[0] * r + b[1]) * r + b[2]) * r + b[3]) * r + b[4]) * r + 1.0))
    # one Halley step against the true CDF, which erf gives exactly
    e = 0.5 * math.erfc(-x / math.sqrt(2.0)) - p
    u = e * math.sqrt(2.0 * math.pi) * math.exp(x * x / 2.0)
    return x - u / (1.0 + x * u / 2.0)


def _alpha_eff(alpha: float, n_comparisons: int) -> float:
    """Bonferroni: a table scanned at 5% is not scanned at 5%.

    Conservative on purpose. A sharper correction (Holm, Benjamini-Hochberg) needs the realised
    p-values, which do not exist at the moment the sample size is being planned, and the desk's
    standing rule is that a gate is never made easier by a refinement nobody has run yet.
    """
    k = max(1, int(n_comparisons))
    return alpha / k


@dataclass(frozen=True)
class PowerVerdict:
    """What a cell can and cannot claim at its current n."""

    #: Observations per arm the comparison needs.
    n_required: int
    #: Observations per arm the corpus actually has (the thinnest arm).
    n_have: int
    #: The difference in means the current n can detect at the stated alpha and power.
    delta_detectable: float | None
    #: The difference the caller wants to act on.
    delta_target: float
    sigma: float
    #: True when sigma came from the corpus rather than from a declared reference.
    sigma_measured: bool
    alpha: float
    power: float
    n_comparisons: int
    #: MEASURED when n_have >= n_required for every arm, else UNMEASURED.
    status: str
    why: str = ""
    extra: dict[str, Any] = field(default_factory=dict)

    @property
    def shortfall(self) -> int:
        """Observations per arm still needed. Zero when the gate is open."""
        return max(0, self.n_required - self.n_have)

    def to_row(self) -> dict[str, Any]:
        return {"status": self.status, "n_required_per_arm": self.n_required,
                "n_have_per_arm": self.n_have, "shortfall_per_arm": self.shortfall,
                "delta_target": self.delta_target,
                "delta_detectable_at_current_n": self.delta_detectable,
                "sigma": self.sigma, "sigma_measured": self.sigma_measured,
                "alpha": self.alpha, "power": self.power,
                "comparisons_charged": self.n_comparisons, "why": self.why, **self.extra}


def required_n(sigma: float, delta: float, *, alpha: float = DEFAULT_ALPHA,
               power: float = DEFAULT_POWER, n_comparisons: int = 1) -> int:
    """Observations PER ARM to detect a difference of `delta` in means at `sigma` dispersion.

    n = 2 (z_{alpha_eff/2} + z_{power})^2 (sigma / delta)^2, rounded up. `n_comparisons` charges
    Bonferroni for every cell the search will look at, which is what stops a 180-cell table from
    reporting nine winners it invented.
    """
    if not (sigma > 0 and math.isfinite(sigma)):
        raise ValueError(f"sigma must be a positive finite number, got {sigma!r}")
    if not (abs(delta) > 0 and math.isfinite(delta)):
        raise ValueError(f"delta must be a non-zero finite number, got {delta!r}")
    za = norm_ppf(1.0 - _alpha_eff(alpha, n_comparisons) / 2.0)
    zb = norm_ppf(power)
    return math.ceil(2.0 * (za + zb) ** 2 * (sigma / abs(delta)) ** 2)


def detectable_delta(n: int, sigma: float, *, alpha: float = DEFAULT_ALPHA,
                     power: float = DEFAULT_POWER, n_comparisons: int = 1) -> float | None:
    """The smallest difference `n` observations per arm can see. None when n < 2.

    The mirror of `required_n`, and the more useful number in a report: it says what the desk
    could have learned from what it has, rather than only what it still lacks.
    """
    if n < 2 or not (sigma > 0 and math.isfinite(sigma)):
        return None
    za = norm_ppf(1.0 - _alpha_eff(alpha, n_comparisons) / 2.0)
    zb = norm_ppf(power)
    return (za + zb) * sigma * math.sqrt(2.0 / n)


def sigma_of(values: Iterable[Any]) -> float | None:
    """Sample standard deviation of a finite-valued sequence, or None below two observations.

    Kept here rather than imported from numpy so a power calculation is available to any caller
    on any container; the corpus's own dispersion is the input every verdict here wants and a
    verdict that cannot be computed is a verdict that gets skipped.
    """
    try:
        xs = [float(v) for v in values]
    except (TypeError, ValueError):
        return None
    xs = [x for x in xs if math.isfinite(x)]
    n = len(xs)
    if n < 2:
        return None
    m = sum(xs) / n
    var = sum((x - m) ** 2 for x in xs) / (n - 1)
    s = math.sqrt(var)
    return s if s > 0 and math.isfinite(s) else None


def verdict(*, n_have: int, delta_target: float, sigma: float | None,
            reference_sigma: float, alpha: float = DEFAULT_ALPHA, power: float = DEFAULT_POWER,
            n_comparisons: int = 1, what: str = "") -> PowerVerdict:
    """The whole gate in one call: measured sigma when there is one, the reference when there is
    not, the required n, what the current n could see, and MEASURED only when n clears the bar.

    A caller that has no sigma at all still gets a number -- computed at `reference_sigma` and
    flagged `sigma_measured=False` -- because "we cannot say how many we need until we have some"
    is how a collection target never gets written down.
    """
    s = sigma if (sigma is not None and sigma > 0 and math.isfinite(sigma)) else None
    use = s if s is not None else float(reference_sigma)
    need = required_n(use, delta_target, alpha=alpha, power=power, n_comparisons=n_comparisons)
    have = max(0, int(n_have))
    ok = have >= need
    basis = ("sigma measured on the corpus" if s is not None else
             f"sigma is the declared reference {reference_sigma:g}, not a measurement")
    why = (f"{what or 'comparison'}: {basis}; needs {need} per arm at delta={delta_target:g}, "
           f"alpha={alpha:g}/{max(1, n_comparisons)}, power={power:g}; has {have}")
    return PowerVerdict(n_required=need, n_have=have,
                        delta_detectable=detectable_delta(have, use, alpha=alpha, power=power,
                                                          n_comparisons=n_comparisons),
                        delta_target=float(delta_target), sigma=use, sigma_measured=s is not None,
                        alpha=alpha, power=power, n_comparisons=max(1, int(n_comparisons)),
                        status=MEASURED if ok else UNMEASURED, why=why)
