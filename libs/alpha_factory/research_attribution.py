"""RESEARCH ATTRIBUTION -- learning which WAYS OF GENERATING IDEAS produce survivors.

The ordinary record is "this alpha worked". The useful record is "this KIND of idea worked":
cross-domain combinations survive at 1.8%, simple momentum mutations at 0.0%, regime-conditioned
signals at 0.9%. That is what lets the desk reallocate search toward productive MECHANISMS rather
than re-testing productive INSTANCES, and it is the only feedback loop here that compounds.

THE TRAP, WHICH IS THE REASON MOST OF THIS FILE EXISTS.

**Picking the best generation method out of many is itself a multiple-testing problem, and it is
the one nobody guards** because it does not look like a backtest. The desk already deflates alpha
selection -- DSR, PBO, the sqrt(2 ln N) hurdle. Then it runs eight generation methods, reads off
"method C survived at 1.8%", and reallocates the research budget to C with no deflation at all.
With eight methods and a few hundred trials each, a spread that wide arises from nothing but
sampling noise routinely. The desk would then pour budget into a method that is not better, watch
its rate regress toward the pooled mean, and conclude the edge decayed.

That failure is WORSE than a false alpha, because it is upstream of every future search. A false
alpha loses one allocation; a false attribution misdirects the search process itself, and does so
invisibly -- every subsequent batch inherits the error and the telemetry never disagrees.

So a method's rate may steer allocation only when BOTH hold:
  1. it has enough trials to say anything (`MIN_TRIALS`), and
  2. its Wilson interval excludes the pooled rate at a bar DEFLATED for the number of methods
     compared (Sidak, exact under independence -- not Bonferroni's approximation, and the
     difference matters at small alpha).
Everything else is UNDECIDED, which is a real answer and not a soft "no".

WILSON, NOT NORMAL-APPROXIMATION. Survivor rates live near zero -- 0/300 and 3/300 are the normal
observations here, and the textbook p +/- z*sqrt(p(1-p)/n) interval is degenerate at p=0 (width
zero: "0% +/- 0%", perfect certainty from no successes) and routinely runs below zero just above
it. Wilson is well-behaved at both ends, which is exactly where this measurement lives.
"""

from __future__ import annotations

import math
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from enum import Enum

#: A method needs this many trials before its rate may move budget. Not an evidence-clock breach
#: (L1.48): this IS an evidence bar stated in observations, which is what that law asks for.
MIN_TRIALS: int = 100

#: Family-wise error rate for the comparison ACROSS methods.
FAMILY_ALPHA: float = 0.05


class Maturity(Enum):
    """How far a cell of the search space has actually been taken.

    A LADDER, NOT A FLAG, because the collapse of these states is how a desk convinces itself a
    region is finished. `UNEXPLORED` and `TOUCHED` both mean "we know nothing here" -- but only one
    of them looks like work was done, and an exploration engine that treats them alike will walk
    away from a region it merely glanced at. Equally, `ADEQUATELY_TESTED` is not
    `ROBUSTLY_VALIDATED`: a single in-sample pass at n=5,000 is a strong-looking number that no
    walk-forward has touched.
    """

    UNEXPLORED = "unexplored"                # nothing run
    TOUCHED = "touched"                      # run, but underpowered -- knows nothing, looks tested
    ADEQUATELY_TESTED = "adequately_tested"  # powered, single pass
    ROBUSTLY_VALIDATED = "robustly_validated"  # survived out-of-sample / walk-forward
    SURVIVOR = "survivor"                    # cleared the deflated bar
    LIVE = "live"                            # trading or shadow-trading
    RETIRED = "retired"                      # was one of the above, now withdrawn

    @property
    def rank(self) -> int:
        return _ORDER.index(self)


_ORDER: tuple[Maturity, ...] = (
    Maturity.UNEXPLORED, Maturity.TOUCHED, Maturity.ADEQUATELY_TESTED,
    Maturity.ROBUSTLY_VALIDATED, Maturity.SURVIVOR, Maturity.LIVE, Maturity.RETIRED,
)


def classify(
    n: int,
    *,
    min_n: int = 30,
    out_of_sample: bool = False,
    cleared_deflated_bar: bool = False,
    live: bool = False,
    retired: bool = False,
) -> Maturity:
    """Place one cell on the ladder.

    RETIRED WINS OVER EVERYTHING, and that ordering is deliberate: a retired survivor is not a
    survivor. Reporting it as one is how a graveyard entry keeps counting toward a live survivor
    tally, which inflates every downstream rate that divides by it.

    A cell cannot be a SURVIVOR without having been out-of-sample validated, no matter what its
    in-sample statistic says -- the flag is required rather than implied, because "cleared the bar"
    computed in-sample is precisely the claim the deflation exists to disbelieve.
    """
    if retired:
        return Maturity.RETIRED
    if live:
        return Maturity.LIVE
    if n <= 0:
        return Maturity.UNEXPLORED
    if n < min_n:
        return Maturity.TOUCHED
    if not out_of_sample:
        return Maturity.ADEQUATELY_TESTED
    return Maturity.SURVIVOR if cleared_deflated_bar else Maturity.ROBUSTLY_VALIDATED


def wilson_interval(successes: int, trials: int, *, alpha: float = 0.05) -> tuple[float, float]:
    """Wilson score interval for a proportion. Well-behaved at p=0, which is where this lives.

    The normal approximation gives (0.0, 0.0) for 0 successes -- perfect certainty derived from no
    information -- and that would make a method with 0/50 look conclusively dead and one with 0/5
    equally so. Wilson widens correctly as n shrinks.
    """
    if trials <= 0:
        return (0.0, 1.0)                       # no information: the interval is everything
    z = _z(alpha)
    p = successes / trials
    d = 1.0 + z * z / trials
    centre = (p + z * z / (2 * trials)) / d
    half = z * math.sqrt(p * (1 - p) / trials + z * z / (4 * trials * trials)) / d
    return (max(0.0, centre - half), min(1.0, centre + half))


def _z(alpha: float) -> float:
    """Two-sided normal quantile. Rational approximation (Beasley-Springer-Moro tail); stdlib-only,
    which matters because this sits in the research path and an import is a dependency on someone
    else's release schedule."""
    p = 1.0 - alpha / 2.0
    if not 0.0 < p < 1.0:
        raise ValueError("alpha must be in (0, 2)")
    # Acklam-style inverse normal CDF, accurate to ~1e-9 over the range used here.
    a = (-3.969683028665376e+01, 2.209460984245205e+02, -2.759285104469687e+02,
         1.383577518672690e+02, -3.066479806614716e+01, 2.506628277459239e+00)
    b = (-5.447609879822406e+01, 1.615858368580409e+02, -1.556989798598866e+02,
         6.680131188771972e+01, -1.328068155288572e+01)
    c = (-7.784894002430293e-03, -3.223964580411365e-01, -2.400758277161838e+00,
         -2.549732539343734e+00, 4.374664141464968e+00, 2.938163982698783e+00)
    d = (7.784695709041462e-03, 3.224671290700398e-01, 2.445134137142996e+00,
         3.754408661907416e+00)
    plow = 0.02425
    if p < plow or p > 1 - plow:
        tail = p if p < plow else 1 - p
        q = math.sqrt(-2 * math.log(tail))
        num = ((((c[0] * q + c[1]) * q + c[2]) * q + c[3]) * q + c[4]) * q + c[5]
        den = (((d[0] * q + d[1]) * q + d[2]) * q + d[3]) * q + 1
        return float(num / den) if p < plow else float(-num / den)
    q = p - 0.5
    r = q * q
    num = (((((a[0] * r + a[1]) * r + a[2]) * r + a[3]) * r + a[4]) * r + a[5]) * q
    den = ((((b[0] * r + b[1]) * r + b[2]) * r + b[3]) * r + b[4]) * r + 1
    return float(num / den)


def sidak_alpha(family_alpha: float, n_comparisons: int) -> float:
    """Per-comparison alpha holding family-wise error at `family_alpha`.

    Sidak (1 - (1-a)^(1/m)), exact under independence, rather than Bonferroni's a/m approximation.
    At the small alphas used here the two are close, but Sidak is never anti-conservative and costs
    one line. `m <= 1` returns the family alpha unchanged -- comparing one method against the pool
    is not a family, and inflating the bar for a comparison nobody chose from would make the desk
    unable to learn anything from its first method.
    """
    if n_comparisons <= 1:
        return family_alpha
    return float(1.0 - (1.0 - family_alpha) ** (1.0 / n_comparisons))


@dataclass(frozen=True)
class MethodResult:
    """One generation method's record, and whether it has earned the right to move budget."""

    method: str
    survivors: int
    trials: int
    rate: float
    ci: tuple[float, float]
    verdict: str                      # "BETTER" | "WORSE" | "UNDECIDED" | "UNDERPOWERED"

    @property
    def steerable(self) -> bool:
        """Only a method that beat the pool at the deflated bar may pull budget toward itself."""
        return self.verdict == "BETTER"


@dataclass(frozen=True)
class Attribution:
    """The whole comparison, including the pooled rate everything is judged against."""

    methods: tuple[MethodResult, ...]
    pooled_rate: float
    total_trials: int
    total_survivors: int
    per_comparison_alpha: float
    notes: tuple[str, ...] = field(default_factory=tuple)

    @property
    def steerable(self) -> tuple[MethodResult, ...]:
        return tuple(m for m in self.methods if m.steerable)


def attribute(
    counts: Mapping[str, tuple[int, int]],
    *,
    min_trials: int = MIN_TRIALS,
    family_alpha: float = FAMILY_ALPHA,
) -> Attribution:
    """Survivor rate per generation method, deflated for the number of methods compared.

    `counts` maps method -> (survivors, trials).

    THE DEFLATION IS THE WHOLE POINT. Reading off the highest point estimate and reallocating to it
    is selection on noise, and it is upstream of every future search -- a false alpha costs one
    allocation, a false attribution misdirects the search process itself and every later batch
    inherits the error. So a method is BETTER only if its interval, at the Sidak-corrected alpha
    for the number of methods on the board, lies entirely above the pooled rate.

    WITH NO SURVIVORS ANYWHERE the pooled rate is 0.0 and NOTHING can be better than the pool.
    That is reported as such rather than dressed up: the desk's current state is 0 survivors, and
    an attribution layer that produced a ranking from it would be ranking noise with no signal
    present at all.
    """
    total_s = sum(s for s, _ in counts.values())
    total_n = sum(n for _, n in counts.values())
    pooled = (total_s / total_n) if total_n else 0.0
    per_alpha = sidak_alpha(family_alpha, len(counts))
    notes: list[str] = []
    if total_s == 0:
        notes.append(
            "ZERO SURVIVORS ACROSS EVERY METHOD: the pooled rate is 0.0 and no method can be "
            "distinguished from it. This is NOT MEASURED. Any ranking produced here would be a "
            "ranking of sampling noise with no signal present.")
    if total_n == 0:
        notes.append("NO TRIALS RUN. Attribution is undefined, not empty.")

    out: list[MethodResult] = []
    for method in sorted(counts):
        s, n = counts[method]
        if n < 0 or s < 0 or s > n:
            raise ValueError(f"{method}: invalid counts survivors={s} trials={n}")
        rate = (s / n) if n else 0.0
        lo, hi = wilson_interval(s, n, alpha=per_alpha)
        if n < min_trials:
            verdict = "UNDERPOWERED"
        elif total_s == 0:
            verdict = "UNDECIDED"
        elif lo > pooled:
            verdict = "BETTER"
        elif hi < pooled:
            verdict = "WORSE"
        else:
            verdict = "UNDECIDED"
        out.append(MethodResult(method, s, n, rate, (lo, hi), verdict))
    return Attribution(tuple(out), pooled, total_n, total_s, per_alpha, tuple(notes))


def steer_weights(
    attribution: Attribution,
    base: Mapping[str, float],
    *,
    boost: float = 0.5,
) -> dict[str, float]:
    """Reweight generation methods by what has DEMONSTRABLY worked -- and only that.

    UNDECIDED and UNDERPOWERED methods keep their base weight rather than being penalised. A method
    with too few trials to judge is not a bad method, and shrinking its budget because it has not
    proven itself yet is self-sealing: it gets fewer trials, so it stays underpowered, so it keeps
    getting fewer. That is the rut again, arriving through the attribution layer instead of through
    the allocator -- and it would be invisible, because the weights would look responsive.

    Returns raw weights; the caller applies exploration FLOORS afterwards (`research_budget`), so
    the two guards compose rather than one silently overriding the other.
    """
    out = {k: max(0.0, float(v)) for k, v in base.items()}
    for m in attribution.methods:
        if m.method not in out:
            continue
        if m.verdict == "BETTER":
            out[m.method] *= (1.0 + boost)
        elif m.verdict == "WORSE":
            out[m.method] *= max(0.0, 1.0 - boost)
    total = sum(out.values())
    return {k: v / total for k, v in out.items()} if total > 0 else dict(base)


def ladder_census(cells: Sequence[Maturity]) -> dict[str, int]:
    """Count of cells at each rung, ALWAYS including the empty ones.

    Omitting zero-count rungs is the small reporting choice that hides the finding: a census
    showing only `touched: 412` reads as progress, while one showing `survivor: 0` beside it reads
    as the truth. Every rung appears, in ladder order.
    """
    counts = dict.fromkeys((m.value for m in _ORDER), 0)
    for c in cells:
        counts[c.value] += 1
    return counts
