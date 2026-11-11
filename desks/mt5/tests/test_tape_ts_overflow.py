"""record_tape's merge must survive a garbage time_msc (box read CF1, 2026-11-11).

MT5-HourlyCore's record_tape leg died with `FloatingPointError: overflow encountered in multiply`
inside merge_day's `pd.to_datetime(time_msc, unit="ms")`. One bad value now yields a null ts on
its own row; every row is kept, because the tape is evidence.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
from mt5desk import tape


def _frame(msc):
    n = len(msc)
    return pd.DataFrame({"time_msc": msc, "bid": [1.0] * n, "ask": [1.1] * n,
                         "last": [0.0] * n, "volume": [0] * n, "flags": [6] * n})


def test_merge_day_keeps_rows_and_nulls_bad_ts_under_raise_mode():
    good = 1_762_866_000_123
    prev = _frame([good, good + 1000])
    chunk = _frame([9.9e300, float("nan"), good + 2000])
    old = np.seterr(all="raise")
    try:
        out = tape.merge_day(prev, chunk)
        table = tape.ticks_table(out)
    finally:
        np.seterr(**old)
    assert len(out) == 5
    assert out["ts"].notna().sum() == 3
    assert table.column("ts").null_count == 2
    assert table.num_rows == 5


def test_ts_from_msc_span():
    s = pd.Series([0.0, 946_684_800_000.0, 4_102_444_800_000.0, -5.0])
    got = tape.ts_from_msc(s)
    assert got.isna().tolist() == [False, False, True, True]
