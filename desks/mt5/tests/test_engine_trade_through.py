"""A resting LIMIT entry fills only when the side's own quote trades THROUGH it (2026-11-03).

`engine.run_backtest` filled every limit when the BID bar's range touched the level, at the
level. A buy limit at L really fills only when the ask trades below L (bid low < L - spread),
and a sell limit only when the bid trades above L: a bare touch leaves the resting order behind
the queue. The touch credited each limit-entry trade about a spread and kept trades that never
filled. These tests pin the trade-through rule, the recorded price, that stop entries and market
entries are untouched, and that the leg memo never reuses a walk across a different fill rule or
spread.
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

DESK = Path(__file__).resolve().parents[1]
if str(DESK) not in sys.path:
    sys.path.insert(0, str(DESK))

from mt5desk import engine  # noqa: E402
from mt5desk.engine import Costs, Signal, run_backtest  # noqa: E402

SPREAD = 0.02                       # price units: spread_per_lot / contract_oz
COSTS = Costs(spread_per_lot=SPREAD * 100.0, commission_per_lot=0.0, contract_oz=100.0)


def _frame(lows: list[float], highs: list[float]) -> pd.DataFrame:
    """Flat bars at 100 except where a low/high is given; enough bars for the hold."""
    n = 30
    idx = pd.date_range("2025-01-06", periods=n, freq="h", tz="UTC")
    lo = np.full(n, 99.9)
    hi = np.full(n, 100.1)
    lo[2:2 + len(lows)] = lows
    hi[2:2 + len(highs)] = highs
    return pd.DataFrame({"open": np.full(n, 100.0), "high": hi, "low": lo,
                         "close": np.full(n, 100.0)}, index=idx)


def _buy_limit(df: pd.DataFrame, level: float = 99.5) -> Signal:
    return Signal(time=df.index[0], side=1, stop=level - 1.0, target=level + 5.0, ttl_bars=4,
                  tag="t", trigger=level, wait_bars=3)


def _sell_limit(df: pd.DataFrame, level: float = 100.5) -> Signal:
    return Signal(time=df.index[0], side=-1, stop=level + 1.0, target=level - 5.0, ttl_bars=4,
                  tag="t", trigger=level, wait_bars=3)


@pytest.fixture(autouse=True)
def _no_memo_carryover():
    engine._LEGS.slot = None
    yield
    engine._LEGS.slot = None


def test_a_buy_limit_the_bid_only_touches_never_fills() -> None:
    # bid low exactly at L, then half a spread under L: the ask never reaches L
    df = _frame(lows=[99.5, 99.5 - SPREAD / 2, 99.9], highs=[100.1, 100.1, 100.1])
    sig = _buy_limit(df)
    assert run_backtest(df, [sig], COSTS).trades == []
    # the old touch rule filled it, at L: that is the flattery being removed
    touched = run_backtest(df, [sig], COSTS, limit_fill="touch").trades
    assert len(touched) == 1 and touched[0].entry == pytest.approx(99.5)


def test_a_buy_limit_fills_when_the_ask_trades_through_and_pays_L() -> None:
    df = _frame(lows=[99.9, 99.5 - SPREAD - 0.001], highs=[100.1, 100.1])
    trades = run_backtest(df, [_buy_limit(df)], COSTS).trades
    assert len(trades) == 1
    t = trades[0]
    # recorded on the bid side: L - spread, so with the spread the cost model charges, L is paid
    assert t.entry == pytest.approx(99.5 - SPREAD)
    assert t.entry_time == df.index[3]


def test_a_sell_limit_fills_only_when_the_bid_trades_above_it() -> None:
    touch = _frame(lows=[99.9, 99.9], highs=[100.5, 100.5])
    assert run_backtest(touch, [_sell_limit(touch)], COSTS).trades == []
    through = _frame(lows=[99.9, 99.9], highs=[100.5, 100.501])
    trades = run_backtest(through, [_sell_limit(through)], COSTS).trades
    assert len(trades) == 1 and trades[0].entry == pytest.approx(100.5)
    assert trades[0].entry_time == through.index[3]


def test_a_stop_entry_and_a_market_entry_are_unchanged() -> None:
    df = _frame(lows=[99.9, 99.9], highs=[100.1, 100.6])
    stop_entry = Signal(time=df.index[0], side=1, stop=99.0, target=106.0, ttl_bars=4, tag="s",
                        trigger=100.6, wait_bars=3)          # buy STOP above the market
    market = Signal(time=df.index[0], side=1, stop=99.0, target=106.0, ttl_bars=4, tag="m")
    for sig in (stop_entry, market):
        new = run_backtest(df, [sig], COSTS).trades
        engine._LEGS.slot = None
        old = run_backtest(df, [sig], COSTS, limit_fill="touch").trades
        assert new == old and len(new) == 1


def test_the_memo_never_reuses_a_walk_across_a_spread_or_fill_rule() -> None:
    """The judge replays a cell at 1x then 3x costs on the same objects. A limit cell's fill now
    reads the spread, so the 3x arm must re-walk; it must equal an un-memoised run."""
    df = _frame(lows=[99.9, 99.5 - 2 * SPREAD], highs=[100.1, 100.1])
    sigs = [_buy_limit(df)]
    one = run_backtest(df, sigs, COSTS)
    assert len(one.trades) == 1
    stressed = Costs(spread_per_lot=3 * SPREAD * 100.0, commission_per_lot=0.0,
                     contract_oz=100.0)
    three = run_backtest(df, sigs, stressed)       # 3x spread: the ask never trades through
    assert three.trades == []
    engine._LEGS.slot = None
    assert run_backtest(df, sigs, stressed).trades == three.trades
    touch = run_backtest(df, sigs, COSTS, limit_fill="touch")
    assert len(touch.trades) == 1 and touch.trades[0].entry == pytest.approx(99.5)


def test_an_unknown_fill_rule_is_refused() -> None:
    df = _frame(lows=[99.9], highs=[100.1])
    with pytest.raises(ValueError):
        run_backtest(df, [_buy_limit(df)], COSTS, limit_fill="mid")


def test_a_generator_that_priced_the_trade_through_is_not_charged_twice() -> None:
    """entry_alpha already shifts its level by its own hourly worst spread; the engine must fill
    that signal on a touch of the shifted level, never subtract a second spread."""
    df = _frame(lows=[99.9, 99.5], highs=[100.1, 100.1])
    priced = Signal(time=df.index[0], side=1, stop=98.5, target=104.5, ttl_bars=4, tag="t",
                    trigger=99.5, wait_bars=3, fill_through_priced=True)
    trades = run_backtest(df, [priced], COSTS).trades
    assert len(trades) == 1 and trades[0].entry == pytest.approx(99.5)
    engine._LEGS.slot = None
    assert run_backtest(df, [_buy_limit(df)], COSTS).trades == []


def test_a_declared_buy_stop_the_open_gapped_past_fills_at_that_open() -> None:
    """Audit should-fix (a): inference reads a gapped buy-stop as a limit and demands a
    trade-through it never needed. Declared as a stop, it is marketable and fills at the open."""
    df = _frame(lows=[99.9, 99.9], highs=[100.1, 100.1])
    gapped = Signal(time=df.index[0], side=1, stop=98.0, target=106.0, ttl_bars=4, tag="s",
                    trigger=99.5, wait_bars=3, order_type="stop")   # open 100 is already above
    trades = run_backtest(df, [gapped], COSTS).trades
    assert len(trades) == 1
    assert trades[0].entry == pytest.approx(100.0) and trades[0].entry_time == df.index[1]
    engine._LEGS.slot = None
    inferred = Signal(time=df.index[0], side=1, stop=98.0, target=106.0, ttl_bars=4, tag="s",
                      trigger=99.5, wait_bars=3)
    assert run_backtest(df, [inferred], COSTS).trades == []


def test_a_declared_limit_the_open_already_sits_through_fills_at_the_open() -> None:
    df = _frame(lows=[99.9, 99.9], highs=[100.1, 100.1])
    marketable = Signal(time=df.index[0], side=1, stop=98.0, target=106.0, ttl_bars=4, tag="l",
                        trigger=100.5, wait_bars=3, order_type="limit")
    trades = run_backtest(df, [marketable], COSTS).trades
    assert len(trades) == 1 and trades[0].entry == pytest.approx(100.0)


def test_an_unknown_order_type_is_refused() -> None:
    df = _frame(lows=[99.9], highs=[100.1])
    bad = Signal(time=df.index[0], side=1, stop=98.0, target=106.0, ttl_bars=4, tag="x",
                 trigger=99.5, wait_bars=3, order_type="market")
    with pytest.raises(ValueError):
        run_backtest(df, [bad], COSTS)


# Audit should-fix (b): only a generator that prices the trade-through into its own trigger may
# opt out of the engine's rule. Today that is entry_alpha, in families_cluster_reach.py.
FILL_THROUGH_PRICED_ALLOWED = {"desks/mt5/mt5desk/families_cluster_reach.py"}


def test_only_the_allowlisted_generator_opts_out_of_trade_through() -> None:
    import re
    repo = DESK.parents[1]
    setter = re.compile(r"fill_through_priced\s*=\s*(?!False)")
    offenders = []
    for path in repo.rglob("*.py"):
        rel = path.relative_to(repo).as_posix()
        if "/tests/" in f"/{rel}" or rel.startswith(("tests/", ".")) or "site-packages" in rel:
            continue
        if rel == "desks/mt5/mt5desk/engine.py" or rel in FILL_THROUGH_PRICED_ALLOWED:
            continue
        try:
            text = path.read_text("utf-8")
        except (OSError, UnicodeDecodeError):
            continue
        if setter.search(text):
            offenders.append(rel)
    assert offenders == [], f"fill_through_priced set outside the allowlist: {offenders}"
