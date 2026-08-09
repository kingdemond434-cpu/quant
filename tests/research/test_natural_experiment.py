"""DiD identification: it must REFUSE the ways a causal claim goes fake, and PASS a planted one.

Both directions are load-bearing and the desk has been burned by testing only one. A module that
only ever refuses has not been shown to work -- it has been shown to be quiet, and "no survivors"
then means nothing (the 420/0 instrument artifact, L1.25). So there is a PLANTED POSITIVE CONTROL
here: a cohort with a real, known effect and clean pre-trends must come back PASS with an estimate
close to what was planted. And there is a PLANTED SELECTION cohort -- the failure this module
exists for -- which must come back REFUSED rather than significant.
"""

from __future__ import annotations

import numpy as np
import pytest

from libs.research.natural_experiment import (
    MAX_TREATED_SHARE,
    MIN_PRE_OBS,
    TreatedUnit,
    control_mean,
    difference_in_differences,
)
from libs.validation.errors import ValidationError

NOTE = "vesting schedules are fixed at token genesis, years before the outcome window"


def _unit(rng, uid: str, *, effect: float = 0.0, drift: float = 0.0, n_pre: int = 30,
          n_post: int = 5, cohort: str = "", day: int = 0) -> TreatedUnit:
    """One clean unit. `effect` shifts the treated POST leg only -- a real causal effect.
    `drift` shifts the treated PRE leg -- selection, visible before the shock.

    `day` STAGGERS the event date. It defaults to 0 only for the tests that refuse before
    inference is ever reached; any test asserting a PASS must stagger, because units sharing one
    event date share one market draw and event_study correctly discounts them to n_eff=1.
    """
    sd = 0.02
    return TreatedUnit(
        unit_id=uid, event_ts=1_700_000_000.0 + day * 86_400.0, cohort_key=cohort,
        treated_pre=list(rng.normal(drift, sd, n_pre)),
        treated_post=list(rng.normal(effect, sd, n_post)),
        control_pre=list(rng.normal(0.0, sd, n_pre)),
        control_post=list(rng.normal(0.0, sd, n_post)),
    )


# ------------------------------------------------------------------ the positive control


def test_planted_effect_is_recovered_and_passes():
    """THE CONTROL THAT WAS NEVER ASKED. A known effect, clean pre-trends, must PASS."""
    rng = np.random.default_rng(7)
    planted = -0.05
    units = [_unit(rng, f"S{i}", effect=planted, cohort=f"S{i}", day=i * 3)
             for i in range(40)]
    res = difference_in_differences(
        units, n_control_pool=200, exogeneity_note=NOTE, direction="decrease")

    assert res.identified, res.verdict
    assert res.passed, res.verdict
    assert res.effect == pytest.approx(planted, abs=0.01), res.effect
    assert res.inference is not None and res.inference.n_events == 40


def test_a_true_null_does_not_pass():
    """The other half of the control: no planted effect must NOT come back significant."""
    rng = np.random.default_rng(11)
    units = [_unit(rng, f"S{i}", cohort=f"S{i}", day=i * 3) for i in range(40)]
    res = difference_in_differences(
        units, n_control_pool=200, exogeneity_note=NOTE, direction="decrease")
    assert res.identified, "a clean null should still be IDENTIFIED -- it just has no effect"
    assert not res.passed, res.verdict


# ------------------------------------------------------------------ the four ways it goes fake


def test_planted_selection_is_refused_not_reported():
    """THE ONE THAT ACTUALLY BITES. Units selected on prior performance diverge in the PRE
    period; DiD cannot separate that from the effect, so it must refuse and say so."""
    rng = np.random.default_rng(3)
    units = [_unit(rng, f"S{i}", drift=-0.03, effect=-0.03, cohort=f"S{i}") for i in range(40)]
    res = difference_in_differences(
        units, n_control_pool=200, exogeneity_note=NOTE, direction="decrease")

    assert not res.identified
    assert not res.passed
    assert not res.parallel_trends_ok
    assert "PARALLEL-TRENDS-VIOLATED" in res.verdict
    assert "SELECTION" in res.verdict
    # AND THE PART THAT MATTERS MOST: no p-value is computed on an unidentified estimate, so
    # there is no precise-looking number for a reader to quote.
    assert res.inference is None
    assert "is NOT reported as an effect" in res.verdict


def test_sutva_refuses_when_the_control_pool_is_too_thin():
    rng = np.random.default_rng(5)
    units = [_unit(rng, f"S{i}", cohort=f"S{i}") for i in range(40)]
    res = difference_in_differences(
        units, n_control_pool=10, exogeneity_note=NOTE, direction="decrease")
    assert not res.identified
    assert "SUTVA-VIOLATED" in res.verdict
    assert res.treated_share > MAX_TREATED_SHARE


def test_short_pre_window_is_untestable_never_ok():
    """Failing to reject parallel trends on 4 points is absence of power, not evidence."""
    rng = np.random.default_rng(9)
    units = [_unit(rng, f"S{i}", n_pre=MIN_PRE_OBS - 1, cohort=f"S{i}") for i in range(40)]
    res = difference_in_differences(
        units, n_control_pool=200, exogeneity_note=NOTE, direction="decrease")
    assert not res.identified
    assert "ASSUMPTION-UNTESTABLE" in res.verdict
    assert "ABSENCE OF POWER" in res.verdict
    assert res.inference is None


def test_empty_cohort_refuses():
    res = difference_in_differences(
        [], n_control_pool=200, exogeneity_note=NOTE, direction="decrease")
    assert not res.passed
    assert "No treated units" in res.verdict


# ------------------------------------------------------------------ SUTVA counts MEMBERS


def test_repeat_events_on_one_symbol_are_one_cross_sectional_member():
    """The bug found by running this on the first real cohort: 1,019 insider events on 50 symbols
    against 195 controls is a 20% treated share, not 84%. Counting events against a pool of
    symbols refuses every well-powered study, and it fails silently."""
    rng = np.random.default_rng(13)
    # 50 symbols x 8 events each = 400 units, but only 50 members of the cross-section.
    units = [_unit(rng, f"S{s}@{e}", cohort=f"S{s}") for s in range(50) for e in range(8)]
    res = difference_in_differences(
        units, n_control_pool=195, exogeneity_note=NOTE, direction="decrease")

    assert res.treated_share == pytest.approx(50 / 245, abs=0.005), res.treated_share
    assert "SUTVA" not in res.verdict, res.verdict
    # Without cohort_key the same cohort is 400/(400+195) = 67% and would be refused outright.
    naive = difference_in_differences(
        [u.model_copy(update={"cohort_key": ""}) for u in units],
        n_control_pool=195, exogeneity_note=NOTE, direction="decrease")
    assert "SUTVA-VIOLATED" in naive.verdict


# ------------------------------------------------------------------ the exogeneity argument


def test_exogeneity_note_is_required():
    rng = np.random.default_rng(17)
    units = [_unit(rng, f"S{i}", cohort=f"S{i}") for i in range(40)]
    with pytest.raises(ValidationError, match="exogeneity_note is required"):
        difference_in_differences(
            units, n_control_pool=200, exogeneity_note="   ", direction="decrease")


def test_the_note_is_carried_into_the_result():
    """It is never inspected by the code -- it is an argument about the world -- so the only way
    it stays honest is by travelling with the estimate."""
    rng = np.random.default_rng(19)
    units = [_unit(rng, f"S{i}", cohort=f"S{i}") for i in range(40)]
    res = difference_in_differences(
        units, n_control_pool=200, exogeneity_note=NOTE, direction="decrease")
    assert res.exogeneity_note == NOTE


# ------------------------------------------------------------------ the control leg


def test_control_mean_refuses_ragged_input():
    with pytest.raises(ValidationError, match="ragged control leg"):
        control_mean([[0.1, 0.2, 0.3], [0.1, 0.2]])


def test_control_mean_refuses_an_empty_leg():
    with pytest.raises(ValidationError, match="DiD needs untreated peers"):
        control_mean([])


def test_control_mean_is_the_cross_sectional_mean_per_day():
    assert control_mean([[0.0, 1.0], [1.0, 3.0]]) == [0.5, 2.0]


# ------------------------------------------------------------------ the pre-registered direction


def test_direction_must_be_pre_registered():
    rng = np.random.default_rng(23)
    units = [_unit(rng, f"S{i}", cohort=f"S{i}") for i in range(40)]
    with pytest.raises(ValidationError, match="pre-registered as 'increase' or 'decrease'"):
        difference_in_differences(
            units, n_control_pool=200, exogeneity_note=NOTE, direction="")


def test_a_negative_effect_is_undetectable_in_the_wrong_direction():
    """THE DEFECT THE POSITIVE CONTROL CAUGHT. event_study is one-sided POSITIVE, so the same
    planted -5% cohort passes as 'decrease' and reports NO-EFFECT as 'increase'. Without a
    pre-registered direction the first real cohort -- supply dilution, predicted sign DOWN --
    could never have been detected, and the failure is silent."""
    rng = np.random.default_rng(7)
    units = [_unit(rng, f"S{i}", effect=-0.05, cohort=f"S{i}", day=i * 3) for i in range(40)]
    kw = {"n_control_pool": 200, "exogeneity_note": NOTE}

    assert difference_in_differences(units, direction="decrease", **kw).passed
    wrong = difference_in_differences(units, direction="increase", **kw)
    assert not wrong.passed
    assert wrong.identified, "identification is direction-free -- only the inference is signed"


def test_the_reported_effect_keeps_its_natural_sign():
    """Only the inference input is oriented; a reader must see the real number."""
    rng = np.random.default_rng(7)
    units = [_unit(rng, f"S{i}", effect=-0.05, cohort=f"S{i}", day=i * 3) for i in range(40)]
    res = difference_in_differences(
        units, n_control_pool=200, exogeneity_note=NOTE, direction="decrease")
    assert res.effect < 0, res.effect
    assert res.direction == "decrease"
