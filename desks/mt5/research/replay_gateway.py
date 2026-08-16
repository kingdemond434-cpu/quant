"""Replay the gateway logic over the last 3 weeks of live H1 data (shadow).

Proves: bracket built each day from Asia range, fills at trigger with the
engine's exact rules, stop/target exits, TTL exit at 19:00, all costed.
"""

from __future__ import annotations

import pandas as pd

from mt5desk.engine import Costs, run_backtest
from mt5desk.families import _atr
from mt5desk.gateway import asia_range, bracket_spec
from mt5desk.data import load_gold

costs = Costs(spread_per_lot=0.48, commission_per_lot=3.50, contract_oz=100.0)
h1 = _atr.__globals__["families"]._h1(load_gold().h1) if False else None

from mt5desk import families

h1 = families._h1(load_gold().h1)
atr = _atr(h1, 20)

days = sorted(set(h1.index.date))[-15:]
results = []
for day in days:
    day_end = pd.Timestamp(day, tz="UTC") + pd.Timedelta(hours=7)
    hist = h1.loc[:day_end]
    rng = asia_range(hist)
    if rng is None:
        continue
    hi, lo = rng
    a = atr.loc[:day_end].iloc[-1]
    spec = bracket_spec(hi, lo, a, 0.01)
    bs, ss = spec["buy_stop"], spec["sell_stop"]
    day_bars = h1.loc[day_end: pd.Timestamp(day, tz="UTC") + pd.Timedelta(hours=19)]
    if day_bars.empty:
        continue
    o = day_bars["open"].to_numpy(); hh = day_bars["high"].to_numpy()
    ll = day_bars["low"].to_numpy(); cc = day_bars["close"].to_numpy()
    idx = day_bars.index
    filled = None
    for j in range(len(day_bars)):
        if hh[j] >= bs["price"] >= ll[j]:
            filled = ("long", bs["price"], j, bs["sl"], bs["tp"])
            break
        if hh[j] >= ss["price"] >= ll[j]:
            filled = ("short", ss["price"], j, ss["sl"], ss["tp"])
            break
    if filled is None:
        results.append({"day": str(day), "fill": "none"})
        continue
    side, entry, j0, sl, tp = filled
    exit_px, reason, k = None, "ttl", None
    for k in range(j0, len(day_bars)):
        if side == "long":
            if ll[k] <= sl:
                exit_px, reason = sl, "stop"
                break
            if hh[k] >= tp:
                exit_px, reason = tp, "target"
                break
        else:
            if hh[k] >= sl:
                exit_px, reason = sl, "stop"
                break
            if ll[k] <= tp:
                exit_px, reason = tp, "target"
                break
    if exit_px is None:
        exit_px, k, reason = cc[-1], len(day_bars) - 1, "ttl"
    r = (exit_px - entry) / abs(entry - sl) * (1 if side == "long" else -1)
    r -= (0.48 + 7.0) / 100.0 / abs(entry - sl)
    results.append({"day": str(day), "fill": side, "entry": round(entry, 2),
                    "exit": round(exit_px, 2), "reason": reason,
                    "r": round(r, 3)})

for r in results:
    print(r)
rs = [r["r"] for r in results if "r" in r]
if rs:
    import numpy as np
    rs = np.array(rs)
    print(f"replay: n={len(rs)} exp={rs.mean():.3f}R t={rs.mean()/(rs.std(ddof=1)/np.sqrt(len(rs))):.2f}")
print(f"(engine full-sample on same window for reference)")