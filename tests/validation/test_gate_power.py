"""A VALIDATOR NEVER MEASURED AGAINST A KNOWN EDGE IS UNCALIBRATED.

The first complete sweep killed 750 of 762 screen-clearing cells at F3. False positives and false
negatives are not symmetric in how they announce themselves: a loose gate ships a phantom edge and
the rails eventually say so, while a tight gate destroys real alpha silently with every board green.
The desk measures the first continuously and had never measured the second.
"""

from __future__ import annotations

import numpy as np
import pytest

from libs.validation.gate_power import (
    f3_both_arms_positive,
    plant,
    power_curve,
    run_controls,
    summarise,
)


def test_THE_GATE_IS_TRANSCRIBED_FROM_THE_SWEEP_NOT_ITS_DOCS() -> None:
    """Calibrating a rule the desk does not run is worthless. The sweep's condition is
    `r_is <= 0 or sign(r_is) != sign(r_oos)`, which on arm means is 'both strictly positive'."""
    ones, negs = np.ones(50), -np.ones(50)
    assert f3_both_arms_positive(ones, ones).passed
    assert not f3_both_arms_positive(ones, negs).passed
    assert not f3_both_arms_positive(negs, negs).passed, "two negative arms share a sign"
    assert not f3_both_arms_positive(np.zeros(50), ones).passed, "zero is not positive"


def test_A_CONDITIONAL_PLANT_IS_ABSENT_NOT_REVERSED() -> None:
    """Conflating the two would FLATTER the gate: rejecting an inverting mechanism is defensible,
    rejecting an absent one is the false negative under investigation."""
    rng = np.random.default_rng(0)
    a, b = plant(rng, 4000, 0.5, kind="conditional")
    assert float(np.mean(a)) > 0.3
    assert abs(float(np.mean(b))) < 0.1, "the second arm must be noise, not a reversed edge"


def test_A_NULL_PLANT_HAS_NO_EFFECT_IN_EITHER_ARM() -> None:
    rng = np.random.default_rng(0)
    a, b = plant(rng, 4000, 0.5, kind="null")
    assert abs(float(np.mean(a))) < 0.1 and abs(float(np.mean(b))) < 0.1


def test_AN_UNKNOWN_PLANT_SHAPE_RAISES_RATHER_THAN_GUESSING() -> None:
    with pytest.raises(ValueError, match="unknown planted kind"):
        plant(np.random.default_rng(0), 100, 0.1, kind="vibes")


def test_A_STABLE_EDGE_IS_KEPT_ALMOST_ALWAYS_AT_A_CLEAR_EFFECT() -> None:
    """The gate must work for what it was designed for, or the comparison means nothing."""
    c = power_curve(f3_both_arms_positive, name="F3", kind="stable",
                    effects=(0.2,), n_obs=1200, n_trials=200, seed=3)
    assert c.pass_rates[0] > 0.95


def test_THE_CONDITIONAL_PLATEAU_IS_ARITHMETIC_NOT_POWER() -> None:
    """THE CENTRAL FINDING. A conditional edge has NO effect in its second arm, so that arm is
    pure noise and lands positive by chance about half the time. F3 therefore discards roughly
    half of all conditional mechanisms HOWEVER STRONG they are -- more tape cannot fix it.
    """
    c = power_curve(f3_both_arms_positive, name="F3", kind="conditional",
                    effects=(0.1, 0.4, 1.0), n_obs=1200, n_trials=300, seed=5)
    for rate in c.pass_rates:
        assert 0.35 < rate < 0.65, f"expected a ~50% plateau, got {c.pass_rates}"
    assert c.pass_rates[-1] < 0.65, "a huge effect must NOT rescue a conditional edge"


def test_STABLE_AND_CONDITIONAL_DIVERGE_AT_THE_SAME_EFFECT_SIZE() -> None:
    """The gate is selecting on a property the desk never intended to select on, and only the two
    curves side by side make that visible rather than arguable."""
    eff = (0.2,)
    stable = power_curve(f3_both_arms_positive, name="F3", kind="stable",
                         effects=eff, n_obs=1200, n_trials=300, seed=7)
    cond = power_curve(f3_both_arms_positive, name="F3", kind="conditional",
                       effects=eff, n_obs=1200, n_trials=300, seed=7)
    assert stable.pass_rates[0] - cond.pass_rates[0] > 0.3


def test_HALF_POWER_IS_NONE_WHEN_THE_GATE_NEVER_REACHES_IT() -> None:
    """None is the FINDING: a gate that never reaches 50% power over the swept range cannot
    detect any edge there, and its kill counts say nothing about whether alpha was present."""
    c = power_curve(f3_both_arms_positive, name="F3", kind="stable",
                    effects=(0.0, 0.0001), n_obs=200, n_trials=60, seed=11)
    assert c.half_power_effect in (None, 0.0001)


def test_THE_NULL_POINT_IS_THE_FALSE_POSITIVE_RATE() -> None:
    c = power_curve(f3_both_arms_positive, name="F3", effects=(0.0, 0.2),
                    n_obs=800, n_trials=200, seed=13)
    assert c.false_positive_rate == c.pass_rates[0]
    assert 0.1 < c.false_positive_rate < 0.4, "a sign test on noise passes ~1/4 of the time"


def test_FALSE_NEGATIVE_RATE_IS_NONE_FOR_AN_UNSWEPT_EFFECT() -> None:
    c = power_curve(f3_both_arms_positive, name="F3", effects=(0.0, 0.2),
                    n_obs=400, n_trials=50, seed=17)
    assert c.false_negative_rate(0.2) is not None
    assert c.false_negative_rate(0.777) is None


def test_THE_SUMMARY_LEADS_WITH_THE_STRUCTURAL_GAP() -> None:
    rep = summarise(run_controls(n_obs=1000, n_trials=200, seed=19))
    head = str(rep["headline"])
    assert "CONDITIONAL" in head
    assert "ARITHMETIC, not power" in head or "gap that is a property of the RULE" in head


def test_MEASURING_A_GATE_IS_NOT_LICENCE_TO_LOOSEN_IT() -> None:
    """No function returns a recommended threshold, and the artifact says why -- this evidence is
    most tempting to misuse as 'many cells died, so lower the bar'."""
    rep = summarise(run_controls(n_obs=400, n_trials=50, seed=23))
    note = str(rep["note"])
    assert "never traded on" in note
    assert "never because many cells died" in note
    from pathlib import Path
    src = Path("libs/validation/gate_power.py").read_text("utf-8").lower()
    assert "recommended_threshold" not in src and "def suggest" not in src
