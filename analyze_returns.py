#!/usr/bin/env python3
"""Analyze the actual returns from mcurve to understand the Sharpe."""
import json
import numpy as np

d = json.load(open('/home/quant/quant-platform/data/live_combined_state.json'))
mcurve = d['mcurve']
print(f"mcurve points: {len(mcurve)}")
print(f"First: {mcurve[0]}")
print(f"Last: {mcurve[-1]}")

# Extract equity values
equity = [float(e) for _, e in mcurve]
print(f"Equity range: {min(equity):.2f} - {max(equity):.2f}")
print(f"Total return: {(equity[-1] - equity[0]) / equity[0] * 100:.2f}%")

# Hourly returns (last per hour)
buckets = {}
for t, e in mcurve:
    buckets[str(t)[:13]] = float(e)
hourly_eq = [buckets[k] for k in sorted(buckets)]
print(f"Hourly points: {len(hourly_eq)}")

rets = np.diff(hourly_eq) / hourly_eq[:-1]
print(f"Hourly returns: mean={np.mean(rets)*100:.6f}%, std={np.std(rets)*100:.6f}%")
print(f"Ann Sharpe (naive): {np.mean(rets)/np.std(rets)*np.sqrt(365*24):.2f}")

# Daily returns (last per day)
buckets_d = {}
for t, e in mcurve:
    buckets_d[str(t)[:10]] = float(e)
daily_eq = [buckets_d[k] for k in sorted(buckets_d)]
print(f"Daily points: {len(daily_eq)}")
rets_d = np.diff(daily_eq) / daily_eq[:-1]
print(f"Daily returns: mean={np.mean(rets_d)*100:.6f}%, std={np.std(rets_d)*100:.6f}%")
print(f"Ann Sharpe (naive daily): {np.mean(rets_d)/np.std(rets_d)*np.sqrt(365):.2f}")

# Check for drift
print(f"\nEquity trend: {equity[-1] - equity[0]:.2f} over {len(equity)} points")
print(f"Daily drift (avg): {(equity[-1] - equity[0]) / len(set(k[:10] for k in buckets)):.2f}")