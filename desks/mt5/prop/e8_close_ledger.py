"""THE E8 CLOSED-TRADE LEDGER: every E8 position this desk opened, once it closes, with its R.

Until 2026-10-13 the E8 lanes journalled what they SENT (e8_intents.jsonl, e8_gold_intents.jsonl)
and nothing recorded what came back: no fill, no exit, no R. So an E8 loss could not be
autopsied, a sizing fault on E8 could not be seen, and "traceable on E8" (principal 2026-10-13)
held only up to the send. This closes that: on each E8 pass it reads the venue's own order
history, groups the FILLED orders by position, and for every position that is no longer open
and whose opening order is one of OUR journalled sends, appends one row to data/e8_ledger.jsonl.

    R            side x (exit - entry) / |entry - stop|, from the venue's average fill prices and
                 the stop our own journal sent -- currency-free, so no conversion can be wrong
    pl_usd_est   R x the risk the lane charged for the lot it sent, scaled by the filled
                 quantity: an estimate, and labelled one (`pl_basis`)
    risk_frac    the charged risk over E8's starting balance, the unit the E8 book is sized in

Idempotent on position id. A position whose opening order is not in either journal is not this
desk's and is never written. A field the venue does not return leaves the row UNMEASURED on it,
never zero. Nothing here sends, modifies or closes anything.

Consumer: research/loss_autopsy.py (the E8 half of the hourly loss autopsy).
"""
from __future__ import annotations

import json
from collections import defaultdict
from collections.abc import Iterable, Mapping
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

DESK = Path(__file__).resolve().parents[1]
LEDGER = DESK / "data" / "e8_ledger.jsonl"
JOURNALS = (DESK / "data" / "e8_intents.jsonl", DESK / "data" / "e8_gold_intents.jsonl")
START_BALANCE = 100_000.0           # `e8_guard.START_BALANCE`; pinned by the ledger's test
LOOKBACK = "7D"
UNMEASURED = "UNMEASURED"


def _f(v: Any) -> float | None:
    try:
        x = float(v)
    except (TypeError, ValueError):
        return None
    return x if x == x else None


def _first(row: Mapping[str, Any], *keys: str) -> Any:
    for k in keys:
        if row.get(k) not in (None, ""):
            return row[k]
    return None


def _jsonl(path: Path) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    try:
        with path.open(encoding="utf-8") as fh:
            for line in fh:
                try:
                    r = json.loads(line)
                except ValueError:
                    continue
                if isinstance(r, dict):
                    out.append(r)
    except OSError:
        pass
    return out


def our_sends(journals: Iterable[list[dict[str, Any]]]) -> dict[int, dict[str, Any]]:
    """order id -> the journal row that sent it, across both E8 lanes."""
    out: dict[int, dict[str, Any]] = {}
    for rows in journals:
        for r in rows:
            oid = _f(r.get("order_id"))
            if r.get("status") == "SENT" and oid:
                out[int(oid)] = r
    return out


def closed_positions(history: list[dict[str, Any]], open_ids: set[int],
                     sends: Mapping[int, dict[str, Any]], *, done: set[str],
                     now: datetime) -> list[dict[str, Any]]:
    by_pos: dict[int, list[dict[str, Any]]] = defaultdict(list)
    for o in history:
        if str(o.get("status") or "").lower() != "filled":
            continue
        pid = _f(o.get("positionId"))
        if pid:
            by_pos[int(pid)].append(o)
    rows: list[dict[str, Any]] = []
    for pid, orders in sorted(by_pos.items()):
        if pid in open_ids or str(pid) in done:
            continue
        orders.sort(key=lambda o: (str(_first(o, "createdDate", "lastModified") or ""),
                                   int(_f(o.get("id")) or 0)))
        opening = next((o for o in orders if int(_f(o.get("id")) or 0) in sends), None)
        if opening is None:
            continue                                   # not one of this desk's sends
        send = sends[int(_f(opening.get("id")) or 0)]
        closing = [o for o in orders if o is not opening]
        side = 1.0 if str(opening.get("side") or send.get("side") or "").lower() == "buy" \
            else -1.0
        entry = _f(_first(opening, "avgPrice", "price"))
        qty_c = sum(_f(_first(o, "filledQty", "qty")) or 0.0 for o in closing)
        exit_px = (sum((_f(_first(o, "avgPrice", "price")) or 0.0)
                       * (_f(_first(o, "filledQty", "qty")) or 0.0) for o in closing) / qty_c
                   if qty_c > 0 else None)
        stop = _f(_first(send, "stop", "sl"))
        qty = _f(_first(opening, "filledQty", "qty"))
        lot = _f(send.get("lot"))
        risk = _f(send.get("risk_usd"))
        r = (side * (exit_px - entry) / abs(entry - stop)
             if entry is not None and exit_px is not None and stop is not None
             and abs(entry - stop) > 1e-12 else None)
        scale = (qty / lot) if qty and lot else 1.0
        rows.append({
            "time": now.isoformat(timespec="seconds"), "venue": "e8", "position_id": pid,
            "order": int(_f(opening.get("id")) or 0),
            "sleeve": _first(send, "sleeve", "name", "window") or UNMEASURED,
            "symbol": _first(send, "symbol") or opening.get("tradableInstrumentId"),
            "side": "buy" if side > 0 else "sell", "qty": qty, "entry_price": entry,
            "exit_price": exit_px, "stop": stop, "intent_at": send.get("at"),
            "latency_send_to_ack_ms": send.get("latency_send_to_ack_ms"),
            "r_multiple": round(r, 4) if r is not None else UNMEASURED,
            "risk_usd": risk if risk is not None else UNMEASURED,
            "risk_frac": round(risk * scale / START_BALANCE, 6) if risk else UNMEASURED,
            "pl_usd_est": (round(r * risk * scale, 2) if r is not None and risk else UNMEASURED),
            "pl_basis": "R x charged risk x filled/sent quantity",
            "closing_orders": [int(_f(o.get("id")) or 0) for o in closing],
        })
    return rows


def record(venue: Any, *, ledger: Path = LEDGER, now: datetime | None = None,
           journals: tuple[Path, ...] = JOURNALS) -> dict[str, Any]:
    """One pass against the live venue. Never raises: an unreadable history is reported."""
    now = now or datetime.now(UTC)
    try:
        hist = venue._api.get_all_orders(history=True, lookback_period=LOOKBACK)
        history = hist.to_dict("records") if hasattr(hist, "to_dict") else list(hist)
        open_ids = {int(_f(p.get("id")) or 0) for p in venue.positions()}
    except Exception as exc:
        return {"status": UNMEASURED, "why": f"{type(exc).__name__}: {exc}"[:200]}
    done = {str(r.get("position_id")) for r in _jsonl(ledger)}
    rows = closed_positions(history, open_ids, our_sends(_jsonl(p) for p in journals),
                            done=done, now=now)
    # The file exists from the first readable pass even with no close yet, so a reader can tell
    # "measured, nothing closed" from "never measured".
    ledger.parent.mkdir(parents=True, exist_ok=True)
    with ledger.open("a", encoding="utf-8") as fh:
        for r in rows:
            fh.write(json.dumps(r, default=str, separators=(",", ":")) + "\n")
    return {"status": "OK", "new_closes": len(rows), "history_orders": len(history)}
