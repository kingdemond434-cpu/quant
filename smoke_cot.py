#!/usr/bin/env python3
"""Smoke-test: run a tiny research cycle on BTCUSDT+ETHUSDT (COT flow) via the real pipeline."""
import sys

from scripts.run_crypto_research import main

sys.argv = ["run_crypto_research.py", "--max-symbols", "3", "--families", "liquidity"]

main()
