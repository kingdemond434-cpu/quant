#!/usr/bin/env python3
"""Patch collect_x_signals.py: mention-based scoring fallback when engagement unavailable."""
from pathlib import Path

p = Path("/home/quant/quant-platform/scripts/collect_x_signals.py")
src = p.read_text()

old = '''    symbol_scores = {}
    for sym, data in by_symbol.items():
        symbol_scores[sym] = {
            "mentions": data["mentions"],
            "engagement": data["engagement"],
            "score": min(1.0, data["mentions"] / 10.0) * np.log1p(data["engagement"]),
        }

    narrative_scores = {}
    for narr, data in by_narrative.items():
        narrative_scores[narr] = {
            "count": data["count"],
            "engagement": data["engagement"],
            "score": min(1.0, data["count"] / 20.0) * np.log1p(data["engagement"]),
        }'''

new = '''    symbol_scores = {}
    for sym, data in by_symbol.items():
        eng = data["engagement"]
        eng_factor = np.log1p(eng) if eng else 1.0
        symbol_scores[sym] = {
            "mentions": data["mentions"],
            "engagement": eng,
            "score": min(1.0, data["mentions"] / 10.0) * eng_factor,
        }

    narrative_scores = {}
    for narr, data in by_narrative.items():
        eng = data["engagement"]
        eng_factor = np.log1p(eng) if eng else 1.0
        narrative_scores[narr] = {
            "count": data["count"],
            "engagement": eng,
            "score": min(1.0, data["count"] / 20.0) * eng_factor,
        }'''

if old not in src:
    print("Pattern not found")
    raise SystemExit(2)
src = src.replace(old, new)
p.write_text(src)
print("Patched OK")