"""Bridges external discoveries into the existing backtest pipeline.

Reads latest_external.json hypotheses, maps them to existing families
in families.py, and adds any new families that don't exist yet.
Outputs a test grid (symbol x family x params) for full_hunt.py.

This is the missing link between DISCOVER and BACKTEST phases.
"""

from __future__ import annotations
import json
import itertools
from pathlib import Path

BASE = Path(__file__).resolve().parent.parent
DATA = BASE / "data"
INTEL = DATA / "intelligence"
HYPO = DATA / "hypotheses"

# Existing families from families.py
EXISTING_FAMILIES = {
    "session_range_breakout": "family_session_range_breakout",
    "momentum_basic": "family_asia_momentum",
    "momentum_volgate": "family_momentum_volgate",
    "level_breakout": "family_level_breakout",
    "failed_breakout": "family_failed_breakout",
    "dow_effect": "family_dow_effect",
    "monday_gap": "family_monday_gap",
    "london_close_momentum": "family_london_close_momentum",
}

# Mapping: external family name -> existing family name
FAMILY_MAP = {
    "session_range_breakout": "session_range_breakout",
    "momentum_basic": "asia_momentum",
    "ema_crossover": "asia_momentum",        # EMA crossover is momentum variant
    "sma_crossover": "asia_momentum",        # SMA crossover is momentum variant
    "order_block_reversion": "level_breakout",  # OB = support/resistance levels
    "liquidity_grab": "level_breakout",      # Liquidity grab = failed breakout
    "rsi_extreme_fade": "failed_breakout",   # RSI fade = failed breakout variant
    "macd_crossover": "momentum_volgate",    # MACD = momentum with vol gate
    "mean_reversion_basic": "session_range_breakout",  # Mean reversion ≈ fade
    "trend_following_basic": "momentum_volgate",  # Trend following = momentum
    "volatility_breakout": "session_range_breakout",  # Vol breakout ≈ session
    "central_bank_reaction": "session_range_breakout",  # CB reaction ≈ breakout
    "signal_provider_follow": "session_range_breakout",  # Signal provider ≈ breakout
}


def load_external_hypotheses() -> list[dict]:
    """Load latest external hypotheses."""
    f = HYPO / "latest_external.json"
    if not f.exists():
        return []
    return json.loads(f.read_text(encoding="utf-8"))


def map_to_existing(hypotheses: list[dict]) -> list[dict]:
    """Map external hypotheses to existing family functions."""
    mapped = []
    for h in hypotheses:
        ext_family = h["family"]
        mapped_family = FAMILY_MAP.get(ext_family)
        if not mapped_family:
            continue

        h["mapped_family"] = mapped_family
        h["family_func"] = EXISTING_FAMILIES.get(mapped_family, "")
        mapped.append(h)
    return mapped


def generate_test_grid(mapped: list[dict]) -> list[dict]:
    """Generate symbol x family x params grid for full_hunt."""
    # Group by (symbol, mapped_family)
    groups = {}
    for h in mapped:
        key = (h["symbol"], h["mapped_family"])
        if key not in groups:
            groups[key] = []
        groups[key].append(h)

    grid = []
    for (sym, family), hyps in groups.items():
        # Dedupe by family
        seen_families = set()
        for h in hyps:
            if h["mapped_family"] in seen_families:
                continue
            seen_families.add(h["mapped_family"])

            # Generate param grid
            for rr in [1.5, 2.0, 2.5]:
                for extra_kw in [{"wait_bars": 8}, {"wait_bars": 12}]:
                    grid.append({
                        "symbol": sym,
                        "family": h["mapped_family"],
                        "family_func": h["family_func"],
                        "params": {"rr": rr, **extra_kw},
                        "source_hypothesis": h["id"],
                        "source_url": h.get("url", ""),
                    })

    return grid


def save_grid(grid: list[dict]) -> Path:
    """Save test grid for full_hunt."""
    out = HYPO / "test_grid.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(grid, indent=2, default=str), encoding="utf-8")
    print(f"Test grid: {len(grid)} cells from external discoveries")
    return out


if __name__ == "__main__":
    hyps = load_external_hypotheses()
    print(f"Loaded {len(hyps)} external hypotheses")

    mapped = map_to_existing(hyps)
    print(f"Mapped {len(mapped)} to existing families")

    grid = generate_test_grid(mapped)
    print(f"Generated {len(grid)} test cells")

    save_grid(grid)

    # Summary
    from collections import Counter
    families = Counter(g["family"] for g in grid)
    symbols = Counter(g["symbol"] for g in grid)
    print(f"\nBy family: {dict(families)}")
    print(f"By symbol: {dict(symbols)}")
