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

FREEZE (2026-09-30). While the immune system's FREEZE stands (the production certifier got
easier to fool, `promotion_authority._freeze`), a third factor moves heat toward the sleeves
whose edge is carried by OUT-OF-SAMPLE evidence -- live fills and forward trades -- and away
from sleeves that stand on their certificate alone: freeze_factor = 1 + KAPPA_FREEZE x (2s - 1)
with s = n / (n + K_CAPTURE), heat-neutral like the others. The book's total is untouched; only
which sleeves carry it changes while the certificates' own word is worth less.

HELD OUT: a sleeve the control arm assigns to the exchange's control (`control_arm.in_control`,
salt "exchange") reads EXACTLY 1.0 -- pinned after the treated sleeves are renormalised among
themselves, and excluded from capture too -- so the exchange is judged by what its tilted
sleeves did against the sleeves it did not touch.
"""
from __future__ import annotations

import math
from collections.abc import Mapping
from typing import Any

TILT_LO, TILT_HI = 0.5, 2.0
#: the exchange may clear a sleeve to NOTHING (ZERO, EXIT, DEFER): its factor reaches 0.0, and the
#: heat it frees goes to the sleeves the exchange holds (verifier 2026-09-30: floored at 0.5, a
#: DEFER could never read as the zero it is)
EXCHANGE_LO = 0.0
KAPPA_EXCHANGE = 0.5
CAPTURE_LO, CAPTURE_HI = 0.25, 2.0
K_CAPTURE = 20.0
KAPPA_FREEZE = 0.5
EPS = 1e-4


def heat_neutral(raw: Mapping[str, float], heat: Mapping[str, float], *,
                 held: frozenset[str] = frozenset(), lo: float = TILT_LO) -> dict[str, float]:
    """raw factors rescaled so their heat-weighted mean over the funded TREATED book is 1.0,
    clipped to [lo, TILT_HI]. Held-out sleeves are pinned to exactly 1.0 and take no part in the
    normalisation (verifier 2026-09-30: normalising them with the rest leaked the treatment into
    the control, which read 0.923 instead of 1.0)."""
    out = {k: 1.0 for k in raw if k in held}
    treated = {k: v for k, v in raw.items() if k not in held}
    w = {k: float(heat.get(k, 0.0)) for k in treated if float(heat.get(k, 0.0)) > 0}
    tot = sum(w.values())
    mean = sum(w[k] * float(treated[k]) for k in w) / tot if tot > 0 else 0.0
    if not math.isfinite(mean) or mean <= 0:
        out.update(dict.fromkeys(treated, 1.0))
        return out
    out.update({k: float(min(TILT_HI, max(lo, float(v) / mean))) for k, v in treated.items()})
    return out


def exchange_raw(exchange_w: float, live_w: float) -> float:
    if max(0.0, exchange_w) <= 0.0 < abs(live_w):
        return 0.0
    r = (max(0.0, exchange_w) + EPS) / (max(0.0, live_w) + EPS)
    return max(EXCHANGE_LO, 1.0 + KAPPA_EXCHANGE * (min(TILT_HI, r) - 1.0))


def capture_raw(capture: float | None, n: int) -> float:
    if capture is None or not math.isfinite(float(capture)) or n <= 0:
        return 1.0
    c = min(CAPTURE_HI, max(CAPTURE_LO, float(capture)))
    return 1.0 + (n / (n + K_CAPTURE)) * (c - 1.0)


def freeze_raw(n_oos: int) -> float:
    s = max(0, n_oos) / (max(0, n_oos) + K_CAPTURE)
    return 1.0 + KAPPA_FREEZE * (2.0 * s - 1.0)


def build(live_book: Mapping[str, float], group_of: Mapping[str, str],
          exchange_by_group: Mapping[str, float], capture_by_group: Mapping[str, Any],
          held_out: Any = None, *, freeze: bool = False,
          oos_n_by_group: Mapping[str, int] | None = None) -> dict[str, dict[str, Any]]:
    """{book name: {exchange_factor, capture_factor, tilt, ...}} over the live book's names."""
    live_by_group: dict[str, float] = {}
    for name, w in live_book.items():
        g = group_of.get(name, name)
        live_by_group[g] = live_by_group.get(g, 0.0) + float(w)
    ex_raw: dict[str, float] = {}
    cap_raw: dict[str, float] = {}
    held = frozenset(n for n in live_book if held_out is not None and held_out(n))
    for name in live_book:
        g = group_of.get(name, name)
        share = float(live_book[name]) / live_by_group[g] if live_by_group.get(g) else 0.0
        if name in held:
            ex_raw[name] = cap_raw[name] = 1.0
            continue
        if g in exchange_by_group:
            ex_raw[name] = exchange_raw(float(exchange_by_group[g]) * share, float(live_book[name]))
        else:
            ex_raw[name] = 1.0
        c = capture_by_group.get(g) or {}
        cap_raw[name] = capture_raw(c.get("capture"), int(c.get("n") or 0))
    heat = {k: abs(float(v)) for k, v in live_book.items()}
    ex = heat_neutral(ex_raw, heat, held=held, lo=EXCHANGE_LO)
    cap = heat_neutral(cap_raw, heat, held=held)
    oos = oos_n_by_group or {}
    fz = heat_neutral({k: freeze_raw(int(oos.get(group_of.get(k, k), 0))) if freeze else 1.0
                       for k in live_book}, heat, held=held)
    return {name: {"group": group_of.get(name, name), "exchange_factor": round(ex[name], 6),
                   "capture_factor": round(cap[name], 6), "freeze_factor": round(fz[name], 6),
                   "tilt": (1.0 if name in held else
                            round(min(TILT_HI, max(EXCHANGE_LO, ex[name] * cap[name] * fz[name])),
                                  6)),
                   "held_out": name in held}
            for name in live_book}
