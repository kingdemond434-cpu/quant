"""Winner pyramiding: exposure grows only after the market proved the thesis.

This is the mechanism two independent public sources converged on, and it is one
character away from the mechanism that destroys accounts. The difference is the
SIGN of the move that triggers the add: a pyramid adds into profit, a martingale
adds into loss. Nothing in a P&L curve distinguishes them until the day it does,
so the engine has to make the difference structural rather than a convention the
caller is trusted to follow -- `add_every_r` is a distance in FAVOUR of the
position and there is no parameter that spends size on an adverse move.

Three properties are load-bearing and each has a known-answer test below:

  1. Every add pays its own full round trip. A three-unit stack charged one
     spread is the same error class as the 0.48 gold spread -- it makes an
     expensive mechanism look free, and pyramiding is expensive by construction.
  2. R stays measured in the INITIAL risk unit, so a pyramided cell and a flat
     cell are still comparable and the promotion gate needs no special case.
  3. With `add_ratchets_stop` the stack's stop moves to the previous add level,
     so open risk cannot grow without bound. The flag exists to MEASURE the
     unratcheted version, not to trade it.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd
import pytest

_DESK = Path(__file__).resolve().parents[1]
if str(_DESK) not in sys.path:
    sys.path.insert(0, str(_DESK))

from mt5desk.engine import Costs, Signal, run_backtest  # noqa: E402

FREE = Costs(spread_per_lot=0.0, commission_per_lot=0.0, contract_oz=100.0)


def _bars(rows: list[tuple[float, float, float, float]]) -> pd.DataFrame:
    """rows = (open, high, low, close), one per hour from a fixed epoch."""
    # naive, not tz-aware: the engine casts the index to datetime64[ns] and numpy
    # warns on dropping a timezone, which `filterwarnings = error` turns into a
    # failure. The desk's frames are naive UTC by convention.
    idx = pd.date_range("2024-01-01", periods=len(rows), freq="1h")
    return pd.DataFrame(
        {"open": [r[0] for r in rows], "high": [r[1] for r in rows],
         "low": [r[2] for r in rows], "close": [r[3] for r in rows]}, index=idx)


def _sig(df, **kw) -> Signal:
    base = dict(time=df.index[0], side=1, stop=99.0, target=103.0,
                ttl_bars=20, tag="t")
    base.update(kw)
    return Signal(**base)


# --------------------------------------------------------------- known answers

def test_flat_trade_is_unchanged_when_pyramiding_is_off() -> None:
    """The default path must be byte-identical to before the feature existed."""
    df = _bars([(100, 100, 100, 100),      # signal bar
                (100, 100.5, 99.8, 100.2),  # entry at open 100
                (100.2, 103.5, 100.0, 103.2)])
    res = run_backtest(df, [_sig(df)], FREE)
    assert len(res.trades) == 1
    t = res.trades[0]
    assert t.reason == "target"
    assert t.units == 1.0 and t.adds == 0
    # entry 100, stop 99 -> risk 1.0; target 103 -> +3R exactly
    assert t.r_multiple == pytest.approx(3.0, abs=1e-9)


def test_one_add_earns_from_its_own_fill_price_not_the_entry() -> None:
    """entry 100, risk 1.0, add at +1R = 101, exit at target 103.

    initial unit : (103 - 100) / 1 = +3.0 R
    add (0.5 unit): 0.5 * (103 - 101) / 1 = +1.0 R
    total 4.0 R -- NOT 4.5, which is what crediting the add from the entry gives.
    """
    df = _bars([(100, 100, 100, 100),
                (100, 100.5, 99.8, 100.2),
                (100.2, 103.5, 100.0, 103.2)])
    s = _sig(df, add_every_r=1.0, add_max=1, add_frac=0.5)
    t = run_backtest(df, [s], FREE).trades[0]
    assert t.adds == 1 and t.units == pytest.approx(1.5)
    assert t.r_multiple == pytest.approx(4.0, abs=1e-9)


def test_adds_stop_at_the_cap() -> None:
    """Three adds are available on the path; add_max=2 must fill exactly two."""
    df = _bars([(100, 100, 100, 100),
                (100, 100.5, 99.8, 100.2),
                (100.2, 106.0, 100.0, 105.8)])
    s = _sig(df, target=106.0, add_every_r=1.0, add_max=2, add_frac=1.0)
    t = run_backtest(df, [s], FREE).trades[0]
    assert t.adds == 2 and t.units == pytest.approx(3.0)
    # 1*(106-100) + 1*(106-101) + 1*(106-102) = 6 + 5 + 4
    assert t.r_multiple == pytest.approx(15.0, abs=1e-9)


def test_every_unit_pays_its_own_round_trip() -> None:
    """A 3-unit stack pays 3 round trips. One spread for the stack is the 0.48 bug."""
    df = _bars([(100, 100, 100, 100),
                (100, 100.5, 99.8, 100.2),
                (100.2, 106.0, 100.0, 105.8)])
    costs = Costs(spread_per_lot=10.0, commission_per_lot=0.0, contract_oz=100.0)
    per_oz = costs.per_oz_roundtrip() / costs.contract_oz          # 0.10 $/oz
    flat = run_backtest(df, [_sig(df, target=106.0)], costs).trades[0]
    pyr = run_backtest(df, [_sig(df, target=106.0, add_every_r=1.0,
                                 add_max=2, add_frac=1.0)], costs).trades[0]
    assert flat.units == 1.0 and pyr.units == pytest.approx(3.0)
    # risk unit is 1.0 price, so cost in R == per_oz * units
    assert (6.0 - flat.r_multiple) == pytest.approx(per_oz * 1.0, abs=1e-9)
    assert (15.0 - pyr.r_multiple) == pytest.approx(per_oz * 3.0, abs=1e-9)


# ------------------------------------------------------------------ risk rails

def test_first_add_ratchets_the_stop_to_breakeven() -> None:
    """Reach +1R, add, then collapse. The stack exits at entry, not at -1R.

    initial unit : (100 - 100) = 0
    add          : 0.5 * (100 - 101) = -0.5 R
    A pyramid that gave back a full stop after being right would be strictly
    worse than not pyramiding, and that is the outcome this rail prevents.
    """
    df = _bars([(100, 100, 100, 100),
                (100, 100.5, 99.8, 100.2),
                (100.2, 101.5, 100.1, 101.2),   # add fills at 101, stop -> 100
                (101.2, 101.3, 95.0, 95.5)])    # collapse through the new stop
    s = _sig(df, target=110.0, add_every_r=1.0, add_max=1, add_frac=0.5)
    t = run_backtest(df, [s], FREE).trades[0]
    assert t.adds == 1
    assert t.reason == "stop"
    assert t.r_multiple == pytest.approx(-0.5, abs=1e-9)


def test_unratcheted_stack_is_measurably_worse_on_the_same_path() -> None:
    """The flag exists to quantify the rail, so the rail must actually bind."""
    df = _bars([(100, 100, 100, 100),
                (100, 100.5, 99.8, 100.2),
                (100.2, 101.5, 100.1, 101.2),
                (101.2, 101.3, 95.0, 95.5)])
    kw = dict(target=110.0, add_every_r=1.0, add_max=1, add_frac=0.5)
    ratcheted = run_backtest(df, [_sig(df, **kw)], FREE).trades[0]
    loose = run_backtest(
        df, [_sig(df, add_ratchets_stop=False, **kw)], FREE).trades[0]
    # loose: initial (99-100) = -1.0, add 0.5*(99-101) = -1.0  ->  -2.0 R
    assert loose.r_multiple == pytest.approx(-2.0, abs=1e-9)
    assert ratcheted.r_multiple > loose.r_multiple


def test_no_add_fills_on_a_bar_that_stopped_out() -> None:
    """One bar reaches BOTH the add level and the stop. The path is unknown, so
    the engine refuses the add rather than assuming the favourable ordering."""
    df = _bars([(100, 100, 100, 100),
                (100, 100.5, 99.8, 100.2),
                (100.2, 101.5, 98.0, 98.5)])   # high 101.5 >= add 101, low 98 <= stop 99
    s = _sig(df, target=110.0, add_every_r=1.0, add_max=1, add_frac=0.5)
    t = run_backtest(df, [s], FREE).trades[0]
    assert t.adds == 0 and t.units == 1.0
    assert t.reason == "stop"
    assert t.r_multiple == pytest.approx(-1.0, abs=1e-9)


def test_short_side_pyramids_downward() -> None:
    """The add level must follow the SIDE, not the chart's up direction."""
    df = _bars([(100, 100, 100, 100),
                (100, 100.2, 99.5, 99.8),
                (99.8, 100.0, 97.0, 97.2)])
    s = _sig(df, side=-1, stop=101.0, target=97.0,
             add_every_r=1.0, add_max=1, add_frac=0.5)
    t = run_backtest(df, [s], FREE).trades[0]
    assert t.adds == 1
    # entry 100 risk 1.0; add at 99; exit at target 97
    # initial 1*(100-97) = 3.0 ; add 0.5*(99-97) = 1.0
    assert t.r_multiple == pytest.approx(4.0, abs=1e-9)


def test_there_is_no_parameter_that_adds_into_an_adverse_move() -> None:
    """The structural guarantee: a negative spacing must not be honoured as a
    martingale. It disables the pyramid instead."""
    df = _bars([(100, 100, 100, 100),
                (100, 100.5, 99.8, 100.2),
                (100.2, 100.4, 99.2, 99.4),
                (99.4, 103.5, 99.2, 103.2)])
    s = _sig(df, add_every_r=-1.0, add_max=3, add_frac=1.0)
    t = run_backtest(df, [s], FREE).trades[0]
    assert t.adds == 0 and t.units == 1.0


# ------------------------------------------------- the fill-bar limit defect

def test_a_limit_fill_is_not_paid_by_its_own_bar() -> None:
    """The bar that filled a BUY LIMIT may not also pay the target.

    We were filled because this bar's LOW reached down to the order. Crediting
    the same bar's HIGH with the target assumes the high came after the fill,
    and on a down bar it did not. Measured on GBPJPY fair-value-gap before this
    rail existed: 59.7% of trades resolved on the fill bar, 1022 targets against
    713 stops, E[R] +0.283 there against +0.105 everywhere else. Removing it
    took the same cell from t=+9.16 to t=-6.18.
    """
    df = _bars([(100, 100, 100, 100),
                (100, 100.2, 99.9, 100.1),
                # this bar dips to fill the limit at 99 AND prints 103 -- but we
                # cannot know the high came after the dip
                (100.1, 103.5, 98.9, 103.0),
                (103.0, 103.2, 102.0, 102.5)])
    s = _sig(df, stop=98.0, target=102.0, trigger=99.0, wait_bars=3, ttl_bars=10)
    t = run_backtest(df, [s], FREE).trades[0]
    assert t.entry == pytest.approx(99.0)
    assert t.reason != "target" or t.bars_held > 1


def test_a_stop_entry_is_still_paid_by_its_own_bar() -> None:
    """A BUY STOP fills on the way UP, so the same bar's later high is genuinely
    later. The rail must not fire here or every breakout family loses real
    fills it did take."""
    df = _bars([(100, 100, 100, 100),
                (100, 100.2, 99.9, 100.1),
                # low 100.5 stays clear of the 100.0 stop, so the only thing
                # this bar can resolve is the target
                (100.1, 104.0, 100.5, 103.8)])   # through the 101 stop, on to 103
    s = _sig(df, stop=100.0, target=103.0, trigger=101.0, wait_bars=3, ttl_bars=10)
    t = run_backtest(df, [s], FREE).trades[0]
    assert t.entry == pytest.approx(101.0)
    assert t.reason == "target" and t.bars_held == 1
