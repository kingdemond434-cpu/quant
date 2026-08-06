"""DOES THE DESK KNOW HOW WRONG IT IS? -- 43 statements, untested until now.

Every organ here emits probabilities: p_success on a recommendation, a promotion's odds, a gate's
confidence. None of that is worth anything unless the desk finds out afterwards whether those
numbers were any good -- and the whole point of a calibration log is that it becomes a claim about
the desk which the desk cannot edit after the fact.

THE THREE PROPERTIES THAT MAKE IT HONEST, and each is one line from being lost:

  A SCORED FORECAST IS IMMUTABLE. `log_forecast` refuses to overwrite a resolved row. Without that,
  a forecast can be "refreshed" after the outcome is known, and the Brier score becomes a
  measurement of hindsight.

  RESOLUTION IS IDEMPOTENT. Re-resolving would let an outcome be flipped, which is the same failure
  from the other end.

  IT IS N-GATED AND SAYS SO. Below five outcomes it returns `status: insufficient` with every
  metric NULL rather than a Brier computed on two rows -- a number that would be quoted, would look
  like calibration, and would be noise.

The sign convention is the fourth: bias > 0 means forecasts were TOO HIGH (over-confident). It is
applied as a shrinkage on future p_success, so an inverted sign would make an over-confident desk
shrink its estimates UPWARD.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from libs.self_improvement import forecast_calibration as FC


@pytest.fixture(autouse=True)
def _isolated_log(tmp_path: Path, monkeypatch):
    monkeypatch.setattr(FC, "_LOG", tmp_path / "forecast_log.json")
    return FC._LOG


def _log_and_resolve(pairs: list[tuple[float, bool]]) -> None:
    for i, (p, outcome) in enumerate(pairs):
        FC.log_forecast(f"k{i}", p, "promotion")
        FC.resolve(f"k{i}", outcome)


# ============================================================ immutability

def test_a_RESOLVED_forecast_can_NEVER_be_overwritten(_isolated_log: Path) -> None:
    """THE PROPERTY THE WHOLE LOG RESTS ON. Without it a forecast can be 'refreshed' after the
    outcome is known, and the Brier score becomes a measurement of hindsight rather than of
    foresight."""
    FC.log_forecast("k", 0.2, "promotion")
    FC.resolve("k", True)
    FC.log_forecast("k", 0.99, "promotion")          # the tempting edit
    stored = json.loads(_isolated_log.read_text("utf-8"))["forecasts"]["k"]
    assert stored["p"] == 0.2
    assert stored["outcome"] == 1.0


def test_an_UNRESOLVED_forecast_may_still_be_refreshed(_isolated_log: Path) -> None:
    """The other half. A forecast that has not been scored is a live belief, and updating it as
    evidence arrives is exactly what a forecaster should do."""
    FC.log_forecast("k", 0.2, "promotion")
    FC.log_forecast("k", 0.6, "promotion")
    assert json.loads(_isolated_log.read_text("utf-8"))["forecasts"]["k"]["p"] == 0.6


def test_RESOLUTION_IS_IDEMPOTENT(_isolated_log: Path) -> None:
    """Re-resolving would let an outcome be flipped -- the same failure as editing the forecast,
    from the other end."""
    FC.log_forecast("k", 0.7, "promotion")
    FC.resolve("k", True)
    FC.resolve("k", False)
    assert json.loads(_isolated_log.read_text("utf-8"))["forecasts"]["k"]["outcome"] == 1.0


def test_resolving_an_UNKNOWN_key_is_a_no_op_rather_than_a_fabricated_row(
        _isolated_log: Path) -> None:
    """Creating a row on resolve would let an outcome be recorded with no forecast attached, which
    scores as a perfect prediction of nothing."""
    FC.resolve("never-forecast", True)
    # Stronger than "no row": it does not write AT ALL, so an outcome for a forecast nobody made
    # cannot even create the log. Asserted this way because the file's absence is the evidence.
    assert not _isolated_log.exists()
    assert FC.report()["n_resolved"] == 0


def test_the_resolution_carries_a_TIMESTAMP(_isolated_log: Path) -> None:
    """A scored forecast with no resolution time cannot be ordered against the evidence that
    resolved it."""
    FC.log_forecast("k", 0.7, "promotion")
    FC.resolve("k", True)
    row = json.loads(_isolated_log.read_text("utf-8"))["forecasts"]["k"]
    assert row["resolved_at"] and "T" in row["resolved_at"]
    assert row["updated"] and "T" in row["updated"]


# ============================================================ the N gate

def test_below_FIVE_outcomes_every_metric_is_NULL(_isolated_log: Path) -> None:
    """A Brier computed on two rows is a number that would be quoted, would look like calibration,
    and would be noise. Nulls cannot be quoted by accident."""
    _log_and_resolve([(0.9, True), (0.8, True)])
    rep = FC.report()
    assert rep["n_resolved"] == 2
    assert "insufficient" in rep["status"]
    assert rep["brier"] is None and rep["reliability"] is None
    assert rep["bias"] is None and rep["hit_rate_posterior"] is None


def test_an_EMPTY_log_reports_zero_rather_than_crashing(_isolated_log: Path) -> None:
    assert FC.report()["n_resolved"] == 0


def test_UNRESOLVED_forecasts_do_not_count_toward_the_gate(_isolated_log: Path) -> None:
    """Ten open forecasts and zero outcomes is not a calibrated desk. Counting them would open the
    gate on evidence that does not exist yet."""
    for i in range(10):
        FC.log_forecast(f"open{i}", 0.5, "promotion")
    assert FC.report()["n_resolved"] == 0


def test_AT_FIVE_outcomes_the_report_becomes_calibrated(_isolated_log: Path) -> None:
    _log_and_resolve([(0.9, True)] * 5)
    rep = FC.report()
    assert rep["status"] == "calibrated" and rep["n_resolved"] == 5
    assert rep["brier"] is not None


# ============================================================ the arithmetic

def test_a_PERFECT_forecaster_scores_BRIER_ZERO(_isolated_log: Path) -> None:
    _log_and_resolve([(1.0, True), (0.0, False)] * 3)
    rep = FC.report()
    assert rep["brier"] == pytest.approx(0.0)
    assert rep["reliability"] == pytest.approx(1.0)


def test_a_MAXIMALLY_WRONG_forecaster_scores_BRIER_ONE(_isolated_log: Path) -> None:
    """The scale has to run the whole way, or a bad desk and a mediocre one look alike."""
    _log_and_resolve([(1.0, False), (0.0, True)] * 3)
    assert FC.report()["brier"] == pytest.approx(1.0)


def test_a_COIN_FLIP_forecaster_scores_a_quarter(_isolated_log: Path) -> None:
    """0.5 on everything gives Brier 0.25 whatever happens -- the reference point every other
    score should be read against."""
    _log_and_resolve([(0.5, True), (0.5, False)] * 3)
    assert FC.report()["brier"] == pytest.approx(0.25)


def test_BIAS_POSITIVE_MEANS_OVER_CONFIDENT(_isolated_log: Path) -> None:
    """The sign is applied as a SHRINKAGE on future p_success. Inverted, an over-confident desk
    would shrink its estimates UPWARD -- compounding the error it was measuring."""
    _log_and_resolve([(0.9, False)] * 6)             # said 90%, happened never
    rep = FC.report()
    assert rep["bias"] > 0
    assert rep["bias_label"] == "over-confident"


def test_BIAS_NEGATIVE_MEANS_UNDER_CONFIDENT(_isolated_log: Path) -> None:
    _log_and_resolve([(0.1, True)] * 6)              # said 10%, happened always
    rep = FC.report()
    assert rep["bias"] < 0
    assert rep["bias_label"] == "under-confident"


def test_a_SMALL_bias_is_labelled_WELL_CALIBRATED(_isolated_log: Path) -> None:
    """A dead band, because no finite sample gives exactly zero and labelling a 1% drift as
    over-confident would make the label meaningless."""
    _log_and_resolve([(0.5, True), (0.5, False)] * 4)
    assert FC.report()["bias_label"] == "well-calibrated"


def test_the_HIT_RATE_uses_a_BETA_PRIOR_so_a_small_sample_cannot_read_100_PERCENT(
        _isolated_log: Path) -> None:
    """Five hits out of five is 100% raw, which every reader would take as a claim. The Beta(1,1)
    posterior reports 6/7 instead -- lower, honest, and it moves toward the raw rate as evidence
    accumulates rather than starting there."""
    _log_and_resolve([(0.9, True)] * 5)
    rep = FC.report()
    assert rep["hit_rate_posterior"] == pytest.approx(6 / 7, abs=1e-3)
    assert rep["hit_rate_posterior"] < 1.0


def test_the_posterior_MOVES_TOWARD_the_raw_rate_as_outcomes_accumulate(
        _isolated_log: Path) -> None:
    _log_and_resolve([(0.9, True)] * 5)
    small = FC.report()["hit_rate_posterior"]
    _log_and_resolve([(0.9, True)] * 95)
    assert FC.report()["hit_rate_posterior"] > small


def test_a_hit_is_scored_on_the_SIDE_of_the_forecast_not_its_magnitude(
        _isolated_log: Path) -> None:
    """p=0.51 on an event that happens is a HIT, and p=0.99 on one that does not is a MISS. Brier
    measures the magnitude; the hit rate measures the call, and conflating them loses one."""
    _log_and_resolve([(0.51, True)] * 5)
    rep = FC.report()
    assert rep["hit_rate_posterior"] > 0.8, "every call was right"
    assert rep["brier"] > 0.2, "and every one was barely confident"


def test_the_report_EXPLAINS_its_own_sign_convention(_isolated_log: Path) -> None:
    """A bias figure with no stated direction gets applied backwards by whoever reads it next."""
    _log_and_resolve([(0.5, True)] * 6)
    note = FC.report()["note"]
    assert "lower=better" in note and "bias>0 means forecasts were too high" in note


# ============================================================ durability

def test_a_CORRUPT_log_degrades_to_empty_rather_than_crashing_the_caller(
        _isolated_log: Path) -> None:
    """Calibration is telemetry. A torn write must not take down the organ that was trying to
    record a forecast."""
    _isolated_log.parent.mkdir(parents=True, exist_ok=True)
    _isolated_log.write_text("{not json", "utf-8")
    assert FC.report()["n_resolved"] == 0
    FC.log_forecast("k", 0.5, "promotion")
    assert json.loads(_isolated_log.read_text("utf-8"))["forecasts"]["k"]["p"] == 0.5


def test_a_MISSING_log_is_created_on_first_write(_isolated_log: Path) -> None:
    assert not _isolated_log.exists()
    FC.log_forecast("k", 0.5, "promotion")
    assert _isolated_log.exists()


def test_forecasts_SURVIVE_across_processes(_isolated_log: Path) -> None:
    """The log is the desk's memory of what it believed. Held in process, it would reset on every
    restart and the desk would never accumulate enough outcomes to clear its own N gate."""
    FC.log_forecast("k", 0.3, "promotion")
    reread = json.loads(_isolated_log.read_text("utf-8"))
    assert reread["forecasts"]["k"]["p"] == 0.3
    assert reread["forecasts"]["k"]["kind"] == "promotion"


def test_the_probability_is_stored_ROUNDED_but_not_truncated(_isolated_log: Path) -> None:
    FC.log_forecast("k", 0.123456789, "promotion")
    assert json.loads(_isolated_log.read_text("utf-8"))["forecasts"]["k"]["p"] == 0.1235


def test_forecasts_of_DIFFERENT_KINDS_share_one_calibration(_isolated_log: Path) -> None:
    """`kind` is carried for slicing later, not for partitioning the score. One desk, one
    calibration -- otherwise every kind has too few outcomes to clear the gate and nothing is ever
    measured."""
    FC.log_forecast("a", 0.9, "promotion")
    FC.resolve("a", True)
    FC.log_forecast("b", 0.9, "gate")
    FC.resolve("b", True)
    for i in range(3):
        FC.log_forecast(f"c{i}", 0.9, "experiment")
        FC.resolve(f"c{i}", True)
    assert FC.report()["n_resolved"] == 5
