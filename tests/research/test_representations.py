"""The transform library: causal by construction, composable, and id-stable.

Every test here pins a property that a plausible-looking wrong implementation would satisfy the
headline of and violate the substance of. A z-score against full-sample dispersion produces a
beautiful series and leaks; a composition that forgets its inner step produces a new id over old
numbers; an `as_of` join that takes the newest vintage rather than the newest KNOWABLE vintage is
the single most expensive bug this library can have, and none of them shows up in a return curve.
"""
from __future__ import annotations

import math
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from libs.research import representations as R  # noqa: E402


def _series(values: list[float], *, dataset: str = "ds", start_day: int = 1,
            periods: list[str] | None = None) -> R.Series:
    """Consecutive CALENDAR days. Real dates matter: the seasonal and matched-control transforms
    key on the weekday, so a stamp generator that skips a day quietly breaks the 7-cycle the
    control depends on -- which is a defect in the test, not in the transform."""
    base = datetime(2026, 1, 1, tzinfo=UTC) + timedelta(days=start_day)
    points = []
    for i, value in enumerate(values):
        stamp = (base + timedelta(days=i)).isoformat()
        points.append(R.Point(available_time=stamp,
                              period_time=(periods[i] if periods else stamp), value=value))
    return R.Series(series_id=f"raw:{dataset}", points=tuple(points), dataset=dataset,
                    region="US", information_type="macro_state")


def test_representation_id_is_stable_and_names_its_parts() -> None:
    rid = R.representation_id("fred", "zscore", {"window": 0})
    assert rid == "repr:fred:zscore:window=0"
    assert R.representation_id("fred", "zscore", {"window": 0}) == rid
    assert R.representation_id("a/b", "diff", {}) == "repr:a_b:diff:default"


def test_zscore_uses_only_the_strict_prefix() -> None:
    """The last point must not move when a LATER observation is appended.

    This is the leak test. A full-sample z-score changes every historical value the moment a new
    observation arrives -- which means the backtest read a dispersion nobody had, and nothing in
    the return series would ever say so.
    """
    base = _series([float(i % 5) for i in range(24)])
    extended = _series([float(i % 5) for i in range(24)] + [400.0, -400.0])
    a = {p.available_time: p.value for p in R.zscore(base, min_prior=8).points}
    b = {p.available_time: p.value for p in R.zscore(extended, min_prior=8).points}
    shared = set(a) & set(b)
    assert shared, "the two runs must share points"
    for stamp in shared:
        assert a[stamp] == pytest.approx(b[stamp])


def test_zscore_refuses_a_flat_prefix_rather_than_dividing_by_zero() -> None:
    assert len(R.zscore(_series([2.0] * 20), min_prior=8).points) == 0


def test_as_of_returns_the_newest_knowable_value_never_a_later_one() -> None:
    series = R.Series(series_id="x", points=(
        R.Point("2026-01-01T00:00:00+00:00", "2025-12", 1.0),
        R.Point("2026-02-01T00:00:00+00:00", "2025-12", 9.0),      # a revision of the same period
        R.Point("2026-03-01T00:00:00+00:00", "2026-02", 3.0)))
    assert R.as_of(series, "2026-01-15T00:00:00+00:00") == 1.0
    assert R.as_of(series, "2026-02-15T00:00:00+00:00") == 9.0
    assert R.as_of(series, "2025-12-31T00:00:00+00:00") is None


def test_lead_lag_refuses_a_lead() -> None:
    with pytest.raises(ValueError, match="look-ahead"):
        R.lead_lag(_series([1.0, 2.0, 3.0]), lag=-1)


def test_lead_lag_carries_the_old_value_at_the_new_stamp() -> None:
    out = R.lead_lag(_series([1.0, 2.0, 3.0, 4.0]), lag=2)
    assert [p.value for p in out.points] == [1.0, 2.0]
    assert out.points[0].available_time == _series([1.0, 2.0, 3.0, 4.0]).points[2].available_time


def test_surprise_removes_the_matched_control_and_not_the_news() -> None:
    """A series that is +10 on one weekday and 0 otherwise: the surprise of a matching day is 0
    once the control is learned, and a genuine deviation survives."""
    values = [10.0 if i % 7 == 0 else 0.0 for i in range(40)]
    values[35] = 25.0                      # 35 % 7 == 0: the same control, a real surprise
    out = R.surprise(_series(values), control="weekday", min_prior=2)
    by_stamp = {p.available_time: p.value for p in out.points}
    raw = _series(values)
    ordinary = [p for i, p in enumerate(raw.points) if i % 7 == 0 and 14 <= i < 35]
    assert all(abs(by_stamp[p.available_time]) < 1e-9 for p in ordinary if
               p.available_time in by_stamp)
    assert by_stamp[raw.points[35].available_time] == pytest.approx(15.0)


def test_vintage_revision_is_final_minus_flash_and_needs_two_vintages() -> None:
    series = R.Series(series_id="x", dataset="kr", points=(
        R.Point("2026-01-20T00:00:00+00:00", "2025-12", 100.0, vintage_id="v1"),
        R.Point("2026-02-20T00:00:00+00:00", "2025-12", 118.0, vintage_id="v2"),
        R.Point("2026-02-20T00:00:00+00:00", "2026-01", 50.0, vintage_id="v2")))
    out = R.vintage_revision(series)
    assert [p.value for p in out.points] == [18.0]
    assert out.points[0].available_time == "2026-02-20T00:00:00+00:00"


def test_interactions_join_point_in_time_and_drop_a_zero_denominator() -> None:
    left = R.Series(series_id="l", dataset="a", points=(
        R.Point("2026-01-03T00:00:00+00:00", "d", 6.0),
        R.Point("2026-01-05T00:00:00+00:00", "d", 8.0)))
    right = R.Series(series_id="r", dataset="b", points=(
        R.Point("2026-01-02T00:00:00+00:00", "d", 2.0),
        R.Point("2026-01-04T00:00:00+00:00", "d", 0.0),
        R.Point("2026-01-09T00:00:00+00:00", "d", 99.0)))
    assert [p.value for p in R.ratio(left, right).points] == [3.0]     # the 0.0 row is dropped
    assert [p.value for p in R.product(left, right).points] == [12.0, 0.0]
    assert R.ratio(left, right).dataset == "axb"


def test_event_window_aggregate_reaches_backwards_only() -> None:
    series = _series([1.0, 2.0, 3.0, 4.0, 5.0])
    events = [series.points[2].available_time]
    out = R.event_window_aggregate(series, events, window_days=2.5, how="mean")
    assert len(out.points) == 1
    assert out.points[0].value == pytest.approx(2.0)      # points 1 and 2 (values 1.0, 2.0, 3.0)


def test_event_window_with_nothing_in_it_produces_no_point() -> None:
    out = R.event_window_aggregate(_series([1.0, 2.0]), ["2020-01-01T00:00:00+00:00"])
    assert len(out.points) == 0


def test_composition_makes_a_new_id_and_actually_runs_both_stages() -> None:
    raw = _series([float(i % 5) for i in range(60)])
    inner = R.Transform("surprise", {"control": "weekday", "min_prior": 2})
    composed = R.compose(R.Transform("zscore", {"min_prior": 8}), inner)
    assert composed.label == "surprise|zscore"
    out = R.apply(composed, raw)
    assert out.series_id.startswith("repr:ds:surprise|zscore:")
    assert out.series_id != R.apply(R.Transform("zscore", {"min_prior": 8}), raw).series_id
    staged = R.zscore(R.surprise(raw, control="weekday", min_prior=2), min_prior=8)
    assert [p.value for p in out.points] == pytest.approx([p.value for p in staged.points])


def test_composition_is_idempotent_and_carries_the_pit_stamps() -> None:
    raw = _series([float(i * i % 11) for i in range(50)])
    transform = R.compose(R.Transform("zscore", {"min_prior": 8}), R.Transform("diff", {"lag": 1}))
    first, second = R.apply(transform, raw), R.apply(transform, raw)
    assert first.series_id == second.series_id
    assert [p.value for p in first.points] == [p.value for p in second.points]
    stamps = {p.available_time for p in raw.points}
    assert {p.available_time for p in first.points} <= stamps
    assert first.dataset == raw.dataset and first.region == raw.region


def test_a_two_input_transform_cannot_be_wrapped() -> None:
    with pytest.raises(ValueError, match="cannot wrap a chain"):
        R.compose(R.Transform("ratio"), R.Transform("diff"))


def test_novelty_is_one_against_nothing_and_zero_against_itself() -> None:
    rid = R.representation_id("fred", "zscore", {"window": 0})
    assert R.novelty(rid, []) == 1.0
    assert R.novelty(rid, [rid]) == 0.0
    assert 0.0 < R.novelty(rid, [R.representation_id("bis", "diff", {"lag": 9})]) < 1.0


def test_expected_value_takes_the_prior_for_an_untried_family() -> None:
    assert R.expected_value("surprise", {}) == pytest.approx(0.25)
    earned = {"surprise": {"uses": 10.0, "candidates": 10.0}}
    assert R.expected_value("surprise", earned) > 0.25
    barren = {"surprise": {"uses": 100.0, "candidates": 0.0}}
    assert R.expected_value("surprise", barren) < 0.25


def test_rank_proposals_is_deterministic_and_respects_the_budget() -> None:
    proposals = [(R.representation_id("d", t, {}), R.TRANSFORMS[t].family)
                 for t in ("zscore", "diff", "surprise", "pace", "spectral_state")]
    a = R.rank_proposals(proposals, [], {}, budget=3)
    b = R.rank_proposals(list(reversed(proposals)), [], {}, budget=3)
    assert [r["id"] for r in a] == [r["id"] for r in b] and len(a) == 3


def test_parse_time_reads_the_axis_vocabularies_and_refuses_nonsense() -> None:
    assert R.parse_time("1999-01") is not None
    assert R.parse_time("2026-09-12") is not None
    assert R.parse_time("2026-09-12T11:40:10+00:00") is not None
    assert R.parse_time("not a date") is None
    assert R.parse_time(None) is None


def test_every_registered_transform_declares_a_known_family_and_runs() -> None:
    raw = _series([float((i * 7) % 13) + 1.0 for i in range(80)])
    other = _series([float((i * 3) % 5) + 1.0 for i in range(80)], dataset="other")
    for name, spec in R.TRANSFORMS.items():
        assert spec.family in R.FAMILIES, name
        out = R.apply(R.Transform(name, {}), raw, other,
                      events=[raw.points[40].available_time])
        assert isinstance(out, R.Series)
        assert all(math.isfinite(p.value) for p in out.points), name
