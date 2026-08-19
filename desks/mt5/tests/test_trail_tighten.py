"""Stall-conditioned tightening: the mechanism, and the thing it must not break.

The finding this implements: on a pullback entry after a strong run, a trail
that STAYS wide bleeds (-$16.82/oz at k=4 over 95 events) while the same k
tightened to 1 after three bars without a new extreme makes +$9.80. Paired
against the whole static family on identical events: +$11.63/oz, better 63% of
the time, t = 2.48.

These tests do not re-measure that. They pin the MECHANICS, because a trail is
a ratchet and every bug in one is silent: it either gives money back or it
invents a stop the market never touched.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd
import pytest

_DESK = Path(__file__).resolve().parents[1]
if str(_DESK) not in sys.path:
    sys.path.insert(0, str(_DESK))

from mt5desk.engine import Costs, Signal, run_backtest          # noqa: E402

FREE = Costs(spread_per_lot=0.0, commission_per_lot=0.0, contract_oz=100.0)


def bars(rows):
    idx = pd.date_range("2024-01-01", periods=len(rows), freq="1h")
    return pd.DataFrame({"open": [r[0] for r in rows], "high": [r[1] for r in rows],
                         "low": [r[2] for r in rows], "close": [r[3] for r in rows]},
                        index=idx)


def sig(**kw):
    base = dict(side=1, stop=90.0, target=1e9, ttl_bars=50, tag="t", bank_frac=0.0)
    base.update(kw)
    return Signal(time=pd.Timestamp("2024-01-01"), **base)


#: rally to 130, then four flat bars, then collapse. stop_dist = 10.
RUN_THEN_STALL = [(100, 100, 100, 100), (100, 110, 99, 109), (109, 120, 108, 119),
                  (119, 130, 118, 129), (129, 130, 128, 129), (129, 130, 128, 129),
                  (129, 130, 128, 129), (129, 130, 128, 129), (129, 130, 80, 85),
                  (85, 86, 80, 82)]


def test_a_wide_trail_that_never_tightens_gives_the_move_back():
    t = run_backtest(bars(RUN_THEN_STALL), [sig(runner_trail_k=4.0)], FREE).trades[0]
    # 130 - 4*10 = 90: the collapse takes it out at the original stop.
    assert t.exit == pytest.approx(90.0)
    assert t.r_multiple == pytest.approx(-1.0)


def test_tightening_after_a_stall_banks_the_move():
    t = run_backtest(bars(RUN_THEN_STALL),
                     [sig(runner_trail_k=4.0, trail_tighten_k=1.0,
                          trail_stall_bars=3)], FREE).trades[0]
    # three bars without a new high -> k drops to 1 -> stop 130 - 10 = 120.
    assert t.exit == pytest.approx(120.0)
    assert t.r_multiple == pytest.approx(2.0)


def test_the_stall_counter_resets_on_a_new_extreme():
    """A move that keeps printing highs must keep its breathing room."""
    rows = [(100, 100, 100, 100)] + [(100 + 5 * i, 105 + 5 * i, 99 + 5 * i,
                                      104 + 5 * i) for i in range(8)] + \
           [(140, 141, 100, 105)]
    t = run_backtest(bars(rows), [sig(runner_trail_k=4.0, trail_tighten_k=1.0,
                                      trail_stall_bars=3)], FREE).trades[0]
    # every bar makes a new high, so k stays 4: stop is 140 - 40 = 100.
    assert t.exit == pytest.approx(100.0)


def test_the_trail_never_widens_again_once_tightened():
    """A ratchet that can loosen is not a ratchet.

    After the stall tightens the stop to 120, a single new high must not let the
    wide k pull the stop back DOWN to 130-40=90 -- that would hand back money
    already protected.
    """
    rows = RUN_THEN_STALL[:8] + [(129, 131, 128, 130), (130, 131, 80, 82)]
    t = run_backtest(bars(rows), [sig(runner_trail_k=4.0, trail_tighten_k=1.0,
                                      trail_stall_bars=3)], FREE).trades[0]
    assert t.exit == pytest.approx(120.0), "the stop was allowed to widen"


def test_it_is_off_by_default_and_changes_nothing():
    """Backward compatibility is load-bearing: every stored sleeve predates this."""
    a = run_backtest(bars(RUN_THEN_STALL), [sig(runner_trail_k=4.0)], FREE).trades[0]
    b = run_backtest(bars(RUN_THEN_STALL),
                     [sig(runner_trail_k=4.0, trail_tighten_k=0.0,
                          trail_stall_bars=3)], FREE).trades[0]
    assert a.r_multiple == pytest.approx(b.r_multiple)


def test_a_pure_runner_needs_no_bank_leg():
    """bank_frac == 0 used to mean NO TRAIL, so this policy was unwritable."""
    t = run_backtest(bars(RUN_THEN_STALL),
                     [sig(bank_frac=0.0, runner_trail_k=4.0,
                          trail_tighten_k=1.0, trail_stall_bars=3)],
                     FREE).trades[0]
    assert t.exit == pytest.approx(120.0)


def test_the_short_side_mirrors_it():
    rows = [(100, 100, 100, 100), (100, 101, 90, 91), (91, 92, 80, 81),
            (81, 82, 70, 71), (71, 72, 70, 71), (71, 72, 70, 71),
            (71, 72, 70, 71), (71, 72, 70, 71), (71, 120, 70, 118)]
    t = run_backtest(bars(rows), [sig(side=-1, stop=110.0, target=-1e9,
                                      runner_trail_k=4.0, trail_tighten_k=1.0,
                                      trail_stall_bars=3)], FREE).trades[0]
    assert t.exit == pytest.approx(80.0)      # 70 + 1*10
    assert t.r_multiple == pytest.approx(2.0)
