"""THE OPPORTUNITY EXCHANGE AND EXECUTION CAPTURE, AS ALLOCATOR EVIDENCE (Tier S layers 23-25).

Until 2026-09-30 the exchange cleared a book every hour that nothing held, and the execution
science measured how much of each sleeve's forward edge its live fills captured while the
allocator went on sizing the forward edge as if it were all bankable. Both now reach
`pf_allocator` through the one channel it already has for evidence it does not price itself: the
TILT of a sleeve's posterior mean (`allocator_evidence`, mean += (tilt - 1) x |mean|).

  exchange_factor  how much more (or less) of a sleeve the exchange's robust E[log W] book holds
                   than the live book does, shrunk halfway to 1.0 (KAPPA_EXCHANGE);
  capture_factor   live mean R / forward expectancy over the sleeve's matched fills, clipped to
                   [CAPTURE_LO, CAPTURE_HI] and shrunk to 1.0 by n / (n + K_CAPTURE).

GROWTH GOVERNANCE (Rules 1 and 2). Each factor is HEAT-NEUTRAL over the live book: normalised so
the heat-weighted mean across the funded sleeves is exactly 1.0, then bounded to
[TILT_LO, TILT_HI]. Capital moves BETWEEN sleeves toward the ones the exchange prefers and the
ones whose fills bank their edge; the total is the heat law's and is never touched, and a sleeve
can be raised to 2x as readily as lowered. UNMEASURED is 1.0 exactly. The optimiser still decides
every fraction; nothing here multiplies a fraction outside the solve.

HELD OUT: a sleeve the control arm assigns to the exchange's control (`control_arm.in_control`,
salt "exchange") reads 1.0, so the exchange is judged by what its tilted sleeves did against the
sleeves it did not touch.
"""
from __future__ import annotations

import math
from collections.abc import Mapping
from typing import Any

TILT_LO, TILT_HI = 0.5, 2.0
KAPPA_EXCHANGE = 0.5
CAPTURE_LO, CAPTURE_HI = 0.25, 2.0
K_CAPTURE = 20.0
EPS = 1e-4


def heat_neutral(raw: Mapping[str, float], heat: Mapping[str, float]) -> dict[str, float]:
    """raw factors rescaled so their heat-weighted mean over the funded book is 1.0, clipped."""
    w = {k: float(heat.get(k, 0.0)) for k in raw if float(heat.get(k, 0.0)) > 0}
    tot = sum(w.values())
    if tot <= 0:
        return dict.fromkeys(raw, 1.0)
    mean = sum(w[k] * float(raw[k]) for k in w) / tot
    if not math.isfinite(mean) or mean <= 0:
        return dict.fromkeys(raw, 1.0)
    return {k: float(min(TILT_HI, max(TILT_LO, float(v) / mean))) for k, v in raw.items()}


def exchange_raw(exchange_w: float, live_w: float) -> float:
    r = (max(0.0, exchange_w) + EPS) / (max(0.0, live_w) + EPS)
    return 1.0 + KAPPA_EXCHANGE * (min(TILT_HI, max(TILT_LO, r)) - 1.0)


def capture_raw(capture: float | None, n: int) -> float:
    if capture is None or not math.isfinite(float(capture)) or n <= 0:
        return 1.0
    c = min(CAPTURE_HI, max(CAPTURE_LO, float(capture)))
    return 1.0 + (n / (n + K_CAPTURE)) * (c - 1.0)


def build(live_book: Mapping[str, float], group_of: Mapping[str, str],
          exchange_by_group: Mapping[str, float], capture_by_group: Mapping[str, Any],
          held_out: Any = None) -> dict[str, dict[str, Any]]:
    """{book name: {exchange_factor, capture_factor, tilt, ...}} over the live book's names."""
    live_by_group: dict[str, float] = {}
    for name, w in live_book.items():
        g = group_of.get(name, name)
        live_by_group[g] = live_by_group.get(g, 0.0) + float(w)
    ex_raw: dict[str, float] = {}
    cap_raw: dict[str, float] = {}
    for name in live_book:
        g = group_of.get(name, name)
        share = float(live_book[name]) / live_by_group[g] if live_by_group.get(g) else 0.0
        if held_out is not None and held_out(name):
            ex_raw[name] = 1.0
        elif g in exchange_by_group:
            ex_raw[name] = exchange_raw(float(exchange_by_group[g]) * share, float(live_book[name]))
        else:
            ex_raw[name] = 1.0
        c = capture_by_group.get(g) or {}
        cap_raw[name] = capture_raw(c.get("capture"), int(c.get("n") or 0))
    heat = {k: abs(float(v)) for k, v in live_book.items()}
    ex = heat_neutral(ex_raw, heat)
    cap = heat_neutral(cap_raw, heat)
    return {name: {"group": group_of.get(name, name), "exchange_factor": round(ex[name], 6),
                   "capture_factor": round(cap[name], 6),
                   "tilt": round(min(TILT_HI, max(TILT_LO, ex[name] * cap[name])), 6),
                   "held_out": bool(held_out(name)) if held_out is not None else False}
            for name in live_book}
