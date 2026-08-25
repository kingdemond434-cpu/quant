"""Converts external discoveries into testable hypotheses.

v3: Handles all 25 miner types — sentiment, calendar, positioning, macro, academic.
Reads latest_discoveries.json, maps to families, outputs test grid.
"""

import json
from datetime import datetime, timezone
from pathlib import Path

BASE = Path(__file__).resolve().parent.parent
DATA = BASE / "data" / "intelligence"
OUT = BASE / "data" / "hypotheses"

SYMBOL_MAP = {
    "XAUUSD": "XAUUSD", "EURUSD": "EURUSD", "GBPUSD": "GBPUSD",
    "USDJPY": "USDJPY", "AUDUSD": "AUDUSD", "USDCAD": "USDCAD",
    "USDCHF": "USDCHF", "NZDUSD": "NZDUSD", "EURJPY": "EURJPY",
    "GBPJPY": "GBPJPY", "AUDJPY": "AUDJPY", "CADJPY": "CADJPY",
    "NZDJPY": "NZDJPY", "CHFJPY": "CHFJPY", "EURAUD": "EURAUD",
    "GBPAUD": "GBPAUD", "AUDNZD": "AUDNZD", "NZDCAD": "NZDCAD",
    "AUDCAD": "AUDCAD", "BTCUSD": "BTCUSD", "ETHUSD": "ETHUSD",
    "US500": "US500", "NAS100": "NAS100", "JPYUSD": "USDJPY",
}

PATTERN_TO_FAMILY = {
    "breakout": "session_range_breakout", "session range": "session_range_breakout",
    "asia range": "session_range_breakout", "london open": "session_range_breakout",
    "order block": "order_block_reversion", "fair value gap": "order_block_reversion",
    "liquidity": "liquidity_grab", "smart money": "order_block_reversion",
    "mean reversion": "mean_reversion_basic", "momentum": "momentum_basic",
    "trend following": "trend_following_basic", "trend": "trend_following_basic",
    "RSI": "rsi_extreme_fade", "MACD": "macd_crossover",
    "EMA": "ema_crossover", "SMA": "sma_crossover",
    "fibonacci": "fib_retracement", "scalping": "scalping_basic",
    "swing": "swing_basic", "grid": "grid_trading",
    "volatility": "volatility_breakout", "carry trade": "carry_trade",
    "pairs trading": "pairs_trading", "statistical arbitrage": "pairs_trading",
    "cointegration": "pairs_trading",
    "price stability": "central_bank_reaction", "hawkish": "central_bank_reaction",
    "dovish": "central_bank_reaction", "rate hike": "central_bank_reaction",
    "rate cut": "central_bank_reaction",
}

# Source → default family mapping (for discoveries without explicit patterns)
SOURCE_FAMILY_MAP = {
    "cot": "momentum_basic",           # Positioning = momentum signal
    "aaii": "session_range_breakout",  # Sentiment extremes = breakout
    "fear_greed": "session_range_breakout",
    "investing": "session_range_breakout",
    "google_trends": "session_range_breakout",
    "correlations": "session_range_breakout",
    "seasonality": "session_range_breakout",
    "forexfactory": "session_range_breakout",
    "earnings": "session_range_breakout",
    "shipping": "momentum_basic",
    "mql5_signals": "session_range_breakout",
}

# Sources to skip (no tradeable signal)
SKIP_SOURCES = {"mql5_forum", "academic", "sec_edgar", "earnings"}


def _normalize_symbol(sym: str) -> str | None:
    return SYMBOL_MAP.get(sym.upper())


def _map_family(patterns: list[str], source: str = "") -> str:
    for p in patterns:
        if p in PATTERN_TO_FAMILY:
            return PATTERN_TO_FAMILY[p]
    return SOURCE_FAMILY_MAP.get(source, "unknown")


def convert_discoveries() -> list[dict]:
    disc_file = DATA / "latest_discoveries.json"
    if not disc_file.exists():
        return []

    raw = json.loads(disc_file.read_text(encoding="utf-8"))
    hypotheses = []
    seen = set()

    for source_name, source_data in raw.items():
        if source_name == "summary":
            continue
        if not isinstance(source_data, dict):
            continue
        if source_name in SKIP_SOURCES:
            continue

        discoveries = source_data.get("discoveries", [])
        for disc in discoveries:
            patterns = disc.get("patterns", disc.get("policy_signals", []))
            symbols = disc.get("symbols", [])

            # Skip if no symbols
            if not symbols:
                continue

            # Map to family
            family = _map_family(patterns, source_name)
            if family == "unknown":
                continue

            # Only use testable families
            testable = {
                "session_range_breakout", "momentum_basic", "momentum_volgate",
                "level_breakout", "failed_breakout", "dow_effect",
                "monday_gap", "london_close_momentum",
            }
            if family not in testable:
                family = "session_range_breakout"  # Default to most common

            for sym in symbols:
                norm_sym = _normalize_symbol(sym)
                if not norm_sym:
                    continue

                key = f"{norm_sym}_{family}_{source_name}"
                if key in seen:
                    continue
                seen.add(key)

                h = {
                    "id": f"ext_{source_name}_{norm_sym}_{family}",
                    "source": f"external_{source_name}",
                    "symbol": norm_sym,
                    "family": family,
                    "description": disc.get("description", disc.get("title", ""))[:200],
                    "url": disc.get("url", ""),
                    "confidence": disc.get("confidence", 0.3),
                    "patterns": patterns,
                    "created": datetime.now(timezone.utc).isoformat(),
                }
                hypotheses.append(h)

    return hypotheses


def save_hypotheses() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    hypotheses = convert_discoveries()

    out_file = OUT / f"external_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M')}.json"
    out_file.write_text(json.dumps(hypotheses, indent=2), encoding="utf-8")
    print(f"Generated {len(hypotheses)} hypotheses from external discoveries")

    latest = OUT / "latest_external.json"
    latest.write_text(json.dumps(hypotheses, indent=2), encoding="utf-8")


if __name__ == "__main__":
    save_hypotheses()
