"""Enable all MT5 symbols, then download H1 data for every one."""
import MetaTrader5 as mt5
import pandas as pd
from pathlib import Path
import time

PARQUET_DIR = Path(r"C:\Users\dell\mt5-research\data\mt5_universe\parquets")
PARQUET_DIR.mkdir(parents=True, exist_ok=True)

mt5.initialize()
print("MT5 initialized")

syms = mt5.symbols_get()
tradable = [s for s in syms if s.visible and s.trade_mode > 0]
existing = set(f.stem.replace("_H1", "") for f in PARQUET_DIR.glob("*_H1.parquet"))
missing = [s for s in tradable if s.name not in existing]
print(f"Tradable: {len(tradable)}, have: {len(existing)}, need: {len(missing)}")

enabled = 0
for si in missing:
    if not si.visible or si.trade_mode == 0:
        continue
    result = mt5.symbol_select(si.name, True)
    if result:
        enabled += 1

print(f"Enabled {enabled} symbols, waiting 3s...")
time.sleep(3)

# Now try downloading with larger history
ok = 0
fail = 0
for i, si in enumerate(missing):
    if not si.visible or si.trade_mode == 0:
        continue
    # Try up to 50000 bars
    rates = mt5.copy_rates_from_pos(si.name, mt5.TIMEFRAME_H1, 0, 50000)
    if rates is None or len(rates) < 100:
        # Try fewer bars
        rates = mt5.copy_rates_from_pos(si.name, mt5.TIMEFRAME_H1, 0, 5000)
    if rates is None or len(rates) < 10:
        fail += 1
        continue
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
    if ok % 10 == 0:
        print(f"  {ok} downloaded so far...", flush=True)

print(f"Downloaded: {ok}, still no data: {fail}")

mt5.shutdown()
