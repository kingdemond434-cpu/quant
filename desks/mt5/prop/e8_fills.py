"""E8 FILLS -- every closed E8 gold position, book "e8", in the prop fills ledger.

WHY (2026-11-03). The loss-learning loop reads `data/live_ledger_prop.jsonl` (prop-fills-v1) and
until now only the FTMO follower wrote it, so E8's losses -- the account the gold book actually
trades first -- never reached it. This module is the ledger's E8 side.

WHERE THE DATA COMES FROM, AND WHY NO NEW BROKER CALL. E8 trades on TradeLocker (not MT5), and
no E8 component writes closed-trade records to disk: `e8_gold_intents.jsonl` holds what was SENT
and `e8_gold_state.json` the day's legs, never an exit. But `e8_gold.run` already reads, every
pass, the venue's two-day order history (`get_all_orders(history=True)`), the open positions and
its own entry orders (`own_entry_orders`, keyed by the order id TradeLocker handed back at the
send -- the venue has no magic number and no comment). `compose_fills` is a PURE transformer of
those three readings; `record_fills` is the hook e8_gold calls with them. It makes no venue call
beyond the cached instrument details for the contract size, and it NEVER RAISES: a ledger that
cannot be written costs a row, never an order.

A position is written when, and only when: its entry order is one of OURS, filled, with a
positionId; it is no longer open (and the positions were readable); and its filled exit orders
(stop, target or a market close on the same positionId, the opposite side) cover the entry's
quantity -- so an unpriced or still-open trade is never written. Prices are the venue's own
`avgPrice`; nothing is invented.

FEES. The TradeLocker order history carries no commission, swap or fee field. E8 is commission
free by its pricing (`e8_executor.E8_ROUND_TRIP_PER_PRICE_UNIT`), but swap on a carried position
is not measured, so all three are NULL with `fees_status` saying why -- never 0.0 -- and
`pl_net_quote` is null.

THE EPISODE FIELDS. `direction` (+1/-1), `sleeve` ("gold_<window>") and `signal_hour_utc` (the
window's signal hour on the send's server date, less the measured server offset --
`ftmo_follower.signal_hour_utc`, the one derivation both books use) let the Auditor collapse
E8's trade and FTMO's copy of the same signal into one episode.
"""
from __future__ import annotations

import math
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

BOOK = "e8"
SYMBOL = "XAUUSD"
#: Exit order type on the venue -> exit_reason. A stop that the ratchet moved to break-even is
#: still a stop; a market order on the position is the desk's close-hour close or a hand close,
#: which the order history cannot tell apart (closed_by "unknown").
EXIT_REASON = {"stop": "stop", "stop_limit": "stop", "limit": "target", "market": "close"}
CLOSED_BY = {"stop": "venue", "stop_limit": "venue", "limit": "venue", "market": "unknown"}
FEES_STATUS = ("UNMEASURED: the TradeLocker order history carries no commission, swap or fee "
               "field; null, never 0.0")
#: Exits must cover the entry's quantity to within this fraction, or the row is not written.
QTY_TOL = 1e-6


def _ms(o: dict[str, Any], *keys: str) -> int | None:
    for k in keys:
        v = o.get(k)
        try:
            if v is not None and not isinstance(v, bool) and int(v) > 0:
                return int(v)
        except (TypeError, ValueError):
            continue
    return None


def _int(v: Any) -> int | None:
    try:
        return int(v) if v is not None and not isinstance(v, bool) else None
    except (TypeError, ValueError):
        return None


def _num(v: Any) -> float | None:
    try:
        f = float(v)
    except (TypeError, ValueError):
        return None
    return f if math.isfinite(f) and not isinstance(v, bool) else None


def _iso_ms(ms: int | None) -> str | None:
    return (datetime.fromtimestamp(ms / 1000.0, tz=UTC).isoformat(timespec="seconds")
            if ms else None)


def _qty(o: dict[str, Any]) -> float | None:
    q = _num(o.get("filledQty"))
    if q is None or q <= 0:
        q = _num(o.get("qty"))
    return q if q is not None and q > 0 else None


def _dir(side: Any) -> int:
    s = str(side or "").lower()
    if s.startswith("buy"):
        return 1
    if s.startswith("sell"):
        return -1
    return 0


def _filled(o: dict[str, Any]) -> bool:
    return str(o.get("status") or "").lower() == "filled"


def _box_utc(at: Any) -> datetime | None:
    try:
        d = datetime.fromisoformat(str(at))
    except (TypeError, ValueError):
        return None
    return d if d.tzinfo else d.replace(tzinfo=UTC)


def server_offset_h(server_time: Any, now: datetime) -> int | None:
    """The server's whole-hour UTC offset from e8_gold's own pass stamps: `server_time` (the
    terminal tick's wall clock written as if UTC, doc["server_time"]) against the box's UTC
    `now`. None unless it is within 5 minutes of a whole hour in UTC+0..+4. Pure."""
    t = _box_utc(server_time)
    if t is None:
        return None
    lag = (t - now).total_seconds()
    off = round(lag / 3600.0)
    if not 0 <= off <= 4 or abs(lag - off * 3600.0) > 300.0:
        return None
    return int(off)


def compose_fills(hist_rows: list[dict[str, Any]], own: dict[int, dict[str, Any]],
                  journal: list[dict[str, Any]], open_position_ids: set[int], *,
                  instrument_id: int | None, contract: float | None, account_key: str | None,
                  server_offset: int | None, venue_clock_skew_ms: int | None,
                  recorded_at: str) -> list[dict[str, Any]]:
    """prop-fills-v1 rows, book "e8", for every CLOSED E8 gold position this lane opened. Pure.

    `hist_rows` is the venue's order history, `own` e8_gold's own entry orders by venue order id
    ({window, side, price, sl, tp, lot}), `journal` the intents journal (send times),
    `open_position_ids` the positions open now. See the module docstring for what is written."""
    from prop.ftmo_follower import PROP_SCHEMA, signal_hour_utc
    sent_at = {_int(r.get("order_id")): r.get("at") for r in journal or []
               if r.get("status") == "SENT" and _int(r.get("order_id")) is not None}
    by_pos: dict[int, list[dict[str, Any]]] = {}
    for o in hist_rows or []:
        if not _filled(o) or o.get("positionId") in (None, "", 0):
            continue
        tid = _int(o.get("tradableInstrumentId"))
        if instrument_id and tid is not None and tid != int(instrument_id):
            continue
        if (pid := _int(o.get("positionId"))) is not None:
            by_pos.setdefault(pid, []).append(o)
    rows: list[dict[str, Any]] = []
    for pid, orders in sorted(by_pos.items()):
        if pid in open_position_ids:
            continue
        entries = [o for o in orders if _int(o.get("id")) in own]
        if len(entries) != 1:
            continue                    # not ours, or more than one entry: not reconstructible
        e = entries[0]
        eid = int(e["id"])
        leg = own[eid]
        dirn = _dir(e.get("side")) or _dir(leg.get("side"))
        exits = [o for o in orders if o is not e]
        if dirn == 0 or not exits or any(_dir(o.get("side")) != -dirn for o in exits):
            continue
        entry_px, q_in = _num(e.get("avgPrice")), _qty(e)
        pxs = [(_num(o.get("avgPrice")), _qty(o)) for o in exits]
        if not (entry_px and entry_px > 0 and q_in) or any(
                not (p and p > 0 and q) for p, q in pxs):
            continue                    # unpriced: never written
        q_out = sum(q for _p, q in pxs if q)
        if q_out + QTY_TOL * q_in < q_in:
            continue                    # exits do not cover the entry: not closed as far as read
        exit_px = sum(p * q for p, q in pxs if p and q) / q_out
        last = max(exits, key=lambda o: _ms(o, "lastModified", "createdDate") or 0)
        sl, tp = _num(leg.get("sl")), _num(leg.get("tp"))
        dist = abs(entry_px - sl) if sl else None
        window = str(leg.get("window") or "")
        etype = str(last.get("type") or "").lower()
        # the send's server date: the journal's box-UTC send time, else the venue's order stamp
        sent = _box_utc(sent_at.get(eid))
        if sent is None and (ms := _ms(e, "createdDate")) is not None:
            sent = datetime.fromtimestamp(ms / 1000.0, tz=UTC)
        server_day = ((sent + timedelta(hours=server_offset)).date().isoformat()
                      if sent is not None and isinstance(server_offset, int) else None)
        sig_at, sig_basis = signal_hour_utc(server_day, window, server_offset)
        pl_quote = (round(dirn * (exit_px - entry_px) * q_in * contract, 2)
                    if contract else None)
        rows.append({
            "schema": PROP_SCHEMA, "book": BOOK, "venue": "tradelocker", "lane": "e8_gold",
            "provenance": "e8_fills:tradelocker_order_history", "recorded_at": recorded_at,
            "time": _iso_ms(_ms(last, "lastModified", "createdDate")),
            "sleeve": f"gold_{window}" if window else None, "window": window or None,
            "symbol": SYMBOL, "entry_side": 0 if dirn == 1 else 1, "side": 1 if dirn == 1 else 0,
            "direction": dirn, "signal_hour_utc": sig_at, "signal_hour_basis": sig_basis,
            "entry_time": _iso_ms(_ms(e, "lastModified", "createdDate")),
            "exit_time": _iso_ms(_ms(last, "lastModified", "createdDate")),
            "timestamp_basis": "tradelocker_order_ms_utc (lastModified of the filled order)",
            "venue_clock_skew_ms": venue_clock_skew_ms,
            "entry_time_box_utc": sent.isoformat(timespec="seconds") if sent else None,
            "entry_price": entry_px, "intended_entry": _num(leg.get("price")),
            "sl": sl, "tp": tp, "volume": q_in, "fill_price": round(exit_px, 6),
            "exit_reason": EXIT_REASON.get(etype, "close"),
            "closed_by": CLOSED_BY.get(etype, "unknown"),
            "exit_magic": None, "exit_order_type": etype or None,
            "r_multiple": (round(dirn * (exit_px - entry_px) / dist, 4) if dist else None),
            "r_basis": "price: side x (exit - entry) / |entry - sent stop|, gross of fees",
            "r_unreconstructible": not dist,
            "risk_quote": (round(dist * q_in * contract, 6) if dist and contract else None),
            "pl_quote": pl_quote, "quote_ccy": "USD",
            "pl_basis": ("price: side x (exit avgPrice - entry avgPrice) x qty x the venue's "
                         "contract size, gross of fees (the order history carries no P&L)"
                         if contract else "UNMEASURED: the venue's contract size is unread"),
            "commission": None, "swap": None, "fees": None,
            "fees_status": FEES_STATUS, "fees_measured": [],
            "fees_basis": "the TradeLocker order history (no fee fields)",
            "pl_net_quote": None,
            "position_id": pid, "entry_order": eid,
            "close_order": _int(last.get("id")),
            "n_exit_orders": len(exits), "server": "E8", "account_kind": "prop",
            "account_key": account_key,
            "account_key_status": "keyed (gold_oco.tradelocker_oco_key)" if account_key
            else "UNMEASURED: no keyed account key"})
    return rows


def append_fills(rows: list[dict[str, Any]], path: Path | None = None) -> int:
    """Append book "e8" rows through the ledger's one writer (`ftmo_follower.append_fills`): one
    os.write per whole line on an O_APPEND descriptor, deduped by "e8:" + position id, refusing
    any login-shaped field. RAISES (ValueError on a row that is not book "e8")."""
    from prop import ftmo_follower as _ff
    for r in rows:
        if r.get("book") != BOOK:
            raise ValueError(f"the E8 writer writes book {BOOK!r} only, not {r.get('book')!r}")
    return _ff.append_fills(rows, path)


def _contract(venue: Any) -> float | None:
    try:
        d = venue.details(SYMBOL)
    except Exception:
        return None
    for k in ("contractSize", "contract_size", "lotSize", "units"):
        v = d.get(k) if isinstance(d, dict) else None
        if isinstance(v, (int, float)) and not isinstance(v, bool) and v > 0:
            return float(v)
    return None


def record_fills(venue: Any, hist_rows: list[dict[str, Any]], own: dict[int, dict[str, Any]],
                 journal: list[dict[str, Any]], open_position_ids: set[int], *,
                 history_ok: bool, positions_ok: bool, instrument_id: int | None,
                 account_key: str | None, server_time: Any, now: datetime,
                 venue_clock_skew_ms: int | None = None,
                 path: Path | None = None) -> dict[str, Any]:
    """Write every closed E8 gold position to the prop fills ledger. NEVER RAISES: a ledger that
    cannot be written costs a row, never an order."""
    try:
        if not history_ok:
            return {"written": 0, "why": "the order history is unreadable"}
        if not positions_ok:
            return {"written": 0, "why": "the positions are unreadable: open and closed are "
                                         "indistinguishable"}
        rows = compose_fills(hist_rows, own, journal, set(open_position_ids),
                             instrument_id=instrument_id, contract=_contract(venue),
                             account_key=account_key,
                             server_offset=server_offset_h(server_time, now),
                             venue_clock_skew_ms=venue_clock_skew_ms,
                             recorded_at=now.isoformat(timespec="seconds"))
        return {"written": append_fills(rows, path), "closed_seen": len(rows)}
    except Exception as exc:
        return {"written": 0, "why": f"{type(exc).__name__}: {exc}"[:160]}
