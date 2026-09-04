"""A second, independent replay of a cell's signals -- to catch the first engine lying.

`mt5desk.engine.run_backtest` is the only thing on this desk that turns signals into R. If it has
a bug -- a fill at the wrong bar, a stop checked against the wrong side, a TTL off by one -- every
certificate carries it and nothing can see it, because every check re-runs the same code. A
second implementation written from the CONTRACT rather than from the first engine's source is the
cheapest way to find that class of error, and it is how every serious replay is validated.

THE CONTRACT, restated from `run_backtest`'s docstring and nothing else:
    * a signal at bar t fills at the OPEN of bar t+1
    * stop and target are checked intrabar on subsequent bars, low against stop for longs and
      high against target; if both are touched in one bar the STOP is assumed first
    * after `ttl_bars` bars without a stop or target the position closes at the next open
    * one position at a time: a signal inside a live trade is ignored
    * R = (exit - entry) * side / (entry - stop) * side, i.e. distance to stop is 1R, and the
      round-trip cost is subtracted in price units

DELIBERATELY SIMPLE. No vectorisation, no shared helpers, no import from `engine`. Its value is
exactly that it was not written by copying the thing it checks.

DISAGREEMENT IS THE OUTPUT. `compare` returns the per-trade R from both engines and where they
part company. A certificate whose two replays disagree by more than tolerance is not certified by
either; it is a defect report.
"""
from __future__ import annotations

import math
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Any

import numpy as np
import pandas as pd


@dataclass(frozen=True)
class Trade2:
    entry_i: int
    exit_i: int
    side: int
    entry: float
    exit: float
    r: float
    reason: str


def replay(df: pd.DataFrame, signals: Sequence[Any], cost_price_units: float = 0.0) -> list[Trade2]:
    o = df["open"].astype(float).to_numpy()
    h = df["high"].astype(float).to_numpy()
    lo = df["low"].astype(float).to_numpy()
    c = df["close"].astype(float).to_numpy()
    pos = {ts: i for i, ts in enumerate(df.index)}
    out: list[Trade2] = []
    busy_until = -1
    for s in sorted(signals, key=lambda x: x.time):
        i = pos.get(s.time)
        if i is None or i + 1 >= len(o):
            continue
        entry_i = i + 1
        if entry_i <= busy_until:
            continue
        side = int(s.side)
        entry = float(o[entry_i])
        risk = abs(entry - float(s.stop))
        if risk <= 0 or not math.isfinite(risk):
            continue
        ttl = max(1, int(s.ttl_bars))
        exit_i, exit_px, reason = None, None, ""
        for j in range(entry_i, min(entry_i + ttl, len(o))):
            if side > 0:
                if lo[j] <= s.stop:
                    exit_i, exit_px, reason = j, float(s.stop), "stop"
                    break
                if h[j] >= s.target:
                    exit_i, exit_px, reason = j, float(s.target), "target"
                    break
            else:
                if h[j] >= s.stop:
                    exit_i, exit_px, reason = j, float(s.stop), "stop"
                    break
                if lo[j] <= s.target:
                    exit_i, exit_px, reason = j, float(s.target), "target"
                    break
        if exit_i is None or exit_px is None:
            j = min(entry_i + ttl, len(o) - 1)
            exit_i, exit_px, reason = j, float(o[j]) if j < len(o) else float(c[-1]), "ttl"
        r = ((exit_px - entry) * side - cost_price_units) / risk
        out.append(Trade2(entry_i, exit_i, side, entry, exit_px, float(r), reason))
        busy_until = exit_i
    return out


def compare(r_engine: Sequence[float], r_replay: Sequence[float],
            tol: float = 0.02) -> dict[str, Any]:
    """Per-trade agreement between the production engine and this replay."""
    a = np.asarray(r_engine, dtype=float)
    b = np.asarray(r_replay, dtype=float)
    n = min(a.size, b.size)
    if n == 0:
        return {"ok": False, "n_engine": int(a.size), "n_replay": int(b.size),
                "why": "one side produced no trades"}
    diff = np.abs(a[:n] - b[:n])
    worst = int(np.argmax(diff)) if n else -1
    ok = bool(a.size == b.size and float(diff.max()) <= tol)
    return {"ok": ok, "n_engine": int(a.size), "n_replay": int(b.size),
            "max_abs_diff_r": round(float(diff.max()), 6), "n_disagree": int((diff > tol).sum()),
            "worst_trade": worst, "mean_r_engine": round(float(a.mean()), 6),
            "mean_r_replay": round(float(b.mean()), 6),
            "why": ("agree within tolerance" if ok else
                    (f"trade counts differ ({a.size} vs {b.size})" if a.size != b.size else
                     f"{int((diff > tol).sum())} trades differ by more than {tol}R"))}
