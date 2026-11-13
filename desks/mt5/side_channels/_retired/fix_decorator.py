#!/usr/bin/env python3
from pathlib import Path

p = Path("/home/quant/quant-platform/libs/autodiscovery/generators.py")
src = p.read_text()

bad = "@dataclass(frozen=True)\ndef _cot_positioning_reversal(s: MarketSeries, p: dict[str, float]) -> np.ndarray:"
good = "def _cot_positioning_reversal(s: MarketSeries, p: dict[str, float]) -> np.ndarray:"
if bad not in src:
    print("Broken pattern not found")
    raise SystemExit(2)
src = src.replace(bad, good)
p.write_text(src)
print("Fixed decorator")