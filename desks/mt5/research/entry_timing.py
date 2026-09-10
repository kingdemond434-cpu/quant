"""WHAT THE BACKTEST CHARGED FOR SPREAD, AGAINST WHAT THE TAPE MEASURED, AT THE HOURS TRADES FIRE.

THE TWO NUMBERS, and the desk owns both:

  CHARGED   `universe.json` -> `median_spread_pts`. `mt5desk/engine.py:124` bills exactly this
            when a caller passes no explicit `spread_pts`, so it is the cost every backtest,
            every gauntlet stage and every certificate's expectancy was computed at.
  MEASURED  `data/cost_surface.json` -> `symbols[SYM].hours[H].p50`, the median spread observed
            on H1 bars at that hour of day, MEASURED or refused.

MEASURED 2026-09-10 across the 195 symbols carrying both: the median ratio is 1.00, so the two
are in the same units and the registry is broadly right -- which is what makes the exceptions
worth reading rather than dismissing as a scale bug:

    EURCHF   charged 0.5 pts,  measured 14.0   28x
    AUDCAD   charged 1.0 pts,  measured 16.0   16x
    CADJPY   charged 1.5 pts,  measured 15.0   10x
    7 of 195 symbols understate by more than 3x, 2 of them by more than 10x

THE BAR IS THE CELL'S OWN, AND THIS FILE DOES NOT SET IT. Every certificate passes
`stress_costs`, which re-runs the cell at THREE TIMES its modelled cost and requires expectancy
to stay positive; 66 of 66 survivors carry it. So a symbol whose real spread is 3x its charged
spread is exactly at the edge of what its own gate tested, and one at 16x is far outside it. The
question is not "is 3x the right multiple" -- the desk decided that -- it is whether the cell's
existing gate ever reached the conditions the cell actually trades in. That comparison invents no
threshold and cannot be tuned, because tuning it would mean disagreeing with a gate that ran.

WHY THE HOUR, AND WHY A WINDOW OF HOURS. Spread is a property of the symbol AND the hour: across
this universe the dearest hour costs a median 2.36x the cheapest, and 128 of 195 symbols swing
more than 1.5x. An entry here is a resting STOP order live for `ttl_bars` after the signal -- 12
hours on the asia window that 65 of the 66 survivors use -- so the trade fires whenever price
reaches the level anywhere in that span, and the exposure is the window's WORST hour rather than
its first.

WHAT THIS FILE WILL NOT DO, and the restraint is the point:

  * IT NEVER MOVES A TRADE OUT OF ITS SESSION. The selector IS the mechanism: a range breakout
    defined on the Asian session is not the same strategy an hour later, it is a different and
    uncertified one. Every comparison is strictly WITHIN the window the certificate holds.
  * IT NEVER VETOES, CAPS, SHRINKS OR SIZES. It publishes what was charged, what was measured,
    and which cells' own gates never reached their window. What to do about that is the
    allocator's decision on evidence, and this is the evidence. A module that quietly refused an
    hour would be reducing the book by fiat.
  * IT NEVER SUBSTITUTES A POOLED FIGURE FOR AN UNMEASURED HOUR. `cost_surface.spread_pts`
    returns None for an unmeasured cell so a caller cannot read one by accident, and an
    unmeasured window here reads UNMEASURED rather than cheap (L1.28a).
  * IT READS THE REGISTRY, NOT THE SURFACE'S COPY OF IT. `cost_surface.json` caches
    `pooled_median_spread_pts` from the registry at build time and that cache has DRIFTED --
    GBPJPY reads 1.0 there against 13.0 in the registry today. The engine bills the registry, so
    the registry is what a cost claim has to be checked against.

    python desks/mt5/research/entry_timing.py
"""
from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

BASE = Path(__file__).resolve().parent.parent
ROOT = BASE.parent.parent
for _p in (str(BASE), str(BASE / "research"), str(ROOT)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

#: THE MULTIPLE THE CELL'S OWN GATE ALREADY RAN AT. `external_gauntlet` computes
#: `stress_costs.exp_x3` by re-running the cell at three times its modelled cost. Comparing
#: against this rather than against a number chosen here is what keeps this a check and not a
#: new hurdle -- and it is why the constant must never be edited.
STRESS_MULTIPLE = 3.0

#: Entry windows, mirrored from `research/trade_path.WINDOWS` and `mt5desk/decision_core`.
#: (signal hour UTC, hours the resting entry stays live).
WINDOWS: dict[str, tuple[int, int]] = {
    "asia": (7, 12),
    "london_am": (13, 12),
    "ny_open": (14, 12),
    "afternoon": (17, 12),
}

CANON_REL = "desks/mt5/data/UNIVERSAL_SURVIVORS.canon.json"
SURFACE_REL = "desks/mt5/data/cost_surface.json"
UNIVERSE_REL = "desks/mt5/data/universe/universe.json"
OUT_REL = "desks/mt5/reports/ENTRY_TIMING.json"

COVERED = "COVERED"
UNCOVERED = "GATE_NEVER_REACHED_THIS_HOUR"
UNMEASURED = "UNMEASURED"


def entry_hours(selector: str) -> tuple[int, ...]:
    """Every UTC hour a resting entry for this selector can fire in. Empty for an unknown one.

    UNKNOWN IS EMPTY, NEVER A DEFAULT WINDOW. Falling back to the asia window would price 65 of
    66 survivors correctly and silently misprice the other, and the mispriced one is the row
    nobody would go back and check.
    """
    win = WINDOWS.get(str(selector or "").strip().lower())
    if win is None:
        return ()
    start, live = win
    return tuple((start + i) % 24 for i in range(live + 1))


def _read(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    return value if isinstance(value, dict) else {}


def registry(root: Path) -> dict[str, dict[str, Any]]:
    """Symbol metadata as the ENGINE sees it -- the source of the spread every backtest charged."""
    doc = _read(root / Path(*UNIVERSE_REL.split("/")))
    syms = doc.get("symbols") or doc
    if isinstance(syms, list):
        return {str(m.get("symbol")): m for m in syms if isinstance(m, dict)}
    return {k: v for k, v in syms.items() if isinstance(v, dict)}


def charged_pts(meta: dict[str, dict[str, Any]], symbol: str) -> float | None:
    """What `engine.spread_cost` bills for this symbol when nobody overrides it."""
    v = (meta.get(symbol) or {}).get("median_spread_pts")
    try:
        return float(v) if v is not None else None
    except (TypeError, ValueError):
        return None


def measured_pts(surface: dict[str, Any], symbol: str, hour: int) -> float | None:
    """The measured p50 spread in points at one hour, or None. Mirrors `cost_surface.spread_pts`
    exactly: a cell that is not MEASURED is a refusal, never the pooled scalar."""
    sym = (surface.get("symbols") or {}).get(symbol)
    if not sym:
        return None
    cell = (sym.get("hours") or {}).get(str(int(hour)))
    if not cell or cell.get("status") != "MEASURED":
        return None
    v = cell.get("p50")
    try:
        return float(v) if v is not None else None
    except (TypeError, ValueError):
        return None


@dataclass(frozen=True)
class Window:
    """One certificate's execution window: what it was charged, and what the hours really cost."""

    cell: str
    symbol: str
    selector: str
    hours: tuple[int, ...]
    by_hour: dict[int, float | None]
    charged: float | None
    verdict: str
    why: str

    @property
    def measured(self) -> dict[int, float]:
        return {h: v for h, v in self.by_hour.items() if v is not None}

    @property
    def understatement(self) -> float | None:
        """The dearest hour the entry can fire in, over the spread the backtest charged."""
        m = self.measured
        if not m or not self.charged:
            return None
        return round(max(m.values()) / float(self.charged), 3)

    @property
    def in_window_ratio(self) -> float | None:
        """Dearest over cheapest INSIDE the window -- what the timing of the fill is worth."""
        m = self.measured
        if len(m) < 2 or min(m.values()) <= 0:
            return None
        return round(max(m.values()) / min(m.values()), 3)

    def to_dict(self) -> dict[str, Any]:
        m = self.measured
        return {
            "cell": self.cell, "symbol": self.symbol, "selector": self.selector,
            "hours": list(self.hours),
            "n_measured": len(m), "n_unmeasured": len(self.hours) - len(m),
            "charged_pts": self.charged,
            "cheapest_hour": (min(m, key=lambda h: m[h]) if m else None),
            "dearest_hour": (max(m, key=lambda h: m[h]) if m else None),
            "cheapest_pts": (min(m.values()) if m else None),
            "dearest_pts": (max(m.values()) if m else None),
            "in_window_ratio": self.in_window_ratio,
            "understatement": self.understatement,
            "stress_multiple": STRESS_MULTIPLE,
            "verdict": self.verdict, "why": self.why,
            "by_hour": {str(h): v for h, v in sorted(self.by_hour.items())},
        }


def price_window(surface: dict[str, Any], meta: dict[str, dict[str, Any]],
                 cell: str, symbol: str, selector: str) -> Window:
    """Price one certificate's whole entry window and say whether its cost gate reached it."""
    hours = entry_hours(selector)
    charged = charged_pts(meta, symbol)
    by_hour = {h: measured_pts(surface, symbol, h) for h in hours}
    w = Window(cell, symbol, selector, hours, by_hour, charged, UNMEASURED, "")

    if not hours:
        why = f"selector {selector!r} is not a window this desk executes"
    elif not w.measured:
        why = f"no hour of {symbol}'s entry window is MEASURED in the cost surface"
    elif charged is None:
        why = f"{symbol} is not in the universe registry, so nothing says what it was charged"
    elif not charged:
        why = (f"{symbol} is charged 0.0 pts of spread: the backtest paid no spread at all, "
               f"so no multiple of it exists. That is a cost bug and not a cheap symbol")
    else:
        mult = w.understatement
        dear = max(w.measured, key=lambda h: w.measured[h])
        if mult is not None and mult <= STRESS_MULTIPLE:
            return Window(cell, symbol, selector, hours, by_hour, charged, COVERED,
                          f"the dearest hour the entry can fire in costs {mult}x what the "
                          f"backtest charged, inside the {STRESS_MULTIPLE}x this cell passed at")
        return Window(cell, symbol, selector, hours, by_hour, charged, UNCOVERED,
                      f"the entry can fire at hour {dear} where the measured spread is "
                      f"{w.measured[dear]} pts against {charged} charged -- {mult}x, and the "
                      f"stress gate tested {STRESS_MULTIPLE}x and never reached it")
    return Window(cell, symbol, selector, hours, by_hour, charged, UNMEASURED, why)


def symbol_gaps(root: Path | None = None) -> list[dict[str, Any]]:
    """Every symbol whose measured spread outruns what it is charged, worst first.

    UNIVERSE-WIDE AND NOT CERTIFICATE-WIDE, deliberately: a symbol with no certificate today is
    one a hunt can propose tomorrow, and it would be admitted on the same understated cost.
    """
    root = Path(root or ROOT)
    surface = _read(root / Path(*SURFACE_REL.split("/")))
    meta = registry(root)
    out: list[dict[str, Any]] = []
    for symbol, sym in (surface.get("symbols") or {}).items():
        charged = charged_pts(meta, symbol)
        hours = {int(h): c.get("p50") for h, c in (sym.get("hours") or {}).items()
                 if isinstance(c, dict) and c.get("status") == "MEASURED"
                 and c.get("p50") is not None}
        if not hours or charged is None:
            continue
        vals = sorted(float(v) for v in hours.values())
        med = vals[len(vals) // 2]
        row = {"symbol": symbol, "charged_pts": charged,
               "measured_median_pts": med, "measured_max_pts": max(vals),
               "median_over_charged": (round(med / charged, 3) if charged else None),
               "max_over_charged": (round(max(vals) / charged, 3) if charged else None),
               "zero_charged": not charged}
        out.append(row)
    out.sort(key=lambda r: -(r["median_over_charged"] or 1e9 if r["zero_charged"] else
                             r["median_over_charged"] or 0.0))
    return out


def assess(root: Path | None = None) -> list[Window]:
    """Every certificate's window, worst understatement first."""
    root = Path(root or ROOT)
    canon = _read(root / Path(*CANON_REL.split("/")))
    surface = _read(root / Path(*SURFACE_REL.split("/")))
    meta = registry(root)
    out: list[Window] = []
    for key, cert in (canon.get("survivors") or {}).items():
        if not isinstance(cert, dict):
            continue
        spec = cert.get("shadow_spec") or {}
        symbol = str(spec.get("symbol") or cert.get("sym") or "")
        if not symbol:
            continue
        out.append(price_window(surface, meta, str(cert.get("cell") or key), symbol,
                                str(spec.get("selector") or "")))
    out.sort(key=lambda w: (-(w.understatement or -1.0), w.cell))
    return out


def census(root: Path | None = None) -> dict[str, Any]:
    root = Path(root or ROOT)
    rows = assess(root)
    gaps = symbol_gaps(root)
    uncovered = [w for w in rows if w.verdict == UNCOVERED]
    ratios = [w.in_window_ratio for w in rows if w.in_window_ratio is not None]
    over = [g for g in gaps if (g["median_over_charged"] or 0) > STRESS_MULTIPLE]
    zero = [g for g in gaps if g["zero_charged"]]
    return {
        "at": datetime.now(tz=UTC).isoformat(),
        "n_certificates": len(rows),
        "covered": sum(1 for w in rows if w.verdict == COVERED),
        "gate_never_reached": len(uncovered),
        "unmeasured": sum(1 for w in rows if w.verdict == UNMEASURED),
        "stress_multiple": STRESS_MULTIPLE,
        "worst_cells": [{"cell": w.cell, "understatement": w.understatement, "why": w.why}
                        for w in uncovered[:10]],
        "median_in_window_ratio": (sorted(ratios)[len(ratios) // 2] if ratios else None),
        "max_in_window_ratio": (max(ratios) if ratios else None),
        "n_symbols_priced": len(gaps),
        "n_symbols_over_stress": len(over),
        "n_symbols_charged_zero": len(zero),
        "symbols_over_stress": over[:20],
        "symbols_charged_zero": [g["symbol"] for g in zero],
        "windows": [w.to_dict() for w in rows],
        "rule": (
            "the comparison is against the multiple each cell's OWN stress_costs gate already "
            "ran at, so this sets no new hurdle and can never be tuned. Nothing here moves a "
            "trade out of its session, vetoes an hour, or sizes anything: the selector is the "
            "mechanism, and what to do about an uncovered hour is the allocator's call. The "
            "charged figure is read from the universe REGISTRY, which is what the engine bills; "
            "the copy cached inside cost_surface.json has drifted and is not used"),
    }


def render(doc: dict[str, Any]) -> str:
    lines = [
        f"ENTRY TIMING  {doc['n_certificates']} certificates: {doc['covered']} covered, "
        f"{doc['gate_never_reached']} whose {doc['stress_multiple']}x stress gate never reached "
        f"their entry window, {doc['unmeasured']} unmeasured",
        f"  universe: {doc['n_symbols_over_stress']} of {doc['n_symbols_priced']} symbols are "
        f"charged less than 1/{doc['stress_multiple']:.0f} of their measured spread; "
        f"{doc['n_symbols_charged_zero']} are charged ZERO",
    ]
    if doc["median_in_window_ratio"] is not None:
        lines.append(f"  dearest/cheapest hour INSIDE the entry window: "
                     f"median {doc['median_in_window_ratio']}x, "
                     f"worst {doc['max_in_window_ratio']}x")
    for g in doc["symbols_over_stress"][:10]:
        lines.append(f"    {g['symbol']:12s} charged {g['charged_pts']:>7} pts   measured median "
                     f"{g['measured_median_pts']:>7} pts   x{g['median_over_charged']}")
    if doc["symbols_charged_zero"]:
        lines.append(f"    CHARGED ZERO SPREAD: {', '.join(doc['symbols_charged_zero'])}")
    for w in doc["worst_cells"]:
        lines.append(f"  {w['cell']}")
        lines.append(f"      {w['why']}")
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(
        description="what a certified entry is charged against what its hours cost")
    ap.add_argument("--root", default=str(ROOT))
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args(argv)

    root = Path(args.root)
    doc = census(root)
    out = root / Path(*OUT_REL.split("/"))
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(doc, indent=1, default=str), encoding="utf-8")
    print(json.dumps(doc, indent=1, default=str) if args.json else render(doc))
    print(f"written: {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
