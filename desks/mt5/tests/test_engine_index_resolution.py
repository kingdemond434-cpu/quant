"""The backtest engine must fill signals whatever RESOLUTION the bar index carries.

MEASURED 2026-08-27, and it had voided every backtest on the desk. `run_backtest` mapped signal
times to bar positions with `np.searchsorted(idx.asi8, [Timestamp.value ...])`. `asi8` returns
the index's OWN unit -- nanoseconds for datetime64[ns] but MILLISECONDS for datetime64[ms] --
while `Timestamp.value` is always nanoseconds. A producer rewrote every universe parquet at ms
resolution, so the comparison was 1.52e12 against 1.52e18: `searchsorted` returned len(idx) for
EVERY signal and the loop discarded all of them as out-of-range.

The damage was invisible because a cell with no trades has no daily series, and a cell with no
daily series is dropped by the gauntlet as "fewer than 60 observations". 118 of 122 cells read as
untestable, all 22 standing certificates rebuilt empty, and the desk looked like it was hunting
ground too thin to judge. Nothing anywhere said "the engine cannot fill".
"""
from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd
import pytest

_DESK = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_DESK))

from mt5desk import families  # noqa: E402
from mt5desk.engine import Costs, Signal, run_backtest  # noqa: E402


def _bars(unit: str, tz: str | None) -> pd.DataFrame:
    idx = pd.date_range("2026-01-05 00:00", periods=200, freq="1h", tz=tz).as_unit(unit)
    return pd.DataFrame({"open": 100.0, "high": 101.0, "low": 99.0, "close": 100.5}, index=idx)


@pytest.mark.parametrize("unit", ["ns", "us", "ms", "s"])
@pytest.mark.parametrize("tz", ["UTC", None])
def test_signals_fill_at_every_index_resolution(unit: str, tz: str | None) -> None:
    """One trade per signal regardless of index unit -- the fill must not depend on resolution."""
    df = _bars(unit, tz)
    sig = Signal(time=df.index[10], side=1, stop=99.0, target=103.0, ttl_bars=12,
                 trigger=100.5, wait_bars=8, tag="unit_probe")
    res = run_backtest(df, [sig], Costs(spread_per_lot=0.1, commission_per_lot=0.0,
                                        contract_oz=1.0))
    assert res.trades, f"no fill at {unit=} {tz=} -- searchsorted unit mismatch is back"


def test_h1_normalizes_resolution_and_timezone() -> None:
    """`_h1` is the one door bars enter through; it must hand on tz-aware UTC nanoseconds."""
    out = families._h1(_bars("ms", None))
    assert str(out.index.tz) == "UTC"
    assert out.index.dtype == "datetime64[ns, UTC]", (
        f"bars left _h1 as {out.index.dtype}; a non-ns index voids every engine fill")


def test_a_real_family_on_ms_bars_produces_trades() -> None:
    """End to end on the shape that actually broke: ms-resolution bars from a parquet."""
    idx = pd.date_range("2026-01-01", periods=24 * 90, freq="1h", tz="UTC").as_unit("ms")
    rng = [100 + (i % 17) - 8 for i in range(len(idx))]
    df = pd.DataFrame({"open": rng, "high": [v + 2 for v in rng],
                       "low": [v - 2 for v in rng], "close": [v + 0.5 for v in rng]}, index=idx)
    sigs = families.family_session_range_breakout(families._h1(df), range_start=7, wait_bars=12,
                                                  rr=2.0, ttl_bars=12)
    assert sigs, "the family produced no signals on this fixture"
    res = run_backtest(families._h1(df), sigs,
                       Costs(spread_per_lot=0.05, commission_per_lot=0.0, contract_oz=1.0))
    assert res.trades, "ms-resolution bars produced signals but ZERO trades -- the silent void"
