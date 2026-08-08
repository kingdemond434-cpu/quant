"""BEHAVIORAL tests for payoff-aware model selection.

The specification names one test explicitly: a higher-hit-rate / lower-EV model must LOSE to a
lower-hit-rate / higher-E[log W] model. That case is first, and it is constructed from the exact
numbers in the module docstring so the test and the argument cannot drift apart.
"""

from __future__ import annotations

import pytest

from libs.research.payoff_selection import (
    MIN_PREDICTIONS,
    ModelRecord,
    calibration_error,
    economic_score,
    expected_bps,
    expected_log_growth,
    rank,
    summarise,
)

#: 89% right, +1bp per win, -12bp per loss. Best on any accuracy leaderboard, and it loses money.
SNIPER = ModelRecord(name="sniper", n_predictions=900, hit_rate=0.89, win_bps=1.0, loss_bps=12.0,
                     trades_per_year=500, capital_fraction=0.2,
                     mean_predicted=0.90, mean_realised=0.89, mean_log_loss=0.31, auc=0.81)

#: 35% right and profitable, because it is paid asymmetrically.
GRINDER = ModelRecord(name="grinder", n_predictions=1400, hit_rate=0.35, win_bps=26.0,
                      loss_bps=9.0, trades_per_year=500, capital_fraction=0.2,
                      mean_predicted=0.36, mean_realised=0.35, mean_log_loss=0.62, auc=0.57)


def test_the_higher_hit_rate_model_loses_to_the_higher_elogw_model() -> None:
    """THE NAMED TEST. If this ever inverts, the module has started ranking on accuracy."""
    rows = rank([SNIPER, GRINDER])
    assert rows[0]["name"] == "grinder", (
        f"the 89%-accurate money-loser ranked first: {rows}")
    assert float(str(rows[0]["hit_rate"])) < float(str(rows[1]["hit_rate"]))
    assert expected_bps(SNIPER) < 0, "the sniper is supposed to be a net loser per trade"
    assert expected_bps(GRINDER) > 0


def test_the_report_states_the_inversion_in_words() -> None:
    """A ranking that is right and silent will be overridden by whoever reads the hit rates."""
    rep = summarise([SNIPER, GRINDER])
    assert "THE HIGHEST HIT RATE IS NOT THE BEST MODEL" in str(rep["headline"])
    assert "sniper" in str(rep["headline"]) and "grinder" in str(rep["headline"])


def test_auc_is_carried_as_a_diagnostic_and_never_ranked_on() -> None:
    """The sniper has the far better AUC. It must still lose."""
    rows = rank([SNIPER, GRINDER])
    assert rows[0]["auc_DIAGNOSTIC_ONLY"] == 0.57
    assert rows[1]["auc_DIAGNOSTIC_ONLY"] == 0.81
    assert "auc" in str(rows[0]).lower()


def test_a_break_even_model_has_negative_log_growth() -> None:
    """The arithmetic reason a flat-looking strategy bleeds: variance costs geometric growth even
    when the arithmetic mean is exactly zero."""
    even = ModelRecord(name="even", n_predictions=500, hit_rate=0.5, win_bps=10.0, loss_bps=10.0,
                       trades_per_year=1000, capital_fraction=0.5)
    assert expected_bps(even) == pytest.approx(0.0)
    g = expected_log_growth(even)
    assert g is not None and g < 0, "zero expected bps produced non-negative log growth"


def test_a_hundred_percent_loss_is_absorbing_and_ranks_last() -> None:
    doom = ModelRecord(name="doom", n_predictions=500, hit_rate=0.99, win_bps=50.0,
                       loss_bps=10_000.0, trades_per_year=100, capital_fraction=1.0)
    g = expected_log_growth(doom)
    assert g == float("-inf")
    rows = rank([doom, GRINDER])
    assert rows[0]["name"] == "grinder"
    assert rows[1]["ruin"] is True


def test_a_small_sample_is_unmeasured_not_a_hit_rate() -> None:
    """Tiny-sample win-rate worship is forbidden by name in the specification; this is where the
    ban is enforced rather than asserted."""
    tiny = ModelRecord(name="tiny", n_predictions=9, hit_rate=0.89, win_bps=40.0, loss_bps=5.0,
                       trades_per_year=200)
    g, why = economic_score(tiny)
    assert g is None
    assert "UNMEASURED" in why and "small-sample" in why
    rows = rank([tiny, GRINDER])
    assert rows[0]["name"] == "grinder", "an unmeasured model outranked a measured one"


def test_a_model_with_no_frequency_cannot_be_ranked() -> None:
    m = ModelRecord(name="orphan", n_predictions=500, hit_rate=0.6, win_bps=10.0, loss_bps=5.0,
                    trades_per_year=0)
    assert expected_log_growth(m) is None


def test_calibration_breaks_ties_and_is_none_when_unmeasured() -> None:
    assert calibration_error(ModelRecord("x", 200, 0.5, 1.0, 1.0, trades_per_year=10)) is None
    bad = ModelRecord("overconfident", 500, 0.55, 10.0, 8.0, trades_per_year=100,
                      mean_predicted=0.80, mean_realised=0.55)
    ce = calibration_error(bad)
    assert ce is not None and ce == pytest.approx(0.25)


def test_two_identical_economics_are_ordered_by_calibration() -> None:
    kw: dict[str, float] = {"n_predictions": 500, "hit_rate": 0.5, "win_bps": 20.0,
                            "loss_bps": 10.0, "trades_per_year": 200, "capital_fraction": 0.2}
    sharp = ModelRecord(name="sharp", mean_predicted=0.51, mean_realised=0.50, **kw)  # type: ignore[arg-type]
    fuzzy = ModelRecord(name="fuzzy", mean_predicted=0.80, mean_realised=0.50, **kw)  # type: ignore[arg-type]
    rows = rank([fuzzy, sharp])
    assert rows[0]["name"] == "sharp", (
        "equal economics were not broken by calibration -- a probability that does not mean what "
        "it says makes every downstream sizing decision wrong")


def test_an_empty_roster_says_selection_was_made_on_something_else() -> None:
    rep = summarise([])
    assert "UNEXERCISED" in str(rep["headline"])


def test_the_prediction_floor_is_not_silently_tiny() -> None:
    assert MIN_PREDICTIONS >= 100
