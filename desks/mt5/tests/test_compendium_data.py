from __future__ import annotations

# ruff: noqa: E402 -- tests add the desk roots before importing standalone research modules.
import sys
from datetime import UTC, datetime
from pathlib import Path
from types import SimpleNamespace

import pandas as pd
import pytest

DESK = Path(__file__).resolve().parents[1]
for path in (DESK, DESK / "research", DESK.parent.parent):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

from mt5desk.tape import contract_terms_row
from mt5desk.triangle_tape import executable_loops
from research.fetch_futures_curves import build_curve, contract_symbol


def test_contract_terms_are_point_in_time_and_keep_both_sides() -> None:
    at = datetime(2026, 8, 23, 12, tzinfo=UTC)
    info = SimpleNamespace(
        swap_long=-3.2, swap_short=1.1, swap_mode=1, swap_rollover3days=3,
        trade_contract_size=100_000, trade_tick_size=0.00001, trade_tick_value=1.0,
        currency_profit="USD", currency_margin="EUR",
    )
    row = contract_terms_row("EURUSD", info, at)
    assert row["observed_at"].startswith("2026-08-23T12:00:00")
    assert row["swap_long"] == -3.2 and row["swap_short"] == 1.1


def test_triangle_uses_executable_bid_ask_not_mid_prices() -> None:
    ts = pd.to_datetime(["2026-08-23T12:00:00Z"])
    direct = pd.DataFrame({"ts": ts, "bid": [0.85], "ask": [0.851]})
    eurusd = pd.DataFrame({"ts": ts, "bid": [1.10], "ask": [1.101]})
    gbpusd = pd.DataFrame({"ts": ts, "bid": [1.29], "ask": [1.291]})
    got = executable_loops(direct, eurusd, gbpusd)
    assert len(got) == 1
    assert got.iloc[0]["direct_sell_loop"] == pytest.approx(0.85 * 1.29 / 1.101 - 1)
    assert got.iloc[0]["direct_buy_loop"] == pytest.approx(1.10 / (1.291 * 0.851) - 1)


def test_contract_curve_is_expiry_ranked_and_has_roll_yield() -> None:
    assert contract_symbol("GC", 2026, 12) == "GCZ26.CMX"
    date = pd.Timestamp("2026-08-20", tz="UTC")
    frames = [
        pd.DataFrame({"date": [date], "close": [4400.0], "expiration": [
            pd.Timestamp("2026-12-29", tz="UTC")], "symbol": ["GCZ26.CMX"]}),
        pd.DataFrame({"date": [date], "close": [4450.0], "expiration": [
            pd.Timestamp("2027-02-25", tz="UTC")], "symbol": ["GCG27.CMX"]}),
    ]
    curve = build_curve(frames, "GC")
    assert list(curve["curve_rank"]) == [1, 2]
    assert curve["annualized_roll_yield"].notna().all()


def test_contract_curve_normalizes_mixed_yahoo_timezones() -> None:
    frames = [
        pd.DataFrame({"date": [pd.Timestamp("2026-08-20", tz="UTC")], "close": [4400.0],
                      "expiration": [pd.Timestamp("2026-12-29")],
                      "symbol": ["GCZ26.CMX"]}),
        pd.DataFrame({"date": [pd.Timestamp("2026-08-20")], "close": [4450.0],
                      "expiration": [pd.Timestamp("2027-02-25", tz="UTC")],
                      "symbol": ["GCG27.CMX"]}),
        pd.DataFrame({"date": [pd.Timestamp("2026-08-20")], "close": [1.0],
                      "expiration": [pd.NaT], "symbol": ["UNKNOWN"]}),
    ]
    curve = build_curve(frames, "GC")
    assert len(curve) == 2
    assert str(curve["date"].dt.tz) == "UTC"
    assert curve["annualized_roll_yield"].notna().all()
