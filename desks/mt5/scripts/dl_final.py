"""Final pass — grab ANY remaining symbols, even with few bars."""
import MetaTrader5 as mt5
import pandas as pd
from pathlib import Path

PARQUET_DIR = Path(r"C:\Users\dell\mt5-research\data\mt5_universe\parquets")

mt5.initialize()
syms = mt5.symbols_get()
tradable = [s for s in syms if s.visible and s.trade_mode > 0]
existing = set(f.stem.replace("_H1", "") for f in PARQUET_DIR.glob("*_H1.parquet"))
missing = [s for s in tradable if s.name not in existing]
print(f"Missing: {len(missing)}")

for si in missing:
    mt5.symbol_select(si.name, True)

import time
time.sleep(2)

ok = 0
for si in missing:
    for bars in [50000, 10000, 1000, 100]:
        rates = mt5.copy_rates_from_pos(si.name, mt5.TIMEFRAME_H1, 0, bars)
        if rates is not None and len(rates) > 0:
            df = pd.DataFrame(rates)
            # utc=True IS LOAD-BEARING: MT5 `rates["time"]` is Unix EPOCH SECONDS, so the instants
            # are unambiguous, but pandas drops the tz label without it and `h1_source._normalise`
            # then REFUSES the file ("bar index is timezone-naive"). Five bulk downloaders omitted
            # it while every other producer passed it, so 173 of 197 H1 parquets were unreadable by
            # the shadow/forward chain -- a 197-symbol universe that was effectively 24 symbols.
            df["time"] = pd.to_datetime(df["time"], unit="s", utc=True)
            df.set_index("time", inplace=True)
            df.to_parquet(PARQUET_DIR / f"{si.name}_H1.parquet", engine="pyarrow")
            ok += 1
            print(f"  {si.name}: {len(df)} bars")
            break
    else:
        print(f"  {si.name}: NO DATA AT ALL")

print(f"Got {ok}/{len(missing)}")
mt5.shutdown()
