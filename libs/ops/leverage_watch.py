"""Watch the trading account's leverage and name every change (CRO finding K3, 2026-11-13).

WHY. Brokers cut leverage before events and weekends. Margin feasibility for every sized order
moves with it, and until now nothing on the desk kept a reading from one pass to the next: only
`financing_lab` read `account_info().leverage`, used it for that one pass, and forgot it. A cut
was therefore visible only as orders refused for margin.

WHAT. `observe` keeps a small history (`desks/mt5/reports/ACCOUNT_LEVERAGE.json`): the last
reading, when it was read, and every change with its old and new value. A change emits an
`ACCOUNT_LEVERAGE_CHANGED` event row (priority 2, so the pager and the board see it). A pass
with no readable leverage writes nothing new and the verdict ages to STALE after
`STALE_AFTER_H`; an absent reading is never recorded as a change. The file carries the venue
label only -- no login, server or account number (the repository is public).

PER SYMBOL (folded in from #1145, 2026-11-18). A broker cuts leverage per symbol too -- gold and
the indices first -- and the account figure does not move when it does. `symbol_margins` reads,
for the core symbols and every symbol held, the venue's own margin for one lot
(`order_calc_margin`, which folds in symbol-specific leverage) and the effective leverage it
implies; `observe` keeps the last per symbol and names a move of `CHANGE_RATIO` or more as a CUT
(margin per lot up) or a RAISE (down), with its own event row.

This is a REPORT. It sets no cap, no size and no veto (GROWTH_GOVERNANCE): the allocator already
reads the live leverage through `financing_lab.load_terms` on every pass.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

STALE_AFTER_H = 36.0
MAX_CHANGES_KEPT = 200
#: The symbols always read, so one the desk has not traded this month is still watched.
CORE_SYMBOLS = ("XAUUSD", "XAGUSD", "EURUSD", "GBPUSD", "USDJPY", "AUDUSD", "USDCAD", "USDCHF",
                "NZDUSD", "EURJPY", "GBPJPY", "AUDJPY", "US500", "US30", "US100", "GER40",
                "UK100", "JP225", "XTIUSD", "XBRUSD")
#: A margin-per-lot move at or beyond this ratio is a CUT (up) or RAISE (down) of leverage.
CHANGE_RATIO = 1.15


def _num(v: Any) -> float | None:
    return float(v) if isinstance(v, (int, float)) and v == v and v > 0 else None


def symbol_margins(mt5: Any, symbols: Any) -> dict[str, dict[str, Any]]:
    """{symbol: margin per lot buy/sell, contract size, effective leverage}, read-only from an
    attached MetaTrader5 module. Sends nothing; a symbol it cannot read is left out."""
    out: dict[str, dict[str, Any]] = {}
    for sym in dict.fromkeys(str(s).upper() for s in symbols if s):
        try:
            info = mt5.symbol_info(sym)
            if info is None:
                continue
            tick = mt5.symbol_info_tick(sym)
            ask = _num(getattr(tick, "ask", None)) if tick is not None else None
            bid = _num(getattr(tick, "bid", None)) if tick is not None else None
            row: dict[str, Any] = {"contract_size": _num(getattr(info, "trade_contract_size",
                                                                 None))}
            for side, otype, px in (("buy", getattr(mt5, "ORDER_TYPE_BUY", 0), ask),
                                    ("sell", getattr(mt5, "ORDER_TYPE_SELL", 1), bid)):
                row[f"margin_per_lot_{side}"] = (_num(mt5.order_calc_margin(otype, sym, 1.0, px))
                                                 if px else None)
            m, cs = row["margin_per_lot_buy"], row["contract_size"]
            row["effective_leverage"] = round(cs * ask / m, 2) if m and cs and ask else None
        except Exception:
            continue
        if row.get("margin_per_lot_buy"):
            out[sym] = row
    return out


def _symbol_changes(prev: dict[str, Any], now_rows: dict[str, dict[str, Any]],
                    at: str) -> list[dict[str, Any]]:
    """A CUT or RAISE per symbol whose margin per lot moved by CHANGE_RATIO or more."""
    out = []
    for sym, row in now_rows.items():
        old = _num((prev.get(sym) or {}).get("margin_per_lot_buy"))
        new = _num(row.get("margin_per_lot_buy"))
        if old is None or new is None:
            continue
        ratio = new / old
        if ratio >= CHANGE_RATIO or ratio <= 1.0 / CHANGE_RATIO:
            out.append({"at": at, "symbol": sym, "from": old, "to": new,
                        "ratio": round(ratio, 3), "direction": "CUT" if ratio > 1 else "RAISED",
                        "effective_leverage": row.get("effective_leverage")})
    return out


def _read(path: Path) -> dict[str, Any]:
    try:
        doc = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    return doc if isinstance(doc, dict) else {}


def _parse(ts: Any) -> datetime | None:
    try:
        t = datetime.fromisoformat(str(ts))
    except (TypeError, ValueError):
        return None
    return t if t.tzinfo else t.replace(tzinfo=UTC)


def observe(path: Path, leverage: float | None, *, venue: str = "fusion",
            now: datetime | None = None, emit: Any = None,
            symbols: dict[str, dict[str, Any]] | None = None) -> dict[str, Any]:
    """Record one reading; return the document written (or that would stand, when unreadable)."""
    now = now or datetime.now(tz=UTC)
    doc = _read(path)
    raw_venues = doc.get("venues")
    venues: dict[str, Any] = raw_venues if isinstance(raw_venues, dict) else {}
    raw_row = venues.get(venue)
    row: dict[str, Any] = raw_row if isinstance(raw_row, dict) else {}
    prior = row
    raw_changes = row.get("changes")
    changes: list[Any] = raw_changes if isinstance(raw_changes, list) else []
    lev = float(leverage) if isinstance(leverage, (int, float)) and leverage > 0 else None
    prev = row.get("leverage")
    changed: dict[str, Any] | None = None
    if lev is not None:
        if isinstance(prev, (int, float)) and float(prev) != lev:
            changed = {"at": now.isoformat(timespec="seconds"), "from": float(prev), "to": lev,
                       "direction": "CUT" if lev < float(prev) else "RAISED"}
            changes = [*changes, changed][-MAX_CHANGES_KEPT:]
        row = {"leverage": lev, "read_at": now.isoformat(timespec="seconds"),
               "changes": changes}
    # The account rebuild above keeps only the account fields; the per-symbol state is read from
    # the row as it stood on disk.
    raw_syms = prior.get("symbols")
    prev_syms: dict[str, Any] = raw_syms if isinstance(raw_syms, dict) else {}
    raw_sc = prior.get("symbol_changes")
    kept: list[Any] = raw_sc if isinstance(raw_sc, list) else []
    sym_changes: list[dict[str, Any]] = []
    if symbols:
        sym_changes = _symbol_changes(prev_syms, symbols, now.isoformat(timespec="seconds"))
        row = {**row, "symbols": {**prev_syms, **symbols},
               "symbols_read_at": now.isoformat(timespec="seconds"),
               "symbol_changes": [*kept, *sym_changes][-MAX_CHANGES_KEPT:]}
    elif prev_syms:
        row = {**row, "symbols": prev_syms, "symbol_changes": kept}
    read_at = _parse(row.get("read_at"))
    age_h = None if read_at is None else round((now - read_at).total_seconds() / 3600.0, 2)
    if read_at is None:
        verdict = "UNMEASURED"
    elif age_h is not None and age_h > STALE_AFTER_H:
        verdict = "STALE"
    elif changed is not None or sym_changes:
        verdict = "CHANGED"
    else:
        verdict = "MEASURED"
    row = {**row, "verdict": verdict, "age_h": age_h}
    venues = {**venues, venue: row}
    out = {"generated_utc": now.isoformat(timespec="seconds"),
           "producer": "libs/ops/leverage_watch.py (via research/financing_lab.py)",
           "stale_after_h": STALE_AFTER_H, "venues": venues,
           "boundary": "REPORT ONLY: no cap, size or veto; the allocator reads live leverage "
                       "through financing_lab.load_terms on every pass"}
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.with_suffix(".tmp")
        tmp.write_text(json.dumps(out, indent=1), encoding="utf-8")
        tmp.replace(path)
    except OSError:
        pass
    if changed is not None or sym_changes:
        try:
            if emit is None:
                from libs.ops.events import emit as emit_fn
            else:
                emit_fn = emit
            if changed is not None:
                fields: dict[str, Any] = {"producer": "research/financing_lab.py",
                                          "priority": 2, "venue": venue,
                                          "from": changed["from"], "to": changed["to"],
                                          "direction": changed["direction"]}
                emit_fn("ACCOUNT_LEVERAGE_CHANGED", **fields)
            for c in sym_changes:
                emit_fn("SYMBOL_MARGIN_CHANGED", producer="research/financing_lab.py",
                        priority=2, venue=venue, symbol=c["symbol"], ratio=c["ratio"],
                        direction=c["direction"])
        except Exception:
            pass
    return out
