"""Information decay: every input carries its true age, and the arithmetic is honest.

Pinned: COT is still worth more than half at three days and under a tenth at thirty; a bar is
worth half at one span; a negative age is a PIT violation and is refused rather than clipped;
`stamp` refuses an availability earlier than publication and defaults availability to
ingestion; a central-bank decision is in force until superseded and worth nothing after; a
minute solve over hourly data is a minute solve over the same hour; every class states why.
"""
from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from libs.data.pit import is_stamped, usable_at
from libs.research import information_decay as idc

DAY = 86_400.0


def test_cot_decays_over_a_week_and_is_gone_in_a_month() -> None:
    assert idc.decay("cot", 3 * DAY) > 0.5
    assert idc.decay("cot", 30 * DAY) < 0.1
    assert idc.decay("cot", 0.0) == 1.0
    assert idc.decay("cot", 7 * DAY) == pytest.approx(0.5)


def test_a_bar_is_worth_half_at_one_span() -> None:
    assert idc.decay("bar_H1", 3600.0) == pytest.approx(0.5)
    assert idc.decay("bar_D1", DAY) == pytest.approx(0.5)
    assert idc.decay("bar_M5", 300.0) == pytest.approx(0.5)
    # and a fresh bar is worth everything
    assert idc.decay("bar_H1", 0.0) == 1.0


def test_negative_age_is_a_pit_violation_never_clipped() -> None:
    with pytest.raises(idc.PITViolation):
        idc.decay("cot", -1.0)
    with pytest.raises(idc.PITViolation):
        idc.information(1.0, "bar_H1", -60.0)
    now = datetime(2026, 9, 5, 12, tzinfo=UTC)
    with pytest.raises(idc.PITViolation):
        idc.age_of(now + timedelta(hours=1), now)
    assert idc.age_of(now - timedelta(hours=1), now) == pytest.approx(3600.0)


def test_information_is_value_times_decay_and_nan_stays_nan() -> None:
    assert idc.information(2.0, "cot", 7 * DAY) == pytest.approx(1.0)
    assert idc.information(float("nan"), "cot", 0.0) != idc.information(float("nan"), "cot", 0.0)
    assert idc.decay("news", float("nan")) == 0.0


def test_central_bank_decision_steps_to_zero_when_superseded() -> None:
    assert idc.decay("cb_decision", 10 * DAY) == 1.0
    assert idc.decay("cb_decision", 41 * DAY) == 1.0
    assert idc.decay("cb_decision", 43 * DAY) == 0.0
    # the caller knows the next meeting: the step lands there, not at the modal interval
    assert idc.decay("cb_decision", 20 * DAY, expiry_s=14 * DAY) == 0.0
    assert idc.decay("cb_decision", 13 * DAY, expiry_s=14 * DAY) == 1.0


def test_macro_release_fades_then_becomes_a_vintage_at_the_next_print() -> None:
    assert idc.decay("macro_monthly", 0.0) == 1.0
    assert 0.0 < idc.decay("macro_monthly", 15 * DAY) < 1.0
    assert idc.decay("macro_monthly", 35 * DAY) == 0.0             # the next print exists
    assert idc.decay("macro_quarterly", 35 * DAY) > 0.5            # a quarter has not passed


def test_cot_availability_is_the_friday_after_the_tuesday() -> None:
    tuesday = datetime(2026, 8, 11, tzinfo=UTC)
    avail = idc.available_time_of("cot", tuesday)
    assert avail == datetime(2026, 8, 14, 21, tzinfo=UTC)
    assert idc.REGISTRY["cot"].publication_lag_s == pytest.approx(3 * DAY + 21 * 3600)


def test_stamp_refuses_availability_before_publication() -> None:
    with pytest.raises(idc.PITViolation):
        idc.stamp({"value": 1.0}, "cot", event_time="2026-08-11",
                  published_time="2026-08-14T20:30:00+00:00",
                  available_time="2026-08-12T00:00:00+00:00")


def test_stamp_defaults_availability_to_ingestion_and_is_pit_complete() -> None:
    row = idc.stamp({"value": 1.0, "series": "gold"}, "cot", event_time="2026-08-11",
                    published_time="2026-08-14T20:30:00+00:00",
                    ingested_time="2026-08-15T00:00:00+00:00")
    assert row["available_time"] == "2026-08-15T00:00:00+00:00"
    assert row["ingested_time"] == "2026-08-15T00:00:00+00:00"
    assert row["published_time"] == "2026-08-14T20:30:00+00:00"
    assert row["event_time"] == "2026-08-11T00:00:00+00:00"
    assert row["information_class"] == "cot"
    assert row["half_life_s"] == idc.REGISTRY["cot"].half_life_s
    assert is_stamped(row)
    assert usable_at(row, datetime(2026, 8, 15, 1, tzinfo=UTC))
    assert not usable_at(row, datetime(2026, 8, 14, 23, tzinfo=UTC))
    # the input is not mutated
    assert "available_time" not in {"value": 1.0, "series": "gold"}


def test_stamp_revision_is_chained_and_available_no_earlier_than_the_revision() -> None:
    first = idc.stamp({"value": 1.0}, "macro_monthly", event_time="2026-07-01",
                      published_time="2026-08-12T12:30:00+00:00",
                      ingested_time="2026-08-12T12:31:00+00:00")
    fixed = idc.stamp({"value": 1.1}, "macro_monthly", event_time="2026-07-01",
                      published_time="2026-08-12T12:30:00+00:00",
                      ingested_time="2026-09-10T12:30:00+00:00",
                      revision_of=first["payload_hash"], revision_reason="BLS restatement")
    assert fixed["revision_of"] == first["payload_hash"]
    assert fixed["revision_n"] == 1
    assert fixed["available_time"] >= "2026-09-10T12:30:00+00:00"
    assert fixed["event_time"] == first["event_time"]


def test_truthful_cadence_says_a_minute_solve_over_hourly_data_is_the_same_hour() -> None:
    assert idc.truthful_cadence("bar_H1") == 3600.0
    assert idc.truthful_cadence("cot") == 7 * DAY
    assert idc.truthful_cadence("tick") <= 1.0
    # two solves a minute apart inside the same hour read the same bar
    assert not idc.is_new_information("bar_H1", 200.0, 260.0)
    # a solve after the next close reads a new one
    assert idc.is_new_information("bar_H1", 3550.0, 3650.0)


def test_state_freshness_reports_age_weight_and_staleness_per_input() -> None:
    out = idc.state_freshness({"cot": 3 * DAY, "regime": ("bar_D1", 3 * DAY),
                               "unstamped": ("news", float("nan"))})
    assert out["cot"]["weight"] > 0.5 and not out["cot"]["stale"]
    assert out["regime"]["cls"] == "bar_D1" and out["regime"]["stale"]
    assert out["unstamped"]["weight"] == 0.0 and out["unstamped"]["stale"]
    assert out["cot"]["cadence_s"] == 7 * DAY


def test_every_class_states_why_and_has_a_positive_clock() -> None:
    for name, c in idc.REGISTRY.items():
        assert c.name == name
        assert len(c.why) > 20, name
        assert c.half_life_s > 0 and c.cadence_s > 0, name
        assert c.cadence_s <= c.half_life_s or c.shape in (idc.STEP, idc.RELEASE), name
        assert c.shape in (idc.EXPONENTIAL, idc.BAR, idc.STEP, idc.RELEASE), name
    with pytest.raises(KeyError):
        idc.decay("no_such_class", 1.0)
