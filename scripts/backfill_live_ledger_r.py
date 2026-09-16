"""Backfill the R multiple on live-ledger rows written while the writer floored it at zero.

THE ZERO THAT JUDGED EVERY SLEEVE (measured 2026-09-16). `mt5desk.decision_core.closed_trade_r`
took `is_buy` from the CLOSING deal, whose type is the opposite of the position's, so the signed
stop distance came out negative, was floored at zero, and every row the desk had ever written
carried `r_multiple: 0.0` -- 141 of 151 rows on the trading box -- with entry, stop, volume and
contract size all present on the row. The writer is fixed (the distance is |entry - stop|); the
rows it wrote before the fix still read zero, and every organ that learns from realised R
(credit_assignment, posterior_alpha, hazard_engine, standing_questions Q5, the scorecard's
attribution row) reads them as evidence of no edge. This recomputes R for exactly those rows
from the numbers already on them, marks each one `r_backfilled` with its basis, and touches
nothing else.

THE BASIS IS STATED, NOT HIDDEN. The row carries the contract size but not the venue's tick
value, so risk is distance x contract_size x volume in the QUOTE currency while P&L is in the
account currency; the ratio is exact when the two coincide (EUR-quoted symbols on this EUR
account) and off by the quote/account rate otherwise -- a few percent, labelled, against a zero
that was wrong by everything. A row without entry, stop or volume stays unreconstructible.

    python scripts/backfill_live_ledger_r.py [--ledger PATH] [--apply]
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
LEDGER = ROOT / "desks" / "mt5" / "data" / "live_ledger.jsonl"


def recompute(row: dict[str, Any]) -> tuple[float | None, str]:
    """(r_multiple, basis) for a row whose R was floored, or (None, why) when it cannot be."""
    try:
        entry = float(row.get("entry_price") or 0.0)
        sl = float(row.get("sl") or 0.0)
        vol = float(row.get("volume") or 0.0)
        contract = float(row.get("contract_size") or 0.0)
        pl = float(row.get("pl_quote") or 0.0)
    except (TypeError, ValueError):
        return None, "non-numeric fields"
    if entry <= 0 or sl <= 0:
        return None, "entry or stop absent: unreconstructible"
    dist = abs(entry - sl)
    if dist <= 0 or vol <= 0 or contract <= 0:
        return None, "zero distance, volume or contract size"
    risk = dist * contract * vol
    return pl / risk, "backfill: |entry-stop| x contract_size x volume (quote ccy) vs account P&L"


def backfill(rows: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], dict[str, int]]:
    out: list[dict[str, Any]] = []
    counts = {"rows": len(rows), "backfilled": 0, "kept": 0, "unreconstructible": 0}
    for r in rows:
        if not isinstance(r, dict):
            out.append(r)
            continue
        rm = r.get("r_multiple")
        floored = isinstance(rm, (int, float)) and float(rm) == 0.0 and not r.get("r_backfilled")
        if not floored or r.get("r_unreconstructible"):
            counts["kept"] += 1
            out.append(r)
            continue
        val, basis = recompute(r)
        if val is None:
            counts["unreconstructible"] += 1
            out.append({**r, "r_unreconstructible": True, "r_backfill_why": basis})
            continue
        counts["backfilled"] += 1
        out.append({**r, "r_multiple": round(val, 4), "r_backfilled": True, "r_basis": basis,
                    "r_multiple_before": rm})
    return out, counts


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--ledger", default=str(LEDGER))
    ap.add_argument("--apply", action="store_true", help="rewrite the ledger in place (atomic)")
    a = ap.parse_args(argv)
    p = Path(a.ledger)
    if not p.exists():
        print(f"backfill: {p} absent; nothing to do")
        return 0
    rows: list[Any] = []
    for ln in p.read_text(encoding="utf-8", errors="replace").splitlines():
        if not ln.strip():
            continue
        try:
            rows.append(json.loads(ln))
        except ValueError:
            rows.append({"_unparsed": ln})
    new, counts = backfill([r for r in rows if isinstance(r, dict) and "_unparsed" not in r])
    print(f"backfill: {counts['rows']} row(s): {counts['backfilled']} backfilled, "
          f"{counts['kept']} kept, {counts['unreconstructible']} unreconstructible"
          f"{'' if a.apply else ' (dry run -- pass --apply)'}")
    if a.apply and counts["backfilled"]:
        tmp = p.with_suffix(".jsonl.tmp")
        with tmp.open("w", encoding="utf-8") as f:
            for r in rows:
                if isinstance(r, dict) and "_unparsed" in r:
                    f.write(r["_unparsed"] + "\n")
            for r in new:
                f.write(json.dumps(r, ensure_ascii=False) + "\n")
        os.replace(tmp, p)
        print(f"-> {p}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
