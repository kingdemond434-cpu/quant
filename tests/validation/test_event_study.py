"""Tests for the event-study promotion path (§39 edges are EVENTS, not time series).

The properties that decide whether this is trustworthy: a thin sample is refused outright, fat
tails cannot buy a pass on the t-stat alone, overlapping windows are discounted rather than
silently counted as independent draws, and the benchmark is subtracted so the result measures
edge rather than beta."""

from __future__ import annotations

import numpy as np
import pytest

from libs.validation.errors import ValidationError
from libs.validation.event_study import (
    MIN_EVENTS,
    Event,
    abnormal_returns,
    event_study,
    overlap_fraction,
)

_HOUR = 3600.0


def _events(rets: list[float], *, spacing: float = 24 * _HOUR, dur: float = 4 * _HOUR):
    return [Event(event_id=f"e{i}", t_start=i * spacing, t_end=i * spacing + dur, ret=r)
            for i, r in enumerate(rets)]


class TestAbnormalReturns:
    def test_no_benchmark_passes_through(self) -> None:
        assert np.allclose(abnormal_returns(np.array([0.01, 0.02])), [0.01, 0.02])

    def test_benchmark_is_subtracted(self) -> None:
        # without this an event study measures BETA -- the exact error of "beating" a falling
        # index by holding cash
        got = abnormal_returns(np.array([0.05, -0.01]), np.array([0.02, -0.03]))
        assert np.allclose(got, [0.03, 0.02])

    def test_misaligned_benchmark_is_refused(self) -> None:
        with pytest.raises(ValidationError):
            abnormal_returns(np.array([0.01, 0.02]), np.array([0.01]))


class TestOverlap:
    def test_disjoint_events_do_not_overlap(self) -> None:
        assert overlap_fraction(_events([0.01] * 5)) == 0.0

    def test_fully_overlapping_events_are_all_flagged(self) -> None:
        evs = [Event(event_id=f"e{i}", t_start=0.0, t_end=10 * _HOUR, ret=0.01) for i in range(4)]
        assert overlap_fraction(evs) == 1.0

    def test_single_event_has_no_overlap(self) -> None:
        assert overlap_fraction(_events([0.01])) == 0.0

    def test_partial_overlap_is_partially_counted(self) -> None:
        evs = _events([0.01] * 4, spacing=24 * _HOUR)
        evs.append(Event(event_id="x", t_start=1 * _HOUR, t_end=3 * _HOUR, ret=0.01))  # inside e0
        assert 0.0 < overlap_fraction(evs) < 1.0


class TestEventStudy:
    def test_thin_sample_is_refused_outright(self) -> None:
        res = event_study(_events([0.05] * 5))
        assert res.passed is False and "too few to judge" in res.verdict

    def test_clear_repeatable_edge_passes(self) -> None:
        rng = np.random.default_rng(1)
        rets = list(0.02 + rng.normal(0, 0.004, MIN_EVENTS + 10))
        res = event_study(_events(rets))
        assert res.passed is True and res.t_stat > 2 and res.boot_lo > 0

    def test_pure_noise_does_not_pass(self) -> None:
        rng = np.random.default_rng(2)
        res = event_study(_events(list(rng.normal(0, 0.03, 40))))
        assert res.passed is False

    def test_fat_tail_cannot_buy_a_pass_on_the_t_stat_alone(self) -> None:
        # one enormous winner drags the mean; the bootstrap CI must still span zero and refuse
        rets = [0.0005] * 39 + [3.0]
        res = event_study(_events(rets))
        assert res.passed is False
        assert "SPANS ZERO" in res.verdict or res.t_stat < res.bar

    def test_overlap_discounts_effective_n(self) -> None:
        rng = np.random.default_rng(3)
        rets = list(0.02 + rng.normal(0, 0.004, 40))
        disjoint = event_study(_events(rets))
        stacked = event_study([Event(event_id=f"e{i}", t_start=0.0, t_end=99 * _HOUR, ret=r)
                               for i, r in enumerate(rets)])
        assert stacked.n_effective < disjoint.n_effective
        assert stacked.t_stat < disjoint.t_stat   # the same data, honestly weaker

    def test_multiplicity_raises_the_bar(self) -> None:
        # returns must VARY: a constant series is a data defect and short-circuits before the bar
        # is ever computed, which would make this assertion pass-by-accident on 0.0 > 0.0.
        rng = np.random.default_rng(11)
        rets = list(0.02 + rng.normal(0, 0.004, 30))
        solo = event_study(_events(rets), n_cohort=1)
        cohort = event_study(_events(rets), n_cohort=20, rank=1)
        assert solo.bar > 0.0
        assert cohort.bar > solo.bar   # one of 20 screened must clear more than a pre-registered 1

    def test_hit_rate_is_reported(self) -> None:
        res = event_study(_events([0.01] * 30 + [-0.01] * 10))
        assert res.hit_rate == 0.75

    def test_result_is_deterministic(self) -> None:
        rets = [0.01, -0.005] * 15
        assert event_study(_events(rets), seed=7) == event_study(_events(rets), seed=7)

    def test_zero_variance_is_refused_as_a_data_defect(self) -> None:
        # `std == 0.0` never fires (numpy returns ~3e-19 for identical values) and the t-stat
        # explodes to ~3e16, clearing every bar. A constant series must be REFUSED, not scored.
        res = event_study(_events([0.01] * 30))
        assert res.t_stat == 0.0 and res.passed is False
        assert "DEGENERATE" in res.verdict
