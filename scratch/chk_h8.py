#!/usr/bin/env python3
import os

os.chdir("/home/quant/quant-platform")
from libs.autodiscovery.crypto_adapter import crypto_symbols
from libs.data.timeframe import Timeframe

syms8 = crypto_symbols(Timeframe.H8)
print(f"H8 symbols: {len(syms8)}")
print(syms8)
