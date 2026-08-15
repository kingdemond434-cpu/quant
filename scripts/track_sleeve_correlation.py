#!/usr/bin/env python3
"""RHO, MEASURED -- the number every return projection on this desk has been assuming.

WHY THIS IS THE HIGHEST-VALUE NUMBER THE DESK IS NOT MEASURING. Combined Sharpe is s*sqrt(k_eff),
and k_eff = n/(1+(n-1)rho). At rho=0 six sleeves at s=0.48 reach S=1.18 and 40%/yr; at rho=0.2 the
same six reach S=0.76 and k_eff ASYMPTOTES to 1/rho=5, so combined Sharpe caps at 1.07 and adding
sleeves past that point buys literally nothing. Those two futures are indistinguishable in every
artifact the desk publishes, and the difference between them is one number nobody has measured.

`libs/research/breadth` refuses to assume it and reports UNMEASURED, correctly. That refusal is
only useful if something is trying to END it.

**IT MEASURES DAILY SIGNAL RETURNS, NOT FILLS, AND SAYS SO.** Per-sleeve realised P&L across books
sharing one margin account is not attributable here. Each sleeve's published positions are marked
forward on the same daily grid instead. Costs are excluded -- but rho is a CORRELATION, and fees
are close to a per-sleeve constant, so they shift the means far more than the co-movement. This is
the one statistic on the desk where the signal-return proxy is nearly as good as the realised one.

**PAIRWISE, ON OVERLAPPING DAYS ONLY.** Two sleeves that ran in different months have no
correlation to measure -- filling the gap with zeros would manufacture independence, which is
exactly the flattering error the whole breadth module exists to prevent.

**IT REPORTS `n` ALONGSIDE EVERY RHO AND REFUSES A SHORT SAMPLE.** A correlation from nine
overlapping days has a standard error near 0.33: it is compatible with anything from -0.3 to +0.9,
and reading a point estimate off it would replace an honest UNMEASURED with a confident wrong one.

    python scripts/track_sleeve_correlation.py [--min-overlap 20] [--json]
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
import math
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import numpy as np

_ROOT = Path(__file__).resolve().parent.parent
_STATE = _ROOT / "data/sleeve_returns.jsonl"
_OUT = _ROOT / "web/sleeve_correlation.json"

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


def report(min_overlap: int = MIN_OVERLAP) -> dict[str, Any]:
    from libs.research.breadth import combined_sharpe, effective_breadth

    series = _daily_returns()
    pairs: list[dict[str, Any]] = []
    measured: list[float] = []
    for a, b in itertools.combinations(sorted(series), 2):
        common = sorted(set(series[a]) & set(series[b]))
        row: dict[str, Any] = {"a": a, "b": b, "n_overlap": len(common)}
        if len(common) < min_overlap:
            row["rho"] = None
            row["why"] = (f"{len(common)} overlapping day(s) against a floor of {min_overlap}. "
                          "A correlation from a handful of days is compatible with almost any "
                          "value; printing the point estimate would replace an honest UNMEASURED "
                          "with a confident wrong number")
        else:
            xa = np.array([series[a][d] for d in common], dtype="float64")
            xb = np.array([series[b][d] for d in common], dtype="float64")
            if xa.std() <= 0 or xb.std() <= 0:
                row["rho"] = None
                row["why"] = "one series has zero variance -- a flat sleeve correlates with nothing"
            else:
                rho = float(np.corrcoef(xa, xb)[0, 1])
                row["rho"] = round(rho, 4)
                # THE STANDARD ERROR TRAVELS WITH THE VALUE. 1/sqrt(n-3) is the Fisher-z SE, and
                # at the n this desk will have for months it is WIDE -- which is the finding, not
                # a footnote to it.
                row["se"] = round(1.0 / math.sqrt(len(common) - 3), 4)
                measured.append(rho)
        pairs.append(row)

    n = len(series)
    rho_bar = float(np.mean(measured)) if measured else None
    k = effective_breadth(n, rho_bar)
    s_bar = 0.48
    return {
        "updated": datetime.now(tz=UTC).isoformat(),
        "n_sleeves": n, "sleeves": sorted(series),
        "days_recorded": {k2: len(v) for k2, v in sorted(series.items())},
        "min_overlap": min_overlap,
        "pairs": pairs,
        "n_pairs_measured": len(measured),
        "mean_rho": None if rho_bar is None else round(rho_bar, 4),
        "rho_state": "MEASURED" if rho_bar is not None else "UNMEASURED",
        "effective_breadth": None if k is None else round(k, 3),
        "combined_sharpe_at_s048": (None if rho_bar is None
                                    else round(combined_sharpe(s_bar, n, rho_bar) or 0.0, 3)),
        "measure": ("daily SIGNAL returns of each sleeve's published positions, marked forward on "
                    "one grid and EXCLUDING costs. Fees are close to a per-sleeve constant, so "
                    "they move the means far more than the co-movement -- this is the one desk "
                    "statistic where the signal proxy is nearly as good as the realised one"),
        "why_it_matters": (
            "k_eff = n/(1+(n-1)rho) asymptotes to 1/rho. At rho=0.2 combined Sharpe caps at "
            "s*sqrt(5) however many sleeves are added, so 40%/yr is unreachable at ANY n -- and "
            "at rho=0 six sleeves reach it. Those two futures are identical in every artifact "
            "except this one"),
    }


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--min-overlap", type=int, default=MIN_OVERLAP)
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args()

    wrote = append_today()
    rep = report(args.min_overlap)
    rep["today"] = wrote
    _OUT.parent.mkdir(parents=True, exist_ok=True)
    _OUT.write_text(json.dumps(rep, indent=1), "utf-8")

    if args.json:
        print(json.dumps(rep, indent=1))
        return 0
    print(f"=== SLEEVE CORRELATION === {rep['n_sleeves']} sleeve(s), rho {rep['rho_state']}"
          + (f" = {rep['mean_rho']:+.3f}" if rep["mean_rho"] is not None else "")
          + f", {rep['n_pairs_measured']} of {len(rep['pairs'])} pair(s) measured")
    if not wrote.get("written"):
        print(f"  today NOT recorded: {wrote.get('why')}")
    else:
        print(f"  recorded {wrote['day']}: {', '.join(wrote['sleeves'])}")
    for d, days in rep["days_recorded"].items():
        print(f"    {d:<20} {days} day(s) of return history")
    for p in rep["pairs"]:
        if p["rho"] is None:
            print(f"  {p['a']} x {p['b']}: UNMEASURED -- {str(p['why'])[:90]}")
        else:
            print(f"  {p['a']} x {p['b']}: rho {p['rho']:+.3f} +/- {p['se']:.3f} "
                  f"over {p['n_overlap']} day(s)")
    if rep["mean_rho"] is not None:
        print(f"  -> k_eff {rep['effective_breadth']}, combined Sharpe "
              f"{rep['combined_sharpe_at_s048']} at s=0.48")
    print(f"\n-> {_OUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
