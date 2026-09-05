"""Converts external discoveries into testable hypotheses.

v6: ZERO-HARDCODE registry sweep. Every external discovery's symbols are tested
against EVERY family the FAMILY_REGISTRY knows how to build, with each family's
registered defaults. No keyword->family guessing, no curated `testable` set --
the 25-family auto-registry IS the source of truth (auto-built from decorated
`family_*` functions by `register_family`). A discovery simply widens the grid;
coverage comes from the registry, not from this file.

Reads latest_discoveries.json, writes the same shape the pipeline consumes
(id/source/symbol/family/description/url/confidence/patterns/created), one
hypothesis per (symbol x family). Downstream (full_pipeline.step_backtest)
dedups to one cell per (symbol, family) and runs each with the family's
registered defaults.
"""

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

BASE = Path(__file__).resolve().parent.parent
DATA = BASE / "data" / "intelligence"
OUT = BASE / "data" / "hypotheses"

EARLY = {p: False for p in sys.path}

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

# Sources with no tradeable signal -- never widen the grid.
SKIP_SOURCES = {"mql5_forum", "academic", "sec_edgar", "earnings"}


def _load_families():
    """Import the auto registry (zero hardcode). Uses the same import the
    full pipeline relies on, so symbols resolve identically."""
    d = BASE / "mt5desk"
    for p in (str(d), str(BASE), str(BASE / "side_channels")):
        if p not in sys.path:
            sys.path.insert(0, p)
    from mt5desk import families as F
    return F


def _normalize_symbol(sym: str) -> str | None:
    return SYMBOL_MAP.get(str(sym).upper())


def convert_discoveries() -> list[dict]:
    disc_file = DATA / "latest_discoveries.json"
    if not disc_file.exists():
        return []

    F = _load_families()
    family_names = F.get_all_family_names()

    raw = json.loads(disc_file.read_text(encoding="utf-8"))
    hypotheses: list[dict] = []
    seen: set[tuple[str, str, str]] = set()

    for source_name, source_data in raw.items():
        if source_name == "summary":
            continue
        if not isinstance(source_data, dict):
            continue
        if source_name in SKIP_SOURCES:
            continue

        discoveries = source_data.get("discoveries", [])
        for disc in discoveries:
            symbols = disc.get("symbols", [])
            if not symbols:
                continue
            for sym in symbols:
                norm_sym = _normalize_symbol(sym)
                if not norm_sym:
                    continue
                for family_name in family_names:
                    key = (norm_sym, family_name, source_name)
                    if key in seen:
                        continue
                    seen.add(key)
                    hypotheses.append({
                        "id": f"ext_{source_name}_{norm_sym}_{family_name}",
                        "source": f"external_{source_name}",
                        "symbol": norm_sym,
                        "family": family_name,
                        "description": disc.get("description", disc.get("title", ""))[:200],
                        "url": disc.get("url", ""),
                        "confidence": disc.get("confidence", 0.3),
                        "patterns": disc.get("patterns", disc.get("policy_signals", [])),
                        "created": datetime.now(timezone.utc).isoformat(),
                    })
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