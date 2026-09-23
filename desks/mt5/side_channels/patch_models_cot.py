#!/usr/bin/env python3
"""Patch models.py: add COT positioning fields to MarketSeries."""
from pathlib import Path

p = Path("/home/quant/quant-platform/libs/autodiscovery/models.py")
src = p.read_text()

old = '''    hashprice: np.ndarray | None = None   # revenue per unit hashrate ($/PH/day), producer margin
    difficulty: np.ndarray | None = None  # network difficulty; its DOWNWARD adjustments mark exit'''

new = '''    hashprice: np.ndarray | None = None   # revenue per unit hashrate ($/PH/day), producer margin
    difficulty: np.ndarray | None = None  # network difficulty; its DOWNWARD adjustments mark exit
    # CFTC COT positioning (weekly, per-asset: BTC/ETH CME+CB futures). Attached like funding:
    # present when data/cot/{asset}.parquet carries the column and the symbol is that asset,
    # None otherwise, NEVER synthesised. Speculative net positioning is the crowding meter: the
    # COT report is published every Friday and non-commercial net positions are the levered
    # crowd's stance. Shares of open interest normalise across contract sizes.
    cot_spec_share: np.ndarray | None = None  # (noncomm_long - noncomm_short) / oi
    cot_comm_share: np.ndarray | None = None  # (comm_long - comm_short) / oi'''

if old not in src:
    print("Pattern not found")
    raise SystemExit(2)
src = src.replace(old, new)
p.write_text(src)
print("Patched models.py")