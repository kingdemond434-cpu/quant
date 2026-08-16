#!/usr/bin/env python3
import os
print("cwd:", os.getcwd())
print("LIVE_ENABLE:", os.path.exists("data/LIVE_ENABLE"))
print("LIVE_VPS_VERIFIED:", os.path.exists("data/LIVE_VPS_VERIFIED"))
print("MARGIN_ENABLE:", os.path.exists("data/MARGIN_ENABLE"))
print("KEYFILE:", os.path.exists("data/secrets/binance_live_spot.json"))