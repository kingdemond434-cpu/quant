"""Positive/negative controls for the validation gauntlet -- the instrument that certifies a gate.

WHY THIS EXISTS (R0017). The desk has tested 434 candidates and promoted 0. Two readings explain
that equally well: price space is picked clean, or the gate is welded shut. Telling them apart
needs a candidate whose quality is KNOWN, pushed through the real gauntlet: if a known-GOOD
candidate cannot pass, the gate is broken and every "0 survivors" result is uninterpretable; if a
known-NULL cohort passes, the gate leaks phantom edges straight into the forward clocks.

THE BUG THIS REPLACES, because it is subtle and it fooled an audit. The previous probe built its
"known-good" candidate as::

    mu = true_ann_sharpe * sd / sqrt(PPY)
    series = mu + sd * rng.standard_t(df, size=T)

That arithmetic is *correct*: the series is drawn from a distribution whose true annualised Sharpe
is ``true_ann_sharpe``. It is also useless as a control, for a reason that has nothing to do with
wiring. The standard error of an annualised Sharpe estimate over T daily bars is ``sqrt(PPY/T)`` --
**1.085 at T=310**. So a draw with true SR +0.5 routinely *realises* anywhere in (-1.6, +2.6), and
the probe's fixed ``seed=7`` happened to realise **-2.32**. Every gate then rejected it, correctly,
and the audit recorded that the funnel cannot promote good candidates. It had never been asked.
(The offset was identical on every row of the sweep -- one seed, one noise draw, reused
throughout -- which is what makes the artifact so easy to misread as a sign error.)

THE FIX: a control must have the target sample Sharpe **by construction**, not in expectation.
``exact_sharpe_series`` standardises the innovations and then adds the drift, so the returned
series' own sample Sharpe equals the target to floating precision at any T. Sampling error is then
zero where we need it to be zero -- in the definition of "good" -- and the only thing under test is
the gate.

THE TRAP ON THE OTHER SIDE (R0017's shape, one level deeper). Do NOT apply the same
standardisation to the null cohort. DSR and CSCV deflate by the *cross-sectional dispersion* of
candidate Sharpes; standardising every null column to exact zero mean destroys that dispersion,
collapses the deflation benchmark, and manufactures survivors. ``null_cohort`` therefore returns
raw, un-standardised draws, and ``test_positive_control.py`` asserts that it does. The asymmetry is
deliberate and load-bearing: exact where "good" is *defined*, raw where dispersion is *measured*.
"""

from __future__ import annotations

from collections.abc import Callable, Sequence

import numpy as np
from pydantic import BaseModel, ConfigDict

from libs.validation.errors import ValidationError

PPY = 365.0  # D1 crypto bars
_DEFAULT_ANN_VOL = 0.40  # a realistic levered crypto sleeve
_DEFAULT_DF = 6  # Student-t innovations: fat tails, finite variance


def exact_sharpe_series(
    target_ann_sharpe: float,
    n_obs: int,
    *,
    rng: np.random.Generator,
    ann_vol: float = _DEFAULT_ANN_VOL,
    df: int = _DEFAULT_DF,
) -> np.ndarray:
    """Fat-tailed daily net returns whose SAMPLE annualised Sharpe IS ``target_ann_sharpe``.

    The innovations are standardised to exact zero mean and unit sample sd (ddof=1) before the
    drift is added, so ``mean/std(ddof=1) * sqrt(PPY) == target_ann_sharpe`` to floating precision
    regardless of ``n_obs`` or seed. Shape (fat tails, autocorrelation-free, ~``ann_vol`` vol) is
    preserved; only the first two sample moments are pinned.

    Costs are assumed already netted out -- the drift IS the net edge, matching what ``net_returns``
    hands the gauntlet.
    """
    if n_obs < 3:
        raise ValidationError("exact_sharpe_series needs n_obs >= 3 to pin a sample sd")
    if ann_vol <= 0.0:
        raise ValidationError("ann_vol must be positive")
    if df <= 2:
        raise ValidationError("Student-t needs df > 2 for finite variance")

    sd = ann_vol / np.sqrt(PPY)
    z = rng.standard_t(df, size=n_obs)
    spread = z.std(ddof=1)
    if spread == 0.0:  # pathological draw; astronomically unlikely, still not silently wrong
        raise ValidationError("degenerate innovation draw (zero sample sd)")
    z = (z - z.mean()) / spread  # exact zero mean, exact unit sample sd
    return sd * (z + target_ann_sharpe / np.sqrt(PPY))


def null_cohort(
    n_candidates: int,
    n_obs: int,
    *,
    rng: np.random.Generator,
    ann_vol: float = _DEFAULT_ANN_VOL,
    df: int = _DEFAULT_DF,
) -> np.ndarray:
    """``(n_obs, n_candidates)`` matrix of RAW zero-edge draws -- deliberately NOT standardised.

    These columns must retain their natural cross-sectional Sharpe dispersion: DSR/CSCV deflate
    against exactly that dispersion, so pinning each column's moments would collapse the benchmark
    and manufacture survivors. See the module docstring.
    """
    if n_candidates < 1:
        raise ValidationError("null_cohort needs n_candidates >= 1")
    sd = ann_vol / np.sqrt(PPY)
    z = rng.standard_t(df, size=(n_obs, n_candidates)) / np.sqrt(df / (df - 2.0))
    return sd * z


class ControlOutcome(BaseModel):
    """Verdicts for one injected control candidate."""

    model_config = ConfigDict(frozen=True)

    target_ann_sharpe: float  # 0.0 marks a null control
    realised_ann_sharpe: float  # sample Sharpe actually handed to the gate
    survived: bool
    failed_gates: tuple[str, ...]


class CertificationReport(BaseModel):
    """Can this gauntlet admit a known edge, and does it still reject known noise?"""

    model_config = ConfigDict(frozen=True)

    n_seeds: int
    pass_rate_by_sharpe: dict[str, float]  # target ann Sharpe -> fraction admitted
    min_passing_sharpe: float | None  # lowest tested target admitted at least once
    null_false_pass_rate: float  # fraction of null controls wrongly admitted
    blocking_gates: dict[str, int]  # gate -> times it was the SOLE cause of a good control failing
    certified: bool  # admits a good candidate at all AND leaks no nulls
    verdict: str

    def __bool__(self) -> bool:
        return self.certified


def certify_gauntlet(
    verdict_fn: Callable[[np.ndarray, float], tuple[bool, Sequence[str]]],
    *,
    n_obs: int,
    targets: Sequence[float] = (0.5, 1.0, 1.5, 2.0, 3.0, 5.0, 7.0, 10.0),
    n_seeds: int = 12,
    seed0: int = 1000,
    ann_vol: float = _DEFAULT_ANN_VOL,
    df: int = _DEFAULT_DF,
    null_tolerance: float = 0.05,
) -> CertificationReport:
    """Push known-GOOD and known-NULL controls through ``verdict_fn`` and grade the gate itself.

    ``verdict_fn(returns, realised_ann_sharpe) -> (survived, failed_gate_names)`` is supplied by the
    caller so this module never has to know which gauntlet it is certifying -- the campaign-level
    plumbing (matrix, trial counts, sharpe_estimates) stays where it belongs.

    Every target is run across ``n_seeds`` INDEPENDENT seeds. That is the second half of the R0017
    lesson: one seed is one draw, and a single unlucky draw reused down a sweep produces a perfectly
    smooth, perfectly wrong answer.
    """
    if n_seeds < 1:
        raise ValidationError("certify_gauntlet needs n_seeds >= 1")

    outcomes: list[ControlOutcome] = []
    for target in targets:
        for k in range(n_seeds):
            rng = np.random.default_rng(seed0 + k)
            rets = exact_sharpe_series(target, n_obs, rng=rng, ann_vol=ann_vol, df=df)
            realised = float(rets.mean() / rets.std(ddof=1) * np.sqrt(PPY))
            survived, failed = verdict_fn(rets, realised)
            outcomes.append(ControlOutcome(
                target_ann_sharpe=target, realised_ann_sharpe=realised,
                survived=bool(survived), failed_gates=tuple(failed),
            ))

    nulls: list[ControlOutcome] = []
    for k in range(n_seeds):
        rng = np.random.default_rng(seed0 + 500_000 + k)
        rets = exact_sharpe_series(0.0, n_obs, rng=rng, ann_vol=ann_vol, df=df)
        realised = float(rets.mean() / rets.std(ddof=1) * np.sqrt(PPY))
        survived, failed = verdict_fn(rets, realised)
        nulls.append(ControlOutcome(
            target_ann_sharpe=0.0, realised_ann_sharpe=realised,
            survived=bool(survived), failed_gates=tuple(failed),
        ))

    pass_rate = {
        f"{t:g}": float(np.mean([o.survived for o in outcomes if o.target_ann_sharpe == t]))
        for t in targets
    }
    admitted = [t for t in targets if pass_rate[f"{t:g}"] > 0.0]
    min_passing = float(min(admitted)) if admitted else None
    null_fpr = float(np.mean([o.survived for o in nulls])) if nulls else 0.0

    blocking: dict[str, int] = {}
    for o in outcomes:
        if not o.survived and len(o.failed_gates) == 1:
            blocking[o.failed_gates[0]] = blocking.get(o.failed_gates[0], 0) + 1

    admits_good = min_passing is not None
    leaks_null = null_fpr > null_tolerance
    certified = admits_good and not leaks_null
    if not admits_good:
        verdict = (
            f"NOT CERTIFIED: no control passed, up to true annual Sharpe {max(targets):g} over "
            f"{n_obs} bars. The gate cannot promote a genuinely good candidate, so every "
            f"'0 survivors' result on this path is uninterpretable. Sole blockers: {blocking}"
        )
    elif leaks_null:
        verdict = (
            f"NOT CERTIFIED: null controls admitted at {null_fpr:.1%} (> {null_tolerance:.0%}) -- "
            f"the gate leaks phantom edges. Tighten before trusting any survivor."
        )
    else:
        verdict = (
            f"CERTIFIED: admits a true Sharpe >= {min_passing:g} candidate over {n_obs} bars; "
            f"null false-pass {null_fpr:.1%} <= {null_tolerance:.0%}."
        )
    return CertificationReport(
        n_seeds=n_seeds, pass_rate_by_sharpe=pass_rate, min_passing_sharpe=min_passing,
        null_false_pass_rate=null_fpr, blocking_gates=blocking, certified=certified,
        verdict=verdict,
    )
