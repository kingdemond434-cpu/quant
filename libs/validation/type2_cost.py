"""TYPE-II COST -- what a rejection COULD NOT HAVE SEEN, published next to the rejection.

THE DEFECT THIS CLOSES. The desk has produced zero survivors across every screen it runs, and
every one of those zeros is written down as "no edge found". A gate calibrated to never admit
noise also rejects weak-but-real edges, and the desk does not publish what that costs. "We found
nothing" stated without a power figure is UNFALSIFIABLE: it cannot be distinguished from "we could
not have found anything even if it were there". Those two statements have opposite consequences --
the first retires a hypothesis class, the second retires an INSTRUMENT -- and the desk currently
files both under the same word.

THE LOAD-BEARING DISTINCTION, and the only thing this module exists to express:

    COULD-NOT-HAVE-SEEN-IT   (UNDERPOWERED)     -- the sample could not resolve an effect of the
                                                   size that would matter. The reading is
                                                   uninformative in EITHER direction. Nothing was
                                                   refuted; nothing was found.
    LOOKED-AND-IT-IS-NOT-THERE (POWERED-NEGATIVE) -- the sample could have resolved such an effect
                                                   and did not. This is negative KNOWLEDGE.
    NO-SAMPLE-RECORDED       (INDETERMINATE)    -- the rejection does not record the sample it was
                                                   taken on, so which of the two above it is
                                                   cannot be determined from the artifact. Counted
                                                   with the underpowered for every headline: an
                                                   unlabellable rejection carries no information
                                                   either, and guessing a sample size would
                                                   fabricate the very evidence this module demands.

A rejection that cannot say which of those it is carries no information at all.

THIS MODULE CANNOT PROMOTE, ADMIT, OR RESURRECT ANYTHING. It computes three numbers about a
rejection that ALREADY HAPPENED and attaches labels to it. No threshold moves, no verdict changes,
alpha stays 0.05, and an UNDERPOWERED label is emphatically NOT a licence to re-open a graveyard
row -- the graveyard is permanent by construction (docs/graveyard.md). The label says the desk
knows less than it wrote down, never that a dead hypothesis is alive.

WHAT IS COMPUTED (the three questions the desk was not answering):

  (a) MINIMUM DETECTABLE EFFECT at this sample's effective size and the gate's alpha.
  (b) POWER at one or more DECLARED effect sizes -- declared in advance, never read off the
      observed statistic. Post-hoc "observed power" computed from the realised estimate is a
      monotone restatement of the p-value and answers nothing (Hoenig & Heisey 2001); it would
      make every null self-certifying, which is exactly the failure `axis_screen.powered` was
      written to avoid.
  (c) P(this gate rejects | a true edge of size X exists) = 1 - power(X). The Type-II cost proper:
      the share of genuine edges of that size this rejection would have thrown away.

THE ARITHMETIC, AND WHY IT IS THIS ARITHMETIC. For a Sharpe-scale test the desk's own identity is

    t = sqrt(T) * SR_per_bar,   SR_per_bar = SR_ann / sqrt(PPY)
      => t = SR_ann * sqrt(T / PPY) = SR_ann * sqrt(YEARS)

so ELAPSED TIME is the evidence and BAR COUNT IS NOT: moving from daily to 4h bars multiplies both
T and PPY by six and changes the statistic by exactly nothing (docs/research/REALITY_CHECK_POWER.md;
scripts/audit_reality_check.py::theoretical_min_sharpe). Every function here therefore consumes
YEARS, and `effective_years` is the only place bars are converted -- so an intraday caller cannot
accidentally buy power by resampling. The critical value is the 1 - alpha/N normal quantile, which
is the desk's own approximation to the Romano-Wolf max-null critical value.

MATCHES THE DESK'S RECORDED NUMBERS EXACTLY, which is the check that this is the desk's gate and
not a model of it. reports/reality_check_audit.json records a closed-form minimum detectable
annualised Sharpe of {196: 1.478, 50: 1.314, 20: 1.194, 5: 0.989, 1: 0.700} at T=2018, and a
pooled 0.767 at m=10 symbols / rho=0.348 / N=20. `min_detectable_sharpe` reproduces all six.

THE HAND-COMPUTED CASE (pinned by tests/validation/test_type2_cost.py::test_hand_computed_case):

    T = 2018 daily bars, PPY = 365      -> years   = 2018 / 365      = 5.5287671...
    N = 196 candidates, alpha = 0.05    -> z_crit  = Phi^-1(1 - 0.05/196)
                                                   = Phi^-1(0.9997448979...) = 3.4753414...
    min detectable ann. Sharpe (50% power) = 3.4753414 / sqrt(5.5287671)
                                           = 3.4753414 / 2.3513331 = 1.4780300
    power at a TRUE ann. Sharpe of 1.0     = Phi(1.0 * 2.3513331 - 3.4753414)
                                           = Phi(-1.1240083) = 0.1305048
    P(reject | true SR = 1.0)              = 1 - 0.1305048 = 0.8694952

So the campaign that reported "196 mechanisms, none survived" would have discarded roughly SEVEN
OF EVERY EIGHT genuine annualised-Sharpe-1.0 edges. That is the number the zero was missing.

BOTH LABELS ARE CONSERVATIVE IN THE DIRECTION THAT ADDS NO AUTHORITY, and asymmetrically so:

  * UNDERPOWERED is computed under the assumptions most FAVOURABLE to the desk's claim of
    knowledge -- where a multiplicity burden is not recorded it is taken as N=1, the smallest it
    can be. So when this module says a rejection was blind, even the most generous reading agrees,
    and the label is not arguable.
  * POWERED-NEGATIVE is an UPPER BOUND on the real gate's power, never a certification. The closed
    form is a single normal-approximation t-test; the real gauntlet stacks reality_check, dsr, pbo,
    cpcv, walk_forward, fragility and more, and each additional gate can only reject MORE. Measured
    proof of the gap: at m=10/rho=0.348/N=20 the closed form gives 47.5% power at true SR 0.75
    where the desk's Monte Carlo measured 20% (reports/reality_check_audit.json). POWERED here
    means "not demonstrably blind", NOT "this negative is certified".

CITED, MEASURED CONTEXT (verified present in this checkout, not re-derived here):
  * docs/research/gate_power_audit.md -- power identical at N=420/100/30/5; sample LENGTH T was the
    only lever that moved it. Campaign width is not evidence.
  * docs/research/REALITY_CHECK_POWER.md -- pooling took power at SR 1.0 from 5% to ~70%; minimum
    detectable pooled Sharpe ~0.68-0.77 in the desk's real-edge band of 0.5-1.5.
  * libs/research/axis_screen.py -- already does this correctly PER CELL (n_eff,
    min_detectable_ic, `powered`, and a SCREEN-UNDERPOWERED verdict that can neither reject on
    merit nor graveyard). This module is that discipline generalised off the axis screen and made
    available to every other rejection the desk records.

Pure functions, no I/O, no randomness. `scripts/run_type2_report.py` is the only caller that
touches disk.
"""

from __future__ import annotations

import math
from collections.abc import Sequence
from dataclasses import dataclass
from statistics import NormalDist
from typing import Any

import numpy as np

from libs.research.cohort_independence import effective_bets
from libs.validation.admission_power import POWER_TARGET
from libs.validation.forward_stats import autocorr_factor

__all__ = [
    "CROSS_SYMBOL_STRATEGY_CORR",
    "DECLARED_CORRELATION_EFFECTS",
    "DECLARED_SHARPES",
    "DEFAULT_ALPHA",
    "DESK_EDGE_BAND",
    "INDETERMINATE",
    "POWERED",
    "PPY",
    "REFERENCE_CORRELATION_EFFECT",
    "REFERENCE_SHARPE",
    "UNDERPOWERED",
    "DeskHeadline",
    "Type2Cost",
    "autocorr_deflator",
    "correlation_n_eff",
    "correlation_negative",
    "correlation_power",
    "critical_z",
    "effective_years",
    "headline",
    "indeterminate",
    "min_detectable_correlation",
    "min_detectable_sharpe",
    "pooling_multiplier",
    "sharpe_negative",
    "sharpe_power",
]

#: The desk's alpha. NOT a parameter of policy -- it is passed around so the arithmetic is explicit
#: and testable, and every caller in this repo uses this value. Nothing here may change it.
DEFAULT_ALPHA = 0.05

#: Periods per year for daily bars. Matches scripts/audit_reality_check.py::PPY and
#: libs/validation/forward_stats._PPY, so the closed form reproduces the recorded artifacts.
PPY = 365.0

#: The desk's real-edge band in annualised Sharpe, from the external 131,441-backtest sweep quoted
#: by docs/research/REALITY_CHECK_POWER.md. A screen whose detection floor sits ABOVE this band
#: cannot see any edge the desk plausibly has, whatever it reports.
DESK_EDGE_BAND = (0.5, 1.5)

#: Effect sizes power is DECLARED at for Sharpe-scale rejections: the edges of the desk's real-edge
#: band plus its midpoint. Declared in advance and identical for every rejection, which is what
#: keeps (b) from degenerating into post-hoc observed power.
DECLARED_SHARPES = (0.5, 1.0, 1.5)

#: The effect the POWERED / UNDERPOWERED label is decided at. 1.0 is the middle of the desk's band
#: and the level at which docs/research/REALITY_CHECK_POWER.md measured the 5% -> 70% pooling gain,
#: so a label at this level is directly comparable to the desk's own measurement.
REFERENCE_SHARPE = 1.0

#: Correlation-scale declared effects (IC, or any standardised effect obeying the same z/sqrt(n)
#: form). 0.03 is `axis_screen`'s own ic_min floor -- the smallest IC the desk says is worth
#: caring about -- with two multiples of it for shape.
DECLARED_CORRELATION_EFFECTS = (0.03, 0.05, 0.10)

#: Label level for correlation-scale rejections. Equals axis_screen's ic_min, so a rejection this
#: module calls UNDERPOWERED is underpowered by the desk's OWN stated floor, not by a new one.
REFERENCE_CORRELATION_EFFECT = 0.03

#: Measured same-mechanism cross-symbol STRATEGY return correlation on the real OKX/Binance panel
#: (docs/research/REALITY_CHECK_POWER.md; reports/reality_check_audit.json). This -- not the 0.622
#: raw return correlation -- is the number that governs how much pooling actually buys.
CROSS_SYMBOL_STRATEGY_CORR = 0.348

POWERED = "POWERED-NEGATIVE"
UNDERPOWERED = "UNDERPOWERED"
INDETERMINATE = "INDETERMINATE"

#: Smallest elapsed time that can carry a power calculation. Below this the normal approximation is
#: meaningless and the honest answer is INDETERMINATE rather than a huge minimum detectable effect
#: dressed up as a measurement.
_MIN_YEARS = 1e-6

#: Smallest effective observation count a correlation-scale test can be computed on. Two points
#: define a correlation of exactly +/-1 and carry no evidence.
_MIN_N_EFF = 3.0

_NORM = NormalDist()


# --------------------------------------------------------------------------- critical values


def critical_z(alpha: float = DEFAULT_ALPHA, n_tests: int = 1, *, two_sided: bool = False) -> float:
    """The normal critical value a statistic must clear at `alpha` across `n_tests` hypotheses.

    One-sided: Phi^-1(1 - alpha/N). Two-sided: Phi^-1(1 - alpha/(2N)), which at alpha=0.05, N=1 is
    the familiar 1.96 that `libs/research/axis_screen.py` uses for `min_detectable_ic` -- reproduced
    here rather than re-chosen, so this module cannot silently disagree with the screen it
    generalises.

    THE N-DIVISION IS NOT A NEW CORRECTION. It is the desk's own approximation to the Romano-Wolf
    max-null critical value (scripts/audit_reality_check.py::theoretical_min_sharpe: "the
    Romano-Wolf critical value is the 95th percentile of the maximum of N bootstrap t-statistics,
    which for approximately independent columns is close to the 1 - 0.05/N normal quantile"). Pass
    the multiplicity the gate ACTUALLY applied. Where an artifact does not record one, pass 1 --
    the smallest it can be, and therefore the reading most favourable to the desk's claim of
    knowledge, which is what makes a resulting UNDERPOWERED label unarguable.
    """
    a = float(alpha)
    n = max(1, int(n_tests))
    if not math.isfinite(a) or a <= 0.0 or a >= 1.0:
        return float("nan")
    tail = a / n / (2.0 if two_sided else 1.0)
    return float(_NORM.inv_cdf(1.0 - tail))


# --------------------------------------------------------------------------- effective sample


def autocorr_deflator(returns: np.ndarray) -> float:
    """Newey-West/Bartlett variance-inflation factor for a return series, clamped to [1, 5].

    A thin, deliberate delegation to `libs.validation.forward_stats.autocorr_factor` so the desk has
    ONE autocorrelation correction rather than two that can drift apart. Effective observations are
    n / factor; the factor is never below 1, so this can only ever SHRINK the effective sample --
    i.e. it can only ever make a rejection look less powered, never more.
    """
    return float(autocorr_factor(np.asarray(returns, dtype="float64")))


def pooling_multiplier(n_units: int, mean_corr: float) -> float:
    """How many independent units' worth of evidence `n_units` correlated units actually carry.

    m / (1 + (m-1) * rho), delegated to `libs.research.cohort_independence.effective_bets` -- which
    clamps to [1, m] and carries the reason that clamp exists (a demeaned panel produced "64.4
    independent bets from 29 perps" before it was added). Pooling a mechanism across symbols is the
    ONE lever docs/research/REALITY_CHECK_POWER.md found that moves power without touching a
    threshold: at m=10, rho=0.348 this returns 2.42, matching the recorded artifact.
    """
    return float(effective_bets(max(1, int(n_units)), float(mean_corr)))


def effective_years(
    n_bars: float,
    *,
    ppy: float = PPY,
    n_units: int = 1,
    cross_corr: float = 0.0,
    deflator: float = 1.0,
) -> float:
    """Elapsed evidence in YEARS, after pooling and autocorrelation. The only bars->time conversion.

    THE WHOLE POINT OF FUNNELLING EVERY CALLER THROUGH ONE FUNCTION. `t = SR_ann * sqrt(years)`
    means bar count is not evidence: 17,568 five-minute bars and 1,464 hourly bars are the SAME 61
    days and carry the same power, and the desk has three intraday artifacts that differ only in
    bar size. A caller computing n_eff from a raw bar count would read the 5-minute run as twelve
    times the evidence of the hourly one. It is not.

    Pooling MULTIPLIES (m correlated symbols carry m/(1+(m-1)rho) units of evidence); serial
    correlation DIVIDES (deflator >= 1). The result is bounded above by `years * n_units`, the total
    observation-time actually collected -- `effective_bets` already clamps to [1, m] so the bound is
    inactive, and it is asserted here because the same domain error (an overlap deflator inverting
    into a multiplier at horizon < 1 and inflating n_eff 1,449x) has already been paid for once in
    `libs/research/axis_screen.py`. A bound that can only LOWER the answer can only tighten.
    """
    bars = float(n_bars)
    per_year = float(ppy)
    if not math.isfinite(bars) or bars <= 0.0 or not math.isfinite(per_year) or per_year <= 0.0:
        return 0.0
    years = bars / per_year
    gain = pooling_multiplier(n_units, cross_corr)
    d = max(1.0, float(deflator)) if math.isfinite(deflator) else 1.0
    return float(min(years * gain / d, years * max(1, int(n_units))))


def correlation_n_eff(n_obs: float, *, horizon_periods: float = 1.0, panel_width: int = 1) -> float:
    """Effective independent observations behind a correlation-scale statistic.

    THE SAME EXPRESSION AS `libs/research/axis_screen.py`, copied rather than re-derived so the two
    cannot disagree, INCLUDING its upper bound at the rows actually observed:

        n_eff = min(n, n / (horizon_periods * panel_width)), floored at 1

    `horizon_periods` deflates for OVERLAPPING targets sampled every period; `panel_width` divides
    out cross-sectional stacking (a 139-symbol panel flattened into one array has n = symbol-days,
    and treating those as independent inflates every t-stat by sqrt(139) ~ 11.8x). The bound at `n`
    exists because at horizon < 1 the deflator inverts into a MULTIPLIER -- measured on the first
    intraday caller, 4,314 five-minute bars reported n_eff = 1,236,384 -- and a bound that can only
    lower n_eff can only tighten the reading.
    """
    n = float(n_obs)
    if not math.isfinite(n) or n <= 0.0:
        return 0.0
    h = float(horizon_periods)
    w = max(1, int(panel_width))
    denom = max(h * w, 1e-9) if math.isfinite(h) and h > 0.0 else float(w)
    return float(max(min(n, n / denom), 1.0))


# --------------------------------------------------------------------------- the three questions


def min_detectable_sharpe(
    *,
    years: float,
    n_tests: int = 1,
    alpha: float = DEFAULT_ALPHA,
    power: float = POWER_TARGET,
    two_sided: bool = False,
) -> float:
    """(a) The smallest TRUE annualised Sharpe this sample could detect at `power`.

    (z_crit + z_power) / sqrt(years). At the desk's default `power` = 0.5 the second term is zero
    and this collapses to z_crit / sqrt(years) -- the exact closed form recorded in
    reports/reality_check_audit.json, reproduced to three decimals for all five of its N values.

    `power` defaults to `libs.validation.admission_power.POWER_TARGET` (0.5), imported rather than
    restated: below 50% a screen misses a genuine edge more often than it finds one, so its null
    carries no information about the space it searched. Raising it to 0.8 answers a stricter
    question and returns a larger floor; it never returns a smaller one.
    """
    y = float(years)
    if not math.isfinite(y) or y < _MIN_YEARS:
        return float("inf")
    zc = critical_z(alpha, n_tests, two_sided=two_sided)
    if not math.isfinite(zc):
        return float("nan")
    p = float(power)
    if not math.isfinite(p) or p <= 0.0 or p >= 1.0:
        return float("nan")
    return float((zc + _NORM.inv_cdf(p)) / math.sqrt(y))


def sharpe_power(
    true_sharpe: float,
    *,
    years: float,
    n_tests: int = 1,
    alpha: float = DEFAULT_ALPHA,
    two_sided: bool = False,
) -> float:
    """(b) P(this gate rejects the null | the true annualised Sharpe is `true_sharpe`).

    Phi(SR * sqrt(years) - z_crit). At SR = 0 this returns the SIZE of the test (alpha/N), which is
    the sanity check that the formula is a power function and not a fitted curve.

    AN UPPER BOUND ON THE REAL GATE'S POWER, never an estimate of it -- see the module docstring.
    The real gauntlet ANDs several gates together and each can only reject more.
    """
    y = float(years)
    sr = float(true_sharpe)
    if not math.isfinite(y) or y < _MIN_YEARS or not math.isfinite(sr):
        return 0.0
    zc = critical_z(alpha, n_tests, two_sided=two_sided)
    if not math.isfinite(zc):
        return float("nan")
    return float(_NORM.cdf(sr * math.sqrt(y) - zc))


def min_detectable_correlation(
    *,
    n_eff: float,
    n_tests: int = 1,
    alpha: float = DEFAULT_ALPHA,
    power: float = POWER_TARGET,
    two_sided: bool = True,
) -> float:
    """(a) on the correlation scale: the smallest true IC this effective sample could detect.

    (z_crit + z_power) / sqrt(n_eff). Two-sided by default so that at alpha=0.05, N=1, power=0.5 it
    is exactly `axis_screen`'s 1.96 / sqrt(n_eff) -- an IC screen and this module must never
    disagree about whether a cell was powered. The same z/sqrt(n) form governs any standardised
    effect (a Cohen's-d mean shift, a standardised event-study abnormal return), so callers on
    those scales use this function and say so in `effect_unit`.
    """
    n = float(n_eff)
    if not math.isfinite(n) or n < _MIN_N_EFF:
        return float("inf")
    zc = critical_z(alpha, n_tests, two_sided=two_sided)
    if not math.isfinite(zc):
        return float("nan")
    p = float(power)
    if not math.isfinite(p) or p <= 0.0 or p >= 1.0:
        return float("nan")
    return float((zc + _NORM.inv_cdf(p)) / math.sqrt(n))


def correlation_power(
    true_effect: float,
    *,
    n_eff: float,
    n_tests: int = 1,
    alpha: float = DEFAULT_ALPHA,
    two_sided: bool = True,
) -> float:
    """(b) on the correlation scale: P(reject | the true IC is `true_effect`)."""
    n = float(n_eff)
    e = float(true_effect)
    if not math.isfinite(n) or n < _MIN_N_EFF or not math.isfinite(e):
        return 0.0
    zc = critical_z(alpha, n_tests, two_sided=two_sided)
    if not math.isfinite(zc):
        return float("nan")
    return float(_NORM.cdf(abs(e) * math.sqrt(n) - zc))


# --------------------------------------------------------------------------- the verdict object


@dataclass(frozen=True)
class Type2Cost:
    """What one recorded rejection could and could not have seen. Labels only; promotes nothing."""

    name: str
    #: The artifact this rejection was read out of. A label with no provenance is an opinion.
    source: str
    label: str
    #: What `min_detectable_effect` and `reference_effect` are denominated in. A 0.03 IC floor and a
    #: 0.2 mean-shift floor are not comparable numbers and must not be read side by side as if.
    effect_unit: str
    alpha: float
    n_tests: int
    z_critical: float
    #: Effective INDEPENDENT observations. On the Sharpe scale this is `years_eff * ppy`, i.e. the
    #: elapsed evidence re-expressed in bars, so pooling shows up as more effective bars than were
    #: collected on any one symbol. On the correlation scale it is the axis_screen n_eff directly.
    n_eff: float
    #: Elapsed evidence in years. NaN on the correlation scale, where time is not the unit.
    years_eff: float
    min_detectable_effect: float
    reference_effect: float
    power_at_reference: float
    power_target: float
    #: declared effect size -> power. Declared in advance, never read off the observed statistic.
    power_curve: tuple[tuple[float, float], ...]
    #: (c) declared effect size -> P(this gate rejects | a true edge of that size exists).
    p_reject_given_true: tuple[tuple[float, float], ...]
    note: str

    @property
    def powered(self) -> bool:
        """True only for POWERED-NEGATIVE. INDETERMINATE is not powered -- it is unlabellable."""
        return self.label == POWERED

    def summary(self) -> str:
        if self.label == INDETERMINATE:
            return f"{self.name}: INDETERMINATE -- {self.note}"
        band = (
            "INSIDE" if self.min_detectable_effect <= self.reference_effect else "ABOVE"
        )
        return (
            f"{self.name}: {self.label} -- min detectable {self.effect_unit} "
            f"{self.min_detectable_effect:.3f} ({band} the {self.reference_effect:g} reference), "
            f"power {self.power_at_reference:.1%}, so P(reject | true {self.reference_effect:g}) "
            f"= {1.0 - self.power_at_reference:.1%}"
        )

    def as_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "source": self.source,
            "label": self.label,
            "effect_unit": self.effect_unit,
            "alpha": self.alpha,
            "n_tests": self.n_tests,
            "z_critical": _round(self.z_critical, 4),
            "n_eff": _round(self.n_eff, 2),
            "years_eff": _round(self.years_eff, 4),
            "min_detectable_effect": _round(self.min_detectable_effect, 4),
            "reference_effect": _round(self.reference_effect, 4),
            "power_at_reference": _round(self.power_at_reference, 4),
            "power_target": self.power_target,
            "power_curve": {f"{k:g}": _round(v, 4) for k, v in self.power_curve},
            "p_reject_given_true": {
                f"{k:g}": _round(v, 4) for k, v in self.p_reject_given_true
            },
            "note": self.note,
        }


def _round(x: float, nd: int) -> float | None:
    """JSON-safe rounding. inf/nan become null rather than a token json.dump silently emits.

    `json.dump` writes bare `Infinity`/`NaN`, which is not valid JSON and which every strict reader
    on the other side rejects. An unreadable artifact is an unpublished one, and this module exists
    to make a number publishable.
    """
    return round(float(x), nd) if math.isfinite(x) else None


def _label(power_at_reference: float, power_target: float) -> str:
    if not math.isfinite(power_at_reference):
        return INDETERMINATE
    return POWERED if power_at_reference >= power_target else UNDERPOWERED


def sharpe_negative(
    name: str,
    *,
    n_bars: float,
    source: str = "",
    ppy: float = PPY,
    n_tests: int = 1,
    alpha: float = DEFAULT_ALPHA,
    n_units: int = 1,
    cross_corr: float = 0.0,
    deflator: float = 1.0,
    effects: Sequence[float] = DECLARED_SHARPES,
    reference_effect: float = REFERENCE_SHARPE,
    power_target: float = POWER_TARGET,
    two_sided: bool = False,
    note: str = "",
) -> Type2Cost:
    """Label a Sharpe-scale rejection (a campaign candidate, a pooled mechanism, a NO-GO screen).

    `n_bars` and `ppy` must describe the SAME clock -- 17,568 five-minute bars is `n_bars=17568,
    ppy=365*24*12`, not `ppy=365`. Getting that pair wrong is the one way to make this function
    overstate power, so callers reading an artifact should derive `ppy` from the artifact's declared
    interval rather than defaulting it.
    """
    years = effective_years(
        n_bars, ppy=ppy, n_units=n_units, cross_corr=cross_corr, deflator=deflator
    )
    if years < _MIN_YEARS:
        return indeterminate(
            name,
            "no usable elapsed time: the artifact records no sample length this rejection "
            "could have been taken on",
            source=source,
            effect_unit="annualised_sharpe",
        )
    mde = min_detectable_sharpe(
        years=years, n_tests=n_tests, alpha=alpha, power=power_target, two_sided=two_sided
    )
    curve = tuple(
        (float(e), sharpe_power(e, years=years, n_tests=n_tests, alpha=alpha, two_sided=two_sided))
        for e in effects
    )
    at_ref = sharpe_power(
        reference_effect, years=years, n_tests=n_tests, alpha=alpha, two_sided=two_sided
    )
    return Type2Cost(
        name=name,
        source=source,
        label=_label(at_ref, power_target),
        effect_unit="annualised_sharpe",
        alpha=float(alpha),
        n_tests=max(1, int(n_tests)),
        z_critical=critical_z(alpha, n_tests, two_sided=two_sided),
        n_eff=years * float(ppy),
        years_eff=years,
        min_detectable_effect=mde,
        reference_effect=float(reference_effect),
        power_at_reference=at_ref,
        power_target=float(power_target),
        power_curve=curve,
        p_reject_given_true=tuple((e, 1.0 - p) for e, p in curve),
        note=note,
    )


def correlation_negative(
    name: str,
    *,
    n_obs: float,
    source: str = "",
    horizon_periods: float = 1.0,
    panel_width: int = 1,
    n_tests: int = 1,
    alpha: float = DEFAULT_ALPHA,
    effects: Sequence[float] = DECLARED_CORRELATION_EFFECTS,
    reference_effect: float = REFERENCE_CORRELATION_EFFECT,
    power_target: float = POWER_TARGET,
    two_sided: bool = True,
    effect_unit: str = "ic",
    note: str = "",
) -> Type2Cost:
    """Label a correlation-scale rejection: an axis-screen cell, an event study, a lagged beta.

    `effect_unit` is free text because the arithmetic is shared: an IC, a Cohen's-d mean shift and a
    standardised abnormal return all have a critical value of z/sqrt(n). Naming the unit in the
    artifact keeps a reader from comparing a 0.03 IC floor against a 0.2 mean-shift floor as though
    they were the same quantity.
    """
    n_eff = correlation_n_eff(n_obs, horizon_periods=horizon_periods, panel_width=panel_width)
    if n_eff < _MIN_N_EFF:
        return indeterminate(
            name,
            "no usable effective sample: fewer than three independent observations behind the "
            "statistic",
            source=source,
            effect_unit=effect_unit,
        )
    mde = min_detectable_correlation(
        n_eff=n_eff, n_tests=n_tests, alpha=alpha, power=power_target, two_sided=two_sided
    )
    curve = tuple(
        (
            float(e),
            correlation_power(e, n_eff=n_eff, n_tests=n_tests, alpha=alpha, two_sided=two_sided),
        )
        for e in effects
    )
    at_ref = correlation_power(
        reference_effect, n_eff=n_eff, n_tests=n_tests, alpha=alpha, two_sided=two_sided
    )
    return Type2Cost(
        name=name,
        source=source,
        label=_label(at_ref, power_target),
        effect_unit=effect_unit,
        alpha=float(alpha),
        n_tests=max(1, int(n_tests)),
        z_critical=critical_z(alpha, n_tests, two_sided=two_sided),
        n_eff=n_eff,
        years_eff=float("nan"),
        min_detectable_effect=mde,
        reference_effect=float(reference_effect),
        power_at_reference=at_ref,
        power_target=float(power_target),
        power_curve=curve,
        p_reject_given_true=tuple((e, 1.0 - p) for e, p in curve),
        note=note,
    )


def indeterminate(
    name: str, why: str, *, source: str = "", effect_unit: str = "unrecorded"
) -> Type2Cost:
    """A rejection whose artifact does not record the sample it was taken on.

    NOT A NEUTRAL OUTCOME AND NOT AN ERROR PATH. A permanent kill written down without its sample
    size cannot be told apart from a blind one, so it is counted with the underpowered in every
    headline this module produces. The alternative -- inferring a sample size from prose -- would
    manufacture the evidence whose absence is the finding.
    """
    return Type2Cost(
        name=name,
        source=source,
        label=INDETERMINATE,
        effect_unit=effect_unit,
        alpha=DEFAULT_ALPHA,
        n_tests=1,
        z_critical=float("nan"),
        n_eff=float("nan"),
        years_eff=float("nan"),
        min_detectable_effect=float("nan"),
        reference_effect=float("nan"),
        power_at_reference=float("nan"),
        power_target=POWER_TARGET,
        power_curve=(),
        p_reject_given_true=(),
        note=why,
    )


# --------------------------------------------------------------------------- desk-level headline


@dataclass(frozen=True)
class DeskHeadline:
    """Of all recorded negatives, what fraction were powered enough to mean anything."""

    n_negatives: int
    n_powered: int
    n_underpowered: int
    n_indeterminate: int
    fraction_powered: float
    verdict: str

    def summary(self) -> str:
        return (
            f"{self.n_powered} of {self.n_negatives} recorded negatives "
            f"({self.fraction_powered:.1%}) were powered enough to mean anything; "
            f"{self.n_underpowered} could not have seen a real edge and "
            f"{self.n_indeterminate} record no sample size at all :: {self.verdict}"
        )


def headline(costs: Sequence[Type2Cost]) -> DeskHeadline:
    """Aggregate labelled rejections into the one desk-level number.

    INDETERMINATE COUNTS IN THE DENOMINATOR AND NEVER IN THE NUMERATOR. Dropping unlabellable
    rejections would compute the powered fraction of the negatives that happened to record their
    sample size, which is a strictly more flattering question than the one asked -- and the
    selection is not random, since the artifacts that record a sample size are the newer, better
    instrumented ones. Reporting that number as "the desk's negatives" would be the same
    unmeasured-reported-as-measured defect this module exists to name.
    """
    total = len(costs)
    powered = sum(1 for c in costs if c.label == POWERED)
    under = sum(1 for c in costs if c.label == UNDERPOWERED)
    indet = sum(1 for c in costs if c.label == INDETERMINATE)
    frac = (powered / total) if total > 0 else float("nan")
    if total == 0:
        verdict = "NO RECORDED NEGATIVES READ -- nothing to label"
    elif frac >= 0.5:
        verdict = (
            "most recorded negatives are informative: the desk's zeros are mostly evidence of "
            "absence, and the marginal hour goes to NEW mechanisms rather than to more power"
        )
    else:
        verdict = (
            "MOST RECORDED NEGATIVES CARRY NO INFORMATION: they could not have detected an edge "
            "of the size the desk is looking for, so they are absence of evidence and must not be "
            "read as evidence of absence. Sample LENGTH and pooling are the levers; alpha is not"
        )
    return DeskHeadline(total, powered, under, indet, frac, verdict)
