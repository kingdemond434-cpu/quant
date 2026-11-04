"""Per-member alpha half-life: how fast each combiner member's edge fades. Report, never size.

THE QUESTION. A pool of thousands of weak edges only compounds if dying edges are replaced faster
than they die. The decay organs retire LIVE sleeves on realised R. Nothing yet measures the decay
rate of the JUDGED members that feed the combiner, so we can't tell a member at 80% of its
discovery-era edge from one at 20%.

THE MEASUREMENT. A member's daily R is cut into consecutive non-overlapping blocks (BLOCK_DAYS
trading days each). The block means are fitted with OLS against block time in years:

    edge(t) = a + b * t        t = 0 at the first block

    start_edge   = a                         (the fitted per-day edge at discovery)
    now_edge     = a + b * T                 (T = the last block's time)
    retained     = now_edge / start_edge     (1.0 = undecayed, 0.5 = half gone)
    half_life_y  = (a / 2) / -b              (years from the start for the fitted edge to halve)

Verdicts:
    DECAYING    b < 0 with t(b) <= -T_STAT
    GROWING     b > 0 with t(b) >= +T_STAT
    STABLE      otherwise (no slope the data can tell from zero)
    UNMEASURED  fewer than MIN_BLOCKS blocks, or a start edge <= 0 (no edge to have a half-life of)

A linear fit, not an exponential one, because block means go negative; the half-life is where the
fitted line crosses half its starting value. Every input is already in the pool, so there is no
look-ahead beyond what the member's own series holds.

AUTHORITY: none. Nothing reads this to size, gate or retire. It exists so that the replacement
rate can be compared against the decay rate, measured and not assumed (L1.28a).
"""
from __future__ import annotations

import math
from typing import Any

import numpy as np
import pandas as pd

BLOCK_DAYS = 63          # one quarter of trading days
MIN_BLOCKS = 8           # two years before a slope is read
T_STAT = 2.0
DAYS_PER_YEAR = 252.0


def member_half_life(r: pd.Series) -> dict[str, Any]:
    """The fitted decay of one member's daily R. Short or edgeless reads UNMEASURED."""
    x = pd.to_numeric(r, errors="coerce").dropna().to_numpy(dtype=float)
    n_blocks = len(x) // BLOCK_DAYS
    base: dict[str, Any] = {"days": len(x), "blocks": n_blocks}
    if n_blocks < MIN_BLOCKS:
        return {**base, "verdict": "UNMEASURED",
                "why": f"{n_blocks} blocks of {BLOCK_DAYS}d < {MIN_BLOCKS}"}
    x = x[len(x) - n_blocks * BLOCK_DAYS:]          # keep the most recent whole blocks
    means = x.reshape(n_blocks, BLOCK_DAYS).mean(axis=1)
    t = np.arange(n_blocks, dtype=float) * BLOCK_DAYS / DAYS_PER_YEAR
    tc = t - t.mean()
    sxx = float((tc ** 2).sum())
    b = float((tc * (means - means.mean())).sum() / sxx)
    a = float(means.mean() - b * t.mean())
    resid = means - (a + b * t)
    dof = n_blocks - 2
    se = math.sqrt(float((resid ** 2).sum()) / dof / sxx) if dof > 0 and sxx > 0 else float("nan")
    tb = b / se if se and math.isfinite(se) and se > 0 else (0.0 if b == 0 else math.copysign(
        math.inf, b))
    out = {**base, "start_edge_daily": a, "slope_per_year": b, "slope_t": tb,
           "now_edge_daily": a + b * float(t[-1]), "span_years": float(t[-1])}
    if a <= 0:
        return {**out, "verdict": "UNMEASURED", "why": "fitted start edge <= 0"}
    out["retained"] = (a + b * float(t[-1])) / a
    out["half_life_years"] = (a / 2.0) / -b if b < 0 else None
    out["verdict"] = ("DECAYING" if b < 0 and tb <= -T_STAT else
                      "GROWING" if b > 0 and tb >= T_STAT else "STABLE")
    return out


def pool_half_lives(series: dict[str, pd.Series]) -> dict[str, Any]:
    """Every member's reading plus the pool summary: how much of the pool's edge is fading."""
    rows = {cid: member_half_life(s) for cid, s in sorted(series.items())}
    verdicts: dict[str, int] = {}
    for r in rows.values():
        verdicts[r["verdict"]] = verdicts.get(r["verdict"], 0) + 1
    measured = [r for r in rows.values() if r["verdict"] != "UNMEASURED"]
    hl = sorted(r["half_life_years"] for r in measured if r.get("half_life_years") is not None)
    ret = sorted(r["retained"] for r in measured)
    return {
        "members": len(rows), "verdicts": verdicts,
        "median_half_life_years": (float(np.median(hl)) if hl else None),
        "median_retained": (float(np.median(ret)) if ret else None),
        "method": {"block_days": BLOCK_DAYS, "min_blocks": MIN_BLOCKS, "t_stat": T_STAT,
                   "fit": "OLS of block-mean daily R on block time (years)"},
        "rows": rows,
    }
