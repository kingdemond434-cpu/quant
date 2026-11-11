"""PLAUSIBILITY CEILING -- a result too good to be true is treated as a leak, not an edge.

zuck, 2026-11-06, forwarding a transcript (an LLM strategy loop on two years of minute crypto
bars): its harness rejected a candidate showing an 11,000% PnL because "if the results look
almost too good it's probably just accessing the future data". The desk's ten gates all ask
"is this good ENOUGH"; none asks "is this too good". Deflated Sharpe, PBO and SPA are all
satisfied MORE easily by a look-ahead leak, never less, and the placebo/PIT audits only catch
the leaks someone has already imagined.

THE CEILING. Net-of-cost daily-R series, measured on the development window:

* annualised Sharpe above ``MAX_ANNUAL_SHARPE`` (6.0). Published multi-year net Sharpes of the
  best systematic books sit well below this; a single retail-venue cell above it is far more
  likely to be reading a future bar, a revised print or a fill price it could not get.
* share of winning active days above ``MAX_WIN_DAY_SHARE`` (0.95) on at least
  ``MIN_ACTIVE_DAYS`` active days: a stopping-time strategy on noise cannot win 19 days in 20.

Failing reads ``SUSPECT_LEAK`` and the cell is refused like any other failed gate. It is
additive under ``gate_policy.all_ten_pass`` (an extra recorded gate must pass and can only
raise the bar). A refused cell goes back through the PIT and placebo audits; it is never
hand-cleared.
"""
from __future__ import annotations

import math
from typing import Any

import numpy as np

MAX_ANNUAL_SHARPE = 6.0
MAX_WIN_DAY_SHARE = 0.95
MIN_ACTIVE_DAYS = 40
DAYS_PER_YEAR = 252


def plausibility_stage(daily: Any) -> dict[str, Any]:
    """The stage dict for one cell's daily net-R series (zeros = flat days)."""
    r = np.asarray(daily, dtype="float64")
    r = r[np.isfinite(r)]
    active = r[r != 0.0]
    n_active = int(active.size)
    ann_sr = 0.0
    if r.size >= 2:
        sd = float(r.std(ddof=1))
        if sd > 0:
            ann_sr = float(r.mean() / sd) * math.sqrt(DAYS_PER_YEAR)
    win_share = float((active > 0).mean()) if n_active else 0.0
    reasons = []
    if ann_sr > MAX_ANNUAL_SHARPE:
        reasons.append(f"annualised Sharpe {ann_sr:.2f} > {MAX_ANNUAL_SHARPE}")
    if n_active >= MIN_ACTIVE_DAYS and win_share > MAX_WIN_DAY_SHARE:
        reasons.append(f"{win_share:.1%} winning days > {MAX_WIN_DAY_SHARE:.0%} "
                       f"on {n_active} active days")
    # A flawless positive series with zero variance is the purest leak signature.
    if r.size >= MIN_ACTIVE_DAYS and n_active >= MIN_ACTIVE_DAYS and float(r.std()) == 0.0 \
            and float(r.mean()) > 0:
        reasons.append("zero-variance positive series")
    return {
        "passed": not reasons,
        "verdict": "SUSPECT_LEAK" if reasons else "PLAUSIBLE",
        "annual_sharpe": round(ann_sr, 4),
        "win_day_share": round(win_share, 4),
        "active_days": n_active,
        "why": "; ".join(reasons) if reasons else "inside the plausibility ceiling",
    }
