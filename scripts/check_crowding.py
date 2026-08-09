#!/usr/bin/env python3
"""CROWDING FENCE -- is a competitor sitting on OUR carry names? (§42 capacity, L1.19 decay)

WHY THIS FENCE EXISTS. The desk's capacity assumption is that its carry names are too small for
funds to bother with. That assumption has never been INSTRUMENTED. If it stops being true the tell
arrives before the P&L does: funding compresses on the specific symbols we hold, our fills degrade
at unchanged size, basis narrows faster than the venue's own average. By the time it shows in
returns the capacity is already gone, because a crowded edge does not announce itself -- it just
pays less, and a book that reads only its own P&L cannot tell "the trade got crowded" from "the
month was quiet" until several months of both have gone by.

WHAT THE INCUMBENT ORGAN CANNOT SEE, and why this is not a duplicate. `run_carry_crowding.py`
measures the top-20 AVERAGE funding rate against its own backtest 25th percentile -- a market-wide
question with a market-wide answer. Our held names are INSIDE that average, so a competitor
compressing exactly our book is diluted ~4:1 and partially subtracted as its own benchmark. This
fence takes the RESIDUAL instead: our rate minus the cross-section at the same instant
(`libs/research/crowding.py`). Level is the market; residual is ours.

FENCE STATUS (exit 2 on everything but OK -- a gate, not a report; ALL live breaches are listed in
`breaches`, never just the headline):
  NO-TAPE        the cross-sectional funding tape is absent or too short. Crowding is a statement
                 about a rate RELATIVE to its cross-section, so with no universe there is no
                 measurement -- not a clean bill of health.
  FLAT-BOOK      the tape has depth but the desk holds nothing. HONESTLY DISTINCT FROM OK: a flat
                 book is unmeasurable, not uncrowded, and collapsing the two would let a paused
                 sleeve read as a healthy one for as long as the pause lasts.
  UNMEASURED     held names exist but no name has enough aligned snapshots to support a t. Names
                 opened after the tape started accrue into this until they clear MIN_SNAPSHOTS.
  CROWDING       held names compressed against the cross-section on BOTH tells (residual in bps
                 AND cross-sectional rank). This is the capacity alarm.
  OK             held names tested against a real universe, no significant residual compression.

THE SECOND TELL IS REPORTED SEPARATELY AND HONESTLY. Fill-quality drift at unchanged size is the
other half of the ask, and it is currently UNMEASURABLE: only 12 of 531 rows on the execution tape
carry `spot_slip_bps`/`fut_slip_bps` (TCA landed 2026-07-27; everything before it is blind). This
fence reports that coverage as a number rather than skipping the tell, because an unmeasured tell
counts as zero measurement (L1.28a) and silence would read as absence.

THIS FENCE NEVER RESIZES ANYTHING. Crowding is capacity evidence and routes to a review, never to
an autonomous sizing change from a single new signal.

    python scripts/check_crowding.py [--report-only] [--json]
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from libs.ops.lawful import guard as _law_guard  # noqa: E402
from libs.research.crowding import (  # noqa: E402
    MIN_SNAPSHOTS,
    SymbolCrowding,
    assess,
    symbol_crowding,
)

_TAPE = _ROOT / "data/funding_cross_section.jsonl"
_POSITIONS = _ROOT / "data/cashcarry_positions.json"
_EXEC_TAPE = _ROOT / "data/moat/execution_tape/cashcarry_trades.jsonl"

#: Snapshots needed before the tape can support any residual test at all.
MIN_TAPE_ROWS = MIN_SNAPSHOTS

#: Slippage rows needed before a fill-quality drift claim is worth making. Matches the desk's own
#: floor for a t-statistic rather than inventing a second one.
MIN_SLIP_ROWS = 20


def _load_tape(path: Path = _TAPE) -> list[dict[str, Any]]:
    """Snapshots oldest-first, ordered by RECEIPT (L1.46: mixed-clock files order by receipt)."""
    if not path.exists():
        return []
    rows: list[dict[str, Any]] = []
    for line in path.read_text("utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            r = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(r, dict) and isinstance(r.get("rates"), dict) and r.get("t"):
            rows.append(r)
    rows.sort(key=lambda r: int(r["t"]))
    return rows


def _held(path: Path = _POSITIONS) -> dict[str, dict[str, Any]]:
    if not path.exists():
        return {}
    try:
        st = json.loads(path.read_text("utf-8"))
    except (json.JSONDecodeError, OSError):
        return {}
    pos = st.get("positions") if isinstance(st, dict) else None
    return pos if isinstance(pos, dict) else {}


def _slippage_coverage(path: Path = _EXEC_TAPE) -> dict[str, int]:
    """How much of the execution tape can support a fill-quality drift claim at all."""
    total = measured = 0
    if not path.exists():
        return {"rows": 0, "with_slippage": 0}
    for line in path.read_text("utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            r = json.loads(line)
        except json.JSONDecodeError:
            continue
        if not isinstance(r, dict):
            continue
        total += 1
        if r.get("spot_slip_bps") is not None or r.get("fut_slip_bps") is not None:
            measured += 1
    return {"rows": total, "with_slippage": measured}


def _opened_ms(rec: dict[str, Any]) -> int | None:
    raw = rec.get("opened")
    if not raw:
        return None
    try:
        return int(datetime.fromisoformat(str(raw)).timestamp() * 1000)
    except (TypeError, ValueError):
        return None


def build_report(tape: list[dict[str, Any]] | None = None,
                 held: dict[str, dict[str, Any]] | None = None) -> dict[str, Any]:
    now = datetime.now(tz=UTC)
    tape = _load_tape() if tape is None else tape
    held = _held() if held is None else held
    slip = _slippage_coverage()

    per_symbol: list[SymbolCrowding] = []
    skipped: dict[str, str] = {}
    for sym, rec in sorted(held.items()):
        since = _opened_ms(rec) or 0
        rates: list[float] = []
        universes: list[list[float]] = []
        for row in tape:
            if int(row["t"]) < since:
                continue
            r = row["rates"].get(sym)
            if r is None:
                continue
            uni = [float(v) for v in row["rates"].values()]
            rates.append(float(r))
            universes.append(uni)
        sc = symbol_crowding(sym, rates, universes)
        if sc is None:
            skipped[sym] = f"{len(rates)}/{MIN_SNAPSHOTS} aligned snapshots since open"
        else:
            per_symbol.append(sc)

    book = assess(per_symbol)

    breaches: list[str] = []
    if len(tape) < MIN_TAPE_ROWS:
        breaches.append(f"NO-TAPE: {len(tape)}/{MIN_TAPE_ROWS} cross-sectional snapshots -- "
                        f"crowding has no denominator until the collector accrues")
    if slip["with_slippage"] < MIN_SLIP_ROWS:
        breaches.append(f"SLIPPAGE-UNMEASURED: {slip['with_slippage']}/{slip['rows']} execution "
                        f"tape rows carry TCA -- the fill-quality tell cannot be tested "
                        f"(needs {MIN_SLIP_ROWS})")
    if skipped:
        breaches.append("ACCRUING: " + ", ".join(f"{k} ({v})" for k, v in sorted(skipped.items())))
    if book["verdict"] == "CROWDING":
        breaches.append(f"CROWDING: {book['detail']}")

    if len(tape) < MIN_TAPE_ROWS:
        status = "NO-TAPE"
        detail = (f"{len(tape)} cross-sectional snapshot(s) on tape; a residual needs a universe "
                  f"at the same instant, so nothing is measurable yet. The collector "
                  f"(collect_funding_cross_section.py) is the producer -- an absent tape is a "
                  f"scheduling defect, never a quiet book")
    elif not held:
        status = "FLAT-BOOK"
        detail = (f"{len(tape)} snapshot(s) on tape but the desk holds nothing -- unmeasurable, "
                  f"NOT uncrowded. Held names are the numerator and there are none")
    elif not per_symbol:
        status = "UNMEASURED"
        detail = (f"{len(held)} held name(s), none with {MIN_SNAPSHOTS} aligned snapshots yet: "
                  + "; ".join(f"{k} {v}" for k, v in sorted(skipped.items())))
    elif book["verdict"] == "CROWDING":
        status = "CROWDING"
        detail = book["detail"]
    else:
        status = "OK"
        detail = book["detail"]

    return {
        "generated": now.isoformat(),
        "law": ("§42 capacity parity / L1.19 information decay -- an edge that is being crowded "
                "pays less before it stops paying, and the desk must measure the compression on "
                "ITS OWN names against the cross-section rather than read the market average"),
        "status": status,
        "detail": detail,
        "breaches": breaches,
        "n_snapshots": len(tape),
        "tape_first": tape[0]["t"] if tape else None,
        "tape_last": tape[-1]["t"] if tape else None,
        "universe_width": tape[-1].get("n") if tape else 0,
        "n_held": len(held),
        "n_tested": len(per_symbol),
        "accruing": skipped,
        "book_verdict": book["verdict"],
        "compressing": book["compressing"],
        "confirmed_both_tells": book.get("confirmed_both_tells", []),
        "per_symbol": [
            {"symbol": s.symbol, "n": s.n_snapshots,
             "residual_bps_early": s.residual_bps_early, "residual_bps_late": s.residual_bps_late,
             "residual_drift_bps": s.residual_drift_bps, "percentile_drift": s.percentile_drift,
             "t_stat": s.t_stat, "sufficient": s.sufficient, "reason": s.reason}
            for s in per_symbol],
        "slippage_tell": {
            **slip,
            "testable": slip["with_slippage"] >= MIN_SLIP_ROWS,
            "note": ("the fill-quality half of the crowding ask -- degrading slippage at UNCHANGED "
                     "size. TCA landed 2026-07-27; rows before it carry no slip fields, so this "
                     "tell is coverage-bound, not signal-bound"),
        },
        "not_a_duplicate_of": ("scripts/run_carry_crowding.py measures the top-20 AVERAGE (market "
                               "level); this measures the RESIDUAL on held names (ours). A "
                               "competitor on our book moves the second and not the first"),
        "next_action": (
            "schedule collect_funding_cross_section.py -- the tape is the denominator and every "
            "uncollected hour is permanently unbuyable"
            if len(tape) < MIN_TAPE_ROWS else
            "book is flat; the tape keeps accruing so the measure is live the day a position opens"
            if not held else
            "hold: named symbols need more aligned snapshots" if not per_symbol else
            "route to capacity review -- crowding evidence never resizes autonomously"
            if status == "CROWDING" else
            "none: held names carry no significant residual compression"),
    }


def main() -> int:
    _law_guard()
    ap = argparse.ArgumentParser()
    ap.add_argument("--report-only", action="store_true")
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args()
    rep = build_report()
    out = _ROOT / "data/crowding_status.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(rep, indent=2) + "\n", "utf-8")
    if args.json:
        print(json.dumps(rep, indent=2))
    else:
        print(f"crowding (§42): {rep['status']} -- {rep['detail']}")
        print(f"  snapshots {rep['n_snapshots']} (universe {rep['universe_width']}) | "
              f"held {rep['n_held']} | tested {rep['n_tested']} | "
              f"slippage rows {rep['slippage_tell']['with_slippage']}/"
              f"{rep['slippage_tell']['rows']}")
        for s in rep["per_symbol"]:
            print(f"    {s['symbol']}: residual {s['residual_drift_bps']:+.2f}bps "
                  f"pct {s['percentile_drift']:+.3f} t={s['t_stat']:.2f} n={s['n']}")
        for b in rep["breaches"]:
            print(f"  BREACH: {b}")
        print(f"  next: {rep['next_action']}")
    if args.report_only:
        return 0
    return 2 if rep["status"] != "OK" else 0


if __name__ == "__main__":
    sys.exit(main())
