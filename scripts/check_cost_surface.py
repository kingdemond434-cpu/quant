#!/usr/bin/env python3
"""COST-BASIS FENCE (L1.5 / L1.28a / L2.10) -- is a cell charged what its own fill hour costs?

THE DEFECT THIS EXISTS TO END. Every gate, certificate, stress scenario and forward clock on this
desk prices a candidate off ONE scalar per symbol, `universe.json:median_spread_pts`, produced by
collapsing the per-bar `spread` column at ingest. Spread is not a constant of a symbol -- it is a
symbol x HOUR state -- so a cell that fills in a thin book is charged the median of a day it does
not trade. The desk has no instrument that compares the cost a cell was CHARGED against the cost
its own tape recorded at the bars it actually filled on, in either direction.

MEASURED 2026-08-29, the two worst live cases, with the engine's own backtest and `mult` held
equal on both arms so only the spread number moves:

    USDZAR.overnight_gap_decay.asia   pooled  329 pts   fill-hour  2028 pts  (6.16x)
    EURZAR.overnight_gap_decay.asia   pooled  310 pts   fill-hour  1918 pts  (6.19x)
      re-priced at mult=2.0 (the desk's own declared honest baseline):
      USDZAR +0.2535R -> -0.1764R      EURZAR +0.2926R -> -0.1120R      BOTH NEGATIVE

Both hold ten-gate certificates and both are on LIVE forward clocks. The two-stage law is
currently deciding their fate on a number 6x wrong, in the direction that MANUFACTURES survivors.

THE OTHER DIRECTION IS THE ONE WITH NO ALERT, and it is why this fence scans every symbol rather
than only the live book. A cell whose fill hour is CHEAPER than the pooled scalar is overcharged,
dies in the gauntlet, and dies silently -- there is no artifact anywhere on this desk that says
"a real edge was killed by a cost it would never have paid". Overcharged cells are reported with
equal weight and counted separately.

PRIOR INCIDENTS OF EXACTLY THIS CLASS, both charged-vs-tape disagreements that no fence compared:
the XAUUSD 0.48 hardcode (engine.py's own docstring: "every gold backtest on this desk has run
very nearly spread-free, and the 3x cost-stress gate meant to catch exactly this was stressing 3%
up to 9%"), and R0695 (EURUSD charged 0.05/lot against a tape truth of 12 -- 240x).

  OK                  (exit 0) -- every live sleeve is charged within tolerance of its fill hour.
  DISPERSED           (exit 0) -- no live sleeve is mispriced, but symbols carry material
                                  hour-to-hour dispersion; published per symbol as the queue.
  COST-BASIS-MISMATCH (exit 2) -- a LIVE or CERTIFIED cell is charged >= MATERIAL_RATIO away from
                                  the spread its own fill bars recorded. Either direction.
  SURFACE-MISSING     (exit 2) -- no cost surface artifact. Run desks/mt5/research/cost_surface.py.
  STALE               (exit 2) -- the surface is older than MAX_AGE_DAYS; the tape has moved on.
  UNMEASURED          (exit 2) -- nothing scanned, or the surface holds no measured cell.
                                  Never OK: absence is not a clean verdict (L1.28a / WS-005).
  NOT-READABLE-HERE   (exit 0) -- the H1 parquets are not on this box, so fill hours cannot be
                                  resolved. Explicitly its own status, never folded into OK: a
                                  verdict about the HOST is not a verdict about the DESK.

The tolerance is a CONSTANT and is not re-baselined by this fence. A fence that re-measures its
own threshold accepts every regression as the new normal, which is a gate welded open (L1.63).
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from libs.ops.fence_exit import fence_exit  # noqa: E402
from libs.ops.lawful import guard as _law_guard  # noqa: E402

_DESK = _ROOT / "desks" / "mt5"
_SURFACE = _DESK / "data" / "cost_surface.json"
_SLEEVES = _DESK / "data" / "sleeve_registry.json"
_UNIVERSE = _DESK / "data" / "universe"
_OUT = _ROOT / "data" / "cost_surface_report.json"

#: A charged cost this far from the tape at the fill hour is material, in EITHER direction.
#: Undercharging manufactures survivors; overcharging kills real edges with no alert.
MATERIAL_RATIO = 2.0

#: The surface is a re-aggregation of a tape that grows daily. Older than this and a cell may be
#: priced on a book the broker no longer runs.
MAX_AGE_DAYS = 14

#: Priced (non-zero-spread) fill bars a sleeve needs before its cost basis may be judged at all.
MIN_FILL_OBS = 30

_PASSING = frozenset({"OK", "DISPERSED", "NOT-READABLE-HERE"})


def _load(p: Path) -> dict | None:
    try:
        return json.loads(p.read_text("utf-8"))
    except (OSError, ValueError):
        return None


def _hours_measured(sym_row: dict) -> dict[int, dict]:
    return {int(h): c for h, c in (sym_row.get("hours") or {}).items()
            if c.get("status") == "MEASURED"}


def scan_symbols(surface: dict) -> list[dict]:
    """Every symbol x hour cell whose measured spread is materially off the pooled scalar.

    This is the whole universe, not the live book: the point is the cells that never became
    survivors because they were overcharged, and those leave no other trace.
    """
    rows: list[dict] = []
    for sym, row in (surface.get("symbols") or {}).items():
        pooled = row.get("pooled_median_spread_pts")
        if not pooled or pooled <= 0:
            continue
        for h, cell in sorted(_hours_measured(row).items()):
            p50 = float(cell["p50"])
            ratio = p50 / float(pooled)
            if ratio >= MATERIAL_RATIO or ratio <= 1.0 / MATERIAL_RATIO:
                rows.append({
                    "symbol": sym, "hour": h, "pooled_pts": float(pooled),
                    "measured_p50_pts": p50, "ratio": round(ratio, 2),
                    "direction": "UNDERCHARGED" if ratio > 1 else "OVERCHARGED",
                    "n_nonzero": cell["n_nonzero"],
                    # Sort on the UNROUNDED ratio. `round(ratio, 2)` is 0.0 for anything more
                    # than 200x cheaper than the pooled scalar -- and those cells exist -- so
                    # sorting on the published field divided by zero. The published value stays
                    # rounded for readability; the ordering uses what was actually measured.
                    "severity": round(max(ratio, 1.0 / ratio), 2),
                })
    rows.sort(key=lambda r: -r["severity"])
    return rows


def fill_bars(symbol: str, family: str, params: dict) -> tuple[list[int], list[float]] | None:
    """The hours a sleeve ACTUALLY fills on AND the spread recorded on those exact bars.

    Returns None when the tape or the family constructor is unreachable here -- a refusal, never
    an empty result. An empty list would read downstream as "this sleeve fills nowhere", which is
    the WS-005 shape: absence rendered as a measurement.

    WHY THE FILL BARS AND NOT THE SURFACE'S HOUR CELL, found when this fence first ran and
    reported DISPERSED over a live sleeve already measured at 2.5x. The surface prices an hour
    UNCONDITIONALLY, across every day. A family does not trade every day: `overnight_gap_decay`
    fires only when the overnight gap exceeds 0.75 ATR, and the book on exactly those mornings is
    wider than a typical one. USDZAR hour 01 costs 1,496 pts across all days and 2,028 pts on the
    days this sleeve actually fills -- so the unconditional cell reads 1.85x (under tolerance,
    silent) where the truth is 2.51x. Selection is part of the cost, and auditing a specific
    sleeve against an average over days it never trades is the same collapse this fence exists to
    catch, one level up.

    The surface's hour cell stays the right instrument for pricing a GENERIC cell at an hour --
    that is what `Costs.from_symbol(spread_pts=...)` consumes. This sharper number is available
    only because a sleeve names its own signal rule, and it is used only where it is available.
    """
    f = _UNIVERSE / f"{symbol}_H1.parquet"
    if not f.exists():
        return None
    try:
        import numpy as np
        import pandas as pd
        if str(_DESK) not in sys.path:
            sys.path.insert(0, str(_DESK))
        from research.shadow_forward import _family_fn
    except ImportError:
        return None
    fn = _family_fn(family)
    if fn is None:
        return None
    try:
        df = pd.read_parquet(f)
        try:
            sigs = fn(df, **(params or {}))
        except TypeError:
            sigs = fn(df, side=1, **(params or {}))
    except (OSError, ValueError, KeyError, TypeError):
        return None
    if not sigs:
        return None
    idx = pd.DatetimeIndex(df.index)
    # THE FILL BAR, NOT THE SIGNAL BAR. `run_backtest` fills at searchsorted(idx, sig.time) + 1
    # (engine.py: `i = i0 + 1`). Measuring the signal bar instead overstates this defect by ~2x
    # on the overnight families -- their signal is the day's first bar and the fill is the next
    # one, a different hour with a different book. Getting this wrong in the OTHER direction is
    # how a fence cries wolf until it gets switched off (L1.43).
    locs = np.searchsorted(
        np.asarray(idx.as_unit("ns").asi8, dtype="int64"),
        np.array([pd.Timestamp(s.time).value for s in sigs], dtype="int64"))
    fills = [int(i) + 1 for i in locs if 0 < int(i) + 1 < len(idx) - 1]
    if not fills:
        return None
    hours = [int(h) for h in idx[fills].hour]
    # Same two exclusions as the surface itself: a `spread == 0` bar is an ABSENT observation,
    # not a free fill, and averaging zeros in would report this sleeve as cheap precisely where
    # the tape says nothing at all.
    spreads = [float(v) for v in df["spread"].iloc[fills].tolist() if v and v > 0]
    return hours, spreads


def scan_sleeves(surface: dict, sleeves: dict) -> tuple[list[dict], list[dict]]:
    """Compare each live sleeve's FROZEN charged spread against its own fill-hour tape."""
    findings: list[dict] = []
    unresolved: list[dict] = []
    rows = (sleeves or {}).get("sleeves") or {}
    for key, sl in rows.items():
        if not isinstance(sl, dict) or sl.get("status") != "LIVE":
            continue
        ident = sl.get("identity") or {}
        sym = ident.get("symbol")
        fam = ident.get("family")
        srow = (surface.get("symbols") or {}).get(sym or "")
        cf = sl.get("cost_fields") or {}
        charged_lot = float(cf.get("spread_per_lot") or 0.0)
        if not (sym and fam and srow and charged_lot > 0):
            unresolved.append({"sleeve": key, "why": "no surface row or no frozen cost"})
            continue
        ts = float(srow.get("tick_size") or 0.0)
        cs = float(srow.get("contract_size") or 0.0)
        if ts <= 0 or cs <= 0:
            unresolved.append({"sleeve": key, "why": "no tick_size/contract_size to convert"})
            continue
        charged_pts = charged_lot / (ts * cs)
        got = fill_bars(sym, fam, ident.get("params") or {})
        if got is None:
            unresolved.append({"sleeve": key, "why": "fill bars unresolvable here"})
            continue
        hrs, fill_spreads = got
        if len(fill_spreads) < MIN_FILL_OBS:
            # This sleeve's own fill bars carry too few PRICED observations to state its cost.
            # Not OK, and deliberately not backfilled from the pooled scalar: substituting the
            # number under audit for the missing measurement is how the audit becomes circular.
            unresolved.append({"sleeve": key, "why": "too few priced fill bars to judge",
                               "n_priced": len(fill_spreads), "n_fills": len(hrs),
                               "hours": sorted(set(hrs))})
            continue
        import statistics
        true_pts = float(statistics.median(fill_spreads))
        ratio = true_pts / charged_pts if charged_pts > 0 else 0.0
        meas = _hours_measured(srow)
        hour_cells = [meas[h]["p50"] for h in hrs if h in meas]
        row = {
            "sleeve": key, "symbol": sym, "family": fam,
            "charged_pts": round(charged_pts, 1),
            "fill_bar_p50_pts": round(true_pts, 1),
            # Published beside it so the SELECTION effect stays visible rather than being
            # absorbed into one number: how the hour costs on an average day, against how it
            # costs on the days this sleeve trades.
            "surface_hour_p50_pts": (round(float(statistics.median(hour_cells)), 1)
                                     if hour_cells else None),
            "ratio": round(ratio, 2), "n_fills": len(hrs), "n_priced_fills": len(fill_spreads),
            "modal_fill_hour": max(set(hrs), key=hrs.count),
            "direction": "UNDERCHARGED" if ratio > 1 else "OVERCHARGED",
            "severity": round(max(ratio, 1.0 / ratio), 2) if ratio > 0 else float("inf"),
        }
        if ratio >= MATERIAL_RATIO or ratio <= 1.0 / MATERIAL_RATIO:
            findings.append(row)
    findings.sort(key=lambda r: -r["severity"])
    return findings, unresolved


def build_report() -> dict:
    now = datetime.now(tz=UTC)
    rep: dict = {"checked_at": now.isoformat(timespec="seconds"),
                 "material_ratio": MATERIAL_RATIO, "max_age_days": MAX_AGE_DAYS}
    surface = _load(_SURFACE)
    if not surface or not (surface.get("symbols") or {}):
        rep["status"] = "SURFACE-MISSING"
        rep["remedy"] = "run: .venv/bin/python desks/mt5/research/cost_surface.py"
        rep["scanned"] = 0
        return rep

    built = surface.get("built_at") or ""
    try:
        age = now - datetime.fromisoformat(built)
    except ValueError:
        age = timedelta(days=10_000)
    rep["surface_built_at"] = built
    rep["surface_age_days"] = round(age.total_seconds() / 86400.0, 2)
    rep["n_symbols"] = len(surface["symbols"])

    measured_cells = sum(len(_hours_measured(r)) for r in surface["symbols"].values())
    rep["measured_cells"] = measured_cells
    rep["unmeasured_cells"] = sum(
        1 for r in surface["symbols"].values()
        for c in (r.get("hours") or {}).values() if c.get("status") == "UNMEASURED")
    if measured_cells == 0:
        rep["status"] = "UNMEASURED"
        rep["scanned"] = 0
        return rep
    if age > timedelta(days=MAX_AGE_DAYS):
        rep["status"] = "STALE"
        rep["scanned"] = measured_cells
        return rep

    disp = scan_symbols(surface)
    rep["dispersed_cells"] = len(disp)
    rep["undercharged_cells"] = sum(1 for r in disp if r["direction"] == "UNDERCHARGED")
    rep["overcharged_cells"] = sum(1 for r in disp if r["direction"] == "OVERCHARGED")
    rep["worst_dispersion"] = disp[:25]

    sleeves = _load(_SLEEVES)
    if sleeves is None or not _UNIVERSE.exists():
        rep["status"] = "NOT-READABLE-HERE"
        rep["why"] = f"no sleeve registry or no H1 parquets under {_UNIVERSE}"
        rep["scanned"] = measured_cells
        return rep

    findings, unresolved = scan_sleeves(surface, sleeves)
    rep["live_sleeves_checked"] = sum(
        1 for s in (sleeves.get("sleeves") or {}).values()
        if isinstance(s, dict) and s.get("status") == "LIVE")
    rep["mispriced_sleeves"] = findings
    rep["unresolved_sleeves"] = unresolved
    rep["scanned"] = measured_cells
    rep["status"] = ("COST-BASIS-MISMATCH" if findings
                     else "DISPERSED" if disp else "OK")
    return rep


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--out", type=Path, default=_OUT)
    ap.add_argument("--quiet", action="store_true")
    args = ap.parse_args(argv)
    _law_guard()

    rep = build_report()
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(rep, indent=1, sort_keys=True) + "\n", "utf-8")

    if not args.quiet:
        print(f"cost-basis fence: {rep['status']}  "
              f"symbols={rep.get('n_symbols', 0)} measured_cells={rep.get('measured_cells', 0)} "
              f"unmeasured={rep.get('unmeasured_cells', 0)}")
        if rep.get("dispersed_cells") is not None:
            print(f"  material dispersion vs pooled scalar: {rep['dispersed_cells']} cells "
                  f"({rep['undercharged_cells']} undercharged, "
                  f"{rep['overcharged_cells']} OVERCHARGED -- the direction with no alert)")
        for f in rep.get("mispriced_sleeves", []):
            print(f"  MISMATCH {f['sleeve']}: charged {f['charged_pts']} pts, "
                  f"fill-bar (h{f['modal_fill_hour']:02d}) {f['fill_bar_p50_pts']} pts "
                  f"= {f['ratio']}x {f['direction']} over {f['n_fills']} fills")
        for u in rep.get("unresolved_sleeves", []):
            print(f"  UNRESOLVED {u['sleeve']}: {u['why']}")
    return fence_exit(rep["status"], _PASSING, scanned=rep.get("scanned"),
                      of="measured symbol-hour cells", fence="check_cost_surface")


if __name__ == "__main__":
    sys.exit(main())
