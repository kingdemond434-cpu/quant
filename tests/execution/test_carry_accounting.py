"""Tests for self-healing spot-realized accounting (the 2026-07-10 phantom-loss fix)."""

from __future__ import annotations

from libs.execution.carry_accounting import (
    carry_bleed_report,
    dedup_basis,
    derive_spot_realized,
)


def _closes() -> list[dict]:
    return [
        {"event": "open", "symbol": "AAA", "opened": "t0"},
        {"event": "close", "symbol": "AAA", "opened": "t0", "price_pnl": 2.0},
        {"event": "close", "symbol": "BBB", "opened": "t1", "price_pnl": -1.0},
    ]


def test_dedup_basis_sums_closes() -> None:
    assert dedup_basis(_closes()) == 1.0


def test_dedup_basis_collapses_duplicate_close_logs() -> None:
    # a flatten logs the same (symbol, opened) close several times -> count once
    trades = [
        *_closes(),
        {"event": "close", "symbol": "AAA", "opened": "t0", "price_pnl": 2.0},
        {"event": "close", "symbol": "AAA", "opened": "t0", "price_pnl": 2.0},
    ]
    assert dedup_basis(trades) == 1.0


def test_derive_spot_realized_offsets_venue_realized() -> None:
    # delta-neutral: shorts realized -650 (market rose) -> spot legs realized ~+650 + basis
    trades = [{"event": "close", "symbol": "X", "opened": "t", "price_pnl": 61.17}]
    assert derive_spot_realized(-650.68, trades) == 711.85


def test_derive_is_robust_to_bad_rows() -> None:
    trades = [
        {"event": "close", "symbol": "X", "opened": "t", "price_pnl": "oops"},
        {"event": "close", "symbol": "Y", "opened": "u", "price_pnl": 5.0},
    ]
    assert derive_spot_realized(0.0, trades) == 5.0
    assert derive_spot_realized(None, trades) == 5.0  # type: ignore[arg-type]


def test_carry_bleed_clean_when_legs_cancel() -> None:
    r = carry_bleed_report(funding=100.0, spot_pnl=60.0, fut_pnl=42.0)  # non-funding +2
    assert not r.alert
    assert bool(r) is True
    assert r.non_funding_pnl == 2.0
    assert "clean" in r.verdict


def test_carry_bleed_ok_when_small_drain() -> None:
    r = carry_bleed_report(funding=100.0, spot_pnl=10.0, fut_pnl=70.0)  # non-funding -20 (20%)
    assert not r.alert
    assert r.non_funding_pnl == -20.0
    assert r.harvest_eaten_frac == 0.2


def test_carry_bleed_alarms_when_hedge_loses_more_than_it_earns() -> None:
    # the live shape: +90 funding, real legs -252 -> non-funding -342 = ~382% of harvest
    r = carry_bleed_report(funding=89.65, spot_pnl=-200.0, fut_pnl=-52.84)
    assert r.alert
    assert bool(r) is False
    assert r.non_funding_pnl == -342.49
    assert r.harvest_eaten_frac > 3.0
    assert "BLEED" in r.verdict


def test_carry_bleed_alarms_on_any_drain_with_no_harvest() -> None:
    r = carry_bleed_report(funding=-5.0, spot_pnl=-10.0, fut_pnl=0.0)
    assert r.alert
    assert r.harvest_eaten_frac == float("inf")


def test_carry_bleed_alarms_on_a_large_POSITIVE_non_funding_pnl() -> None:
    # delta-neutral target is ~0 in BOTH signs: a windfall this size is a naked/untracked leg
    # (the 2026-07-26 stranded-spot class), never edge. A one-sided alarm called this "clean".
    r = carry_bleed_report(funding=100.0, spot_pnl=500.0, fut_pnl=-100.0)  # non-funding +300
    assert r.alert
    assert bool(r) is False
    assert r.non_funding_pnl == 300.0
    assert "BLEED(inverted)" in r.verdict
    assert "NAKED" in r.verdict


def test_carry_bleed_small_positive_non_funding_is_still_clean() -> None:
    # only a windfall >= alert_frac of the harvest is a broken hedge; noise must not page
    r = carry_bleed_report(funding=100.0, spot_pnl=60.0, fut_pnl=42.0)  # non-funding +2
    assert not r.alert
    assert "clean" in r.verdict
