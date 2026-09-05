import pandas as pd
from mt5desk.families import get_family_func
from mt5desk import families

df = pd.read_parquet("/home/quant/quant-platform/desks/mt5/data/universe/XAUUSD_H1.parquet")
h1 = families._h1(df)
fn = get_family_func("session_range_breakout")
sigs = fn(h1, range_start=7, wait_bars=8, atr_n=20, ttl_bars=12, rr=2.0)
print("signals:", len(sigs))
for s in sigs[:5]:
    print(f"  time={s.time} side={s.side} entry? stop={s.stop} target={s.target} ttl={s.ttl_bars} trigger={s.trigger}")