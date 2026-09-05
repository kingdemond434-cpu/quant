import sys, traceback
sys.path.insert(0, r"C:\Users\dell\mt5-research")
sys.path.insert(0, r"C:\Users\dell\mt5-research\research")
import pandas as pd
import numpy as np
from mt5desk import families
from run_hunt17 import FAMILIES, resample
import signal_gate as sg

try:
    h1 = families._h1(pd.read_parquet(r"C:\Users\dell\mt5-research\data\universe\XAUUSD_H1.parquet"))
    h4, d1 = resample(h1)
    c = h4["close"].to_numpy(float)
    params = {"n": 34, "rr": 2.0, "ttl": 12, "yield_z": 0.0}
    sigs = FAMILIES["macro_gold_yield"](h4, d1, 1, **params)
    print("sigs:", len(sigs))
    idx = h4.index
    arr = idx.to_numpy().astype("datetime64[ns]").astype("int64")
    print("arr sample:", arr[:2])
    sig_times = []
    for s in sigs[:5]:
        loc = int(np.searchsorted(arr, pd.Timestamp(s.time).value))
        sig_times.append(loc + 1)
    print("sig_times:", sig_times)
    g = sg.gate_cell(c, sig_times)
    print("gate:", g)
except Exception:
    traceback.print_exc()