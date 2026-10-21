"""E8 GOLD SLIP -- one leg's fill-through, IN PRICE POINTS, measured from the lane's own stop exits.

`e8_gold` budgets a bracket as both legs' risk to their stops plus ONE leg's slip at the lot sent:

    sum(leg_risk) + slip_points x lot x contract  <=  room to the nearer floor

and `e8_gold.bracket_slip` reads `slip_points` from data/E8_GOLD_SLIP.json -- but only once the
file is MEASURED on at least `e8_gold.MIN_SLIP_EXITS` (20) stop exits. Until then the lane uses
DEFAULT_SLIP_POINTS, 24.13: the worst single-leg fill-through measured (2026-09-24).

POINTS, NEVER R (audit HOLD on 3ce5aaf85, 2026-10-20). A fill-through is a price distance the
venue's market moved past the level; it does not scale with the stop. 24.13 points was 0.82R of
that day's 29.55-point stop, 1.86R of a 13-point one and 0.22R of a 110-point one.

THE MEASURE, per stop exit:

    slip_points = (exit side sell: stop - fill; buy: fill - stop)   [+ entry fill-through]

the price distance the protective stop filled beyond its level, plus, when the row names the
intended trigger, how far the entry filled beyond it. A stop filled at its level is 0.

SOURCES. `e8_gold` journals each stop exit it sees in the venue's order history to
data/e8_gold_stop_exits.jsonl (with the window that opened it) and, on EVERY pass after placement,
re-measures this file (`refresh`, via `e8_gold.publish_slip`), pooled and per window, and
publishes the same block into reports/E8_GOLD.json["slip"]. A failure there only logs and
publishes UNMEASURED; the guard keeps 24.13 points. A CSV of past fills can be added:
`--fills <csv>`, columns side (of the EXIT order: buy/sell), stop, fill; optional trigger, entry,
entry_side.

NO FILLS, NO NUMBER. Under MIN_EXITS stop exits the file is written UNMEASURED with n, the
provisional p95 if any, the sources read and what is missing; it carries no `slip_points`, so the
lane keeps its default. A number is never invented here.

    python prop/e8_gold_slip.py [--fills <csv>]... [--measured-at 2026-10-20]
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
STOP_EXITS = DESK / "data" / "e8_gold_stop_exits.jsonl"
#: The quantile written as `slip_points`: the bracket budget is a tail bound, not a mean.
QUANTILE = 0.95
#: Stop exits needed before the p95 is MEASURED (mirrors e8_gold.MIN_SLIP_EXITS).
MIN_EXITS = 20

#: What a measurement needs that this repository did not hold on 2026-10-20.
MISSING = (
    "exit fills of the E8 gold positions before the lane journalled them: the venue's filled "
    "stop-loss orders (fill price and the stopPrice in force) per position id. TradeLocker's "
    "order history holds them; no tracked file does, and the lane's history read looks back 2 "
    "days, so exits older than that are recorded only if exported (--fills)",
)


def _f(row: dict[str, Any], key: str) -> float | None:
    try:
        v = row.get(key)
        x = float(v) if v not in (None, "") else None
    except (TypeError, ValueError):
        return None
    return x if x is not None and math.isfinite(x) else None


def exit_slip_points(row: dict[str, Any]) -> float | None:
    """How far one stop exit filled beyond its level, in price points (plus the entry's
    fill-through past its trigger when the row names both). None when unreadable. Pure."""
    side = str(row.get("side") or "").strip().lower()
    stop, fill = _f(row, "stop"), _f(row, "fill")
    if side not in ("buy", "sell") or stop is None or fill is None or not stop > 0:
        return None
    pts = (stop - fill) if side == "sell" else (fill - stop)
    trigger, entry = _f(row, "trigger"), _f(row, "entry")
    entry_side = str(row.get("entry_side") or "").strip().lower()
    if trigger is not None and entry is not None and entry_side in ("buy", "sell"):
        pts += (entry - trigger) if entry_side == "buy" else (trigger - entry)
    return pts


def quantile(xs: list[float], q: float) -> float:
    """Linear-interpolated quantile of a non-empty list. Pure."""
    v = sorted(xs)
    if len(v) == 1:
        return v[0]
    pos = q * (len(v) - 1)
    lo = math.floor(pos)
    hi = min(lo + 1, len(v) - 1)
    return v[lo] + (v[hi] - v[lo]) * (pos - lo)


def _per_window(rows: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    """The same measure per window (rows without a `window` are pooled only). Pure."""
    by: dict[str, list[float]] = {}
    for r in rows:
        w, x = r.get("window"), exit_slip_points(r)
        if w and x is not None:
            by.setdefault(str(w), []).append(x)
    out: dict[str, dict[str, Any]] = {}
    for w, xs in sorted(by.items()):
        p95, mx = round(quantile(xs, QUANTILE), 4), round(max(xs), 4)
        if len(xs) < MIN_EXITS:
            out[w] = {"status": "UNMEASURED", "n": len(xs), "provisional_p95_points": p95,
                      "max_points": mx}
        else:
            out[w] = {"status": "MEASURED", "n": len(xs), "slip_points": round(max(0.0, p95), 4),
                      "max_points": mx}
    return out


def measure(rows: list[dict[str, Any]], *, sources: list[str], measured_at: str,
            notes: list[str] | None = None) -> dict[str, Any]:
    """The E8_GOLD_SLIP.json document for these stop exits. Pure."""
    samples = [x for x in (exit_slip_points(r) for r in rows) if x is not None]
    base: dict[str, Any] = {"measured_at": measured_at, "n": len(samples),
                            "rows_read": len(rows), "quantile": QUANTILE, "unit": "points",
                            "min_n": MIN_EXITS,
                            "measure": "one stop exit's fill beyond its level, in price points",
                            "sources": list(sources)}
    if notes:
        base["notes"] = list(notes)
    base["windows"] = _per_window(rows)
    if len(samples) < MIN_EXITS:
        doc = {**base, "status": "UNMEASURED", "missing": list(MISSING),
               "why": (f"{len(samples)} stop exits measured, under {MIN_EXITS}: the lane keeps "
                       f"its default slip")}
        if samples:
            doc["provisional_p95_points"] = round(quantile(samples, QUANTILE), 4)
            doc["max_points"] = round(max(samples), 4)
        return doc
    return {**base, "status": "MEASURED",
            "slip_points": round(max(0.0, quantile(samples, QUANTILE)), 4),
            "p50_points": round(quantile(samples, 0.5), 4), "max_points": round(max(samples), 4)}


def read_fills(path: Path) -> list[dict[str, Any]]:
    with path.open(encoding="utf-8-sig", newline="") as fh:
        return [dict(r) for r in csv.DictReader(fh)]


def read_stop_exits(path: Path = STOP_EXITS) -> list[dict[str, Any]]:
    """The lane's journalled stop exits; a missing or unreadable file is none."""
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except (OSError, UnicodeDecodeError):
        return []
    rows: list[dict[str, Any]] = []
    for ln in lines:
        try:
            r = json.loads(ln) if ln.strip() else None
        except ValueError:
            continue
        if isinstance(r, dict):
            rows.append(r)
    return rows


def write(doc: dict[str, Any], path: Path = OUT) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    body = json.dumps(doc, indent=1) + "\n"
    tmp = path.with_name(path.name + ".tmp")
    try:
        tmp.write_text(body, encoding="utf-8")
        tmp.replace(path)
    except OSError:
        path.write_text(body, encoding="utf-8")
    return path


def refresh(*, exits: Path = STOP_EXITS, out: Path = OUT, measured_at: str | None = None,
            notes: list[str] | None = None) -> dict[str, Any]:
    """Re-measure from the lane's stop-exit journal and write the file. Called by `e8_gold`'s
    pass; a previous file's notes and other sources are carried forward so its provenance is not
    lost (the journal's own line is re-counted)."""
    kept: list[str] = []
    try:
        prev = json.loads(out.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        prev = None
    if isinstance(prev, dict):
        if notes is None:
            notes = [str(x) for x in prev.get("notes") or []]
        kept = [str(x) for x in prev.get("sources") or []
                if not str(x).startswith(f"data/{exits.name}")]
    rows = read_stop_exits(exits)
    doc = measure(rows, sources=[*kept, f"data/{exits.name} ({len(rows)} rows)"],
                  measured_at=measured_at or datetime.now(tz=UTC).date().isoformat(),
                  notes=notes)
    write(doc, out)
    return doc


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--fills", type=Path, action="append", default=[])
    ap.add_argument("--source", action="append", default=[])
    ap.add_argument("--note", action="append", default=[],
                    help="context recorded on the file; never counted as a sample")
    ap.add_argument("--measured-at", default=datetime.now(tz=UTC).date().isoformat())
    ap.add_argument("--exits", type=Path, default=STOP_EXITS)
    ap.add_argument("--out", type=Path, default=OUT)
    a = ap.parse_args(argv)
    rows = read_stop_exits(a.exits)
    sources = [*a.source, f"data/{a.exits.name} ({len(rows)} rows)"]
    for p in a.fills:
        extra = read_fills(p)
        rows.extend(extra)
        sources.append(f"{p} ({len(extra)} rows)")
    doc = measure(rows, sources=sources, measured_at=a.measured_at, notes=a.note)
    write(doc, a.out)
    print(f"E8 GOLD SLIP {doc['status']} n={doc['n']} slip_points={doc.get('slip_points')} "
          f"-> {a.out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
