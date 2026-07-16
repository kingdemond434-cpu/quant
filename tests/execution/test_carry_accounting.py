"""Tests for self-healing spot-realized accounting (the 2026-07-10 phantom-loss fix)."""

from __future__ import annotations

from libs.execution.carry_accounting import dedup_basis, derive_spot_realized


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
