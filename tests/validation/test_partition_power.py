"""L1.63 -- a robustness certificate whose partition cannot fail carries no information.

These tests fail if the wiring is removed: the refusal paths (UNMEASURED on an empty or
under-observed set) are the whole point, because "every group was positive" and "no group had
enough observations to tell" are different claims and only one is evidence (L1.28a).
"""

from __future__ import annotations

import numpy as np
import pytest

from libs.validation.partition_power import (
    MIN_GROUP_OBS,
    UNLABELLED,
    partition_power,
    summarise,
)

_RNG = np.random.default_rng(20260813)


def _labels(*counts: tuple[str, int]) -> np.ndarray:
    return np.array([name for name, n in counts for _ in range(n)])


def test_partition_that_produces_a_negative_group_is_discriminating() -> None:
    """An axis able to fail an edge is the only kind whose pass means anything."""
    good = _RNG.normal(5e-4, 1e-4, 200)
    bad = _RNG.normal(-5e-4, 1e-4, 200)
    v = partition_power(np.concatenate([good, bad]),
                        _labels(("a", 200), ("b", 200)), name="two_sided")
    assert v.status == "DISCRIMINATING"
    assert v.can_fail is True
    assert v.n_groups_graded == 2
    assert v.n_groups_positive == 1


def test_partition_where_every_group_is_positive_is_welded() -> None:
    """The defect this module exists for: a certificate that would have passed anything.

    This is the desk's live case -- 4 of 4 partitions welded on 213 symbols x 2,384 days.
    """
    r = np.concatenate([_RNG.normal(5e-4, 1e-4, 200), _RNG.normal(9e-4, 1e-4, 200)])
    v = partition_power(r, _labels(("a", 200), ("b", 200)), name="all_positive")
    assert v.status == "WELDED"
    assert v.can_fail is False
    assert v.n_groups_positive == v.n_groups_graded == 2
    assert "carries no information" in v.why


def test_under_observed_partition_refuses_to_grade() -> None:
    """UNMEASURED, never WELDED: an under-observed axis is not a welded one."""
    n = MIN_GROUP_OBS - 1
    v = partition_power(_RNG.normal(5e-4, 1e-4, 2 * n),
                        _labels(("a", n), ("b", n)), name="thin")
    assert v.status == "UNMEASURED"
    assert v.n_groups_graded == 0
    assert v.attrition["ungraded_groups"] == 2
    assert "cannot distinguish" in v.why


def test_single_group_cannot_discriminate() -> None:
    """One group is not a partition -- it must refuse rather than report a clean verdict."""
    v = partition_power(_RNG.normal(5e-4, 1e-4, 300), _labels(("only", 300)), name="one_group")
    assert v.status == "UNMEASURED"
    assert v.can_fail is False


def test_unlabelled_observations_are_counted_not_silently_dropped() -> None:
    """L1.60: a denominator that loses members in silence is a coverage claim we cannot cash."""
    r = np.concatenate([_RNG.normal(5e-4, 1e-4, 100), _RNG.normal(-5e-4, 1e-4, 100),
                        _RNG.normal(0.0, 1e-4, 50)])
    v = partition_power(r, _labels(("a", 100), ("b", 100), (UNLABELLED, 50)), name="warmup")
    assert v.attrition["unlabelled"] == 50
    assert v.attrition["observations"] == 250
    assert v.n_obs == 200


def test_mismatched_lengths_refuse_rather_than_guess() -> None:
    v = partition_power(np.zeros(10), _labels(("a", 5)), name="ragged")
    assert v.status == "UNMEASURED"
    assert "differ in length" in v.why


def test_empty_rollup_is_unmeasured_never_ok() -> None:
    """THE WIRING TEST: an empty measurement set must never read as health (L1.28a)."""
    s = summarise([])
    assert s["status"] == "UNMEASURED"
    assert s["status"] != "OK"
    assert s["n_partitions"] == 0


def test_rollup_flags_welded_over_discriminating() -> None:
    """One welded certificate is a failure even when others discriminate -- it is not averaged."""
    ok = partition_power(np.concatenate([_RNG.normal(5e-4, 1e-4, 200),
                                         _RNG.normal(-5e-4, 1e-4, 200)]),
                         _labels(("a", 200), ("b", 200)), name="good")
    bad = partition_power(np.concatenate([_RNG.normal(5e-4, 1e-4, 200),
                                          _RNG.normal(9e-4, 1e-4, 200)]),
                          _labels(("a", 200), ("b", 200)), name="welded")
    s = summarise([ok, bad])
    assert s["status"] == "WELDED"
    assert s["n_welded"] == 1
    assert s["n_discriminating"] == 1
    assert "never delete it" in s["next_action"]


def test_rollup_of_only_ungraded_partitions_is_unmeasured() -> None:
    thin = partition_power(_RNG.normal(5e-4, 1e-4, 10), _labels(("a", 5), ("b", 5)), name="thin")
    s = summarise([thin])
    assert s["status"] == "UNMEASURED"


class TestFenceWiring:
    """The fence must keep grading the axis the live gates actually use.

    REWRITTEN FOR THE MT5 DESK, 2026-09-05. These tests were built against a fence whose axes were
    `funding_state` and `funding_breadth` -- crypto-exchange concepts -- and they passed a
    `funding` DataFrame of BTCUSDT rates. That fence was correctly deleted with the crypto desk
    under the universe mandate, and the LAW it enforced was not: `docs/CONSTITUTION.md` still
    named the path, `release_identity.json` still listed it, and these four tests had been failing
    on ModuleNotFoundError ever since. The law is now fenced over the partitions THIS desk
    certifies on, and these test that.
    """

    def test_roster_includes_the_wired_vol_partition(self) -> None:
        """Fails if someone drops the WIRED axis from the roster -- the one gating live capital."""
        import pandas as pd
        from scripts.check_partition_power import build_partitions

        idx = pd.date_range("2024-01-01", periods=400, freq="h", tz="UTC")
        returns = pd.Series(_RNG.normal(5e-4, 2e-4, 400), index=idx)

        roster = build_partitions(returns)
        assert "vol_terciles_WIRED" in roster, (
            "the vol-tercile axis is what regime_robust / min_regimes_positive / two_regimes "
            "actually use; dropping it from the roster blinds the fence to the live gate")
        for name, labels in roster.items():
            assert len(labels) == len(returns), f"{name} labels must align with the return series"

    def test_the_roster_grades_the_desks_own_sessions(self) -> None:
        """A session sleeve is selected BY its window, so the session split is the one it is most
        likely to be silently welded on -- every cell in the window, nothing outside it."""
        import pandas as pd
        from scripts.check_partition_power import build_partitions

        idx = pd.date_range("2024-01-01", periods=240, freq="h", tz="UTC")
        roster = build_partitions(pd.Series(_RNG.normal(0, 1e-3, 240), index=idx))
        assert "session" in roster
        assert {"asia", "london_am", "ny_open", "afternoon"} <= set(roster["session"])

    def test_welded_status_is_not_a_passing_status(self) -> None:
        """A welded certificate must exit non-zero -- a report nobody fails is not a fence."""
        from scripts.check_partition_power import _PASSING

        assert "WELDED" not in _PASSING
        assert "UNMEASURED" not in _PASSING
        assert "OK" in _PASSING

    def test_no_evidence_exits_non_zero_rather_than_reporting_clean(self) -> None:
        """UNMEASURED is the ABSENCE of what L1.63 requires, not a quiet pass (L1.28a)."""
        import scripts.check_partition_power as cpp

        original = cpp._series
        try:
            cpp._series = lambda: ({}, "no certified series on this host")
            out = cpp.check()
        finally:
            cpp._series = original
        assert out["status"] == "UNMEASURED"
        assert "not a pass" in out["note"]


@pytest.mark.parametrize("status", ["WELDED", "UNMEASURED"])
def test_failing_statuses_are_distinct_from_ok(status: str) -> None:
    from scripts.check_partition_power import _PASSING

    assert status not in _PASSING
