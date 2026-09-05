"""GAP 132 (L1.68): weekend session stubs resample into fake "D1" rows and reached DSR/CPCV
and regime-conditioning inputs unmarked -- a Sunday row is 1-3 real H1 bars weighted as a day,
and ``resample("D").sum()`` additionally manufactures 0.0-value Saturday rows from empty groups.
The shared rule lives in libs/research/bar_span.py; ``families.d1_session_filtered`` is the ONE
desk-side consumption point, and the source assertions below are the fence that keeps the three
D1 builders wired to it (the same trample class that unwired shadow_forward's h1_source repoint).
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

_DESK = Path(__file__).resolve().parents[1]
if str(_DESK) not in sys.path:
    sys.path.insert(0, str(_DESK))
_ROOT = _DESK.parents[1]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from mt5desk import families  # noqa: E402


def _h1_fri_to_mon() -> pd.DataFrame:
    # Fri 2026-08-21 00:00 UTC .. Mon 2026-08-24 23:00 UTC, hourly, including weekend rows
    idx = pd.date_range("2026-08-21", "2026-08-24 23:00", freq="1h", tz="UTC")
    px = np.linspace(100.0, 101.0, len(idx))
    return pd.DataFrame({"open": px, "high": px + 0.1, "low": px - 0.1, "close": px}, index=idx)


def test_weekend_d1_rows_are_dropped_at_consumption():
    h1 = _h1_fri_to_mon()
    agg = {"open": "first", "high": "max", "low": "min", "close": "last"}
    d1 = h1.resample("D").agg(agg).dropna()
    days = {ts.date().isoformat() for ts in d1.index}
    assert "2026-08-22" in days and "2026-08-23" in days  # the defect: Sat+Sun "D1" rows exist
    kept = families.d1_session_filtered(d1)
    kept_days = {ts.date().isoformat() for ts in kept.index}
    assert kept_days == {"2026-08-21", "2026-08-24"}


def test_a_weekend_trading_instrument_is_passed_through_whole():
    h1 = _h1_fri_to_mon()
    d1 = h1.resample("D").agg({"close": "last"}).dropna()
    assert families.d1_session_filtered(d1, trades_weekends=True) is d1


def test_resample_sum_zero_rows_are_dropped_from_series_too():
    """sum() over an empty calendar day is 0.0, not NaN -- dropna cannot see it."""
    idx = pd.date_range("2026-08-21", "2026-08-24 23:00", freq="1h", tz="UTC")
    s = pd.Series(0.001, index=idx)
    daily = s.resample("D").sum().dropna()
    assert len(daily) == 4
    kept = families.d1_session_filtered(daily)
    assert [ts.date().isoformat() for ts in kept.index] == ["2026-08-21", "2026-08-24"]


def test_the_three_d1_builders_stay_wired():
    """Source-marker fence: the consumption-point calls must not be trampled away."""
    for rel in ("research/run_hunt17.py", "research/regime_discovery.py",
                "research/fragility.py"):
        src = (_DESK / rel).read_text(encoding="utf-8")
        assert "d1_session_filtered(" in src, f"{rel} lost its GAP-132 wiring"


def test_the_rule_is_the_shared_encoding_not_a_third_copy():
    src = (_DESK / "mt5desk" / "families.py").read_text(encoding="utf-8")
    assert "from libs.research.bar_span import is_out_of_calendar" in src
    # a re-encoded weekday rule inside the FILTER is how two organs diverge (L1.61); the
    # dow_effect/monday_gap families' own dayofweek reads are signal logic, out of scope
    body = src.split("def d1_session_filtered", 1)[1].split("\ndef ", 1)[0]
    assert "dayofweek" not in body and "weekday()" not in body
