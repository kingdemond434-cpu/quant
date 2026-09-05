"""Shared symbol loader — reads universe.json for ALL valid MT5 symbols."""
from __future__ import annotations

import json
from pathlib import Path

BASE = Path(__file__).resolve().parent.parent
UNI = BASE / "data" / "universe"

_universe_symbols = None
_universe_by_category = None

def load_universe() -> dict:
    """Load universe.json and cache."""
    global _universe_symbols, _universe_by_category
    if _universe_symbols is None:
        uf = UNI / "universe.json"
        if uf.exists():
            data = json.loads(uf.read_text("utf-8"))
            _universe_symbols = set(data.keys())
            _universe_by_category = {}
            for k, v in data.items():
                cat = v.get("category", "Unknown")
                _universe_by_category.setdefault(cat, []).append(k)
        else:
            _universe_symbols = set()
            _universe_by_category = {}
    return _universe_symbols, _universe_by_category

def get_all_symbols() -> list[str]:
    """Return all valid symbols from universe.json."""
    symbols, _ = load_universe()
    return sorted(symbols)

def get_symbols_by_category(category: str) -> list[str]:
    """Return symbols for a specific category (Forex, Equities, Crypto, etc.)."""
    _, by_cat = load_universe()
    return by_cat.get(category, [])

def get_major_forex() -> list[str]:
    """Major forex pairs."""
    cat = get_symbols_by_category("Forex")
    # Filter to majors (exclude exotics)
    majors = [s for s in cat if not any(x in s for x in ["HUF", "DKK", "NOK", "SEK", "PLN", "CZK", "HKD", "SGD", "ILS", "MXN", "ZAR", "TRY", "RUB", "IDR", "INR", "KRW", "THB", "CNH", "BRL"])]
    return majors

def get_exotics() -> list[str]:
    """Forex exotics."""
    return get_symbols_by_category("Forex Exotics")

def get_equities() -> list[str]:
    """Individual stocks."""
    return get_symbols_by_category("Equities")

def get_crypto() -> list[str]:
    """Crypto."""
    return get_symbols_by_category("Crypto")

def get_commodities() -> list[str]:
    """Metals/Commodities."""
    return get_symbols_by_category("Commodities")

def get_energy() -> list[str]:
    """Energy."""
    return get_symbols_by_category("Energy")

def get_indices() -> list[str]:
    """Indices."""
    return get_symbols_by_category("Indices")

def get_soft_commodities() -> list[str]:
    """Soft commodities."""
    return get_symbols_by_category("Soft Commodity")

def extract_symbols(text: str) -> list[str]:
    """Extract symbols mentioned in text from universe."""
    symbols, _ = load_universe()
    text_upper = text.upper()
    return [s for s in symbols if s in text_upper]


if __name__ == "__main__":
    load_universe()
    print(f"Total symbols: {len(_universe_symbols)}")
    for cat, syms in sorted(_universe_by_category.items()):
        print(f"  {cat}: {len(syms)}")
    print(f"\nAll: {sorted(_universe_symbols)}")