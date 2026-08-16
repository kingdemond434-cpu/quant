#!/usr/bin/env python3
from libs.execution import binance_margin_live as m
import os

print("LIVE_ENABLE exists:", os.path.exists("/home/quant/quant-platform/data/LIVE_ENABLE"))
print("LIVE_VPS_VERIFIED exists:", os.path.exists("/home/quant/quant-platform/data/LIVE_VPS_VERIFIED"))
print("MARGIN_ENABLE exists:", os.path.exists("/home/quant/quant-platform/data/MARGIN_ENABLE"))
print("binance_live_spot.json exists:", os.path.exists("/home/quant/quant-platform/data/secrets/binance_live_spot.json"))

print("\nModule paths:")
print("  _ENABLE_FLAG:", m._ENABLE_FLAG)
print("  _VPS_MARKER:", m._VPS_MARKER)
print("  _MARGIN_FLAG:", m._MARGIN_FLAG)
print("  _KEYFILE:", m._KEYFILE)

print("\nArmed check:")
armed, why = m.is_armed()
print(f"  armed: {armed}, why: {why}")