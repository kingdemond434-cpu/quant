"""Cross-market correlation miner.

Calculates real-time correlations between assets and detects
correlation breakdowns (which often signal regime changes).
When gold and USD suddenly decouple = something is happening.
"""

import json
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd
import requests

BASE = Path(__file__).resolve().parent.parent
OUT = BASE / "data" / "intelligence" / "correlations"
OUT.mkdir(parents=True, exist_ok=True)

# Pairs to monitor
CORR_PAIRS = [
    ("XAUUSD", "USDJPY", "gold_jpy"),
    ("XAUUSD", "DXY", "gold_dollar"),
    ("EURUSD", "USDJPY", "eur_jpy"),
    ("GBPUSD", "USDJPY", "gbp_jpy"),
    ("US500", "USDJPY", "spy_jpy"),
    ("US500", "XAUUSD", "spy_gold"),
    ("USOIL", "USDCAD", "oil_cad"),
    ("USOIL", "XAUUSD", "oil_gold"),
]


def load_data(sym: str, lookback: int = 100) -> pd.Series | None:
    """Load H1 data and compute returns."""
    f = BASE / "data" / "universe" / f"{sym}_H1.parquet"
    if not f.exists():
        return None
    df = pd.read_parquet(f)
    if len(df) < lookback:
        return None
    return df["close"].pct_change().dropna().tail(lookback)


def mine_correlations() -> list[dict]:
    """Calculate rolling correlations and detect breakdowns."""
    discoveries = []

    for sym1, sym2, label in CORR_PAIRS:
        try:
            ret1 = load_data(sym1)
            ret2 = load_data(sym2)
            if ret1 is None or ret2 is None:
                continue

            # Align indices
            common = ret1.index.intersection(ret2.index)
            if len(common) < 50:
                continue

            r1 = ret1.loc[common]
            r2 = ret2.loc[common]

            # Rolling correlation (20-period)
            long_corr = r1.rolling(50).corr(r2).dropna()
            short_corr = r1.rolling(20).corr(r2).dropna()

            if len(long_corr) < 5 or len(short_corr) < 5:
                continue

            current_long = long_corr.iloc[-1]
            current_short = short_corr.iloc[-1]
            avg_long = long_corr.mean()

            # Detect correlation breakdown
            corr_change = abs(current_short - current_long)
            if corr_change > 0.4:
                discoveries.append({
                    "source": "correlation",
                    "type": "correlation_breakdown",
                    "pair": label,
                    "symbol1": sym1,
                    "symbol2": sym2,
                    "long_correlation": round(float(current_long), 3),
                    "short_correlation": round(float(current_short), 3),
                    "change": round(float(corr_change), 3),
                    "symbols": [sym1, sym2],
                    "confidence": min(0.7, corr_change),
                    "description": f"{label} correlation breakdown: {current_long:.2f} -> {current_short:.2f}",
                })
            # Also detect extreme correlations
            elif abs(current_long) > 0.7:
                discoveries.append({
                    "source": "correlation",
                    "type": "extreme_correlation",
                    "pair": label,
                    "symbol1": sym1,
                    "symbol2": sym2,
                    "correlation": round(float(current_long), 3),
                    "symbols": [sym1, sym2],
                    "confidence": min(0.5, abs(current_long)),
                    "description": f"{label} extreme correlation: {current_long:.2f}",
                })

        except Exception:
            continue

    return discoveries


def run_and_save() -> list[dict]:
    discoveries = mine_correlations()
    out_file = OUT / f"discoveries_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M')}.json"
    out_file.write_text(json.dumps(discoveries, indent=2, default=str), encoding="utf-8")
    print(f"correlations: {len(discoveries)} discoveries saved")
    return discoveries


if __name__ == "__main__":
    run_and_save()
