from __future__ import annotations

import numpy as np
import pandas as pd

from mt5desk.families_orthogonal import family_lvc_asia_london


def _m5_day() -> pd.DataFrame:
    idx = pd.date_range("2026-01-05", periods=12 * 60 // 5, freq="5min", tz="UTC")
    base = np.full(len(idx), 100.0)
    frame = pd.DataFrame({"open": base, "high": base + 0.08,
                          "low": base - 0.08, "close": base}, index=idx)
    asia = (idx.hour < 6)
    frame.loc[asia, "high"] = 100.70
    frame.loc[asia, "low"] = 99.30
    # The high is touched in the last Asia bar: recent within Asia, but 13 M5 shifts old at 07:00.
    frame.loc[pd.Timestamp("2026-01-05 05:55", tz="UTC"), "high"] = 101.00
    frame.loc[pd.Timestamp("2026-01-05 00:30", tz="UTC"), "low"] = 99.00
    # Bull break, followed by a sufficiently deep close back inside the Asia range.
    frame.loc[pd.Timestamp("2026-01-05 07:00", tz="UTC")] = [100.5, 102.0, 100.4, 101.8]
    frame.loc[pd.Timestamp("2026-01-05 07:05", tz="UTC")] = [101.8, 101.9, 100.4, 100.5]
    return frame


def test_source_shift_bug_is_dormant_but_session_relative_repair_changes_trade() -> None:
    frame = _m5_day()
    source = family_lvc_asia_london(frame, bias_mode="source_shift", max_range_atr=20.0)
    repaired = family_lvc_asia_london(frame, bias_mode="session_relative", max_range_atr=20.0)

    assert source and source[0].side == 1
    assert repaired and repaired[0].side == -1
    assert source[0].time == pd.Timestamp("2026-01-05 07:00", tz="UTC")
    assert repaired[0].time == pd.Timestamp("2026-01-05 07:05", tz="UTC")
