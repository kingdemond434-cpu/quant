"""Fill rules fill-2026-11-25-a: gapped stop entries and short exits on the ask.

1. A resting STOP entry the market gaps through fills at the gapping bar's OPEN, never at the
   trigger (a price that was never offered). Stop versus limit is read against the SIGNAL bar's
   close -- the price known when the order was placed -- never against the fill bar's open.
   True limits keep their rule.
2. Bars are bid. A short buys back at the ASK, so its stop and target trigger when bid + spread
   touches them. The round-trip cost charged per trade is unchanged; only trigger levels move.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd
import pytest

_DESK = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_DESK))

from mt5desk import engine  # noqa: E402
from mt5desk.engine import Costs, Signal, run_backtest  # noqa: E402

FREE = Costs(spread_per_lot=0.0, commission_per_lot=0.0, contract_oz=1.0)
SPREAD = Costs(spread_per_lot=0.01, commission_per_lot=0.0, contract_oz=1.0)


def _bars(rows: list[tuple[float, float, float, float]]) -> pd.DataFrame:
    idx = pd.date_range("2026-01-05", periods=len(rows), freq="1h", tz="UTC")
    return pd.DataFrame(rows, columns=["open", "high", "low", "close"], index=idx)


def _flat(n: int, px: float = 1.00) -> list[tuple[float, float, float, float]]:
    return [(px, px + 0.001, px - 0.001, px)] * n


def test_fill_rules_are_versioned() -> None:
    assert engine.FILL_RULES == "fill-2026-11-25-a"
    df = _bars(_flat(6))
    assert run_backtest(df, [], FREE).fill_rules == engine.FILL_RULES


def test_a_buy_stop_gapped_over_fills_at_the_open_not_the_trigger() -> None:
    df = _bars([*_flat(2), (1.03, 1.035, 1.015, 1.03), *_flat(4, 1.03)])
    sig = Signal(time=df.index[1], side=1, stop=0.97, target=1.20, ttl_bars=3, tag="brk",
                 trigger=1.02, wait_bars=1)
    (t,) = run_backtest(df, [sig], FREE).trades
    assert t.entry == pytest.approx(1.03)
    assert t.entry_time == df.index[2]


def test_a_buy_stop_gapped_over_on_a_later_wait_bar_fills_at_that_open() -> None:
    # bar 2 stays below the trigger; bar 3 opens above it with its low above it too.
    df = _bars([*_flat(3), (1.03, 1.035, 1.025, 1.03), *_flat(4, 1.03)])
    sig = Signal(time=df.index[1], side=1, stop=0.97, target=1.20, ttl_bars=3, tag="brk",
                 trigger=1.02, wait_bars=3)
    (t,) = run_backtest(df, [sig], FREE).trades
    assert t.entry == pytest.approx(1.03) and t.entry_time == df.index[3]


def test_a_buy_stop_touched_inside_the_bar_still_fills_at_the_trigger() -> None:
    df = _bars([*_flat(2), (1.00, 1.03, 0.995, 1.02), *_flat(4, 1.02)])
    sig = Signal(time=df.index[1], side=1, stop=0.97, target=1.20, ttl_bars=3, tag="brk",
                 trigger=1.02)
    (t,) = run_backtest(df, [sig], FREE).trades
    assert t.entry == pytest.approx(1.02)


def test_a_buy_limit_is_unchanged() -> None:
    # trigger below the signal close: a LIMIT. Touched inside the bar, filled at the limit.
    df = _bars([*_flat(2), (1.00, 1.002, 0.985, 0.99), *_flat(4, 0.99)])
    sig = Signal(time=df.index[1], side=1, stop=0.95, target=1.10, ttl_bars=3, tag="lim",
                 trigger=0.99)
    (t,) = run_backtest(df, [sig], FREE).trades
    assert t.entry == pytest.approx(0.99)
    # a limit the market opened BELOW is still not filled at that open (rule kept as it was:
    # the bar must straddle the level).
    df2 = _bars([*_flat(2), (0.98, 0.985, 0.975, 0.98), *_flat(4, 0.98)])
    assert run_backtest(df2, [sig], FREE).trades == []


def test_a_sell_stop_gapped_through_fills_at_the_open() -> None:
    df = _bars([*_flat(2), (0.97, 0.985, 0.965, 0.97), *_flat(4, 0.97)])
    sig = Signal(time=df.index[1], side=-1, stop=1.03, target=0.80, ttl_bars=3, tag="brk",
                 trigger=0.98)
    (t,) = run_backtest(df, [sig], FREE).trades
    assert t.entry == pytest.approx(0.97)


def test_a_sell_limit_is_unchanged() -> None:
    df = _bars([*_flat(2), (1.00, 1.015, 0.998, 1.01), *_flat(4, 1.01)])
    sig = Signal(time=df.index[1], side=-1, stop=1.05, target=0.90, ttl_bars=3, tag="lim",
                 trigger=1.01)
    (t,) = run_backtest(df, [sig], FREE).trades
    assert t.entry == pytest.approx(1.01)


def test_order_type_is_read_from_the_signal_bar_not_the_fill_bar() -> None:
    # Signal close 1.00, trigger 1.02 => a buy STOP. The next bar opens 1.03: the old rule read
    # that as a limit (trigger < next open) and filled at 1.02.
    df = _bars([*_flat(2), (1.03, 1.04, 1.01, 1.03), *_flat(4, 1.03)])
    sig = Signal(time=df.index[1], side=1, stop=0.97, target=1.20, ttl_bars=3, tag="brk",
                 trigger=1.02)
    (t,) = run_backtest(df, [sig], FREE).trades
    assert t.entry == pytest.approx(1.03)


def test_a_shorts_stop_triggers_when_the_ask_touches_it() -> None:
    # bid high 1.045, ask high 1.055: the BID never reaches 1.05, the ASK does.
    df = _bars([(1.00, 1.00, 1.00, 1.00)] * 2 + [(1.00, 1.045, 1.00, 1.00)]
               + [(1.00, 1.00, 1.00, 1.00)] * 4)
    short = Signal(time=df.index[1], side=-1, stop=1.05, target=0.90, ttl_bars=3, tag="s")
    (t,) = run_backtest(df, [short], SPREAD).trades
    assert t.reason == "stop"
    # bought back at the ask 1.05 having sold at the bid 1.00: exactly -1R, the spread not
    # charged a second time on top of the ask fill.
    assert t.r_multiple == pytest.approx(-1.0)
    assert t.exit == pytest.approx(1.04)                 # recorded as the bid equivalent


def test_a_shorts_target_triggers_on_the_ask() -> None:
    # bid low 0.905 reaches the 0.91 target on the bid but the ask (0.915) does not.
    df = _bars([(1.00, 1.00, 1.00, 1.00)] * 2 + [(1.00, 1.00, 0.905, 1.00)]
               + [(1.00, 1.00, 1.00, 1.00)] * 4)
    short = Signal(time=df.index[1], side=-1, stop=1.10, target=0.91, ttl_bars=3, tag="s")
    (t,) = run_backtest(df, [short], SPREAD).trades
    assert t.reason == "ttl"
    # and one that the ask does reach fills at the target exactly (+R minus nothing extra)
    df2 = _bars([(1.00, 1.00, 1.00, 1.00)] * 2 + [(1.00, 1.00, 0.895, 1.00)]
                + [(1.00, 1.00, 1.00, 1.00)] * 4)
    (t2,) = run_backtest(df2, [short], SPREAD).trades
    assert t2.reason == "target" and t2.r_multiple == pytest.approx(0.09 / 0.10)


def test_a_long_still_exits_on_the_bid() -> None:
    df = _bars([(1.00, 1.00, 1.00, 1.00)] * 2 + [(1.00, 1.00, 0.955, 1.00)]
               + [(1.00, 1.00, 1.00, 1.00)] * 4)
    long_ = Signal(time=df.index[1], side=1, stop=0.95, target=1.10, ttl_bars=3, tag="l")
    (t,) = run_backtest(df, [long_], SPREAD).trades
    assert t.reason == "ttl"
    assert t.r_multiple == pytest.approx(-0.01 / 0.05)      # bought the ask, sold the bid


@pytest.mark.parametrize("side", [1, -1])
def test_round_trip_cost_per_trade_is_unchanged(side: int) -> None:
    # A time exit moves no trigger, so its R difference between a free and a costed run is the
    # whole round-trip charge: exactly `per_oz_roundtrip / contract / stop_dist`, both sides.
    costs = Costs(spread_per_lot=0.01, commission_per_lot=0.002, contract_oz=1.0,
                  quote_per_account=1.0)
    df = _bars([(1.00, 1.00, 1.00, 1.00)] * 8)
    sig = Signal(time=df.index[1], side=side, stop=1.00 - side * 0.10,
                 target=1.00 + side * 0.10, ttl_bars=3, tag="c")
    (free,) = run_backtest(df, [sig], FREE).trades
    (paid,) = run_backtest(df, [sig], costs).trades
    assert free.reason == paid.reason == "ttl"
    assert free.r_multiple - paid.r_multiple == pytest.approx(
        costs.per_oz_roundtrip() / costs.contract_oz / 0.10)
    assert costs.per_oz_roundtrip() == pytest.approx(0.01 + 0.002 * 2)


def test_the_leg_memo_rewalks_a_short_list_under_a_different_spread() -> None:
    df = _bars([(1.00, 1.00, 1.00, 1.00)] * 2 + [(1.00, 1.045, 1.00, 1.00)]
               + [(1.00, 1.00, 1.00, 1.00)] * 4)
    sigs = [Signal(time=df.index[1], side=-1, stop=1.05, target=0.90, ttl_bars=3, tag="s")]
    free = run_backtest(df, sigs, FREE).trades[0]
    paid = run_backtest(df, sigs, SPREAD).trades[0]
    assert free.reason == "ttl" and paid.reason == "stop"
