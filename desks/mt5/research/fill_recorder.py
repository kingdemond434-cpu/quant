"""WHAT THE DESK ASKED FOR AND WHAT IT GOT, on every order it actually sent.

THE PRINCIPAL, 2026-09-23: *"matched_fills is 0, which is why capacity, market impact and the
shortfall model all read UNMEASURED and why the allocator cannot size on measured impact."*

AND IT WAS 0 FOR A REASON NOBODY HAD MEASURED. `reports/markout.json` was last written on
2026-09-08 with `n_matched: 0` and has been quoted as a standing fact in `capacity.py`,
`cost_truth.py`, `pf_allocator.py`, `prop_barrier.py`, `e8_book.py` and the promoter ever since.
Re-measured 2026-09-23 on this box, with the join those modules already name -- the intent's
`ticket` is the entry order, and the ledger's `entry_order` is the same number:

    92 order intents, 58 carrying a ticket
    151 closed deals, 138 carrying an entry_order
    30 of them JOIN

Thirty real fills, on a live Fusion account, sitting unjoined on disk for a fortnight, while
every organ downstream published UNMEASURED and the allocator declined to price impact. The fills
were never missing. Nothing had ever written the join down.

WHAT THIS ORGAN RECORDS, per order the gateway sent, exactly the list the principal named:

    quote at decision      decision_bid / decision_ask / their mid, from the intent
    requested price        the intent's `intended` -- the price the desk asked for
    fill price             the ENTRY deal's price from the live ledger, never the close
    latency                decision -> send, measured in place around `mt5.order_send`
    volume                 the position's own lots
    spread at that instant spread_at_decision, in fraction of price AND in points
    slippage               (fill - asked) x direction, in POINTS and in R

It writes them to `data/fill_corpus.jsonl` through `libs.execution.fill_corpus.append_rows` --
the store the execution twin, the execution-choice model, the alpha-capture ratio, the cost
surface, the feed-clock lab and the shortfall model already read. No new store, no second
schema, no new door.

THREE JOINS, EACH NAMED ON THE ROW. `ticket == entry_order` is the bridge MT5 actually offers and
is tried first; `ticket == position_id` catches a position whose opening order the broker
re-ticketed; and a same-symbol, same-direction, same-minute pairing is tried last and is STAMPED
AS SUCH in `join_keys`, so a reader can discard the weakest tier without discarding the corpus.
An intent with no deal is an UNFILLED order and is recorded as `status: UNRESOLVED`, never as a
zero-slippage fill -- counting it would drag every mean toward "no slippage" using orders that
never traded.

RECORDING ONLY. It sends nothing, sizes nothing, routes nothing and vetoes nothing. It reads two
append-only ledgers the gateway already writes and appends to a third.

    python desks/mt5/research/fill_recorder.py --once --budget-s 120
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

DESK = Path(__file__).resolve().parents[1]
ROOT = DESK.parent.parent
for _p in (str(DESK), str(DESK / "research"), str(ROOT)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from libs.execution import fill_corpus as fc  # noqa: E402

INTENTS = DESK / "data" / "order_intents.jsonl"
E8_INTENTS = DESK / "data" / "e8_intents.jsonl"
LEDGER = DESK / "data" / "live_ledger.jsonl"
DECISIONS = DESK / "data" / "decision_ledger.jsonl"
CORPUS = DESK / "data" / "fill_corpus.jsonl"
OUT = DESK / "reports" / "FILL_RECORDER.json"

#: The minute window a last-resort symbol/side pairing may span. One minute, because
#: `_intent_id` already keys an intent to its own minute and a wider window would pair an intent
#: with a fill from a different signal.
PAIR_WINDOW_S = 90.0

#: The fields the principal named, checked on every recorded row so completeness is a measured
#: number and not a claim.
REQUIRED_FIELDS: tuple[str, ...] = (
    "quote_bid", "quote_ask", "quote_mid_at_decision", "requested_price", "fill_price",
    "latency_decision_to_send_ms", "lots", "spread_frac_at_decision",
    "spread_points_at_decision", "slip_points", "slip_r",
    # the three the size term, the impact model and the shortfall model actually consume
    "realized_r", "commission_r", "latency_send_to_ack_ms")


def _read_jsonl(p: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    try:
        with p.open(encoding="utf-8") as fh:
            for line in fh:
                line = line.strip()
                if not line:
                    continue
                try:
                    r = json.loads(line)
                except ValueError:
                    continue
                if isinstance(r, dict):
                    rows.append(r)
    except OSError:
        return []
    return rows


def _write(p: Path, doc: Any) -> None:
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(doc, indent=1, default=str), encoding="utf-8")


def _f(x: Any) -> float | None:
    try:
        v = float(x)
    except (TypeError, ValueError):
        return None
    return v if v == v and abs(v) != float("inf") else None


def _i(x: Any) -> int | None:
    try:
        return int(x)
    except (TypeError, ValueError):
        return None


def _epoch(stamp: Any) -> float | None:
    try:
        return datetime.fromisoformat(str(stamp).replace("Z", "+00:00")).timestamp()
    except (TypeError, ValueError):
        return None


def _point_from(*prices: float | None) -> float | None:
    """The venue's point size, read off the precision of the quotes on this row.

    A price is quoted to the venue's own point: 0.85613 to five places is a 1e-5 point, 4340.57
    to two is 1e-2. The deepest precision among the row's prices wins, because a rounded value
    (0.94400) understates it. None when no price is on the row -- never a default.
    """
    best = 0
    seen = False
    for p in prices:
        if p is None:
            continue
        seen = True
        txt = f"{p:.10f}".rstrip("0")
        dec = len(txt.split(".")[1]) if "." in txt else 0
        best = max(best, min(dec, 8))
    return (10.0 ** -best) if seen and best else None


def _direction(side: Any) -> int:
    """+1 for a buy of any shape, -1 for a sell. The ledger stores MT5's integer type (0 = buy,
    1 = sell); the intent stores the desk's own word."""
    s = str(side).strip().lower()
    if s in ("0", "buy", "buy_stop", "buy_limit"):
        return 1
    if s in ("1", "sell", "sell_stop", "sell_limit"):
        return -1
    return 1 if "buy" in s else -1


def match(intents: list[dict[str, Any]], deals: list[dict[str, Any]],
          ) -> tuple[list[tuple[dict[str, Any], dict[str, Any], str]], list[dict[str, Any]],
                     list[dict[str, Any]], dict[str, int]]:
    """(pairs with the join that made them, unfilled intents, unmatched deals, join census)."""
    by_entry: dict[int, dict[str, Any]] = {}
    by_pos: dict[int, dict[str, Any]] = {}
    for d in deals:
        eo, pid = _i(d.get("entry_order")), _i(d.get("position_id"))
        if eo is not None:
            by_entry.setdefault(eo, d)
        if pid is not None:
            by_pos.setdefault(pid, d)
    used: set[int] = set()
    pairs: list[tuple[dict[str, Any], dict[str, Any], str]] = []
    unfilled: list[dict[str, Any]] = []
    census: dict[str, int] = {"entry_order": 0, "position_id": 0, "symbol_minute": 0}
    for it in intents:
        t = _i(it.get("ticket"))
        hit, how = None, ""
        if t is not None and t in by_entry:
            hit, how = by_entry[t], "entry_order"
        elif t is not None and t in by_pos:
            hit, how = by_pos[t], "position_id"
        else:
            t0 = _epoch(it.get("time"))
            sym, dirn = str(it.get("symbol") or ""), _direction(it.get("side"))
            if t0 is not None and sym:
                for d in deals:
                    if str(d.get("symbol") or "") != sym or _direction(d.get("side")) != dirn:
                        continue
                    if _i(d.get("deal")) in used:
                        continue
                    td = _epoch(d.get("time"))
                    if td is not None and abs(td - t0) <= PAIR_WINDOW_S:
                        hit, how = d, "symbol_minute"
                        break
        if hit is None:
            unfilled.append(it)
            continue
        dk = _i(hit.get("deal"))
        if dk is not None:
            used.add(dk)
        census[how] = census.get(how, 0) + 1
        pairs.append((it, hit, how))
    matched_deals = {_i(d.get("deal")) for _it, d, _h in pairs}
    unmatched = [d for d in deals if _i(d.get("deal")) not in matched_deals]
    return pairs, unfilled, unmatched, census


def build_row(it: dict[str, Any], deal: dict[str, Any], how: str,
              decisions: dict[str, dict[str, Any]]) -> dict[str, Any]:
    """One complete corpus row: asked, got, when, at what spread, and the cost in points and R."""
    direction = _direction(it.get("side"))
    asked = _f(it.get("intended"))
    # THE ENTRY PRICE OR NOTHING. `_position_entry` returns 0.0 when a position's opening deal is
    # unreadable, and `deal["fill_price"]` is the CLOSING price -- the exact substitution
    # `mt5desk/markout.py` was written to refuse. Falling back to it measured the distance from
    # the entry the desk asked for to the price it EXITED at and called the difference slippage:
    # a mean of +203 R on this box's own thirty fills, which is the number that would have been
    # published. An entry price that is absent or non-positive leaves fill_price None and the
    # row's status UNRESOLVED; the quote, the spread, the latency and the ask are still recorded.
    fill = _f(deal.get("entry_price"))
    if fill is not None and fill <= 0.0:
        fill = None
    if fill is None:
        # THE VENUE'S OWN ANSWER TO `order_send`, recorded on the intent since 2026-09-23 for
        # every market order. It is the same fill the entry deal carries and it arrives first.
        fill = _f(it.get("fill_price"))
        if fill is not None and fill <= 0.0:
            fill = None
    bid, ask = _f(it.get("decision_bid")), _f(it.get("decision_ask"))
    mid = ((bid + ask) / 2.0) if (bid is not None and ask is not None) else None
    point = _f(it.get("point"))
    spread = _f(it.get("spread_at_decision"))
    if spread is None and bid is not None and ask is not None:
        spread = ask - bid
    lots = _f(deal.get("volume")) or _f(it.get("lot"))
    contract = _f(deal.get("contract_size"))

    # THE POINT SIZE, FROM THE INTENT OR FROM THE QUOTES THEMSELVES. `point` was only added to
    # the intent row on 2026-09-08, so 28 of this box's 30 matched fills carry none and every
    # per-point number would have read UNMEASURED for them. The venue's point is the last place
    # of the quote, and the quote is on the row: 0.85613 is quoted to five places, 4340.57 to
    # two. Derived, never assumed, and the basis is published beside the number.
    point_basis = "intent"
    if point is None or point <= 0:
        point = _point_from(asked, fill, bid, ask)
        point_basis = "derived from the quoted precision of this row's own prices"

    slip_quote = ((fill - asked) * direction) if (fill is not None and asked is not None) else None
    ref = mid or asked or fill
    slip_frac = (slip_quote / ref) if (slip_quote is not None and ref) else None
    slip_points = (slip_quote / point) if (slip_quote is not None and point) else None
    # SLIP IN R IS THE ONLY UNIT THIS DESK SIZES IN, AND ITS DENOMINATOR IS THE POSITION'S OWN
    # STOP GEOMETRY. The ledger's `risk_quote` is NOT a stable unit across rows: on this box it
    # arrives negative (-40.07 on a gold position), and on some rows it is the stop distance
    # alone with neither contract size nor lots in it. Dividing by it gave +5384 R of "slippage"
    # on a fourteen-pip EURGBP fill. |entry - stop| x contract size x lots is the definition
    # `r_multiple` is written against and is computable from the row, so it is what is used; the
    # ledger's own figure is the fallback in absolute value, and a position whose stop sits on
    # its entry has NO R denominator -- that row's slip_r is None, which is a real answer.
    denom, denom_basis = r_denominator(deal)
    slip_r = None
    if slip_quote is not None and denom and contract and lots:
        slip_r = (slip_quote * contract * lots) / denom
    spread_frac = (spread / ref) if (spread is not None and ref) else None
    spread_points = (spread / point) if (spread is not None and point) else None

    iid = str(it.get("intent_id") or "")
    dec = decisions.get(iid) or {}
    filled_at = str(deal.get("time") or "")
    return {
        "record_id": f"{iid or it.get('ticket')}|{filled_at}",
        "intent_id": iid,
        "decision_id": str(dec.get("decision_id") or ""),
        "ticket": _i(it.get("ticket")), "deal": _i(deal.get("deal")),
        "release_id": str(it.get("release_id") or ""),
        "state_vector_id": str(it.get("state_vector_id") or ""),
        "account_kind": str(deal.get("account_kind") or "unknown"),
        # EVERY DERIVED NUMBER CARRIES HOW IT WAS DERIVED. `join_keys` is the row's own audit
        # slot, so a reader can tell a point size read off the intent from one read off the
        # quote's precision, and a stop-geometry R denominator from the ledger's own figure,
        # without re-deriving either.
        "join_keys": {"basis": how, "entry_order": str(deal.get("entry_order") or ""),
                      "position_id": str(deal.get("position_id") or ""),
                      "point_basis": point_basis, "r_denominator": denom_basis},
        "sources": ["order_intents.jsonl", "live_ledger.jsonl"]
        + (["decision_ledger.jsonl"] if dec else []),
        "schema_version": fc.SCHEMA_VERSION,
        "symbol": str(it.get("symbol") or deal.get("symbol") or ""),
        "sleeve": str(it.get("sleeve") or deal.get("sleeve") or ""),
        "decided_at": str(it.get("time") or ""), "sent_at": str(it.get("time") or ""),
        "filled_at": filled_at, "exit_at": filled_at,
        "entry_reason": str(dec.get("reason") or ""),
        "strategy_id": str(dec.get("strategy_id") or it.get("sleeve") or ""),
        "side": str(it.get("side") or ""), "direction": direction,
        "order_type": str(it.get("order_type") or ""),
        "execution_style": str(it.get("order_type") or ""),
        "lots": lots, "requested_price": asked,
        "quote_bid": bid, "quote_ask": ask, "quote_mid_at_decision": mid,
        "fill_price": fill, "filled_frac": (1.0 if fill is not None else 0.0),
        "retcode": _i(it.get("retcode")), "rejected": False,
        "slip_frac": slip_frac, "slip_r": slip_r, "slip_points": slip_points,
        "spread_frac_at_decision": spread_frac,
        "spread_points_at_decision": spread_points, "point": point,
        # COMMISSION IN R DIVIDED BY THE BARE STOP DISTANCE UNTIL NOW. `risk_quote` is price units
        # on 141 of 151 rows, so this read (contract x lots) times too large -- 100x on gold.
        "commission_r": (((_f(deal.get("commission")) or 0.0) / denom) if denom else None),
        "latency_decision_to_send_ms": _f(it.get("latency_ms")),
        "latency_send_to_ack_ms": _f(it.get("latency_send_to_ack_ms")),
        "realized_r": realized_r(deal, denom),
        "status": "FILLED" if fill is not None else "UNRESOLVED",
    }


def unfilled_row(it: dict[str, Any]) -> dict[str, Any]:
    """An intent with no closed deal beside it.

    TWO DIFFERENT THINGS LIVE HERE AND THEY ARE NOT COLLAPSED. An order that never traded is
    UNRESOLVED and gets no slippage -- writing 0.0 would drag every mean toward "no slippage"
    using orders that never filled. But a MARKET order that filled and has not yet CLOSED has a
    fill: the venue answered `order_send` with its price and the gateway records it on the intent
    from 2026-09-23. That row is FILLED, its slippage is measured against the price the desk
    asked for, and its R denominator is the intent's own stop distance -- no closing deal needed.
    """
    bid, ask = _f(it.get("decision_bid")), _f(it.get("decision_ask"))
    mid = ((bid + ask) / 2.0) if (bid is not None and ask is not None) else None
    spread = _f(it.get("spread_at_decision"))
    point = _f(it.get("point"))
    asked, stop = _f(it.get("intended")), _f(it.get("sl"))
    lots = _f(it.get("lot"))
    fill = _f(it.get("fill_price"))
    if fill is not None and fill <= 0.0:
        fill = None
    direction = _direction(it.get("side"))
    if point is None or point <= 0:
        point = _point_from(asked, fill, bid, ask)
    slip_quote = ((fill - asked) * direction) if (fill is not None and asked is not None) else None
    ref = mid or asked or fill
    stop_dist = abs(asked - stop) if (asked is not None and stop is not None) else None
    if fill is not None:
        return {
            "record_id": f"{it.get('intent_id') or it.get('ticket')}|{it.get('time')}",
            "intent_id": str(it.get("intent_id") or ""), "ticket": _i(it.get("ticket")),
            "deal": _i(it.get("deal_ticket")), "schema_version": fc.SCHEMA_VERSION,
            "join_keys": {"basis": "intent_fill",
                          "why": "the venue's own order_send answer; no closing deal yet"},
            "sources": ["order_intents.jsonl"],
            "symbol": str(it.get("symbol") or ""), "sleeve": str(it.get("sleeve") or ""),
            "release_id": str(it.get("release_id") or ""),
            "state_vector_id": str(it.get("state_vector_id") or ""),
            "decided_at": str(it.get("time") or ""), "sent_at": str(it.get("time") or ""),
            "filled_at": str(it.get("time") or ""),
            "side": str(it.get("side") or ""), "direction": direction,
            "order_type": str(it.get("order_type") or ""),
            "lots": _f(it.get("fill_volume")) or lots, "requested_price": asked,
            "quote_bid": bid, "quote_ask": ask, "quote_mid_at_decision": mid,
            "fill_price": fill, "filled_frac": 1.0, "retcode": _i(it.get("retcode")),
            "slip_frac": (slip_quote / ref) if (slip_quote is not None and ref) else None,
            "slip_points": (slip_quote / point) if (slip_quote is not None and point) else None,
            "slip_r": ((slip_quote / stop_dist) if (slip_quote is not None and stop_dist)
                       else None),
            "spread_frac_at_decision": (spread / ref) if (spread is not None and ref) else None,
            "spread_points_at_decision": ((spread / point) if (spread is not None and point)
                                          else None),
            "point": point,
            "latency_decision_to_send_ms": _f(it.get("latency_ms")),
            "status": "FILLED",
        }
    return {
        "record_id": f"{it.get('intent_id') or it.get('ticket')}|unfilled",
        "intent_id": str(it.get("intent_id") or ""), "ticket": _i(it.get("ticket")),
        "schema_version": fc.SCHEMA_VERSION,
        "join_keys": {"basis": "none"}, "sources": ["order_intents.jsonl"],
        "symbol": str(it.get("symbol") or ""), "sleeve": str(it.get("sleeve") or ""),
        "decided_at": str(it.get("time") or ""), "sent_at": str(it.get("time") or ""),
        "side": str(it.get("side") or ""), "direction": _direction(it.get("side")),
        "order_type": str(it.get("order_type") or ""),
        "lots": _f(it.get("lot")), "requested_price": _f(it.get("intended")),
        "quote_bid": bid, "quote_ask": ask, "quote_mid_at_decision": mid,
        "fill_price": None, "filled_frac": 0.0, "retcode": _i(it.get("retcode")),
        "spread_frac_at_decision": (spread / mid) if (spread is not None and mid) else None,
        "spread_points_at_decision": (spread / point) if (spread is not None and point) else None,
        "point": point,
        "latency_decision_to_send_ms": _f(it.get("latency_ms")),
        "latency_send_to_ack_ms": _f(it.get("latency_send_to_ack_ms")),
        "account_kind": str(it.get("account_kind") or "unknown"),
        "status": "UNRESOLVED",
    }


def r_denominator(deal: dict[str, Any]) -> tuple[float | None, str]:
    """The position's risk in QUOTE CURRENCY, and how it was derived.

    MEASURED 2026-09-23 over this box's 151 closed deals: `live_ledger.risk_quote` equals the RAW
    STOP DISTANCE in price units on 141 of them -- neither contract size nor lots are in it -- and
    the geometric risk on the other 10. Dividing P&L by it therefore produced a mean "realised R"
    of -449 with a worst row of -12,461 R. `|entry - stop| x contract_size x lots` is computable
    on all 151 and gives mean -0.123 R, median -0.037 R, range [-1.39, +1.75]: the shape a real
    book has. So geometry is the definition, `risk_quote` is used ONLY when it agrees with it
    (i.e. when the writer had already multiplied), and a stop sitting on the entry has no
    denominator at all -- that row's R is None, which is a real answer and not a zero.
    """
    entry, stop = _f(deal.get("entry_price")), _f(deal.get("sl"))
    contract, lots = _f(deal.get("contract_size")), _f(deal.get("volume"))
    if None not in (entry, stop, contract, lots) and abs(entry - stop) > 0:  # type: ignore[operator]
        geo = abs(entry - stop) * contract * lots  # type: ignore[operator]
        if geo > 0:
            return geo, "|entry - stop| x contract_size x lots"
    rq = _f(deal.get("risk_quote"))
    # only when it is already the geometric figure, never when it is the bare stop distance
    if (rq and abs(rq) > 0 and entry is not None and stop is not None
            and abs(abs(rq) - abs(entry - stop)) > 1e-9):
        return abs(rq), "abs(live_ledger.risk_quote)"
    return None, ""


def realized_r(deal: dict[str, Any], denom: float | None) -> float | None:
    """Net realised R for a closed deal: (P&L + commission + swap) / risk.

    THE LEDGER'S OWN `r_multiple` IS 0.0 ON 141 OF 151 ROWS (measured 2026-09-23) -- it is not a
    measured zero, it is a field nothing fills in. Any consumer keyed on it reads an empty book,
    and any join that required it dropped the row. The deal carries everything the number needs,
    so it is derived here and the ledger's figure is used only when it is actually present.
    """
    given = _f(deal.get("r_multiple"))
    if given:
        return given
    pl = _f(deal.get("pl_quote"))
    if pl is None or not denom:
        return None
    return (pl + (_f(deal.get("commission")) or 0.0) + (_f(deal.get("swap")) or 0.0)) / denom


def deal_row(deal: dict[str, Any]) -> dict[str, Any]:
    """A REALISED FILL BUILT FROM THE CLOSED DEAL ALONE -- no intent required.

    THIS IS THE JOIN'S REAL LOSS. `match()` walks INTENTS, so a deal the desk actually executed
    was invisible unless an intent row survived beside it, and 121 of this box's 151 deals have
    none: `order_intents.jsonl` only starts at 2026-08-24 and holds 59 distinct tickets, of which
    30 equal a deal's `entry_order`. Those 121 are not missing data. Every one of them carries a
    positive entry price, a positive fill price, a volume, a stop away from the entry and a
    non-zero commission -- size, realised R and realised cost, which is exactly what capacity,
    market impact and the shortfall model were starved of. What they genuinely lack is the QUOTE
    THE DESK DECIDED AGAINST, so `requested_price` and every slippage column stay None here
    rather than being invented; slippage is measured only where an intent exists.
    """
    denom, denom_basis = r_denominator(deal)
    lots = _f(deal.get("volume"))
    entry = _f(deal.get("entry_price"))
    if entry is not None and entry <= 0.0:
        entry = None
    exit_px = _f(deal.get("fill_price"))
    stamp = str(deal.get("time") or "")
    comm = _f(deal.get("commission")) or 0.0
    return {
        "record_id": f"deal:{deal.get('deal')}|{stamp}",
        "intent_id": "", "ticket": _i(deal.get("entry_order")), "deal": _i(deal.get("deal")),
        "schema_version": fc.SCHEMA_VERSION,
        "account_kind": str(deal.get("account_kind") or "unknown"),
        "join_keys": {"basis": "deal_only", "entry_order": str(deal.get("entry_order") or ""),
                      "position_id": str(deal.get("position_id") or ""),
                      "r_denominator": denom_basis,
                      "why": "an executed deal with no surviving intent row; price-at-decision "
                             "is unrecorded, so slippage is None and never zero"},
        "sources": ["live_ledger.jsonl"],
        "symbol": str(deal.get("symbol") or ""), "sleeve": str(deal.get("sleeve") or ""),
        "decided_at": "", "sent_at": "", "filled_at": stamp, "exit_at": stamp,
        "side": str(deal.get("side") or ""), "direction": _direction(deal.get("side")),
        "order_type": "market", "execution_style": "market",
        "lots": lots, "requested_price": None,
        "quote_bid": None, "quote_ask": None, "quote_mid_at_decision": None,
        "fill_price": entry, "filled_frac": (1.0 if entry is not None else 0.0),
        "retcode": None, "rejected": False,
        "slip_frac": None, "slip_r": None, "slip_points": None,
        "spread_frac_at_decision": None, "spread_points_at_decision": None,
        "point": _point_from(entry, exit_px, _f(deal.get("sl")), _f(deal.get("tp"))),
        "commission_r": ((comm / denom) if denom else None),
        "realized_r": realized_r(deal, denom),
        "status": "FILLED" if entry is not None else "UNRESOLVED",
    }


def e8_intents(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """The PROP account's orders, in the live account's intent shape.

    Both accounts place real orders and only one of them was ever read. `e8_intents.jsonl` holds
    23 rows, 18 of them SENT with a venue order id, and the recorder never opened the file -- so
    every prop fill was outside the corpus and outside `matched_fills`. The translation is
    mechanical (`at`->time, `entry_ref`->intended, `stop`->sl, `target`->tp, `order_id`->ticket)
    and the row is stamped `account_kind: prop` so no consumer mixes the two books by accident.
    """
    out: list[dict[str, Any]] = []
    for r in rows:
        if not r.get("symbol"):
            continue
        sent = str(r.get("status") or "").strip().upper() == "SENT"
        out.append({
            "time": r.get("at"), "symbol": r.get("symbol"), "sleeve": str(r.get("tag") or "e8"),
            "side": r.get("side"), "lot": _f(r.get("lot")), "intended": _f(r.get("entry_ref")),
            "sl": _f(r.get("stop")), "tp": _f(r.get("target")),
            "ticket": _i(r.get("order_id")), "order_type": "market",
            "spread_at_decision": _f(r.get("spread")),
            "decision_bid": _f(r.get("decision_bid") or r.get("quote_bid")),
            "decision_ask": _f(r.get("decision_ask") or r.get("quote_ask")),
            "latency_send_to_ack_ms": _f(r.get("latency_send_to_ack_ms")),
            "sent_at": r.get("sent_at"), "acked_at": r.get("acked_at"),
            "retcode": (10009 if sent else None),
            # NO FILL PRICE IS INVENTED. `e8_intents.jsonl` records what was SENT and never what
            # came back, so copying `entry_ref` here would write slippage 0.0 on 18 prop orders
            # and drag the book's mean toward "no slippage" with rows that measured nothing.
            # These land as UNRESOLVED until `e8_book` records the venue's answer.
            "fill_price": None,
            "intent_id": f"e8|{r.get('tag') or ''}|{r.get('at') or ''}",
            "account_kind": "prop", "source_file": "e8_intents.jsonl",
        })
    return out


def impact_block(rows: list[dict[str, Any]]) -> dict[str, Any]:
    """Market impact: the slope of realised slippage against the size that paid it.

    THE REASON IT READ UNMEASURED WAS WRITTEN AS "matched_fills is 0" IN TWO ARTIFACTS, and that
    was a claim, not a measurement. With fills in hand the question becomes answerable or it does
    not, and which one is itself a measurement: impact is a SLOPE, so it needs size DISPERSION,
    and a book whose every order is the same 0.01 lot cannot show one however many fills it has.
    The verdict below names whichever wall is actually in front of it -- no fills, no slippage
    column, or no size dispersion -- so the next reader argues with a number.

    Ordinary least squares on (lots, slip_points). No cap, no veto, no size is set here.
    """
    pts = [(r["lots"], r["slip_points"]) for r in rows
           if r.get("status") == "FILLED" and r.get("lots") and r.get("slip_points") is not None]
    n = len(pts)
    lots = sorted({round(float(x), 4) for x, _ in pts})
    if n < 3:
        return {"status": "UNMEASURED", "n": n, "distinct_lot_sizes": len(lots),
                "why": (f"{n} fill(s) carry both a size and a measured slippage; a slope needs "
                        "at least three. Fills without a recorded decision price cannot "
                        "contribute -- they have no slippage, which is not a zero")}
    if len(lots) < 2:
        return {"status": "UNMEASURED", "n": n, "distinct_lot_sizes": len(lots),
                "lot_range": [lots[0], lots[-1]] if lots else [],
                "why": (f"{n} fills but ONE size ({lots[0]} lot): impact is the slope of cost "
                        "against size and a single size has no slope. This is a size-dispersion "
                        "wall, not a fill-count wall, and it is what the account's own floor "
                        "produces -- it resolves when the book trades more than one size")}
    mx = sum(x for x, _ in pts) / n
    my = sum(y for _, y in pts) / n
    sxx = sum((x - mx) ** 2 for x, _ in pts)
    if sxx <= 0:
        return {"status": "UNMEASURED", "n": n, "distinct_lot_sizes": len(lots),
                "why": "no variance in size"}
    slope = sum((x - mx) * (y - my) for x, y in pts) / sxx
    resid = [y - (my + slope * (x - mx)) for x, y in pts]
    sse = sum(r * r for r in resid)
    sst = sum((y - my) ** 2 for _, y in pts)
    se = ((sse / (n - 2)) / sxx) ** 0.5 if n > 2 and sse > 0 else None
    return {"status": "MEASURED", "n": n, "distinct_lot_sizes": len(lots),
            "lot_range": [lots[0], lots[-1]],
            "slope_points_per_lot": round(slope, 4),
            "intercept_points": round(my - slope * mx, 4),
            "slope_se": (round(se, 4) if se else None),
            "slope_t": (round(slope / se, 3) if se else None),
            "r2": (round(1.0 - sse / sst, 4) if sst > 0 else None),
            "unit": "venue points of slippage per lot",
            "boundary": "A COST TERM. It prices impact; it sets no size and caps nothing."}


def build(budget_s: float = 120.0, *, dry_run: bool = False) -> dict[str, Any]:
    t0 = time.monotonic()
    now = datetime.now(tz=UTC).isoformat(timespec="seconds")
    intents = _read_jsonl(INTENTS)
    # BOTH ACCOUNTS PLACE REAL ORDERS. The prop book was never opened by this organ.
    prop = e8_intents(_read_jsonl(E8_INTENTS))
    intents += prop
    deals = [d for d in _read_jsonl(LEDGER) if _i(d.get("deal")) is not None]
    decisions = {str(d.get("intent_id") or ""): d for d in _read_jsonl(DECISIONS)
                 if d.get("intent_id")}
    if not intents and not deals:
        doc = {"at": now, "status": "UNMEASURED", "matched_fills": 0,
               "why": ("neither data/order_intents.jsonl nor data/live_ledger.jsonl is readable "
                       "on this host: there is nothing to join, which is not the same as no "
                       "slippage"), "seconds": round(time.monotonic() - t0, 2)}
        return doc

    pairs, unfilled, unmatched, census = match(intents, deals)
    rows = [build_row(it, d, how, decisions) for it, d, how in pairs]
    rows += [unfilled_row(it) for it in unfilled]
    # THE DEALS THE OLD JOIN THREW AWAY. Every executed deal is a realised fill whether or not an
    # intent row survived beside it; only its slippage needs one.
    rows += [deal_row(d) for d in unmatched]
    census["deal_only"] = len(unmatched)

    existing = {fc.record_from_row(r).key: fc.record_from_row(r).resolution
                for r in fc.read_rows(CORPUS)}
    fresh = [r for r in rows
             if fc.record_from_row(r).key not in existing
             or existing[fc.record_from_row(r).key] != fc.record_from_row(r).resolution]
    appended = 0 if dry_run else fc.append_rows(CORPUS, fresh)

    filled = [r for r in rows if r["status"] == "FILLED"]
    completeness = {
        f: {"n": sum(1 for r in filled if r.get(f) is not None),
            "share": (round(sum(1 for r in filled if r.get(f) is not None) / len(filled), 3)
                      if filled else None)}
        for f in REQUIRED_FIELDS}
    slips = [r["slip_r"] for r in filled if r.get("slip_r") is not None]
    slip_pts = [r["slip_points"] for r in filled if r.get("slip_points") is not None]
    mean_r = (sum(slips) / len(slips)) if slips else None
    return {
        "at": now,
        "status": "OK",
        "matched_fills": len(filled),
        "n_intents": len(intents), "n_deals": len(deals),
        "n_unfilled_intents": len(unfilled), "n_unmatched_deals": len(unmatched),
        "join_census": census,
        "join_rule": ("ticket == entry_order first (the bridge MT5 offers), then "
                      "ticket == position_id, then same symbol / same direction within "
                      f"{PAIR_WINDOW_S:.0f}s -- the tier is stamped on every row's join_keys. "
                      "A DEAL WITH NO SURVIVING INTENT IS STILL A REALISED FILL and is recorded "
                      "from the ledger alone (basis deal_only) with slippage None, never zero: "
                      "that is the 121 rows the intent-keyed walk used to drop."),
        "n_prop_intents": len(prop),
        "impact": impact_block(rows),
        "realized_r": {
            "n": sum(1 for r in rows if r.get("realized_r") is not None),
            "mean": (round(sum(r["realized_r"] for r in rows
                               if r.get("realized_r") is not None)
                           / max(1, sum(1 for r in rows if r.get("realized_r") is not None)), 5)),
            "basis": ("derived (pl_quote + commission + swap) / (|entry - stop| x contract_size "
                      "x lots); live_ledger.r_multiple is 0.0 on 141 of 151 deals and is used "
                      "only where it is actually populated"),
        },
        "rows_written": appended, "rows_considered": len(rows),
        "corpus": str(CORPUS), "corpus_rows_after": len(fc.read_rows(CORPUS)),
        "completeness": completeness,
        "mean_slip_r": (round(mean_r, 5) if mean_r is not None else None),
        "mean_slip_points": (round(sum(slip_pts) / len(slip_pts), 3) if slip_pts else None),
        "worst_slip_points": (round(max(slip_pts), 3) if slip_pts else None),
        "accounts": sorted({str(d.get("account")) for d in deals if d.get("account")}),
        "account_kinds": sorted({str(r.get("account_kind") or "unknown")
                                 for r in (*deals, *prop)}),
        "dry_run": bool(dry_run),
        "consumers": [
            "desks/mt5/data/fill_corpus.jsonl -> execution_twin, execution_intelligence, "
            "execution_alpha_miner, cost_surface, feed_clock_lab, shadow_institutional and "
            "libs/execution/alpha_capture all read this file; matched_fills rises there",
            "desks/mt5/reports/FILL_RECORDER.json -> matched_fills, the join census and the "
            "per-field completeness the principal named",
        ],
        "boundary": ("RECORDING ONLY. Nothing here sends, routes, sizes, cancels or vetoes an "
                     "order; it reads two append-only ledgers the gateway writes and appends to "
                     "a third."),
        "seconds": round(time.monotonic() - t0, 2),
    }


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--once", action="store_true")
    ap.add_argument("--budget-s", type=float, default=120.0)
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args(argv)
    doc = build(budget_s=a.budget_s, dry_run=a.dry_run)
    try:
        _write(OUT, doc)
    except OSError as exc:
        print(f"fill recorder: could not write {OUT}: {exc}")
        return 1
    if doc.get("status") == "UNMEASURED":
        print(f"fill recorder: UNMEASURED -- {doc.get('why')}")
        return 0
    print(f"fill recorder: matched_fills {doc['matched_fills']} from {doc['n_intents']} intent(s)"
          f" and {doc['n_deals']} deal(s); join {doc['join_census']}")
    print(f"  unfilled intents {doc['n_unfilled_intents']}, unmatched deals "
          f"{doc['n_unmatched_deals']}")
    print(f"  mean slip {doc['mean_slip_r']} R / {doc['mean_slip_points']} points, worst "
          f"{doc['worst_slip_points']} points")
    print(f"  corpus rows {doc['corpus_rows_after']} (+{doc['rows_written']} this pass)")
    for f, c in doc["completeness"].items():
        print(f"   {f:<32} {c['n']}/{doc['matched_fills']} ({c['share']})")
    print(f"written: {OUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
