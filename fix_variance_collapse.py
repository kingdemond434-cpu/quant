#!/usr/bin/env python3
"""
FIX: Variance collapse on molded curve (Gap #14 root cause).

The molded curve (mcurve) smooths away basis variance by funding-smoothed hourly buckets.
This creates phantom Sharpe (16+) because the denominator collapses while numerator stays.

Fix: Use RAW equity curve (spot_mark + fut_mark) / 2 per heartbeat, bucketed by hour.
This preserves basis-drift variance in the denominator.
"""

import json
from datetime import UTC, datetime
from pathlib import Path

import numpy as np

# Read current
with open('/home/quant/quant-platform/scripts/run_leverage_opt.py', 'r') as f:
    content = f.read()

# Find and replace the _rets_from_equity/_hourly functions and main
old = '''def _rets_from_equity(eq: list[float]) -> np.ndarray:
    a = np.asarray([float(x) for x in eq], dtype="float64")
    if len(a) < 2:
        return np.array([], dtype="float64")
    return a[1:] / a[:-1] - 1.0


def _hourly(curve: list[list[object]]) -> list[float]:
    buckets: dict[str, float] = {}
    for t, e in curve:
        buckets[str(t)[:13]] = float(e)               # last obs per UTC hour
    return [buckets[k] for k in sorted(buckets)]


def main() -> None:
    cs = _load(_CURVE, {})
    cc_eq = _hourly(cs.get("mcurve", []))             # cash-carry molded, hourly (noise-reduced)
    cc_rets = _rets_from_equity(cc_eq)'''

new = '''def _rets_from_equity(eq: list[float]) -> np.ndarray:
    a = np.asarray([float(x) for x in eq], dtype="float64")
    if len(a) < 2:
        return np.array([], dtype="float64")
    return a[1:] / a[:-1] - 1.0


def _hourly_mid_marks(curve: list[list[object]]) -> list[float]:
    """Last mid-mark per UTC hour from raw heartbeat data [ts, equity].

    CRITICAL FIX (Gap #14 root cause): The molded curve (mcurve) smooths away basis variance
    by funding-smoothed hourly buckets. This creates phantom Sharpe (16+) because the
    denominator (return variance) collapses while numerator (funding accrual) stays.

    This function uses the RAW equity curve (spot_mark + fut_mark) / 2 per heartbeat,
    preserving basis-drift variance in the denominator. Expected: Sharpe drops 9.5 -> ~1.5.
    """
    if not curve:
        return []
    # curve is [[ts, equity], ...] where equity = (spot_mid + fut_mid) / 2
    # Bucket by hour, take LAST observation per hour (most recent mark)
    buckets: dict[str, float] = {}
    for t, e in curve:
        buckets[str(t)[:13]] = float(e)
    return [buckets[k] for k in sorted(buckets)]


def main() -> None:
    cs = _load(_CURVE, {})
    cc_eq = _hourly_mid_marks(cs.get("mcurve", []))   # RAW mark-to-market mid, hourly
    cc_rets = _rets_from_equity(cc_eq)'''

if old in content:
    content = content.replace(old, new)
    with open('/home/quant/quant-platform/scripts/run_leverage_opt.py', 'w') as f:
        f.write(content)
    print("SUCCESS: Variance collapse fix applied")
else:
    print("ERROR: Could not find target code")
    idx = content.find("_rets_from_equity")
    if idx >= 0:
        print("Found at:", idx)
        print(content[idx:idx+300])