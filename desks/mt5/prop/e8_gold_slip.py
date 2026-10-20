"""E8 GOLD SLIP -- the fill-through the bracket lane's floor budget is grossed up by, measured.

`e8_gold.bracket_floor_breach` requires n_legs x leg_risk x (1 + slip) <= the room to today's
floor, and `e8_gold.bracket_slip` reads `slip` from data/E8_GOLD_SLIP.json, falling back to
DEFAULT_BRACKET_SLIP (0.3) when the file is absent or UNMEASURED. This module writes that file
from the lane's own fills, and only from them.

THE MEASURE. For every E8 gold trade that exited ON ITS STOP (the exit is at or through the stop
level on the losing side), the realised loss beyond the stop, in R of the trade's planned stop
distance:

    slip_r = (ref - exit) * dir / |ref - stop| - 1

where `ref` is the intended trigger level when the row carries it (so an entry that filled
through its trigger counts too) and the entry fill otherwise, and `stop` is the stop IN FORCE at
the exit (a ratcheted stop when the row names one). A stop filled exactly at its level is 0; the
2026-09-24 short whose ratcheted stop filled 24.13 points through is +0.82R. The file carries the
p95 of slip_r with n, the measurement date and the sources.

NO FILLS, NO NUMBER. With no stop exit to measure the file is written UNMEASURED, with `n: 0`, the
sources it looked at and what is missing; it carries no `slip`, so the lane keeps the fallback.
A number is never invented here.

    python prop/e8_gold_slip.py --fills <csv> [--source <label>]... [--measured-at 2026-10-20]

CSV columns: side (buy/sell/long/short), entry, sl, exit; optional trigger, stop_at_exit,
position_id.
"""
from __future__ import annotations

import argparse
import csv
import json
import math
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

DESK = Path(__file__).resolve().parents[1]
OUT = DESK / "data" / "E8_GOLD_SLIP.json"
#: The quantile written as `slip`: the bracket budget is a tail bound, not a mean.
QUANTILE = 0.95
#: How close to the stop level an exit must sit to count as a stop exit, as a fraction of R:
#: a target or time exit is never mistaken for a stop that filled better than its level.
STOP_EXIT_TOL_R = 0.05

#: What a measurement needs and this repository does not hold (2026-10-20). Written into an
#: UNMEASURED file so the gap is stated where the number would be.
MISSING = (
    "exit fills of the E8 gold positions: the venue's filled stop-loss orders (fill price and "
    "the stopPrice in force), or closed-position history, per position id. TradeLocker holds "
    "them (get_all_orders(history=True)); no tracked file does",
    "the intended trigger level of each leg, which `data/e8_gold_intents.jsonl` (SENT rows: "
    "price, sl) holds on the box and is not tracked in git",
)


def _f(row: dict[str, Any], key: str) -> float | None:
    try:
        v = row.get(key)
        x = float(v) if v not in (None, "") else None
    except (TypeError, ValueError):
        return None
    return x if x is not None and math.isfinite(x) else None


def trade_slip_r(row: dict[str, Any]) -> float | None:
    """The loss beyond the stop of one trade, in R, or None when it did not exit on its stop
    (or a field it needs is missing). Pure."""
    side = str(row.get("side") or "").strip().lower()
    if side not in ("buy", "sell", "long", "short"):
        return None
    sign = 1.0 if side in ("buy", "long") else -1.0
    entry, sl, exit_ = _f(row, "entry"), _f(row, "sl"), _f(row, "exit")
    ref = _f(row, "trigger") or entry
    stop = _f(row, "stop_at_exit") or sl
    if ref is None or sl is None or exit_ is None or stop is None:
        return None
    dist = abs(ref - sl)
    if not dist > 0:
        return None
    # A stop exit: the exit sits at or past the stop in force, on the losing side.
    if sign * (exit_ - stop) > STOP_EXIT_TOL_R * dist:
        return None
    planned = sign * (ref - stop) / dist          # 1.0 for an original stop, less if ratcheted
    return sign * (ref - exit_) / dist - planned


def quantile(xs: list[float], q: float) -> float:
    """Linear-interpolated quantile of a non-empty list. Pure."""
    v = sorted(xs)
    if len(v) == 1:
        return v[0]
    pos = q * (len(v) - 1)
    lo = math.floor(pos)
    hi = min(lo + 1, len(v) - 1)
    return v[lo] + (v[hi] - v[lo]) * (pos - lo)


def measure(rows: list[dict[str, Any]], *, sources: list[str], measured_at: str,
            notes: list[str] | None = None) -> dict[str, Any]:
    """The E8_GOLD_SLIP.json document for these fills. Pure."""
    samples = [x for x in (trade_slip_r(r) for r in rows) if x is not None]
    base: dict[str, Any] = {"measured_at": measured_at, "n": len(samples),
                            "rows_read": len(rows), "quantile": QUANTILE, "unit": "R",
                            "measure": "realised loss beyond the stop in force, in R of the "
                                       "planned stop distance, over stop exits",
                            "sources": list(sources)}
    if notes:
        base["notes"] = list(notes)
    if not samples:
        return {**base, "status": "UNMEASURED", "missing": list(MISSING),
                "why": "no stop exit among the fills read: the lane keeps its fallback slip"}
    return {**base, "status": "MEASURED", "slip": round(max(0.0, quantile(samples, QUANTILE)), 4),
            "p50": round(quantile(samples, 0.5), 4), "max": round(max(samples), 4)}


def read_fills(path: Path) -> list[dict[str, Any]]:
    with path.open(encoding="utf-8-sig", newline="") as fh:
        return [dict(r) for r in csv.DictReader(fh)]


def write(doc: dict[str, Any], path: Path = OUT) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(doc, indent=1) + "\n", encoding="utf-8")
    return path


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--fills", type=Path, action="append", default=[])
    ap.add_argument("--source", action="append", default=[])
    ap.add_argument("--note", action="append", default=[],
                    help="context recorded on the file; never counted as a sample")
    ap.add_argument("--measured-at", default=datetime.now(tz=UTC).date().isoformat())
    ap.add_argument("--out", type=Path, default=OUT)
    a = ap.parse_args(argv)
    rows: list[dict[str, Any]] = []
    for p in a.fills:
        rows.extend(read_fills(p))
    doc = measure(rows, sources=[*a.source, *(str(p) for p in a.fills)],
                  measured_at=a.measured_at, notes=a.note)
    write(doc, a.out)
    print(f"E8 GOLD SLIP {doc['status']} n={doc['n']} slip={doc.get('slip')} -> {a.out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
