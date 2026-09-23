"""R0601: the forward ratio and ladder refuse to publish a number they cannot measure."""
from __future__ import annotations

import math

import pytest

from libs.research.forward_ladder import (
    LADDER_FRACTIONS,
    coverage,
    os_is_ratio,
    sharpe_ladder,
)


def test_ladder_rungs_are_observations_not_days() -> None:
    """Rungs are quarter/half/full/double of the clock's OWN decision point."""
    rungs = sharpe_ladder([0.01] * 60, decision_at_obs=20)
    assert [r["obs"] for r in rungs] == [5, 10, 20, 40]
    assert [r["fraction_of_decision_point"] for r in rungs] == list(LADDER_FRACTIONS)


def test_unreached_rung_is_published_as_unreached_not_dropped() -> None:
    """L1.60: a rung the clock has not reached must stay in the denominator."""
    arr = [0.01, -0.005, 0.02, 0.001, -0.01, 0.015]      # n=6, decision point 20
    rungs = sharpe_ladder(arr, decision_at_obs=20)
    assert len(rungs) == 4, "no rung may be silently dropped"
    assert rungs[0]["reached"] is True and rungs[0]["sharpe"] is not None   # obs=5 <= 6
    for r in rungs[1:]:                                   # obs 10/20/40 all beyond n=6
        assert r["reached"] is False
        assert r["sharpe"] is None, "an unreached rung has no Sharpe, and 0.0 is not None"


def test_ladder_is_nested_and_tracks_decay() -> None:
    """A strong first half followed by a dead second half must show the ladder falling."""
    # A strong but NOT constant first segment -- a constant one has sd=0 and no Sharpe at all,
    # which is the module behaving correctly and would test nothing here.
    arr = [0.020, 0.018, 0.023, 0.019, 0.021,
           0.022, 0.017, 0.024, 0.020, 0.019] + [0.02, -0.02] * 15   # then pure chop
    rungs = {r["obs"]: r["sharpe"] for r in sharpe_ladder(arr, decision_at_obs=20)}
    assert rungs[5] is not None and rungs[40] is not None
    assert rungs[5] > rungs[40], "decay while confirming is the whole point of a ladder"


def test_zero_variance_window_has_no_sharpe() -> None:
    rungs = sharpe_ladder([0.01] * 30, decision_at_obs=20)
    assert all(r["sharpe"] is None for r in rungs), "sd=0 is undefined, never 0.0"


def test_collapsed_rungs_are_deduplicated() -> None:
    """A decision point of 2 puts 0.25 and 0.5 on the same observation."""
    obs = [r["obs"] for r in sharpe_ladder([0.01, 0.02, 0.03, 0.04], decision_at_obs=2)]
    assert len(obs) == len(set(obs))


def test_ratio_refuses_unlike_annualisation() -> None:
    """THE LOAD-BEARING REFUSAL: sqrt(20) apart is an artifact, not screen optimism."""
    out = os_is_ratio(1.0, 2.0, forward_horizon_days=1.0, screen_horizon_days=20.0)
    assert out["ratio"] is None
    assert out["status"] == "UNLIKE-ANNUALISATION"


def test_ratio_measures_when_like_annualised() -> None:
    out = os_is_ratio(1.0, 2.0, forward_horizon_days=1.0, screen_horizon_days=1.0)
    assert out["status"] == "MEASURED"
    assert math.isclose(out["ratio"], 0.5)


@pytest.mark.parametrize("screen", [None, 0.0, 0.01, -0.02])
def test_ratio_never_fabricates_a_number(screen: float | None) -> None:
    """Missing or near-zero denominator must refuse, never divide."""
    out = os_is_ratio(1.0, screen, forward_horizon_days=1.0, screen_horizon_days=1.0)
    assert out["ratio"] is None
    assert out["status"] in {"UNMEASURED-NO-SCREEN", "DENOM-TOO-SMALL"}


def test_missing_forward_half_also_refuses() -> None:
    assert os_is_ratio(None, 2.0, screen_horizon_days=1.0)["ratio"] is None


def test_coverage_of_zero_scored_clocks_is_unmeasured_not_ok() -> None:
    """L1.28a/L1.57: absence must not resolve to a clean verdict."""
    assert coverage([])["status"] == "UNMEASURED"
    assert coverage([{"axis": "a"}])["status"] == "UNMEASURED"
    assert coverage([])["pct"] is None


def test_coverage_counts_unmeasured_clocks_in_its_denominator() -> None:
    """Coverage may not rise by dropping the clocks it could not measure."""
    recs = [
        {"axis": "a", "os_is_sharpe": {"status": "MEASURED", "ratio": 0.4}},
        {"axis": "b", "os_is_sharpe": {"status": "UNMEASURED-NO-SCREEN", "ratio": None}},
    ]
    cov = coverage(recs)
    assert cov["scanned"] == 2 and cov["measured"] == 1
    assert cov["status"] == "PARTIAL" and cov["pct"] == 50.0
    assert cov["by_status"]["UNMEASURED-NO-SCREEN"] == 1
