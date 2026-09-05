#!/usr/bin/env python3
import numpy as np
from libs.autodiscovery.crypto_adapter import lake_provider
from libs.autodiscovery.generators import _cot_positioning_reversal

prov = lake_provider(["BTCUSDT", "ETHUSDT", "SOLUSDT"], min_bars=100)
for sym in ["BTCUSDT", "ETHUSDT", "SOLUSDT"]:
    s = prov(sym)
    if s is None:
        print(sym, "-> None")
        continue
    cot = s.cot_spec_share
    print(f"{sym}: bars={len(s)} cot_spec_share={'PRESENT' if cot is not None else 'None'}")
    if cot is not None:
        finite = cot[np.isfinite(cot)]
        print(f"   finite={len(finite)} range=[{finite.min():.4f},{finite.max():.4f}]")
        sig = _cot_positioning_reversal(s, {"weeks": 26, "z_entry": 2.0})
        nz = (sig != 0).sum()
        print(f"   signal nonzero bars: {nz} (longs={(sig==1).sum()} shorts={(sig==-1).sum()})")