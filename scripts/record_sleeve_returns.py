#!/usr/bin/env python3
"""DAILY SLEEVE RETURN STREAMS -- the input `track_sleeve_correlation` has been waiting on.

That analyser is complete and correct and had nothing to read: it expects
`{mechanism: {YYYY-MM-DD: daily_return}}` and no organ on this desk was producing it. It printed
"nothing to measure yet" every run, which is true and stays true until something records the
streams. This records them.

**THE SPLIT IS DELIBERATE: RECORDER HERE, ANALYSER THERE.** Two sessions built a correlation tool
the same day; the other one is the better statistician (Fisher CI, se = (1-rho^2)/sqrt(n-3),
thresholds priced against the 40%/yr target) and this one is the half it lacked. Merging them into
one file would have produced a second implementation of the arithmetic, which is the defect this
desk names most.

**WHAT IS ALREADY KNOWN, from `measure_cross_mechanism_corr.py` on 2026-08-05.** Mean absolute
off-diagonal rho 0.375 across 920 BACKTEST streams, k_eff 4.08, combined-Sharpe ceiling 0.78 at
s=0.48 -- on which 40%/yr is unreachable at ANY sleeve count. That is a real measurement of
BACKTEST streams, which share fitted parameters and a common sample. Live streams need not agree,
and this exists to find out. Expect to confirm the wall; settling it is worth as much as opening it.

**A DAY'S RETURN USES YESTERDAY'S WEIGHTS.** The position is credited with the move it was HELD
into. Marking today's weights against today's prices is lookahead of the purest kind and would
flatter every sleeve identically, which is invisible in a correlation.

**AN UNREADABLE DAY IS NOT RECORDED.** A row of zeros enters every correlation as a real day on
which nothing moved together -- dragging rho toward zero and manufacturing the diversification
being measured.

    python scripts/record_sleeve_returns.py
"""


from __future__ import annotations

# PATH BOOTSTRAP. `python scripts/x.py` puts scripts/ on sys.path, NOT the repo root.
import sys as _sys
from pathlib import Path as _P

if str(_P(__file__).resolve().parent.parent) not in _sys.path:
    _sys.path.insert(0, str(_P(__file__).resolve().parent.parent))

import argparse
import itertools
import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import numpy as np

_ROOT = Path(__file__).resolve().parent.parent
_STATE = _ROOT / "data/sleeve_returns.jsonl"
#: EXACTLY the shape and path `track_sleeve_correlation._load` reads. A recorder that
#: wrote a different schema would leave the analyser printing "nothing to measure"
#: beside a full file -- the two halves have to agree on one artifact or neither runs.
_OUT = _ROOT / "data/sleeve_returns.json"

#: Overlapping days below which a pairwise rho is reported as UNMEASURED rather than as a number.
#: At n=20 the standard error of a correlation is ~1/sqrt(n-3) = 0.24, which is still wide -- so
#: this is the floor at which the estimate becomes worth PRINTING, not the point at which it
#: becomes reliable. The standard error travels with every value for exactly that reason.
MIN_OVERLAP = 20

#: Where each sleeve's daily positions come from. Every source publishes symbol -> weight, so one
#: reader serves all of them and a new sleeve needs a row here rather than a new script.
SOURCES: tuple[tuple[str, str, str], ...] = (
    ("momentum", "data/spot_momentum.json", "target_weights"),
    ("mechanism_sleeves", "data/mechanism_sleeve_targets.json", "target_weights"),
    ("discretionary", "web/discretionary_live.json", "intents"),
)


def _prices() -> dict[str, float]:
    try:
        from libs.execution import binance_spot_live

        return {str(k): float(v) for k, v in binance_spot_live.prices().items()}
    except Exception:
        return {}


def _weights_today() -> dict[str, dict[str, float]]:
    """sleeve -> {symbol: signed weight}, from whatever each sleeve published today."""
    from libs.execution.spot_order_path import retarget

    out: dict[str, dict[str, float]] = {}
    for name, rel, key in SOURCES:
        try:
            doc = json.loads((_ROOT / rel).read_text("utf-8"))
        except (OSError, ValueError):
            continue
        node = doc.get(key)
        w: dict[str, float] = {}
        if isinstance(node, dict):
            w = {retarget(str(k), ""): float(v) for k, v in node.items()}
        elif isinstance(node, list):
            # the discretionary sleeve publishes INTENTS; only taken ones are positions
            for row in node:
                if isinstance(row, dict) and row.get("taken"):
                    sym = retarget(str(row.get("symbol", "")), "")
                    side = 1.0 if str(row.get("side", "BUY")).upper() == "BUY" else -1.0
                    if sym:
                        w[sym] = w.get(sym, 0.0) + side
        if w:
            out[name] = w
    return out


def append_today(now: datetime | None = None) -> dict[str, Any]:
    """Mark each sleeve's CURRENT positions and append one row per day. Idempotent per date.

    APPEND-ONLY AND ONE ROW PER DAY. A second run the same day updates that day's marks rather
    than adding a second observation -- two rows for one day would double-count it in every
    correlation and inflate n without adding information.
    """
    now = now or datetime.now(tz=UTC)
    day = now.strftime("%Y-%m-%d")
    px, weights = _prices(), _weights_today()
    if not px or not weights:
        return {"day": day, "written": False,
                "why": ("prices or weights unreadable -- UNMEASURED. A row of zeros would enter "
                        "every correlation as a real day on which nothing moved together")}
    rows = []
    if _STATE.exists():
        for line in _STATE.read_text("utf-8").splitlines():
            try:
                r = json.loads(line)
            except ValueError:
                continue
            if isinstance(r, dict) and r.get("day") != day:
                rows.append(r)
    marks = {name: {s: px[s + "USDC"] for s in w if s + "USDC" in px}
             for name, w in weights.items()}
    rows.append({"day": day, "at": now.isoformat(), "weights": weights, "marks": marks})
    _STATE.parent.mkdir(parents=True, exist_ok=True)
    _STATE.write_text("\n".join(json.dumps(r) for r in rows) + "\n", "utf-8")
    return {"day": day, "written": True, "sleeves": sorted(weights)}


def _daily_returns() -> dict[str, dict[str, float]]:
    """sleeve -> {day: signal return}, from consecutive marks of the SAME positions.

    A day's return uses YESTERDAY's weights against today's prices -- the position was held into
    the move. Using today's weights would mark a position the sleeve had not yet taken, which is
    lookahead of the purest kind and would flatter every sleeve identically.
    """
    rows = []
    try:
        for line in _STATE.read_text("utf-8").splitlines():
            try:
                rows.append(json.loads(line))
            except ValueError:
                continue
    except OSError:
        return {}
    rows.sort(key=lambda r: str(r.get("day", "")))
    out: dict[str, dict[str, float]] = {}
    for prev, cur in itertools.pairwise(rows):
        for name, w in (prev.get("weights") or {}).items():
            p0 = (prev.get("marks") or {}).get(name) or {}
            p1 = (cur.get("marks") or {}).get(name) or {}
            legs = [(1.0 if v > 0 else -1.0) * (float(p1[s]) / float(p0[s]) - 1.0)
                    for s, v in w.items()
                    if s in p0 and s in p1 and float(p0[s]) > 0 and float(p1[s]) > 0]
            if legs:
                out.setdefault(name, {})[str(cur["day"])] = float(np.mean(legs))
    return out


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args()

    wrote = append_today()
    streams = _daily_returns()
    _OUT.parent.mkdir(parents=True, exist_ok=True)
    _OUT.write_text(json.dumps({"updated": datetime.now(tz=UTC).isoformat(),
                                "streams": streams,
                                "measure": ("daily SIGNAL returns of each sleeve's published "
                                            "positions, marked forward on one grid and EXCLUDING "
                                            "costs. Fees are near a per-sleeve constant, so they "
                                            "move the means far more than the co-movement -- this "
                                            "is the one desk statistic where the signal proxy is "
                                            "nearly as good as the realised one")}, indent=1),
                    "utf-8")

    if args.json:
        print(json.dumps({k: len(v) for k, v in streams.items()}, indent=1))
        return 0
    if not wrote.get("written"):
        print(f"sleeve returns: today NOT recorded -- {wrote.get('why')}")
    else:
        print(f"sleeve returns: recorded {wrote['day']} for {', '.join(wrote['sleeves'])}")
    for name, days in sorted(streams.items()):
        print(f"  {name:<20} {len(days)} day(s) of return history")
    if not streams:
        print("  no stream has two consecutive days yet -- a return needs a mark on each side")
    print(f"-> {_OUT}  (read by scripts/track_sleeve_correlation.py)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
