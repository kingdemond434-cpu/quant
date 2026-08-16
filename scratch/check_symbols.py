#!/usr/bin/env python3
from libs.autodiscovery.crypto_adapter import load_universe
from libs.data.timeframe import Timeframe

symbols, _ = load_universe(Timeframe.D1, limit=None)
print(f"Total liquid symbols: {len(symbols)}")
print("Symbols:", symbols[:50])
