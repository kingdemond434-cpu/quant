#!/usr/bin/env python3
"""THE PORTFOLIO GAP -- every unfilled point of heat becomes a research request.

    "Make every unused percentage point generate a research emergency ... the purpose of
     research becomes: make high-quality 20% utilisation possible in more states of the world."
                                                            -- the principal, 2026-09-02

WHAT THIS IS FOR. `pf_allocator.py` answers "what should the book be". This answers the question
that follows: WHERE THE LIBRARY IS EMPTY. A heat gap that says "4% unfilled" is a number nobody
can act on; one that says "4% unfilled, and the desk owns nothing that trades the 00-04 UTC band
outside JPY" is a search. The gap is the bridge between the allocator and the hunt: the allocator
discovers what it cannot fund, and the hunt goes and finds it.

NOTHING IS ENUMERATED HERE. The mechanism axis is READ OUT OF THE CERTIFICATES -- every family
name that has ever cleared the ten gates appears, and one that appears tomorrow appears
tomorrow. There is no list of families in this file and there must never be one: a hardcoded axis
turns "we have not looked there" into "that cell does not exist", which is the failure mode this
whole artifact exists to prevent. The session axis is likewise read from the windows the desk
actually trades.

WHAT IT IS NOT. Not a gate, not a promoter, not a sizer. It writes `reports/portfolio_gap.json`
and ranks cells. Nothing here can admit or reject a candidate.
"""
from __future__ import annotations

import json
import re
import sys
from collections import defaultdict
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

BASE = Path(__file__).resolve().parent.parent
for _p in (str(BASE), str(BASE.parent.parent)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

OUT = BASE / "reports" / "portfolio_gap.json"
ALLOC = BASE / "reports" / "pf_allocation.json"
SURVIVORS = BASE / "reports" / "UNIVERSAL_SURVIVORS.json"

#: UTC hour bands. Coarse on purpose: the desk's sleeves are session-bracketed, so a finer grid
#: would report structure the evidence cannot support.
BANDS = ((0, 4), (4, 8), (8, 12), (12, 16), (16, 20), (20, 24))

#: Signal hour per known window, read from the gateway when it can be imported. This is the ONLY
#: place a window name is turned into a clock, and it defers to the gateway's own definition.
_FALLBACK_WINDOW_HOUR = {"asia": 7, "london_am": 13, "afternoon": 17, "ny_open": 20}


def window_hours() -> dict[str, int]:
    """Window -> signal hour, from the gateway if importable, else the last known mapping."""
    try:
        from mt5desk.gateway import GOLD_WINDOWS
        got = {str(w[0]): int(w[1]) for w in GOLD_WINDOWS}
        return {**_FALLBACK_WINDOW_HOUR, **got}
    except Exception:
        return dict(_FALLBACK_WINDOW_HOUR)


def band_of(hour: int) -> str:
    for lo, hi in BANDS:
        if lo <= hour < hi:
            return f"{lo:02d}-{hi:02d}"
    return "??"


def parse_cell(cell: str) -> dict[str, str]:
    """Split a survivor cell into its axes WITHOUT assuming a fixed shape.

    Two shapes exist in the live ledger and more have existed:
        `AUDNZD dav_range_filter_adx SHORT afternoon NORMAL_DAY`   (hunt cells)
        `XAUUSD.session_range_breakout`                            (external discoveries)

    Tokens are therefore CLASSIFIED rather than positioned -- a side is LONG/SHORT, a state ends
    in _DAY, a window is one the desk trades, the symbol is the first token, and whatever is left
    is the mechanism. A hunt inventing a new token order is parsed, not dropped.
    """
    raw = str(cell).strip()
    if not raw:
        return {}
    toks = raw.split()
    if len(toks) == 1 and "." in toks[0]:
        sym, _, fam = toks[0].partition(".")
        return {"symbol": sym, "side": "", "window": "", "state": "",
                "family": fam or "unspecified"}
    wins = set(window_hours())
    out = {"symbol": toks[0], "side": "", "window": "", "state": "", "family": ""}
    rest: list[str] = []
    for t in toks[1:]:
        if t in ("LONG", "SHORT") and not out["side"]:
            out["side"] = t
        elif t in wins and not out["window"]:
            out["window"] = t
        elif t.endswith("_DAY") and not out["state"]:
            out["state"] = t
        else:
            rest.append(t)
    out["family"] = "_".join(rest) if rest else "unspecified"
    return out


def load_survivors() -> list[dict[str, Any]]:
    """Every universal 10-gate survivor, as parsed axes. UNMEASURED, never zero, on absence.

    `shadow_spec` WINS OVER THE CELL STRING when a row carries one. The external-discovery rows
    carry `{symbol, selector, family, condition}` -- the spec the forward engine actually enrols
    -- while their cell collapses all of it into `SYMBOL.family`. Measured 2026-09-02: parsing
    the cell alone put 62 of 63 certificates into an unspecified family with no window, so the
    coverage matrix showed ONE certificate and read like a desk that had certified almost
    nothing. Reading the spec recovers the real axes.
    """
    if not SURVIVORS.exists():
        return []
    try:
        doc = json.loads(SURVIVORS.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return []
    rows = doc.get("survivors") if isinstance(doc, dict) else doc
    if isinstance(rows, dict):
        rows = list(rows.values())
    out: list[dict[str, Any]] = []
    for r in rows or []:
        if not isinstance(r, dict):
            continue
        axes = parse_cell(str(r.get("cell") or ""))
        spec = r.get("shadow_spec")
        if isinstance(spec, dict):
            axes = {
                "symbol": str(spec.get("symbol") or axes.get("symbol") or "?"),
                "window": str(spec.get("selector") or axes.get("window") or ""),
                "family": str(spec.get("family") or axes.get("family") or "unspecified"),
                "state": str(spec.get("condition") or axes.get("state") or ""),
                "side": axes.get("side", ""),
            }
        if not axes:
            continue
        axes["hunt"] = str(r.get("hunt") or "")
        axes["days"] = str(r.get("days") or "")
        out.append(axes)
    return out


def sleeve_axes(name: str) -> dict[str, str]:
    """Axes for an allocator book entry, whose names are `symbol_window_state` or `gold_window`."""
    if name.startswith("gold_"):
        return {"symbol": "XAUUSD", "window": name[len("gold_"):], "state": "",
                "family": "session_bracket", "side": ""}
    m = re.match(r"^([A-Za-z0-9]+)_(.+?)_([A-Z]+_DAY)$", name)
    if m:
        return {"symbol": m.group(1), "window": m.group(2), "state": m.group(3),
                "family": "session_bracket", "side": ""}
    parts = name.split("_")
    return {"symbol": parts[0], "window": parts[-1] if len(parts) > 1 else "",
            "state": "", "family": "_".join(parts[1:-1]) or "unspecified", "side": ""}


def build(alloc: dict[str, Any], survivors: list[dict[str, Any]]) -> dict[str, Any]:
    """The coverage matrix, the gap, and the ranked research requests."""
    hours = window_hours()
    book = {str(k): float(v) for k, v in (alloc.get("book") or {}).items()}
    marginal = {str(k): float(v) for k, v in (alloc.get("marginal_delta_elog") or {}).items()}
    heat = alloc.get("heat") or {}
    target = float(heat.get("target") or 0.0)
    held = float(heat.get("total") or 0.0)

    cells: dict[tuple[str, str], dict[str, Any]] = defaultdict(
        lambda: {"certificates": 0, "funded_sleeves": 0, "funded_heat": 0.0,
                 "positive_marginal": 0.0, "symbols": set(), "windows": set()})

    for s in survivors:
        band = band_of(hours.get(s.get("window", ""), -1))
        c = cells[(band, s.get("family") or "unspecified")]
        c["certificates"] += 1
        c["symbols"].add(s.get("symbol", "?"))
        c["windows"].add(s.get("window", "?"))

    for name, h in book.items():
        ax = sleeve_axes(name)
        band = band_of(hours.get(ax["window"], -1))
        c = cells[(band, ax["family"])]
        c["funded_sleeves"] += 1
        c["funded_heat"] += h
        c["windows"].add(ax["window"])
        c["symbols"].add(ax["symbol"])
    for name, mv in marginal.items():
        if mv <= 0:
            continue
        ax = sleeve_axes(name)
        cells[(band_of(hours.get(ax["window"], -1)), ax["family"])]["positive_marginal"] += mv

    bands = [f"{lo:02d}-{hi:02d}" for lo, hi in BANDS]
    # "??" IS A REAL ROW, NOT A DROPPED ONE. A certificate whose window the desk cannot place on
    # a clock is unschedulable evidence, and letting it fall out of the matrix would report a
    # library smaller than the one that exists -- the same silent zero this file exists to catch.
    if any(b == "??" for b, _f in cells):
        bands = [*bands, "??"]
    families = sorted({f for _b, f in cells})
    matrix = [
        {"band": b, "family": f,
         **{k: (sorted(v) if isinstance(v, set) else round(v, 6) if isinstance(v, float) else v)
            for k, v in cells[(b, f)].items()}}
        for b in bands for f in families if (b, f) in cells
    ]

    # EMPTY CELLS ARE THE POINT. A band/family the desk has never certified anything in is not a
    # zero to be reported once -- it is the search target that would let the heat target be
    # filled in a state of the world it currently cannot be.
    real = [b for b in bands if b != "??"]
    empty = [{"band": b, "family": f} for b in real for f in families if (b, f) not in cells]
    dark_bands = [b for b in real
                  if not any(cells[(b, f)]["funded_heat"] > 0 for f in families if (b, f) in cells)]
    unplaced = sum(int(v["certificates"]) for (b, _f), v in cells.items() if b == "??")

    gap = max(target - held, 0.0)
    requests: list[dict[str, Any]] = []
    if gap > 1e-9:
        requests.append({
            "kind": "heat_gap", "priority": 1,
            "detail": f"{gap:.2%} of the {target:.0%} heat target is unfunded by the current "
                      f"library at its per-sleeve bounds",
        })
    for b in dark_bands:
        requests.append({
            "kind": "dark_band", "priority": 2, "band": b,
            "detail": f"no funded sleeve trades the {b} UTC band -- the book is flat there "
                      f"whatever the opportunity set offers",
        })
    if unplaced:
        requests.append({
            "kind": "unplaced_certificates", "priority": 2, "count": str(unplaced),
            "detail": f"{unplaced} certificate(s) carry a window this desk cannot place on a "
                      f"clock, so they can be neither scheduled nor counted toward coverage",
        })
    for e in empty[:40]:
        requests.append({
            "kind": "empty_cell", "priority": 3, **e,
            "detail": f"no certificate has ever come from {e['family']} in the {e['band']} "
                      f"UTC band",
        })

    return {
        "generated_utc": datetime.now(UTC).isoformat(),
        "target_heat": target, "held_heat": held, "heat_gap": round(gap, 6),
        "bands": bands, "families": families,
        "n_certificates": len(survivors), "n_funded": len(book),
        "certificates_unplaced_on_a_clock": unplaced,
        "matrix": matrix,
        "dark_bands": dark_bands,
        "empty_cells": empty,
        "research_requests": requests,
        "note": ("Mechanism axis is read from the certificates, never enumerated here: a family "
                 "that clears the gates tomorrow appears in this matrix tomorrow."),
    }


def main() -> int:
    if not ALLOC.exists():
        print("no pf_allocation.json -- the gap is UNMEASURED, not zero. Run pf_allocator first.")
        return 2
    alloc = json.loads(ALLOC.read_text(encoding="utf-8"))
    survivors = load_survivors()
    doc = build(alloc, survivors)

    print(f"heat {doc['held_heat']:.2%} / target {doc['target_heat']:.2%}  "
          f"gap {doc['heat_gap']:.2%}   certificates {doc['n_certificates']}  "
          f"funded {doc['n_funded']}")
    fams = doc["families"]
    print(f"\n{'band':>7} " + " ".join(f"{f[:14]:>14}" for f in fams))
    lookup = {(m["band"], m["family"]): m for m in doc["matrix"]}
    for b in doc["bands"]:
        row = []
        for f in fams:
            m = lookup.get((b, f))
            row.append("             ." if m is None
                       else f"{m['certificates']:>6}c{m['funded_heat'] * 100:>6.2f}%")
        print(f"{b:>7} " + " ".join(row))
    print(f"\ndark bands (no funded sleeve): {doc['dark_bands'] or 'none'}")
    for r in doc["research_requests"][:12]:
        print(f"  [{r['priority']}] {r['kind']}: {r['detail']}")

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(doc, indent=2, default=str), encoding="utf-8")
    print(f"-> {OUT.relative_to(BASE.parent.parent)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
