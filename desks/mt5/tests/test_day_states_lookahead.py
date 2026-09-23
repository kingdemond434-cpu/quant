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
        if 13 <= ts.hour <= 22:
            hi.iloc[i] += 1.0           # every NY session has SOME range: a literal zero
            lo.iloc[i] -= 1.0           # median reads as "no observation" and skips the label
            if ts.dayofyear % 2 == 0:
                hi.iloc[i] += 12.0      # a violently wide NY on even days only
                lo.iloc[i] -= 12.0
    return pd.DataFrame({"open": base, "high": hi, "low": lo, "close": base,
                         "tick_volume": 1.0}, index=idx)


def test_a_days_label_comes_from_the_previous_day():
    """Canon computes labels directly from D-1/D-2 aggregates (not the old branch's two-step
    re-keying), so the pin is the CAUSAL property itself: on a fixture where NY is violently
    wide on even days only, the wide-day states must surface on the FOLLOWING days."""
    h1 = _frame()
    prior = day_states(h1)
    tradeable = {d: s for d, s in prior.items() if s != "NONE"}
    assert tradeable, "no labelled days"
    for d, s in tradeable.items():
        prev_even = pd.Timestamp(d - pd.Timedelta(days=1)).dayofyear % 2 == 0
        if s == "TREND_DAY":
            assert prev_even, f"{d} TREND_DAY without a wide prior session -- same-day join"
        if s == "RANGE_DAY":
            assert not prev_even, f"{d} RANGE_DAY after a wide prior session -- same-day join"


def test_unobservable_days_carry_no_state_rather_than_a_default():
    """No completed prior session means NO STATE -- the day is OMITTED, and consumers
    (gateway.state_allows) treat absence as refusal. Defaulting would make an unobservable
    day tradeable."""
    h1 = _frame()
    prior = day_states(h1)
    first_bar_day = min(ts.date() for ts in h1.index)
    assert first_bar_day not in prior
    assert "NONE" not in set(prior.values())


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
    """Truncation invariance on real bars: withholding a day's own future must not change its
    label. Implementation-agnostic, so it survives refactors of the join arithmetic."""
    parquet = _DESK / "data" / "universe" / f"{sym}_H1.parquet"
    if not parquet.exists():
        pytest.skip(f"{sym} bars not present")
    from mt5desk import families
    h1 = families._h1(pd.read_parquet(parquet))
    full = day_states(h1)
    days = sorted(full)
    for d in days[40:200:20]:
        cutoff = pd.Timestamp(d, tz="UTC") + pd.Timedelta(hours=8)
        truncated = day_states(h1[h1.index < cutoff])
        assert d in truncated and truncated[d] == full[d], (
            f"{sym} {d}: label changed when its own future was withheld")
