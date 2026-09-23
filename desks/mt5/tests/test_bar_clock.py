"""The bar loader must hand every caller a timezone, because 154 call sites assume one.

On 2026-08-26 a producer rewrote all 197 H1 parquets tz-NAIVE (`pd.to_datetime(..., unit="s")`
with no `utc=True`) over files that had carried `datetime64[ms, UTC]`. Nothing crashed loudly:
the desk's own look-ahead guard simply began raising "Cannot compare tz-naive and tz-aware
datetime-like objects" instead of checking anything, in a suite nothing has ever run.

An undeclared clock is an assumption wearing a timestamp (L1.46). These pin the declaration.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd

_DESK = Path(__file__).resolve().parents[1]
if str(_DESK) not in sys.path:
    sys.path.insert(0, str(_DESK))

from mt5desk.families import _h1  # noqa: E402


def _bars(tz: str | None) -> pd.DataFrame:
    idx = pd.date_range("2024-01-01", periods=48, freq="h", tz=tz)
    return pd.DataFrame({"open": 1.0, "high": 1.5, "low": 0.5, "close": 1.0,
                         "spread": 2.0}, index=idx)


def test_naive_bars_come_back_tz_aware() -> None:
    out = _h1(_bars(None))
    assert out.index.tz is not None, "the exact state that turned a look-ahead guard into an error"
    assert str(out.index.tz) == "UTC"


def test_aware_bars_are_unchanged_in_wall_clock() -> None:
    out = _h1(_bars("UTC"))
    assert str(out.index.tz) == "UTC"
    assert out.index[0] == pd.Timestamp("2024-01-01 00:00", tz="UTC")


def test_localize_moves_no_bar() -> None:
    # LABEL, never convert: these are broker-clock stamps and the desk converts them explicitly
    # through h1_source.broker_utc_offset_hours(). A silent shift here would move every session
    # window on a desk whose live family is entirely session-scoped.
    naive, aware = _h1(_bars(None)), _h1(_bars("UTC"))
    assert list(naive.index.tz_localize(None)) == list(aware.index.tz_localize(None))
    assert naive["close"].tolist() == aware["close"].tolist()


def test_the_real_parquets_on_disk_load_with_a_clock() -> None:
    universe = _DESK / "data" / "universe"
    checked = 0
    for path in sorted(universe.glob("*_H1.parquet"))[:5]:
        out = _h1(pd.read_parquet(path))
        assert out.index.tz is not None, f"{path.name} loads without a timezone"
        checked += 1
    assert checked, "no parquets on this box -- absence is not a pass (L1.28a)"
