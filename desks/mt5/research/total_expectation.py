"""THE LAW OF TOTAL EXPECTATION, MEASURED HOURLY (Roman row 0997, 2026-10-06).

For each of the desk's anchor symbols and each state family `families_roman.bar_states` defines,
how much of the forward 12-bar return variance the state's conditional mean explains (the
between-state share of the law of total variance), the per-state probabilities and means, and
the state the last bar sits in with its causal z against the total mean -- the same estimate
`total_expectation_state` cells trade. Fitted with `libs/research/conditional_expectation.py`.

A module of the hourly `research/elitequant_breadth.py --once` leg, never run on its own: that
leg calls `run()` inside its own budget. Writes `reports/TOTAL_EXPECTATION.json` (RAN or
UNMEASURED per symbol, with why); `research/health_board.py` reads it.
"""
from __future__ import annotations

import json
import math
import sys
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import numpy as np

BASE = Path(__file__).resolve().parent.parent
ROOT = BASE.parent.parent
for _p in (str(BASE), str(ROOT)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from libs.research import conditional_expectation as ce  # noqa: E402

OUT = BASE / "reports" / "TOTAL_EXPECTATION.json"
SYMBOLS = ("XAUUSD", "EURUSD", "USDJPY", "US500", "XTIUSD", "GER40", "GBPUSD", "AUDUSD")
H_BARS = 12
MIN_N = 60


def _now() -> str:
    return datetime.now(tz=UTC).isoformat(timespec="seconds")


def _num(x: float) -> float | None:
    return round(float(x), 6) if math.isfinite(x) else None


def one(symbol: str) -> dict[str, Any]:
    from mt5desk import families_roman as rm
    from mt5desk.families import _h1
    from research import proposer_common as pc

    d = pc.bars(symbol)
    if d is None or len(d) < 1500:
        return {"status": "UNMEASURED", "why": "fewer than 1,500 H1 bars"}
    h = _h1(d)
    lc = np.log(h["close"].to_numpy(dtype=float))
    fwd = np.r_[lc[H_BARS:] - lc[:-H_BARS], np.full(H_BARS, np.nan)]
    out: dict[str, Any] = {"status": "RAN", "bars": len(h), "states": {}}
    for kind in rm.STATE_KINDS:
        st, k = rm.bar_states(h, kind)
        dec = ce.decomposition(fwd, st, k)
        m = ce.causal_state_means(fwd, st, H_BARS, k, MIN_N)
        last = len(h) - 1
        z = ((m.mean[last] - m.total[last]) / m.se[last]
             if m.se[last] and math.isfinite(m.se[last]) and m.se[last] > 0 else float("nan"))
        out["states"][kind] = {**dec, "between_share": _num(dec["between_share"]),
                               "current_state": int(st[last]), "current_z": _num(z)}
    return out


def run(budget_s: float = 60.0, write: bool = True) -> dict[str, Any]:
    started = time.monotonic()
    sets: dict[str, Any] = {}
    for sym in SYMBOLS:
        if time.monotonic() - started > budget_s:
            sets[sym] = {"status": "UNMEASURED", "why": "time budget reached; next pass"}
            continue
        try:
            sets[sym] = one(sym)
        except Exception as exc:
            sets[sym] = {"status": "UNMEASURED", "why": f"{type(exc).__name__}: {exc}"[:200]}
    ran = sorted(k for k, v in sets.items() if v.get("status") == "RAN")
    rep = {"generated_at": _now(), "row": "ROMAN-0997",
           "status": "RAN" if ran else "UNMEASURED", "ran": ran, "symbols": sets,
           "h_bars": H_BARS, "min_n": MIN_N, "seconds": round(time.monotonic() - started, 1),
           "method": ("law of total expectation / total variance by causal bar state, "
                      "libs/research/conditional_expectation.py")}
    if write:
        OUT.parent.mkdir(parents=True, exist_ok=True)
        tmp = OUT.with_suffix(".tmp")
        tmp.write_text(json.dumps(rep, indent=1, sort_keys=True, default=str), "utf-8")
        tmp.replace(OUT)
    return rep
