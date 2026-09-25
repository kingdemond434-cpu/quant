"""The engine fills in TIME order and only takes fills the live venue would give (2026-09-25).

Four defects, confirmed by an audit with real-bar experiments, each pinned here:

1. LOOK-AHEAD. `run_backtest` walked signals in LIST order. `family_session_range_breakout`
   emits a long then a short at one timestamp, each a resting stop alive `wait_bars` bars. The
   long was evaluated over its whole window first; if it filled, the short was blocked, so the
   short was only ever taken when the long had NOT filled later -- selected by future bars. On a
   driftless random walk at zero cost that printed about +0.06R a trade.
2. GAP-THROUGH ENTRIES. A buy stop whose arming bar opens above it was re-read as a limit and
   filled on the pullback -- an order live refuses (10015).
3. PERFECT STOPS. Every stop exit was paid at exactly its level, even on a bar that opened
   through it, and with no slippage.
4. WRONG-SIDE STOPS. A stop at or beyond the actual fill was booked as a "stop" at about +1R.
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

_DESK = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_DESK))

from mt5desk import families  # noqa: E402
from mt5desk.engine import (  # noqa: E402
    MEASURED_STOP_SLIPPAGE_PTS,
    BacktestResult,
    Costs,
    Signal,
    run_backtest,
)
from mt5desk.families_orthogonal import family_overnight_gap_decay  # noqa: E402

ZERO = Costs(spread_per_lot=0.0, commission_per_lot=0.0, contract_oz=100.0)


def _frame(rows: list[tuple[float, float, float, float]]) -> pd.DataFrame:
    idx = pd.date_range("2026-01-05 00:00", periods=len(rows), freq="1h", tz="UTC")
    o, h, lo, c = (list(x) for x in zip(*rows, strict=True))
    return pd.DataFrame({"open": o, "high": h, "low": lo, "close": c}, index=idx)


FLAT = (100.0, 100.5, 99.5, 100.0)


def _bracket(df: pd.DataFrame, wait: int = 8, ttl: int = 3) -> list[Signal]:
    t = df.index[0]
    return [
        Signal(time=t, side=1, stop=100.0, target=115.0, ttl_bars=ttl, tag="b",
               trigger=105.0, wait_bars=wait, entry_type="stop"),
        Signal(time=t, side=-1, stop=100.0, target=85.0, ttl_bars=ttl, tag="b",
               trigger=95.0, wait_bars=wait, entry_type="stop"),
    ]


def _short_then(long_later: bool) -> pd.DataFrame:
    """The short fills at bar 2 and times out at bar 5. Bar 6 either hits the long or does not."""
    rows = [FLAT, FLAT,
            (100.0, 100.0, 94.0, 94.5),      # 2: short triggers at 95
            (94.5, 96.0, 93.5, 95.0),
            (95.0, 96.0, 93.5, 95.0),
            (95.0, 96.0, 94.0, 95.0),        # 5: short's TTL exit at this open
            (95.0, 106.0, 95.0, 105.5) if long_later else (95.0, 96.0, 94.0, 95.0),
            (95.0, 96.0, 94.0, 95.0)]
    rows += [(95.0, 96.0, 94.0, 95.0)] * 6
    return _frame(rows)


def _shorts(res: BacktestResult) -> list[tuple[object, ...]]:
    return [(t.entry_time, t.entry, t.exit, round(t.r_multiple, 12))
            for t in res.trades if t.side < 0]


@pytest.mark.parametrize("mode", ["independent", "oco"])
def test_short_is_never_chosen_by_the_longs_future_non_fill(mode: str) -> None:
    """Two tapes identical through the short's whole life, different only AFTER it: the short's
    trade must be identical on both. The list-order engine dropped it on the tape where the long
    filled later, and took it on the tape where the long never filled."""
    a, b = _short_then(long_later=True), _short_then(long_later=False)
    ra = run_backtest(a, _bracket(a), ZERO, bracket_mode=mode)
    rb = run_backtest(b, _bracket(b), ZERO, bracket_mode=mode)
    assert _shorts(ra) == _shorts(rb)
    assert len(_shorts(ra)) == 1
    assert _shorts(ra)[0][0] == a.index[2]


def test_oco_takes_the_earliest_fill_and_cancels_the_sibling() -> None:
    df = _short_then(long_later=True)
    res = run_backtest(df, _bracket(df), ZERO, bracket_mode="oco")
    assert [t.side for t in res.trades] == [-1]


def test_independent_legs_both_trade_like_the_live_bracket() -> None:
    df = _short_then(long_later=True)
    res = run_backtest(df, _bracket(df), ZERO)            # default mode
    assert [(t.side, t.entry_time) for t in res.trades] == [(-1, df.index[2]), (1, df.index[6])]


def test_independent_legs_may_overlap_each_other() -> None:
    """The short is still open when the long fills: live holds both, and so does the engine."""
    rows = [FLAT, FLAT, (100.0, 100.0, 94.0, 94.5), (94.5, 105.5, 94.0, 105.2)]
    rows += [(105.2, 105.8, 104.8, 105.3)] * 10
    df = _frame(rows)
    res = run_backtest(df, _bracket(df, ttl=6), ZERO)
    assert sorted(t.side for t in res.trades) == [-1, 1]
    res_oco = run_backtest(df, _bracket(df, ttl=6), ZERO, bracket_mode="oco")
    assert [t.side for t in res_oco.trades] == [-1]


def test_oco_same_bar_tie_goes_to_the_first_listed_leg() -> None:
    rows = [FLAT, FLAT, (100.0, 106.0, 94.0, 100.0)] + [FLAT] * 8
    df = _frame(rows)
    res = run_backtest(df, _bracket(df), ZERO, bracket_mode="oco")
    assert [t.side for t in res.trades] == [1]


def test_other_signals_position_still_blocks() -> None:
    """Single-position discipline across DIFFERENT signals is unchanged."""
    df = _frame([FLAT] * 20)
    s1 = Signal(time=df.index[0], side=1, stop=98.0, target=110.0, ttl_bars=5, tag="x")
    s2 = Signal(time=df.index[2], side=1, stop=98.0, target=110.0, ttl_bars=5, tag="x")
    s3 = Signal(time=df.index[8], side=1, stop=98.0, target=110.0, ttl_bars=5, tag="x")
    res = run_backtest(df, [s1, s2, s3], ZERO)
    assert [t.entry_time for t in res.trades] == [df.index[1], df.index[9]]


def test_trades_come_back_in_fill_order() -> None:
    df = _frame([FLAT] * 30)
    late = Signal(time=df.index[20], side=1, stop=98.0, target=110.0, ttl_bars=2, tag="x")
    early = Signal(time=df.index[2], side=1, stop=98.0, target=110.0, ttl_bars=2, tag="x")
    res = run_backtest(df, [late, early], ZERO)
    assert [t.entry_time for t in res.trades] == [df.index[3], df.index[21]]


# --- 2. gap-through entries ---------------------------------------------------------------

def test_stop_entry_gapped_at_placement_is_skipped() -> None:
    """Arming bar opens at 106, above a buy stop at 105; a pullback to 104 later must NOT fill
    it as though it were a limit."""
    rows = [FLAT, (106.0, 106.5, 105.5, 106.0), (106.0, 106.0, 104.0, 104.5)] + [FLAT] * 8
    df = _frame(rows)
    sig = _bracket(df)[0]
    assert run_backtest(df, [sig], ZERO).trades == []


def test_undeclared_trigger_keeps_the_inferred_limit_semantics() -> None:
    """Without `entry_type` a trigger below the arming open IS a buy limit, as it always was."""
    rows = [FLAT, (106.0, 106.5, 105.5, 106.0), (106.0, 106.0, 104.0, 104.5)] + [FLAT] * 8
    df = _frame(rows)
    sig = Signal(time=df.index[0], side=1, stop=100.0, target=115.0, ttl_bars=3, tag="l",
                 trigger=105.0, wait_bars=8)
    res = run_backtest(df, [sig], ZERO)
    assert [(t.entry_time, t.entry) for t in res.trades] == [(df.index[2], 105.0)]


def test_resting_stop_gapped_through_later_fills_at_the_open() -> None:
    rows = [FLAT, FLAT, FLAT, (107.0, 108.0, 106.5, 107.5)] + [(107.5, 108.0, 107.0, 107.5)] * 8
    df = _frame(rows)
    res = run_backtest(df, [_bracket(df)[0]], ZERO)
    assert [(t.entry_time, t.entry) for t in res.trades] == [(df.index[3], 107.0)]


def test_session_range_breakout_declares_stop_entries() -> None:
    idx = pd.date_range("2026-01-05", periods=24 * 30, freq="1h", tz="UTC")
    rng = np.random.default_rng(0)
    c = 100 + np.cumsum(rng.normal(0, 0.2, len(idx)))
    df = pd.DataFrame({"open": c, "high": c + 0.3, "low": c - 0.3, "close": c}, index=idx)
    sigs = families.family_session_range_breakout(df)
    assert sigs and all(s.entry_type == "stop" for s in sigs)
    lvl = families.family_level_breakout(df)
    assert lvl and all(s.entry_type == "stop" for s in lvl)


# --- 3. stop exits --------------------------------------------------------------------------

def test_stop_exit_on_a_gap_pays_the_open_not_the_stop() -> None:
    rows = [FLAT, FLAT, (96.0, 96.5, 95.5, 96.0)] + [FLAT] * 5
    df = _frame(rows)
    sig = Signal(time=df.index[0], side=1, stop=98.0, target=110.0, ttl_bars=5, tag="x")
    (t,) = run_backtest(df, [sig], ZERO).trades
    assert t.reason == "stop" and t.exit == 96.0
    assert t.r_multiple == pytest.approx(-2.0)


def test_short_stop_exit_on_a_gap_pays_the_open() -> None:
    rows = [FLAT, FLAT, (104.0, 104.5, 103.5, 104.0)] + [FLAT] * 5
    df = _frame(rows)
    sig = Signal(time=df.index[0], side=-1, stop=102.0, target=90.0, ttl_bars=5, tag="x")
    (t,) = run_backtest(df, [sig], ZERO).trades
    assert t.reason == "stop" and t.exit == 104.0


def test_stop_slippage_is_charged_adversely() -> None:
    rows = [FLAT, FLAT, (100.0, 100.2, 97.0, 97.5)] + [FLAT] * 5
    df = _frame(rows)
    costs = Costs(spread_per_lot=0.0, commission_per_lot=0.0, contract_oz=100.0,
                  stop_slippage_pts=13.0, point=0.01)
    lng = Signal(time=df.index[0], side=1, stop=98.0, target=110.0, ttl_bars=5, tag="x")
    (t,) = run_backtest(df, [lng], costs).trades
    assert t.exit == pytest.approx(98.0 - 0.13)
    rows = [FLAT, FLAT, (100.0, 103.0, 99.8, 102.5)] + [FLAT] * 5
    df = _frame(rows)
    sht = Signal(time=df.index[0], side=-1, stop=102.0, target=90.0, ttl_bars=5, tag="x")
    (t,) = run_backtest(df, [sht], costs).trades
    assert t.exit == pytest.approx(102.0 + 0.13)


def test_targets_pay_no_stop_slippage() -> None:
    rows = [FLAT, FLAT, (100.0, 103.0, 99.8, 102.5)] + [FLAT] * 5
    df = _frame(rows)
    costs = Costs(spread_per_lot=0.0, commission_per_lot=0.0, contract_oz=100.0,
                  stop_slippage_pts=13.0, point=0.01)
    sig = Signal(time=df.index[0], side=1, stop=98.0, target=102.0, ttl_bars=5, tag="x")
    (t,) = run_backtest(df, [sig], costs).trades
    assert t.reason == "target" and t.exit == 102.0


def test_from_symbol_resolves_stop_slippage() -> None:
    gold = {"symbol": "XAUUSD", "contract_size": 100.0, "tick_size": 0.01, "tick_value": 1.0,
            "median_spread_pts": 16.0}
    c = Costs.from_symbol(gold)
    assert c.stop_slippage_pts == MEASURED_STOP_SLIPPAGE_PTS["XAUUSD"] == 13.0
    assert c.stop_slippage_px() == pytest.approx(0.13)
    # unmeasured symbol: zero, stated as such
    eur = {"symbol": "EURUSD", "contract_size": 1e5, "tick_size": 1e-5, "tick_value": 1.0,
           "median_spread_pts": 2.0}
    assert Costs.from_symbol(eur).stop_slippage_px() == 0.0
    # per-symbol override on the metadata, then the argument
    assert Costs.from_symbol({**eur, "stop_slippage_pts": 4.0}).stop_slippage_px() \
        == pytest.approx(4e-5)
    assert Costs.from_symbol(gold, stop_slippage_pts=0.0).stop_slippage_px() == 0.0
    # carried through the stress derivation
    assert c.stressed(3.0).stop_slippage_px() == pytest.approx(0.13)


def test_hand_built_costs_charge_no_slippage() -> None:
    assert Costs().stop_slippage_px() == 0.0


# --- 4. wrong-side stops ----------------------------------------------------------------------

def test_wrong_side_stop_is_skipped_not_booked_as_a_profit() -> None:
    """overnight_gap_decay's shape: stop sized off the signal bar's open (101), fill at the next
    open (100.5), already past it. The engine used to exit at the stop for about +1R."""
    rows = [(101.5, 101.6, 101.4, 101.5), (100.5, 100.8, 100.2, 100.6)] + [FLAT] * 8
    df = _frame(rows)
    lng = Signal(time=df.index[0], side=1, stop=101.0, target=103.0, ttl_bars=4, tag="gap")
    sht = Signal(time=df.index[0], side=-1, stop=100.0, target=97.0, ttl_bars=4, tag="gap")
    assert run_backtest(df, [lng], ZERO).trades == []
    assert run_backtest(df, [sht], ZERO).trades == []


def test_wrong_side_skip_does_not_block_the_next_signal() -> None:
    rows = [(101.5, 101.6, 101.4, 101.5), (100.5, 100.8, 100.2, 100.6)] + [FLAT] * 8
    df = _frame(rows)
    bad = Signal(time=df.index[0], side=1, stop=101.0, target=103.0, ttl_bars=4, tag="gap")
    ok = Signal(time=df.index[1], side=1, stop=98.0, target=110.0, ttl_bars=2, tag="x")
    res = run_backtest(df, [bad, ok], ZERO)
    assert [t.entry_time for t in res.trades] == [df.index[2]]


def test_every_booked_trade_has_its_stop_on_the_losing_side() -> None:
    """Generic, on a gappy tape through the family that exposed it."""
    rng = np.random.default_rng(7)
    idx = pd.date_range("2025-01-06", periods=24 * 200, freq="1h", tz="UTC")
    o = np.empty(len(idx))
    c = np.empty(len(idx))
    prev = 100.0
    for k, ts in enumerate(idx):
        jump = rng.normal(0, 2.0) if ts.hour == 0 else (rng.normal(0, 0.8) if ts.hour == 1 else 0)
        o[k] = prev + jump                                 # overnight gap, then a second jump
        c[k] = prev = o[k] + rng.normal(0, 0.3)
    df = pd.DataFrame({"open": o, "high": np.maximum(o, c) + 0.2,
                       "low": np.minimum(o, c) - 0.2, "close": c}, index=idx)
    res = run_backtest(df, family_overnight_gap_decay(df), ZERO)
    assert res.trades
    assert all((t.entry - t.stop) * t.side > 0 for t in res.trades)


# --- the whole point: a driftless tape pays nothing --------------------------------------------

def _random_walk(seed: int, n: int, sub: int, vol: float = 2.0, px: float = 2000.0) -> pd.DataFrame:
    """H1 bars aggregated from `sub` Gaussian steps each, so the intrabar path is nearly
    continuous and the engine's fill-at-level assumption is nearly exact."""
    rng = np.random.default_rng(seed)
    idx = pd.date_range("2020-01-06", periods=n, freq="1h", tz="UTC")
    p = (px + np.cumsum(rng.normal(0, vol / np.sqrt(sub), n * sub))).reshape(n, sub)
    o = np.concatenate([[px], p[:-1, -1]])
    return pd.DataFrame({"open": o, "high": np.maximum(p.max(1), o),
                         "low": np.minimum(p.min(1), o), "close": p[:, -1]}, index=idx)


@pytest.mark.parametrize("mode", ["independent", "oco"])
def test_session_range_breakout_earns_nothing_on_a_random_walk(mode: str) -> None:
    """MEASURED before the fix, on these generators: +0.06R a trade at zero cost at 600 steps a
    bar, +0.10R at 30. After: about 0 at zero cost and negative after gold costs. The bound below
    is what separates the two, with the seeds fixed so the test is deterministic."""
    frames = [_random_walk(s, 12_000, 300) for s in range(3)]
    gold = Costs(spread_per_lot=16.0, commission_per_lot=2.0, contract_oz=100.0,
                 stop_slippage_pts=13.0, point=0.01)
    rz, rc = [], []
    for df in frames:
        sigs = families.family_session_range_breakout(df)
        rz += [t.r_multiple for t in run_backtest(df, sigs, ZERO, bracket_mode=mode).trades]
        rc += [t.r_multiple for t in run_backtest(df, sigs, gold, bracket_mode=mode).trades]
    assert len(rz) > 500
    assert float(np.mean(rz)) < 0.03
    assert float(np.mean(rc)) < 0.0


def test_unknown_bracket_mode_is_refused() -> None:
    df = _frame([FLAT] * 5)
    with pytest.raises(ValueError):
        run_backtest(df, [], ZERO, bracket_mode="both")
