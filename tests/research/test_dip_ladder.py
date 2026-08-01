"""The dip ladder is a CANDIDATE. These tests pin its mechanics so the gauntlet scores the
source's claim rather than my improvement of it."""
from __future__ import annotations

import numpy as np

from libs.research.dip_ladder import (
    CLOSE_TRIGGER,
    INTRADAY_LADDER,
    N_TRANCHES,
    ladder_returns,
    run_ladder,
)


def _flat(n, px=100.0):
    a = np.full(n, px)
    return a.copy(), a.copy(), a.copy(), a.copy()


def test_a_quiet_tape_fires_nothing_and_says_so():
    """A ladder that never fires has no edge -- it has an opinion it never expressed. That must
    read as zero, never as a win."""
    r = run_ladder(*_flat(50))
    assert r.spent_tranches == 0 and r.pnl_fraction == 0.0
    assert "never expressed" in r.why


def test_the_budget_is_the_binding_constraint():
    """THE PROPERTY WORTH EXTRACTING even if the dip thesis fails: no sequence of triggers can
    spend more than the tranche count."""
    n = 400
    o = np.full(n, 100.0)
    lo = np.full(n, 60.0)                      # a 40% intraday hole every single bar
    c = np.linspace(100.0, 40.0, n)
    r = run_ladder(o, np.full(n, 100.0), lo, c, n_tranches=5)
    assert r.spent_tranches == 5
    assert len(r.fills) == 5 and r.unspent == 0


def test_each_intraday_level_fires_at_most_once_ever():
    """An 18% day buys six tranches, not six hundred -- and a second 18% day buys none, because
    the levels are consumed."""
    n = 10
    o = np.full(n, 100.0)
    lo = np.full(n, 100.0 * (1 - 0.19))        # every bar is a 19% hole
    c = np.full(n, 95.0)
    r = run_ladder(o, np.full(n, 100.0), lo, c, close_trigger=9.9, consecutive_red=99)
    kinds = {f.trigger for f in r.fills}
    assert len(kinds) == len(INTRADAY_LADDER)   # each level once
    assert r.spent_tranches == len(INTRADAY_LADDER)


def test_the_consecutive_red_trigger_catches_the_slow_bleed():
    """3%/2%/1% trips no single-day threshold and is exactly the drawdown shape that quietly
    does the damage."""
    c = np.array([100.0, 99.0, 98.0, 97.0, 96.0])
    o = c.copy()
    r = run_ladder(o, c.copy(), c.copy(), c, consecutive_red=3)
    assert any(f.trigger.startswith("red_x") for f in r.fills)


def test_a_single_large_close_fires_the_close_trigger_not_the_red_run():
    c = np.array([100.0, 100.0 * (1 - CLOSE_TRIGGER - 0.01)])
    o = c.copy()
    r = run_ladder(o, c.copy(), c.copy(), c, consecutive_red=2)
    assert [f.trigger for f in r.fills] == ["close"]


def test_average_price_falls_as_the_move_extends():
    """The mechanical claim: a deeper move buys more size at worse prices, so the average fill
    improves monotonically. This is testable independently of whether dips revert."""
    n = 200
    shallow_c = np.linspace(100.0, 95.0, n)
    deep_c = np.linspace(100.0, 60.0, n)
    sh = run_ladder(shallow_c.copy(), shallow_c.copy(), shallow_c.copy(), shallow_c)
    dp = run_ladder(deep_c.copy(), deep_c.copy(), deep_c.copy(), deep_c)
    assert dp.spent_tranches >= sh.spent_tranches
    assert dp.avg_price < sh.avg_price


def test_no_fill_is_informed_by_a_later_bar():
    """CAUSALITY. The natural way to write a dip-buyer is to scan for the lows first; that
    version backtests beautifully and is worthless. Truncating the future must not change any
    fill that already happened."""
    c = np.concatenate([np.linspace(100.0, 80.0, 60), np.linspace(80.0, 130.0, 60)])
    o, h, lo = c.copy(), c.copy(), c.copy()
    full = run_ladder(o, h, lo, c)
    early = run_ladder(o[:60], h[:60], lo[:60], c[:60])
    shared = [f for f in full.fills if f.bar < 60]
    assert [(f.bar, f.trigger) for f in early.fills] == [(f.bar, f.trigger) for f in shared]


def test_windows_do_not_overlap():
    """Overlapping windows share bars, inflating the apparent count of independent observations
    and every statistic built on them -- the same defect that inflates a rolling stickiness."""
    n = 300
    c = np.linspace(100.0, 70.0, n)
    r = ladder_returns(c.copy(), c.copy(), c.copy(), c, window=60)
    assert len(r) == (n - 60) // 60


def test_ragged_input_is_unrunnable_not_silently_wrong():
    r = run_ladder(np.zeros(10), np.zeros(9), np.zeros(10), np.zeros(10))
    assert r.spent_tranches == 0 and "UNRUNNABLE" in r.why


def test_defaults_match_the_source_claim():
    """Kept verbatim so the gauntlet scores THEIR mechanism, not my tuned version of it."""
    assert INTRADAY_LADDER == (0.047, 0.070, 0.095, 0.120, 0.150, 0.180)
    assert CLOSE_TRIGGER == 0.033 and N_TRANCHES == 15
