"""Cohort assembly for the unlock DiD -- the three designs must differ in the way they claim to.

`build_cohort` is where a causal study is actually won or lost: the estimator can only be as
honest as the control leg handed to it. Each design here fixes a named defect in the one before,
so each gets a test that would fail if that fix silently stopped applying.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest
from scripts.run_natural_experiment import (
    MIN_CONTROLS_PER_DAY,
    POST_DAYS,
    PRE_DAYS,
    build_cohort,
)

N_PEERS = MIN_CONTROLS_PER_DAY + 15


@pytest.fixture
def rets():
    """A daily return panel: one unlocking symbol plus enough peers to clear the control floor."""
    idx = pd.date_range("2023-01-01", periods=400, freq="D", tz="UTC")
    rng = np.random.default_rng(0)
    cols = {"TREATED": rng.normal(0, 0.01, len(idx))}
    for i in range(N_PEERS):
        cols[f"PEER{i}"] = rng.normal(0, 0.01, len(idx))
    return pd.DataFrame(cols, index=idx)


def _ev(sym: str, date: str, cat: str = "insiders") -> dict:
    return {"symbol": sym, "date": date, "category": cat, "tokens": 1.0}


def test_only_pre_registered_categories_are_treated(rets):
    events = [_ev("TREATED", "2023-04-01"), _ev("TREATED", "2023-05-01", cat="Uncategorized")]
    out = build_cohort(rets, events, control_mode="never-treated")
    assert len(out["units"]) == 1
    assert out["dropped"]["category"] == 1


def test_never_treated_controls_exclude_every_unlocking_symbol(rets):
    """The control pool must be symbols that NEVER appear in the unlock file."""
    events = [_ev("TREATED", "2023-04-01"), _ev("PEER0", "2023-06-01")]
    out = build_cohort(rets, events, control_mode="never-treated")
    assert out["n_control_pool"] == N_PEERS - 1, "PEER0 unlocks, so it is not a never-treated peer"


def test_not_yet_treated_controls_are_drawn_from_the_unlocking_population(rets):
    """Same population, timing varies -- the whole point of the second design."""
    events = [_ev("TREATED", "2023-04-01")] + [
        _ev(f"PEER{i}", "2023-09-01") for i in range(N_PEERS)]
    out = build_cohort(rets, events, control_mode="not-yet-treated")
    # TREATED is excluded from its own control leg, leaving the peers that also unlock.
    assert out["n_control_pool"] >= N_PEERS - 1
    assert out["units"], "a treated unit should survive"


def test_a_symbol_is_never_its_own_control(rets):
    """If the treated symbol sat in its own control mean the estimate shrinks toward zero
    mechanically, and nothing in the output would look wrong."""
    events = [_ev("TREATED", "2023-04-01")] + [
        _ev(f"PEER{i}", "2023-09-01") for i in range(N_PEERS)]
    out = build_cohort(rets, events, control_mode="not-yet-treated")
    u = out["units"][0]
    # The control leg must not equal the treated leg on any window.
    assert u.control_pre != u.treated_pre
    assert u.control_post != u.treated_post


def test_clean_pre_window_drops_events_whose_pre_period_holds_a_prior_unlock(rets):
    """THE DEFECT THE FIRST TWO DESIGNS DIED OF. Monthly vesting puts a previous unlock inside
    almost every 30-day pre-window, so the 'before' leg is already under supply pressure."""
    first = pd.Timestamp("2023-04-01", tz="UTC")
    second = first + pd.Timedelta(days=PRE_DAYS - 5)      # lands INSIDE the second's pre-window
    events = [_ev("TREATED", str(first.date())), _ev("TREATED", str(second.date()))]

    dirty = build_cohort(rets, events, control_mode="never-treated", require_clean_pre=False)
    clean = build_cohort(rets, events, control_mode="never-treated", require_clean_pre=True)

    assert len(dirty["units"]) == 2
    assert len(clean["units"]) == 1, "the second event's pre-window holds the first unlock"
    assert clean["dropped"]["prior-unlock-in-pre-window"] == 1
    assert clean["units"][0].unit_id.endswith(str(first.date()))


def test_a_far_apart_prior_unlock_is_kept(rets):
    """The filter must cost only what it claims to -- it is a contamination rule, not a cull."""
    first = pd.Timestamp("2023-04-01", tz="UTC")
    second = first + pd.Timedelta(days=PRE_DAYS + POST_DAYS + 30)
    events = [_ev("TREATED", str(first.date())), _ev("TREATED", str(second.date()))]
    clean = build_cohort(rets, events, control_mode="never-treated", require_clean_pre=True)
    assert len(clean["units"]) == 2
    assert "prior-unlock-in-pre-window" not in clean["dropped"]


def test_events_outside_the_pre_registered_window_are_dropped(rets):
    out = build_cohort(rets, [_ev("TREATED", "2019-04-01")], control_mode="never-treated")
    assert not out["units"]
    assert out["dropped"]["outside-window"] == 1


def test_a_symbol_absent_from_the_panel_is_dropped_not_guessed(rets):
    out = build_cohort(rets, [_ev("NOTLISTED", "2023-04-01")], control_mode="never-treated")
    assert not out["units"]
    assert out["dropped"]["symbol-not-in-panel"] == 1


def test_an_unknown_control_mode_raises_rather_than_defaulting(rets):
    with pytest.raises(ValueError, match="unknown control_mode"):
        build_cohort(rets, [], control_mode="whatever-is-convenient")


def test_a_thin_control_day_is_not_quietly_averaged(rets):
    """Below MIN_CONTROLS_PER_DAY live peers the control mean is masked, and the unit is dropped
    for a short window rather than resting on three symbols."""
    thin = rets[["TREATED"] + [f"PEER{i}" for i in range(MIN_CONTROLS_PER_DAY - 5)]]
    out = build_cohort(thin, [_ev("TREATED", "2023-04-01")], control_mode="never-treated")
    assert not out["units"]
    assert out["dropped"]["short-window"] == 1
