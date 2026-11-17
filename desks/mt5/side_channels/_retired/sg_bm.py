import sys, time, traceback
sys.path.insert(0, r"C:\Users\dell\mt5-research")
sys.path.insert(0, r"C:\Users\dell\mt5-research\research")
import numpy as np
import signal_gate as sg

rng = np.random.default_rng(7)
c = np.exp(np.cumsum(rng.normal(0, 0.001, 13013)))
sig_times = [int(x) for x in rng.integers(5, 12900, 3276)]
t0 = time.time()
try:
    g = sg.gate_cell(c, sig_times)
    print("ok", g["verdict"], g["n"], "%.2fs" % (time.time() - t0))
except Exception:
    traceback.print_exc()