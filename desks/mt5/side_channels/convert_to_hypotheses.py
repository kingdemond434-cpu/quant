"""Converts external discoveries into testable hypotheses.

Reads latest_discoveries.json, filters for actionable signals,
and outputs hypotheses in the format expected by the 10-gate pipeline.

v2: Better coverage — catches central bank signals, MQL5 signal providers,
and maps more pattern types to families.
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
    "US500": "US500", "NAS100": "NAS100",
    "JPYUSD": "USDJPY",
}

PATTERN_TO_FAMILY = {
    "breakout": "session_range_breakout",
    "session range": "session_range_breakout",
    "asia range": "session_range_breakout",
    "london open": "session_range_breakout",
    "order block": "order_block_reversion",
    "fair value gap": "order_block_reversion",
    "liquidity": "liquidity_grab",
    "smart money": "order_block_reversion",
    "mean reversion": "mean_reversion_basic",
    "momentum": "momentum_basic",
    "trend following": "trend_following_basic",
    "trend": "trend_following_basic",
    "RSI": "rsi_extreme_fade",
    "MACD": "macd_crossover",
    "EMA": "ema_crossover",
    "SMA": "sma_crossover",
    "fibonacci": "fib_retracement",
    "scalping": "scalping_basic",
    "swing": "swing_basic",
    "grid": "grid_trading",
    "volatility": "volatility_breakout",
    "carry trade": "carry_trade",
    "pairs trading": "pairs_trading",
    "statistical arbitrage": "pairs_trading",
    "cointegration": "pairs_trading",
    "price stability": "central_bank_reaction",
    "hawkish": "central_bank_reaction",
    "dovish": "central_bank_reaction",
    "rate hike": "central_bank_reaction",
    "rate cut": "central_bank_reaction",
}

# Central bank → currency pairs mapping
BANK_CURRENCY_PAIRS = {
    "Fed": ["EURUSD", "GBPUSD", "XAUUSD"],
    "ECB": ["EURUSD", "EURJPY", "EURAUD"],
    "BoE": ["GBPUSD", "GBPJPY", "GBPAUD"],
    "BoJ": ["USDJPY", "EURJPY", "GBPJPY", "AUDJPY", "CADJPY", "NZDJPY", "CHFJPY", "XAUUSD"],
    "RBA": ["AUDUSD", "AUDJPY", "AUDNZD", "AUDCAD", "EURAUD", "GBPAUD"],
    "RBNZ": ["NZDUSD", "NZDJPY", "NZDCAD", "AUDNZD"],
    "BoC": ["USDCAD", "NZDCAD", "AUDCAD"],
    "SNB": ["USDCHF", "CHFJPY"],
}


def _normalize_symbol(sym: str) -> str | None:
    return SYMBOL_MAP.get(sym.upper())


def _map_family(patterns: list[str]) -> str:
    for p in patterns:
        if p in PATTERN_TO_FAMILY:
            return PATTERN_TO_FAMILY[p]
    return "unknown"


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

        discoveries = source_data.get("discoveries", [])
        for disc in discoveries:
            patterns = disc.get("patterns", disc.get("policy_signals", []))

            # Get symbols
            symbols = disc.get("symbols", [])

            # Special: central bank → derive pairs from bank name
            bank = disc.get("bank")
            if bank and bank in BANK_CURRENCY_PAIRS:
                symbols = list(set(symbols + BANK_CURRENCY_PAIRS[bank]))

            if not symbols:
                continue

            family = _map_family(patterns)
            if family == "unknown":
                # Assign a default family based on source
                if source_name in ("mql5_signals",):
                    family = "signal_provider_follow"
                elif source_name in ("mql5_forum",):
                    continue  # Skip forum noise
                else:
                    continue

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
