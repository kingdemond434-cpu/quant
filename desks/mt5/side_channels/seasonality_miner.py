"""Seasonality patterns miner.

Calculates historical seasonality patterns for each symbol.
Some patterns are well-known (sell in May, January effect).
Others may be unique to each pair.
"""

from datetime import UTC, datetime
from pathlib import Path

import numpy as np
import pandas as pd

BASE = Path(__file__).resolve().parent.parent
OUT = BASE / "data" / "intelligence" / "seasonality"
OUT.mkdir(parents=True, exist_ok=True)

# Known seasonality patterns
KNOWN_PATTERNS = {
    "sell_in_may": {"month": [5, 6, 7, 8], "direction": "down", "symbols": ["US500", "NAS100"]},
    "january_effect": {"month": [1], "direction": "up", "symbols": ["US500", "NAS100"]},
    "quarter_end": {"days": [25, 26, 27, 28, 29, 30, 31], "direction": "up", "symbols": ["US500"]},
    "nfp_week": {"day_of_month": [1, 2, 3, 4, 5, 6, 7, 8], "direction": "volatile", "symbols": ["EURUSD", "GBPUSD", "USDJPY"]},
}


#: |t| across years at or above this emits a row. Years are few (bars start 2018), so this is a
#: screen for the judge, not a significance claim.
T_MIN = 2.0
MIN_YEARS = 5


def month_effect(close: "pd.Series | None", month: int) -> dict | None:
    """{mean, t, n, hit} of the log return of calendar `month` across years, or None."""
    if close is None or len(close) < 400:
        return None
    m = np.log(close.resample("ME").last().dropna()).diff().dropna()
    x = m[m.index.month == month].to_numpy(dtype="float64")
    x = x[np.isfinite(x)]
    if len(x) < MIN_YEARS:
        return None
    sd = float(x.std(ddof=1))
    if not np.isfinite(sd) or sd <= 0:
        return None
    mean = float(x.mean())
    return {"mean": mean, "t": mean / (sd / np.sqrt(len(x))), "n": len(x),
            "hit": float((x > 0).mean())}


def mine_seasonality() -> list[dict]:
    """Calculate current seasonality signals."""
    discoveries = []
    now = datetime.now(UTC)
    month = now.month
    day = now.day

    # Check known patterns
    for pattern_name, pattern in KNOWN_PATTERNS.items():
        if "month" in pattern and month in pattern["month"]:
            discoveries.append({
                "source": "seasonality",
                "type": "known_pattern",
                "pattern": pattern_name,
                "month": month,
                "direction": pattern["direction"],
                "symbols": pattern["symbols"],
                "confidence": 0.4,
                "description": f"Seasonal pattern '{pattern_name}' active (month {month})",
            })

    # Measured seasonality: each year's return in this calendar month, per hypothesis-lane symbol,
    # and its t-statistic across years. A row is a HYPOTHESIS for the judge, not a verdict: the
    # judge charges the trial and applies its own multiple-testing bar.
    try:
        from side_channels._bars import daily_close, hypothesis_symbols
    except ModuleNotFoundError:
        from _bars import daily_close, hypothesis_symbols
    for target, label in ((month, "this_month"), (month % 12 + 1, "next_month")):
        for sym in hypothesis_symbols():
            row = month_effect(daily_close(sym), target)
            if row is None or abs(row["t"]) < T_MIN:
                continue
            direction = "bullish" if row["mean"] > 0 else "bearish"
            discoveries.append({
                "source": "seasonality",
                "type": "historical_pattern",
                "symbol": sym,
                "month": target,
                "window": label,
                "years": row["n"],
                "avg_return": round(row["mean"] * 100, 4),
                "hit_rate": round(row["hit"], 3),
                "t_stat": round(row["t"], 2),
                "direction": direction,
                "symbols": [sym],
                "confidence": round(min(0.6, abs(row["t"]) / 6), 3),
                "description": (f"{sym} {direction} in calendar month {target}: mean "
                                f"{row['mean']*100:.2f}% over {row['n']} years, t={row['t']:.2f}"),
            })

    return discoveries


def run_and_save() -> list[dict]:
    discoveries = mine_seasonality()
    out_file = OUT / f"discoveries_{datetime.now(UTC).strftime('%Y%m%d_%H%M')}.json"
    try:
        from side_channels.discovery_io import write_discoveries
    except ModuleNotFoundError:
        from discovery_io import write_discoveries
    discoveries = write_discoveries(out_file, discoveries)
    print(f"seasonality: {len(discoveries)} discoveries saved")
    return discoveries


if __name__ == "__main__":
    run_and_save()
