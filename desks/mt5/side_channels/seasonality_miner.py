"""Seasonality patterns miner.

Calculates historical seasonality patterns for each symbol.
Some patterns are well-known (sell in May, January effect).
Others may be unique to each pair.
"""

import json
from datetime import datetime, timezone
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


def mine_seasonality() -> list[dict]:
    """Calculate current seasonality signals."""
    discoveries = []
    now = datetime.now(timezone.utc)
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

    # Calculate actual seasonality from data
    universe_dir = BASE / "data" / "universe"
    for sym_file in universe_dir.glob("*_H1.parquet"):
        sym = sym_file.stem.replace("_H1", "")
        try:
            df = pd.read_parquet(sym_file)
            if len(df) < 1000:
                continue

            # Group by month
            df["month"] = df.index.month
            monthly_returns = df.groupby("month")["close"].pct_change().dropna()
            monthly_mean = monthly_returns.groupby(df["month"].iloc[1:]).mean()

            if month in monthly_mean.index:
                current_month_return = monthly_mean[month]
                avg_return = monthly_mean.mean()
                if abs(current_month_return) > abs(avg_return) * 1.5:
                    direction = "bullish" if current_month_return > 0 else "bearish"
                    discoveries.append({
                        "source": "seasonality",
                        "type": "historical_pattern",
                        "symbol": sym,
                        "month": month,
                        "avg_return": round(float(current_month_return) * 100, 4),
                        "overall_avg": round(float(avg_return) * 100, 4),
                        "direction": direction,
                        "symbols": [sym],
                        "confidence": min(0.6, abs(current_month_return) / abs(avg_return) * 0.3),
                        "description": f"{sym} historically {direction} in month {month} (avg {current_month_return*100:.3f}%)",
                    })
        except Exception:
            continue

    return discoveries


def run_and_save() -> list[dict]:
    discoveries = mine_seasonality()
    out_file = OUT / f"discoveries_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M')}.json"
    out_file.write_text(json.dumps(discoveries, indent=2, default=str), encoding="utf-8")
    print(f"seasonality: {len(discoveries)} discoveries saved")
    return discoveries


if __name__ == "__main__":
    run_and_save()
