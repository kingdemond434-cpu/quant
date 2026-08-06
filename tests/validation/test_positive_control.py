"""THE INSTRUMENT THAT CERTIFIES A GATE -- 80 statements, and the test file its own docstring
cites as the guardian of a load-bearing asymmetry did not exist until now.

`positive_control.py` says, verbatim: "``null_cohort`` therefore returns raw, un-standardised
draws, and ``test_positive_control.py`` asserts that it does." It did not. The asymmetry it names
-- exact where "good" is DEFINED, raw where dispersion is MEASURED -- was documented, relied upon,
and unguarded.

WHY THE MODULE EXISTS (R0017). 434 candidates tested, 0 promoted. Two readings explain that
equally well: price space is picked clean, or the gate is welded shut. Telling them apart needs a
candidate whose quality is KNOWN.

WHY THE OLD PROBE FOOLED AN AUDIT, and why the fix is subtle. It drew `mu + sd * t(df)`, which is
arithmetically correct -- the series really does have true annualised Sharpe `target`. It is also
useless as a control, because the standard error of an annualised Sharpe over T daily bars is
sqrt(PPY/T) = 1.085 at T=310. A draw with true SR +0.5 routinely REALISES anywhere in (-1.6, +2.6),
and the probe's fixed seed=7 realised -2.32. Every gate rejected it, correctly, and the audit
recorded that the funnel cannot promote good candidates. It had never been asked.

So the two properties under test here are the two halves of that lesson:

  1. A control must have its target sample Sharpe BY CONSTRUCTION, not in expectation -- asserted
     at several T and many seeds, because "in expectation" is exactly what looked fine before.
  2. The null cohort must NOT be standardised. DSR and CSCV deflate against the cross-sectional
     DISPERSION of candidate Sharpes; pinning every null column to exact zero mean collapses that
     benchmark and manufactures survivors. This is the assertion the module asked for by name.
"""

from __future__ import annotations

import numpy as np
import pytest
from pydantic import ValidationError as ValidationErrorPydantic

from libs.validation import positive_control as PC
from libs.validation.errors import ValidationError

_PPY_SQRT = np.sqrt(PC.PPY)


def _sample_sharpe(r: np.ndarray) -> float:
    return float(r.mean() / r.std(ddof=1) * _PPY_SQRT)


# ================================================================ property 1: exact by construction

@pytest.mark.parametrize("target", [-2.0, 0.0, 0.5, 1.0, 3.0, 10.0])
@pytest.mark.parametrize("n_obs", [10, 310, 2_000])
def test_the_sample_sharpe_IS_the_target_at_every_size_and_sign(target, n_obs) -> None:
    """BY CONSTRUCTION, not in expectation. The previous probe was correct in expectation and
    realised -2.32 against a +0.5 target on its one fixed seed."""
    r = PC.exact_sharpe_series(target, n_obs, rng=np.random.default_rng(0))
    assert _sample_sharpe(r) == pytest.approx(target, abs=1e-9)


@pytest.mark.parametrize("seed", range(25))
def test_NO_SEED_can_move_the_realised_sharpe(seed: int) -> None:
    """THE HEART OF R0017. Sampling error must be exactly zero where "good" is DEFINED, or the
    thing under test stops being the gate and becomes the draw."""
    r = PC.exact_sharpe_series(0.5, 310, rng=np.random.default_rng(seed))
    assert _sample_sharpe(r) == pytest.approx(0.5, abs=1e-9)


def test_the_old_expectation_based_construction_really_would_have_scattered() -> None:
    """The counterfactual, measured rather than asserted -- it is the reason the fix is not
    cosmetic. At T=310 the standard error of an annualised Sharpe is sqrt(365/310) = 1.085, so a
    +0.5 target lands anywhere in roughly (-1.6, +2.6)."""
    sd = 0.40 / _PPY_SQRT
    mu = 0.5 * sd / _PPY_SQRT
    realised = []
    for seed in range(200):
        rng = np.random.default_rng(seed)
        realised.append(_sample_sharpe(mu + sd * rng.standard_t(6, size=310)))
    assert np.std(realised) > 0.5, "the old construction was not scattered -- premise broken"
    assert min(realised) < 0.0, "and it really does realise NEGATIVE on a positive target"


def test_only_the_first_two_moments_are_pinned_and_the_fat_tails_survive() -> None:
    """A control that had been Gaussianised would certify the gate against a distribution the desk
    never trades. Kurtosis is what the tail-risk gates actually see."""
    r = PC.exact_sharpe_series(1.0, 5_000, rng=np.random.default_rng(3))
    z = (r - r.mean()) / r.std(ddof=1)
    kurt = float((z ** 4).mean())
    assert kurt > 3.5, f"excess kurtosis gone (kurt={kurt:.2f}) -- the innovations were flattened"


def test_the_volatility_is_approximately_the_requested_annual_vol() -> None:
    r = PC.exact_sharpe_series(1.0, 4_000, rng=np.random.default_rng(4), ann_vol=0.40)
    assert float(r.std(ddof=1) * _PPY_SQRT) == pytest.approx(0.40, rel=0.02)


def test_the_drift_IS_the_net_edge() -> None:
    """Costs are assumed already netted out, matching what `net_returns` hands the gauntlet. A
    control built gross would certify the gate against an edge that does not survive fees."""
    r = PC.exact_sharpe_series(2.0, 1_000, rng=np.random.default_rng(5))
    assert r.mean() > 0.0


@pytest.mark.parametrize(("kwargs", "match"), [
    ({"n_obs": 2}, "n_obs >= 3"),
    ({"ann_vol": 0.0}, "ann_vol must be positive"),
    ({"ann_vol": -0.4}, "ann_vol must be positive"),
    ({"df": 2}, "df > 2"),
    ({"df": 1}, "df > 2"),
])
def test_degenerate_parameters_RAISE_rather_than_returning_a_broken_control(kwargs,
                                                                           match) -> None:
    """A silently-wrong control certifies a gate against nothing, and the certification is what
    everything downstream trusts. df<=2 is the sharp one: Student-t has INFINITE variance there,
    so the sample sd is meaningless and the pinned Sharpe would be a number about nothing."""
    args = {"n_obs": 100, "rng": np.random.default_rng(0), **kwargs}
    with pytest.raises(ValidationError, match=match):
        PC.exact_sharpe_series(1.0, **args)


# ================================================================ property 2: the null stays RAW

def test_the_null_cohort_is_NOT_standardised_and_keeps_its_dispersion() -> None:
    """THE ASSERTION THE MODULE ASKED FOR BY NAME. DSR and CSCV deflate against the cross-sectional
    dispersion of candidate Sharpes. Pinning every null column to exact zero mean collapses that
    benchmark and MANUFACTURES SURVIVORS -- the same R0017 shape, one level deeper and pointing the
    other way."""
    cohort = PC.null_cohort(200, 310, rng=np.random.default_rng(11))
    sharpes = np.array([_sample_sharpe(cohort[:, j]) for j in range(cohort.shape[1])])
    assert float(sharpes.std(ddof=1)) > 0.5, (
        "the null columns have no Sharpe dispersion -- the deflation benchmark is collapsed")
    assert float(np.abs(sharpes).max()) > 1.0, (
        "no null column realised a large Sharpe; a raw cohort must produce some by luck")


def test_the_asymmetry_is_real_good_is_pinned_and_null_is_not() -> None:
    """Stated as one assertion because it is one design decision: exact where "good" is DEFINED,
    raw where dispersion is MEASURED."""
    rng = np.random.default_rng(12)
    good = [_sample_sharpe(PC.exact_sharpe_series(1.0, 310, rng=np.random.default_rng(s)))
            for s in range(50)]
    cohort = PC.null_cohort(50, 310, rng=rng)
    null = [_sample_sharpe(cohort[:, j]) for j in range(50)]
    assert float(np.std(good)) == pytest.approx(0.0, abs=1e-9)
    assert float(np.std(null)) > 0.3


def test_the_null_cohort_is_centred_on_zero_edge_in_aggregate() -> None:
    """Individually raw, collectively unbiased. A null cohort with drift would be a positive
    control wearing the wrong label."""
    cohort = PC.null_cohort(400, 310, rng=np.random.default_rng(13))
    sharpes = [_sample_sharpe(cohort[:, j]) for j in range(cohort.shape[1])]
    assert float(np.mean(sharpes)) == pytest.approx(0.0, abs=0.2)


def test_the_null_cohort_has_the_requested_shape_and_scale() -> None:
    cohort = PC.null_cohort(7, 250, rng=np.random.default_rng(14), ann_vol=0.4)
    assert cohort.shape == (250, 7)
    assert float(cohort.std(ddof=1) * _PPY_SQRT) == pytest.approx(0.4, rel=0.25)


def test_an_empty_null_cohort_is_refused() -> None:
    with pytest.raises(ValidationError, match="n_candidates >= 1"):
        PC.null_cohort(0, 100, rng=np.random.default_rng(0))


# ================================================================ the certification itself

def _gate(min_sharpe: float):
    """A gate that admits on realised Sharpe alone -- the simplest thing that can be certified."""
    def verdict(rets: np.ndarray, realised: float) -> tuple[bool, list[str]]:
        return (realised >= min_sharpe, [] if realised >= min_sharpe else ["sharpe_floor"])
    return verdict


def test_a_WELDED_SHUT_gate_is_NOT_CERTIFIED_and_says_the_results_are_uninterpretable() -> None:
    """THE READING THE MODULE EXISTS TO PRODUCE. If a known-good candidate cannot pass, every
    '0 survivors' result on that path means nothing at all -- and that has to be said, not implied.
    """
    rep = PC.certify_gauntlet(_gate(999.0), n_obs=310, n_seeds=3)
    assert rep.certified is False and not rep
    assert "NOT CERTIFIED" in rep.verdict
    assert "uninterpretable" in rep.verdict
    assert rep.min_passing_sharpe is None


def test_a_LEAKY_gate_is_NOT_CERTIFIED_even_though_it_admits_good_candidates() -> None:
    """Admitting a good candidate is necessary and not sufficient. A gate that also passes noise
    leaks phantom edges straight into the forward clocks, where they consume scarce slots and
    raise the Holm bar for everything genuine."""
    rep = PC.certify_gauntlet(_gate(-99.0), n_obs=310, n_seeds=4)
    assert rep.certified is False
    assert rep.null_false_pass_rate == 1.0
    assert "leaks phantom edges" in rep.verdict


def test_a_SOUND_gate_is_certified_and_reports_the_weakest_edge_it_can_see() -> None:
    """The number that turns '0 survivors' into a statement: this gate cannot see anything below
    Sharpe X, so a picked-clean space and a blind instrument are finally distinguishable."""
    rep = PC.certify_gauntlet(_gate(2.5), n_obs=310, n_seeds=3)
    assert rep.certified is True and bool(rep) is True
    assert rep.min_passing_sharpe == 3.0
    assert "CERTIFIED" in rep.verdict and rep.null_false_pass_rate == 0.0


def test_the_pass_rate_is_reported_per_target_and_is_monotone_for_a_sharpe_gate() -> None:
    rep = PC.certify_gauntlet(_gate(2.5), n_obs=310, n_seeds=3)
    assert rep.pass_rate_by_sharpe["0.5"] == 0.0
    assert rep.pass_rate_by_sharpe["3"] == 1.0
    assert rep.pass_rate_by_sharpe["10"] == 1.0


def test_EVERY_TARGET_IS_RUN_ACROSS_INDEPENDENT_SEEDS() -> None:
    """The second half of the R0017 lesson: one seed is one draw, and a single unlucky draw reused
    down a sweep produces a perfectly smooth, perfectly wrong answer."""
    seen: list[int] = []

    def verdict(rets: np.ndarray, realised: float) -> tuple[bool, list[str]]:
        seen.append(hash(rets.tobytes()))
        return True, []

    PC.certify_gauntlet(verdict, n_obs=64, targets=(1.0,), n_seeds=8)
    good = seen[:8]
    assert len(set(good)) == 8, "the same draw was reused across seeds"


def test_the_null_controls_use_a_DIFFERENT_seed_stream_from_the_good_ones() -> None:
    """Sharing the stream would correlate the two arms, so a lucky null draw would pair with the
    good control that shared its noise -- and the false-pass rate would stop being independent
    evidence."""
    draws: list[bytes] = []

    def verdict(rets: np.ndarray, realised: float) -> tuple[bool, list[str]]:
        draws.append(rets.tobytes())
        return True, []

    PC.certify_gauntlet(verdict, n_obs=64, targets=(0.0,), n_seeds=5)
    assert len(set(draws)) == 10, "the good arm and the null arm drew the same series"


def test_a_gate_is_only_named_a_BLOCKER_when_it_was_the_SOLE_cause() -> None:
    """A gate that fired alongside three others did not block anything on its own, and counting it
    would send the desk to loosen a bar that was never the binding one."""
    def verdict(rets: np.ndarray, realised: float) -> tuple[bool, list[str]]:
        if realised < 4.0:
            return False, ["dsr"] if realised < 1.0 else ["dsr", "pbo", "capacity"]
        return True, []

    rep = PC.certify_gauntlet(verdict, n_obs=310, n_seeds=2)
    assert rep.blocking_gates.get("dsr", 0) > 0
    assert "pbo" not in rep.blocking_gates and "capacity" not in rep.blocking_gates


def test_the_null_tolerance_is_configurable_and_binds() -> None:
    """A 5% default is the declared bar. Making it explicit means a caller who needs a stricter one
    does not have to reimplement the whole certification to get it."""
    flaky = [True, False, False, False]

    def verdict(rets: np.ndarray, realised: float) -> tuple[bool, list[str]]:
        return (True, []) if realised > 0.1 else (flaky.pop(0) if flaky else False, ["x"])

    strict = PC.certify_gauntlet(verdict, n_obs=310, n_seeds=4, null_tolerance=0.0)
    assert strict.certified is False


def test_zero_seeds_is_refused_rather_than_certifying_on_no_evidence() -> None:
    """A certification computed from nothing is the loosest possible gate wearing a certificate."""
    with pytest.raises(ValidationError, match="n_seeds >= 1"):
        PC.certify_gauntlet(_gate(1.0), n_obs=310, n_seeds=0)


def test_the_report_is_frozen_so_a_certification_cannot_be_edited_after_the_fact() -> None:
    rep = PC.certify_gauntlet(_gate(2.5), n_obs=310, n_seeds=2)
    with pytest.raises(ValidationErrorPydantic):
        rep.certified = True                      # type: ignore[misc]


def test_the_realised_sharpe_handed_to_the_gate_is_recorded_on_every_outcome() -> None:
    """The gate is graded on what it actually saw. Recording the TARGET instead would hide exactly
    the discrepancy that produced R0017."""
    captured: list[float] = []

    def verdict(rets: np.ndarray, realised: float) -> tuple[bool, list[str]]:
        captured.append(realised)
        return True, []

    PC.certify_gauntlet(verdict, n_obs=310, targets=(1.5,), n_seeds=3)
    assert all(v == pytest.approx(1.5, abs=1e-9) for v in captured[:3])
