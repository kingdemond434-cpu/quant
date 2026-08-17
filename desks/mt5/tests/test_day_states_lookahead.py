"""`day_states` must label a day from the PRIOR day's NY session, never its own.

The original join gated an 07:00 UTC asia signal with data through 22:00 UTC THE SAME DAY. It
produced the desk's headline finding (gold asia TREND_DAY +0.908R, t=11.34) and hunt12's AUDCAD
survivor cluster; corrected, the former falls to +0.191R and all five of the latter fail their
own gate. Eleven modules import this function, so the property is pinned here rather than trusted.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd
import pytest

_DESK = Path(__file__).resolve().parents[1]
for p in (str(_DESK), str(_DESK / "research")):
    if p not in sys.path:
        sys.path.insert(0, p)

from research.run_hunt12 import _day_states_same_day, day_states  # noqa: E402


def _frame(days: int = 40) -> pd.DataFrame:
    """Hourly bars whose NY session is deliberately distinctive on alternating days."""
    idx = pd.date_range("2024-01-01", periods=days * 24, freq="h", tz="UTC")
    base = pd.Series(100.0, index=idx)
    hi, lo = base.copy(), base.copy()
    for i, ts in enumerate(idx):
        if 13 <= ts.hour <= 22 and ts.dayofyear % 2 == 0:
            hi.iloc[i] += 12.0          # a violently wide NY on even days only
            lo.iloc[i] -= 12.0
    return pd.DataFrame({"open": base, "high": hi, "low": lo, "close": base,
                         "tick_volume": 1.0}, index=idx)


def test_a_days_label_comes_from_the_previous_day():
    h1 = _frame()
    same, prior = _day_states_same_day(h1), day_states(h1)
    days = sorted(prior)
    assert days, "no labelled days"
    for d in days:
        yesterday = sorted(x for x in same if x < d)[-1]
        assert prior[d] == same[yesterday], (
            f"{d} was labelled from its own session, not {yesterday}'s")


def test_the_first_day_is_dropped_rather_than_defaulted():
    """No prior session means NO STATE. Defaulting would make an unobservable day tradeable."""
    h1 = _frame()
    same, prior = _day_states_same_day(h1), day_states(h1)
    assert min(same) not in prior
    assert len(prior) == len(same) - 1


def test_the_label_is_not_computed_from_future_bars():
    """THE REGRESSION. Truncating the feed after a day's asia session must not change that
    day's label -- if it does, the label is reading bars the trade could not have seen."""
    h1 = _frame()
    full = day_states(h1)
    target = sorted(full)[10]
    # everything strictly before that day's 08:00 UTC (asia signals fire ~07:00)
    cutoff = pd.Timestamp(target, tz="UTC") + pd.Timedelta(hours=8)
    truncated = day_states(h1[h1.index < cutoff])
    assert target in truncated, "the day vanished when its own future was removed"
    assert truncated[target] == full[target], (
        "the label changed once future bars were withheld -- it is reading them")


def test_same_day_variant_is_private_and_still_available():
    """Kept only to reproduce the historical artifacts; must not be the default."""
    import research.run_hunt12 as m
    assert hasattr(m, "_day_states_same_day")
    assert m.day_states is not m._day_states_same_day


def test_the_two_joins_actually_disagree():
    """Guards the test itself: a fixture where both agree would prove nothing."""
    h1 = _frame()
    same, prior = _day_states_same_day(h1), day_states(h1)
    shared = set(same) & set(prior)
    assert any(same[d] != prior[d] for d in shared), "fixture cannot distinguish the two joins"


@pytest.mark.parametrize("sym", ["XAUUSD", "AUDCAD"])
def test_on_real_data_every_label_is_strictly_backward_looking(sym):
    parquet = _DESK / "data" / "universe" / f"{sym}_H1.parquet"
    if not parquet.exists():
        pytest.skip(f"{sym} bars not present")
    from mt5desk import families
    h1 = families._h1(pd.read_parquet(parquet))
    same, prior = _day_states_same_day(h1), day_states(h1)
    days = sorted(prior)
    for d in days[:200]:
        yesterday = sorted(x for x in same if x < d)[-1]
        assert prior[d] == same[yesterday]
