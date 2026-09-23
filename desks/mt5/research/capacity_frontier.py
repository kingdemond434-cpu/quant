"""F21 -- AT WHAT COST DOES EACH EDGE DIE, which is the only capacity question this venue answers.

THE PRINCIPAL, 2026-09-12:

    Measure alpha(size), slippage(size), fill probability(size), rejection probability, broker
    depth/proxy liquidity, spread widening, market-impact decay and crowding; allocate strategy
    AND scale by marginal Elog of the NEXT unit of capital.

WHAT THIS VENUE ACTUALLY PERMITS, MEASURED RATHER THAN ASSUMED. `data/tape/depth_probe.json` says
`symbols_with_real_depth: []` -- every subscribed symbol returns `levels: 0`, verdict NO_DEPTH.
There is no order book here. So fill probability by size, rejection probability and impact decay
are not merely unmeasured on this box: they are unmeasurable on this venue with this feed, and
saying "we will measure them later" would be a promise against data that does not exist.

WHAT IS MEASURABLE, AND IT IS THE QUESTION THAT BINDS. Size reaches a CFD account through the cost
it pays, so the capacity frontier here is: at what MULTIPLE of today's round trip does each
mechanism's edge reach zero? A mechanism that dies at 1.3x is one spread widening away from
nothing; one that survives 6x has room. That is alpha(size) in the only unit this venue supplies,
and it is computed with the desk's own evaluator at `costs_for(mult)` -- the same lever F22 uses to
separate signal from fill, swept instead of toggled.

SPREAD WIDENING IS MEASURED DIRECTLY, per symbol and hour, because it is the mechanism by which a
cost multiple actually arrives: the difference between the quietest and noisiest hour IS a live
multiple the book pays every day without anyone choosing it.

THE OTHER HALF OF CAPACITY ALREADY EXISTS AND WAS RUNNING NOWHERE. `research/capacity.py` answers
the LOWER bound -- the venue's minimum lot forcing more risk per trade than the policy asked for --
and its docstring is right that this is the binding constraint at this account size. It had no
runner and no contract. It is on the clock in the same commit as this.

    python desks/mt5/research/capacity_frontier.py [--apply]
"""
from __future__ import annotations

import argparse
import contextlib
import itertools
import json
import math
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

DESK = Path(__file__).resolve().parents[1]
ROOT = DESK.parent.parent
for _p in (str(DESK), str(DESK / "research"), str(DESK / "scripts"), str(ROOT)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

UNI = DESK / "data" / "universe"
SLEEVES = DESK / "data" / "sleeves.json"
DEPTH = DESK / "data" / "tape" / "depth_probe.json"
OUT = DESK / "reports" / "CAPACITY_FRONTIER.json"

FAMILIES: tuple[str, ...] = ("momentum_volgate", "session_range_breakout", "mean_reversion_rsi")
MAX_SYMBOLS = 6
BARS = 6000
TRAIN_FRAC = 0.70
EMBARGO = 240
RANK_RISK_FRAC = 0.01

#: Cost multiples swept. 1.0 is today's modelled round trip. The ladder is geometric because the
#: question is "how many DOUBLINGS of cost does this survive", not "how many pips".
MULTIPLES: tuple[float, ...] = (1.0, 1.5, 2.0, 3.0, 4.0, 6.0, 8.0)


def _live_symbols(limit: int = MAX_SYMBOLS) -> list[str]:
    try:
        doc = json.loads(SLEEVES.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return []
    rows = doc if isinstance(doc, list) else (doc.get("sleeves") or [])
    out: list[str] = []
    for r in rows:
        if isinstance(r, dict) and str(r.get("status", "")).upper() == "LIVE":
            s = str(r.get("symbol") or "").strip()
            if s and s not in out:
                out.append(s)
    return out[:limit]


def _growth(ds: Any) -> float:
    import numpy as np
    if ds is None or len(ds) < 20:
        return float("nan")
    r = np.asarray(ds, dtype=float) * RANK_RISK_FRAC
    r = r[np.isfinite(r)]
    if r.size < 20 or np.any(r <= -1.0):
        return float("nan")
    return float(np.mean(np.log1p(r)))


def _depth_verdict() -> dict[str, Any]:
    """What the venue publishes about its own book. Measured, and it is nothing."""
    try:
        d = json.loads(DEPTH.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {"status": "UNMEASURED",
                "why": f"no depth probe at {DEPTH.relative_to(ROOT)}"}
    syms = d.get("symbols") or {}
    with_depth = d.get("symbols_with_real_depth") or []
    return {
        "status": "OK",
        "probed_at": d.get("at"),
        "n_symbols_probed": len(syms),
        "n_with_real_depth": len(with_depth),
        "verdict": ("NO ORDER BOOK ON THIS VENUE. Every subscribed symbol returns levels: 0."
                    if not with_depth else
                    f"{len(with_depth)} symbol(s) publish real depth"),
        "consequence": (
            "fill probability by size, rejection probability and market-impact decay are "
            "UNMEASURABLE here -- not unmeasured. They need a book, and this feed does not "
            "publish one. Promising them later would be a promise against data that does not "
            "exist."
            if not with_depth else
            "depth-based capacity measurement is available for the symbols listed"),
    }


def _spread_by_hour(symbol: str) -> dict[str, Any]:
    """The multiple the book already pays for trading the wrong hour, from its own bars."""
    try:
        import numpy as np
        import pandas as pd
    except ImportError:
        return {"status": "UNMEASURED", "why": "numpy/pandas unavailable"}
    p = UNI / f"{symbol}_H1.parquet"
    if not p.exists():
        return {"status": "UNMEASURED", "why": "no H1 parquet"}
    try:
        df = pd.read_parquet(p).tail(BARS)
    except (OSError, ValueError):
        return {"status": "UNMEASURED", "why": "unreadable parquet"}
    if "spread" not in df.columns or float(df["spread"].abs().max() or 0) <= 0:
        return {"status": "UNMEASURED",
                "why": ("the bar feed records spread 0 on every bar for this symbol -- that is "
                        "the feed not carrying it, never a zero-cost venue")}
    idx = pd.DatetimeIndex(df.index)
    sp = pd.Series(np.asarray(df["spread"], dtype=float), index=idx.hour)
    med = sp.groupby(level=0).median()
    if med.empty or float(med.min()) <= 0:
        return {"status": "UNMEASURED", "why": "no positive median spread in any hour"}
    return {"status": "OK",
            "cheapest_hour_utc": int(med.idxmin()), "cheapest_median": float(med.min()),
            "dearest_hour_utc": int(med.idxmax()), "dearest_median": float(med.max()),
            "widening_multiple": round(float(med.max() / med.min()), 3),
            "by_hour": {int(h): round(float(v), 3) for h, v in med.items()},
            "reads": ("the ratio between the dearest and cheapest hour is a cost multiple the "
                      "book pays every day without anyone choosing it. It is the mechanism by "
                      "which the capacity frontier below is actually reached.")}


def build() -> dict[str, Any]:
    now = datetime.now(tz=UTC)
    try:
        import pandas as pd
    except ImportError as exc:
        return {"at": now.isoformat(timespec="seconds"), "status": "UNMEASURED",
                "why": f"pandas unavailable ({exc})"}
    try:
        import external_gauntlet as eg  # type: ignore[import-not-found]
        from mt5desk import families as FAM
    except ImportError as exc:
        return {"at": now.isoformat(timespec="seconds"), "status": "UNMEASURED",
                "why": f"the canonical evaluator is not importable ({exc})"}
    try:
        meta = json.loads((UNI / "universe.json").read_text("utf-8"))
    except (OSError, ValueError) as exc:
        return {"at": now.isoformat(timespec="seconds"), "status": "UNMEASURED",
                "why": f"universe registry unreadable: {exc}"}

    curves: list[dict[str, Any]] = []
    spreads: dict[str, Any] = {}
    for sym in _live_symbols():
        spreads[sym] = _spread_by_hour(sym)
        p = UNI / f"{sym}_H1.parquet"
        if not p.exists():
            continue
        try:
            df = pd.read_parquet(p).tail(BARS)
        except (OSError, ValueError):
            continue
        if len(df) < 2000:
            continue
        ntr = int(len(df) * TRAIN_FRAC)
        test = df.iloc[ntr + EMBARGO:]
        if len(test) < 500:
            continue
        for fam in FAMILIES:
            entry = FAM.FAMILY_REGISTRY.get(fam)
            fn: Any = (entry.get("func") if isinstance(entry, dict)
                       else getattr(FAM, f"family_{fam}", None))
            if fn is None or not callable(fn):
                continue
            try:
                with contextlib.redirect_stdout(None):
                    sigs = list(fn(test) or [])
            except Exception:
                continue
            if len(sigs) < 30:
                continue
            pts: list[dict[str, Any]] = []
            for m in MULTIPLES:
                try:
                    g = _growth(eg.daily_series(test, sigs, eg.costs_for(sym, meta, m)))
                except Exception:
                    continue
                if math.isfinite(g):
                    pts.append({"cost_multiple": m, "growth": round(g, 8)})
            if len(pts) < 3 or pts[0]["growth"] <= 0:
                # A MECHANISM THAT IS ALREADY UNDERWATER AT 1x HAS NO CAPACITY FRONTIER, and
                # reporting a crossing for it would be reading a curve that starts below zero.
                curves.append({"symbol": sym, "family": fam, "n_signals": len(sigs),
                               "points": pts,
                               "dies_at_cost_multiple": None,
                               "status": "NO_EDGE_AT_1X",
                               "why": ("net growth is already <= 0 at today's modelled cost, so "
                                       "there is no frontier to find -- this is an alpha "
                                       "question, not a capacity one")})
                continue
            cross = None
            for a, b in itertools.pairwise(pts):
                if float(a["growth"]) > 0 >= float(b["growth"]):
                    ga, gb = float(a["growth"]), float(b["growth"])
                    ma, mb = float(a["cost_multiple"]), float(b["cost_multiple"])
                    cross = round(ma + (mb - ma) * (ga / (ga - gb)), 3) if ga != gb else mb
                    break
            curves.append({
                "symbol": sym, "family": fam, "n_signals": len(sigs), "points": pts,
                "dies_at_cost_multiple": cross,
                "status": "OK" if cross is not None else "SURVIVES_THE_SWEEP",
                "why": (None if cross is not None else
                        f"still positive at {MULTIPLES[-1]}x today's round trip -- the frontier "
                        f"is beyond the swept range, which is a real reading and not a failure"),
            })

    if not curves:
        return {"at": now.isoformat(timespec="seconds"), "status": "UNMEASURED",
                "why": "no (symbol, family) pair produced enough signals on the held-out slice"}

    priced = [c for c in curves if c.get("dies_at_cost_multiple") is not None]
    priced.sort(key=lambda c: float(c["dies_at_cost_multiple"]))
    survives = [c for c in curves if c["status"] == "SURVIVES_THE_SWEEP"]
    no_edge = [c for c in curves if c["status"] == "NO_EDGE_AT_1X"]
    widen = [(s, v.get("widening_multiple")) for s, v in spreads.items()
             if isinstance(v, dict) and v.get("status") == "OK"]
    widen.sort(key=lambda t: -float(t[1] or 0))

    # THE CROSS-FINDING, WHICH NEITHER HALF SHOWS ALONE. A mechanism's death multiple and its
    # symbol's intraday spread widening are the same units, so they can be compared directly --
    # and when the widening EXCEEDS the death multiple, that mechanism is not fragile in theory,
    # it is already underwater in that hour, every day, and the daily average hides it.
    already_dead: list[dict[str, Any]] = []
    for c in curves:
        dm = c.get("dies_at_cost_multiple")
        sp = spreads.get(str(c["symbol"]))
        if dm is None or not isinstance(sp, dict) or sp.get("status") != "OK":
            continue
        w = float(sp.get("widening_multiple") or 0.0)
        if w > float(dm):
            already_dead.append({
                "symbol": c["symbol"], "family": c["family"],
                "dies_at_cost_multiple": dm,
                "intraday_widening_multiple": round(w, 3),
                "dearest_hour_utc": sp.get("dearest_hour_utc"),
                "cheapest_hour_utc": sp.get("cheapest_hour_utc"),
                "reads": (f"this mechanism's edge reaches zero at {dm}x today's round trip, and "
                          f"this symbol's spread is {w:.1f}x wider at hour "
                          f"{sp.get('dearest_hour_utc'):02d} than at hour "
                          f"{sp.get('cheapest_hour_utc'):02d}. It is not fragile in theory; it "
                          f"is underwater in that hour every day, and a daily average hides it."),
            })
    already_dead.sort(key=lambda r: -float(r["intraday_widening_multiple"]))

    return {
        "at": now.isoformat(timespec="seconds"),
        "status": "OK",
        "n_curves": len(curves),
        "underwater_in_the_dearest_hour": {
            "n": len(already_dead),
            "rows": already_dead[:12],
            "why": ("a death multiple and a spread-widening multiple are the SAME unit, so they "
                    "compare directly. Neither half of this report shows it alone, and it is the "
                    "most actionable thing here: the fix is an hour filter, not an abandonment."),
        },
        "depth": _depth_verdict(),
        "frontier": {
            "n_with_a_crossing": len(priced),
            "n_survive_the_sweep": len(survives),
            "n_no_edge_at_1x": len(no_edge),
            "most_fragile": priced[:10],
            "sweep": list(MULTIPLES),
            "unit": ("MULTIPLE of today's modelled round trip. Size reaches a CFD account "
                     "through the cost it pays, so this is alpha(size) in the only unit this "
                     "venue supplies."),
        },
        "spread_widening": {
            "by_symbol": spreads,
            "worst_intraday_multiples": widen[:8],
            "reads": ("the dearest hour against the cheapest, per symbol. This is the multiple "
                      "the book already pays for trading the wrong hour, and it is how the "
                      "frontier above is actually reached."),
        },
        "curves": curves[:60],
        "unmeasurable_here": {
            "fill_probability_by_size": "needs a book; this venue publishes none",
            "rejection_probability": "needs order-level rejects; the ledger holds 16 deals",
            "market_impact_decay": ("needs fills at different sizes against a book, so it fails "
                                    "both tests at once"),
            "note": ("these are UNMEASURABLE on this venue and feed, which is a stronger "
                     "statement than unmeasured. They are listed so nobody plans work against "
                     "data that does not exist."),
        },
        "lower_bound_half": (
            "research/capacity.py answers the other half -- the venue's minimum lot forcing MORE "
            "risk per trade than the policy asked for -- and its docstring is right that this is "
            "the binding constraint at this account size. It had no runner and no contract; it "
            "is on the clock from the same commit as this."),
        "boundary": (
            "NOTHING HERE SIZES. It reports how much cost each mechanism can absorb before its "
            "edge reaches zero. Allocation stays the allocator's."),
        "why": (
            "an admission decision made as though an edge's value were a property of the edge "
            "alone ignores that the same edge is worth nothing at twice the spread -- and the "
            "spread doubles between the cheapest and dearest hour of an ordinary day."),
    }


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--apply", action="store_true")
    a = ap.parse_args(argv)
    doc = build()
    if doc.get("status") != "OK":
        print(f"capacity frontier: {doc.get('status')} -- {doc.get('why')}")
        return 0
    d = doc["depth"]
    print(f"capacity frontier: OK   {doc['n_curves']} curve(s)")
    print(f"  depth: {d.get('verdict')}")
    f = doc["frontier"]
    print(f"  {f['n_with_a_crossing']} mechanism(s) have a crossing, "
          f"{f['n_survive_the_sweep']} survive {doc['frontier']['sweep'][-1]}x, "
          f"{f['n_no_edge_at_1x']} have no edge at 1x")
    for c in f["most_fragile"][:8]:
        print(f"    dies at {float(c['dies_at_cost_multiple']):>5.2f}x  {c['symbol']:<9} "
              f"{c['family']:<24} n={c['n_signals']}")
    uw = doc["underwater_in_the_dearest_hour"]
    if uw["n"]:
        print(f"  {uw['n']} mechanism(s) are UNDERWATER in their symbol's dearest hour:")
        for r in uw["rows"][:6]:
            print(f"    {r['symbol']:<9} {r['family']:<24} dies at "
                  f"{float(r['dies_at_cost_multiple']):.2f}x, spread widens "
                  f"{float(r['intraday_widening_multiple']):.1f}x at hour "
                  f"{r['dearest_hour_utc']:02d}")
    print("  spread widening, dearest hour vs cheapest:")
    for sym, mult in doc["spread_widening"]["worst_intraday_multiples"][:6]:
        v = doc["spread_widening"]["by_symbol"][sym]
        print(f"    {sym:<9} {float(mult):>5.2f}x  (hour {v['dearest_hour_utc']:02d} vs "
              f"{v['cheapest_hour_utc']:02d})")
    for k, v in doc["unmeasurable_here"].items():
        if k != "note":
            print(f"  UNMEASURABLE {k:<28} {v}")
    if not a.apply:
        print("  --apply not given; nothing written")
        return 0
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(doc, indent=1, default=str), encoding="utf-8")
    print(f"-> {OUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
