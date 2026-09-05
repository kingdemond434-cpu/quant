import MetaTrader5 as mt5
import pandas as pd
from pathlib import Path
import sys

PARQUET_DIR = Path(r"C:\Users\dell\mt5-research\data\mt5_universe\parquets")
PARQUET_DIR.mkdir(parents=True, exist_ok=True)

if not mt5.initialize():
    print("MT5 init failed:", mt5.last_error())
    sys.exit(1)
print("MT5 OK")

syms = mt5.symbols_get()
tradable = [s for s in syms if s.visible and s.trade_mode > 0]
existing = set(f.stem.replace("_H1", "") for f in PARQUET_DIR.glob("*_H1.parquet"))
to_dl = [s for s in tradable if s.name not in existing]
print(f"Need {len(to_dl)} of {len(tradable)} (have {len(existing)})")

ok = 0
fail = 0
for i, si in enumerate(to_dl):
    rates = mt5.copy_rates_from_pos(si.name, mt5.TIMEFRAME_H1, 0, 50000)
    if rates is None or len(rates) < 100:
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
        print(f"  {ok}/{len(to_dl)} done...", flush=True)

mt5.shutdown()
print(f"Complete: {ok} new, {fail} failed")
