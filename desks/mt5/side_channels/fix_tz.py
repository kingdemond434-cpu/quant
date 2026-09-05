#!/usr/bin/env python3
from pathlib import Path

p = Path("/home/quant/quant-platform/libs/autodiscovery/crypto_adapter.py")
src = p.read_text()

old = '''        out[asset] = pd.Series(
            cot["net_spec"].to_numpy("float64") / cot["oi"].clip(lower=1.0).to_numpy("float64"),
            index=pd.DatetimeIndex(pd.to_datetime(cot["pub_date"])),
        ).sort_index()'''
new = '''        idx = pd.DatetimeIndex(pd.to_datetime(cot["pub_date"])).tz_localize("UTC")
        out[asset] = pd.Series(
            cot["net_spec"].to_numpy("float64") / cot["oi"].clip(lower=1.0).to_numpy("float64"),
            index=idx,
        ).sort_index()'''
if old not in src:
    print("Anchor not found")
    raise SystemExit(2)
src = src.replace(old, new)
p.write_text(src)
print("UTC-aware COT index")