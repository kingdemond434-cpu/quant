"""THE HAT ON Ê[log W] -- every marginal quantity in this constitution is an ESTIMATE.

THE CORRECTION THIS MODULE EXISTS FOR, and it is the sharpest one in the directive. The objective
is written argmax_pi Ê[log W_T] with a hat, and then every downstream rule is written as though
the derivatives were observable: retire when ΔÊ[log W] < 0, allocate to argmax ΔÊ[log W]/ΔR,
suspend a law that fails to contribute. Those read like arithmetic. They are not. Every one of
those quantities is a posterior estimate with a standard error, usually estimated from a handful
of observations, and treating a noisy estimate as a number is how a desk:

  * retires a genuinely useful module on one bad period,
  * reallocates every cycle toward whichever subsystem got lucky most recently,
  * and reports precision it does not have, which is worse than reporting nothing.

So nothing in this codebase compares raw point estimates. Every comparison goes through an
`Estimate`, carries its standard error, and answers questions in the form "is the evidence strong
enough to act on?" rather than "which number is bigger?".

THE ASYMMETRY IS DELIBERATE AND IT IS NOT TIMIDITY. Acting requires evidence; CONTINUING does
not. A module keeps its resources until there is significant evidence against it, because the
null is "it was built for a reason". A new claim on resources needs evidence FOR it, because the
null is "nobody has shown this works". Both directions point the same way: toward acting on
evidence rather than on noise, which is the only thing that raises E[log W] reliably.

CALIBRATION DRIVES SIZE. Poor calibration (high Brier) means the desk's own uncertainty estimates
are untrustworthy, so the penalty on uncertainty rises and size falls; good calibration earns
size back. That is not a safety margin bolted on -- it is the correct posterior response to
knowing your estimator is bad, and it is why calibration is worth measuring at all.

Pure, dependency-free, no I/O.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

__all__ = [
    "ADMIT_Z",
    "LAMBDA_MAX",
    "LAMBDA_MIN",
    "MIN_N_FOR_ACTION",
    "RETIRE_Z",
    "Estimate",
    "adjusted",
    "better",
    "retirement_verdict",
    "uncertainty_penalty",
]

#: z for the retirement test. 1.64 is a one-sided 95% bound: a module is retired only when its
#: contribution is significantly NEGATIVE, never on a point estimate that happens to be below
#: zero. The directive's own amendment, and it is right -- single-period underperformance retires
#: useful modules faster than any process can replace them.
RETIRE_Z = 1.64

#: z for admitting a NEW claim on resources. 1.28 (one-sided 80%) matches the capital significance
#: gate. Lower than RETIRE_Z on purpose: the cost of trying something that turns out flat is one
#: cycle of resource, while the cost of never trying it is unbounded. Asymmetric evidence bars for
#: asymmetric costs.
ADMIT_Z = 1.28

#: Below this many observations an estimate is not evidence in either direction -- and the honest
#: report is UNKNOWN, not zero. A subsystem with 2 observations has not earned resources and has
#: not earned retirement.
MIN_N_FOR_ACTION = 5

#: Bounds on the uncertainty penalty lambda. Never zero: a perfectly-calibrated forecaster is
#: still forecasting, and pretending otherwise is how a desk sizes on a backtest. Never unbounded
#: either: an infinite penalty means never acting, which is a guaranteed zero growth rate and
#: therefore the WORST available outcome under a log objective, not the safest.
LAMBDA_MIN = 0.25
LAMBDA_MAX = 3.0


@dataclass(frozen=True)
class Estimate:
    """A posterior estimate of a marginal contribution to E[log W]. Never a bare float.

    `value` is the point estimate, `se` its standard error, `n` the observations behind it.
    Constructing one with se=0 is legal only for a quantity that is genuinely deterministic
    (a fee schedule, a fixed cost) -- and those are rare enough that the caller should have to
    think about it.
    """

    value: float
    se: float = 0.0
    n: int = 0
    label: str = ""

    def lower(self, z: float = ADMIT_Z) -> float:
        """Conservative bound. What the desk can defend, not what it hopes."""
        return float(self.value) - z * abs(float(self.se))

    def upper(self, z: float = ADMIT_Z) -> float:
        return float(self.value) + z * abs(float(self.se))

    @property
    def informative(self) -> bool:
        return int(self.n) >= MIN_N_FOR_ACTION or float(self.se) == 0.0

    def significant_positive(self, z: float = ADMIT_Z) -> bool:
        return self.informative and self.lower(z) > 0.0

    def significant_negative(self, z: float = RETIRE_Z) -> bool:
        return self.informative and self.upper(z) < 0.0


def uncertainty_penalty(brier: float | None) -> float:
    """lambda = f(calibration). Poor calibration -> heavier penalty on uncertainty -> smaller size.

    Brier ranges 0 (perfect) to 0.25 for an always-0.5 forecaster to 1.0 for confidently wrong.
    The map is linear through those anchors and CLAMPED at both ends.

    WHY NOT ZERO AT PERFECT CALIBRATION. A measured Brier of 0.0 over a realistic sample is
    evidence of a small sample, not of omniscience -- and a lambda of zero would size as though
    the point estimate were the truth. LAMBDA_MIN is the floor that survives that.

    WHY BOUNDED ABOVE. Unbounded penalty means never acting. Under a log objective a guaranteed
    zero growth rate is not the safe outcome, it is the worst one available -- the desk that
    never bets has already lost to the desk that bets small.

    `None` -- no calibration measured yet -- returns the MAXIMUM penalty. Absence of evidence
    about your own reliability is not evidence of reliability, and the direction has to be
    conservative here specifically because it is the one input the desk cannot fake later.
    """
    if brier is None:
        return LAMBDA_MAX
    b = max(0.0, min(1.0, float(brier)))
    lam = LAMBDA_MIN + (LAMBDA_MAX - LAMBDA_MIN) * (b / 0.25)
    return round(max(LAMBDA_MIN, min(LAMBDA_MAX, lam)), 4)


def adjusted(est: Estimate, *, brier: float | None = None) -> float:
    """Ê[log W] - lambda * U. The number every allocation decision actually compares.

    Uncertainty is penalised rather than ignored, which reorders the queue in exactly the way a
    point-estimate ranking gets wrong: a 0.05 +- 0.01 contribution beats a 0.09 +- 0.06 one,
    because the second is barely distinguishable from nothing and the first is bankable.
    """
    return round(float(est.value) - uncertainty_penalty(brier) * abs(float(est.se)), 6)


def better(a: Estimate, b: Estimate, *, brier: float | None = None) -> Estimate | None:
    """The uncertainty-adjusted winner, or None when the two are not distinguishable.

    NONE IS A REAL ANSWER and callers must handle it. Forcing a winner between two statistically
    indistinguishable options is how a desk churns: it reallocates every cycle on noise, pays the
    switching cost every time, and books the churn as responsiveness. When this returns None the
    directive's own tie-break applies -- prefer the higher information gain, because that is the
    tie-break that makes the NEXT comparison decidable.
    """
    diff = float(a.value) - float(b.value)
    joint_se = math.sqrt(float(a.se) ** 2 + float(b.se) ** 2)
    if joint_se > 0 and abs(diff) < ADMIT_Z * joint_se:
        return None
    return a if adjusted(a, brier=brier) >= adjusted(b, brier=brier) else b


def retirement_verdict(est: Estimate, *, z: float = RETIRE_Z) -> dict:
    """RETIRE / KEEP / INSUFFICIENT-EVIDENCE for a law, module, fence or routine.

    THREE OUTCOMES, NOT TWO. "We do not have enough evidence to judge this" is the honest verdict
    for most of the desk most of the time, and collapsing it into either KEEP or RETIRE loses the
    one fact that should drive the next action: go and measure it.

    Retirement requires SIGNIFICANT evidence of negative contribution. A point estimate below
    zero is not that -- with a handful of observations, roughly half of everything neutral will
    read negative on any given cycle, and a desk that retired on that signal would churn its way
    through its own infrastructure while believing it was optimising.
    """
    if not est.informative:
        return {"verdict": "INSUFFICIENT-EVIDENCE", "label": est.label,
                "value": est.value, "n": est.n,
                "action": ("instrument it. A subsystem that cannot show its contribution has not "
                           "earned resources AND has not earned retirement -- the next action is "
                           "measurement, not a decision"),
                "note": f"n={est.n} < {MIN_N_FOR_ACTION}"}
    if est.significant_negative(z):
        return {"verdict": "RETIRE", "label": est.label, "value": est.value,
                "upper_bound": round(est.upper(z), 6),
                "action": "retire or evolve -- contribution is significantly negative",
                "note": f"upper {z}-sigma bound {est.upper(z):.6f} < 0"}
    return {"verdict": "KEEP", "label": est.label, "value": est.value,
            "action": ("keep. Retirement requires SIGNIFICANT evidence against, not a point "
                       "estimate below zero -- churning useful modules on single-period noise "
                       "costs more than the modules ever did"),
            "note": f"upper {z}-sigma bound {est.upper(z):.6f} >= 0"}
