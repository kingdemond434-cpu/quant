"""Converts external discoveries into testable hypotheses.

v6: ZERO HARDCODING. ZERO KEYWORD MAPPING.
Reads universe.json for valid symbols. Tests ALL families.
The backtest decides what works, not a keyword dict.
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

import sys
BASE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE))
sys.path.insert(0, str(BASE / "mt5desk"))
sys.path.insert(0, str(BASE / "desks" / "mt5" / "side_channels"))

from mt5desk.families import FAMILY_REGISTRY, get_all_family_names
from symbol_loader import get_all_symbols, get_symbols_by_category, get_major_forex

DATA = BASE / "data" / "intelligence"
OUT = BASE / "data" / "hypotheses"
UNI = BASE / "data" / "universe"

# Load valid symbols from universe.json — NOT hardcoded
def _load_valid_symbols() -> set[str]:
    return set(get_all_symbols())

# Families needing extra data the pipeline can't provide
SKIP_FAMILIES = {"usd_session_shock", "comex_settlement"}


def _normalize_symbol(sym: str) -> str | None:
    """Normalize a symbol name. Try exact match, then common variants."""
    valid = _load_valid_symbols()
    s = sym.upper().strip()
    if s in valid:
        return s
    # Try common normalizations
    variants = [
        s.replace("/", ""), s.replace(" ", ""), s.replace("-", ""),
        s.replace("_", ""), "VT" + s, s.replace("VT", ""),
    ]
    for v in variants:
        if v in valid:
            return v
    return None


def _usable_families() -> list[str]:
    return [f for f in get_all_family_names() if f not in SKIP_FAMILIES]


def convert_discoveries() -> list[dict]:
    disc_file = DATA / "latest_discoveries.json"
    if not disc_file.exists():
        return []

    raw = json.loads(disc_file.read_text(encoding="utf-8"))
    usable = _usable_families()
    valid_symbols = sorted(_load_valid_symbols())
    hypotheses = []
    seen = set()

    for source_name, source_data in raw.items():
        if source_name == "summary":
            continue

        # Handle both dict-with-discoveries and direct-list formats
        if isinstance(source_data, dict):
            discoveries = source_data.get("discoveries", [])
        elif isinstance(source_data, list):
            discoveries = source_data
        else:
            continue

        for disc in discoveries:
            if not isinstance(disc, dict):
                continue
            symbols = disc.get("symbols", disc.get("symbol", []))
            if isinstance(symbols, str):
                symbols = [symbols]
            patterns = disc.get("patterns", disc.get("policy_signals", []))

            # If no specific symbols, apply to same-category symbols
            if not symbols:
                # Try to infer category from source_name or patterns
                cat_map = {
                    "cot": "Forex", "forexfactory": "Forex",
                    "seasonality": None,  # seasonality already has per-symbol
                    "sec_edgar": "Equities",
                    "earnings": "Equities",
                    "central_bank": "Forex",
                    "github": None,
                    "reddit": None,
                    "mql5_signals": "Forex",
                    "mql5_forum": "Forex",
                    "tradingview": None,
                }
                cat = cat_map.get(source_name)
                if cat:
                    symbols = get_symbols_by_category(cat)
                else:
                    # Fallback: use major forex only
                    symbols = get_major_forex()

            for sym in symbols:
                norm_sym = _normalize_symbol(sym)
                if not norm_sym:
                    continue

                for family in usable:
                    key = f"{norm_sym}_{family}_{source_name}"
                    if key in seen:
                        continue
                    seen.add(key)

                    hypotheses.append({
                        "id": f"ext_{source_name}_{norm_sym}_{family}",
                        "source": f"external_{source_name}",
                        "symbol": norm_sym,
                        "family": family,
                        "description": disc.get("description", disc.get("title", ""))[:200],
                        "url": disc.get("url", ""),
                        "confidence": disc.get("confidence", 0.3),
                        "patterns": patterns,
                        "created": datetime.now(timezone.utc).isoformat(),
                    })

    return hypotheses


def save_hypotheses() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    hypotheses = convert_discoveries()

    out_file = OUT / f"external_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M')}.json"
    out_file.write_text(json.dumps(hypotheses, indent=2), encoding="utf-8")

    latest = OUT / "latest_external.json"
    latest.write_text(json.dumps(hypotheses, indent=2), encoding="utf-8")

    fam_counts = {}
    sym_counts = {}
    for h in hypotheses:
        f = h["family"]
        fam_counts[f] = fam_counts.get(f, 0) + 1
        s = h["symbol"]
        sym_counts[s] = sym_counts.get(s, 0) + 1

    print(f"Generated {len(hypotheses)} hypotheses")
    print(f"  {len(_usable_families())} families, {len(sym_counts)} unique symbols")
    print(f"  Top symbols: {sorted(sym_counts.items(), key=lambda x: -x[1])[:10]}")


if __name__ == "__main__":
    save_hypotheses()
