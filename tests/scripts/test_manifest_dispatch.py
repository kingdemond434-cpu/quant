"""Tests for scripts/run_manifest_dispatch.py -- the cron-manifest resurrection dispatcher.

Root cron died 2026-08-20 (OOM, principal-gated restart); the dispatcher re-runs allowlisted
manifest rows under a user timer with exact vixie-cron semantics. The matcher is the part that
silently mis-firing would make WORSE than the outage it repairs, so it is pinned here.
"""
from __future__ import annotations

from datetime import UTC, datetime

from scripts.run_manifest_dispatch import cron_matches, due_times, parse_field


def dt(y: int, mo: int, d: int, h: int, mi: int) -> datetime:
    return datetime(y, mo, d, h, mi, tzinfo=UTC)


def test_parse_field_star_step_range_list() -> None:
    assert parse_field("*", 0, 5) == {0, 1, 2, 3, 4, 5}
    assert parse_field("*/15", 0, 59) == {0, 15, 30, 45}
    assert parse_field("7-59/15", 0, 59) == {7, 22, 37, 52}
    assert parse_field("1,13", 0, 23) == {1, 13}
    assert parse_field("0,3", 0, 7) == {0, 3}
    assert parse_field("7", 0, 7) == {0}  # cron: dow 7 == Sunday == 0


def test_cron_matches_real_manifest_rows() -> None:
    # 7 7 * * * -- the daily ratchet raiser
    assert cron_matches("7 7 * * *", dt(2026, 8, 26, 7, 7))
    assert not cron_matches("7 7 * * *", dt(2026, 8, 26, 7, 8))
    assert not cron_matches("7 7 * * *", dt(2026, 8, 26, 8, 7))
    # 5 * * * * -- the hourly law gate
    assert cron_matches("5 * * * *", dt(2026, 8, 26, 3, 5))
    # */10 * * * * -- pull_deploy
    assert cron_matches("*/10 * * * *", dt(2026, 8, 26, 3, 50))
    assert not cron_matches("*/10 * * * *", dt(2026, 8, 26, 3, 55))
    # 50 */4 * * * -- intelligence cycle
    assert cron_matches("50 */4 * * *", dt(2026, 8, 26, 8, 50))
    assert not cron_matches("50 */4 * * *", dt(2026, 8, 26, 9, 50))
    # 19 4 1 * * -- monthly event calendar, day-of-month restricted
    assert cron_matches("19 4 1 * *", dt(2026, 9, 1, 4, 19))
    assert not cron_matches("19 4 1 * *", dt(2026, 9, 2, 4, 19))


def test_cron_dow_semantics() -> None:
    # 2026-08-30 is a Sunday; 35 5 * * 0,3 (kimi deep row)
    assert cron_matches("35 5 * * 0,3", dt(2026, 8, 30, 5, 35))
    # Wednesday 2026-08-26
    assert cron_matches("35 5 * * 0,3", dt(2026, 8, 26, 5, 35))
    # Thursday 2026-08-27
    assert not cron_matches("35 5 * * 0,3", dt(2026, 8, 27, 5, 35))
    # vixie OR rule: both dom and dow restricted -> either matches
    assert cron_matches("0 0 13 * 0", dt(2026, 8, 13, 0, 0))   # dom matches, dow is Thursday
    assert cron_matches("0 0 13 * 0", dt(2026, 8, 30, 0, 0))   # dow Sunday matches, dom 30


def test_due_times_window_and_boundaries() -> None:
    # law gate at :05 -- a 5-minute window straddling it fires exactly once
    since, until = dt(2026, 8, 26, 3, 2), dt(2026, 8, 26, 3, 7)
    assert due_times("5 * * * *", since, until) == [dt(2026, 8, 26, 3, 5)]
    # window excludes `since` itself (already checked last run), includes `until`
    assert due_times("5 * * * *", dt(2026, 8, 26, 3, 5), dt(2026, 8, 26, 3, 9)) == []
    assert due_times("9 * * * *", dt(2026, 8, 26, 3, 5), dt(2026, 8, 26, 3, 9)) == [
        dt(2026, 8, 26, 3, 9)]
    # a daily row outside the window does not fire
    assert due_times("7 7 * * *", dt(2026, 8, 26, 3, 0), dt(2026, 8, 26, 3, 20)) == []
