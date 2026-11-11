"""E8 GOLD OCO WATCH -- every minute, cancel and flatten only: no opposite gold exposure across
accounts stands longer than a minute.

WHY (audit HOLD on #959, M1, 2026-11-11). With FTMO mirroring E8's bracket (gold_oco rule 8), the
two accounts rest the same two levels. FTMO's buy stop can fill on FTMO's own quote while E8's
has not; the day's direction is then long, and E8's SELL stop must go. E8's own pass
(`prop/e8_gold.py`, task E8-Gold) cancels it -- but only every five minutes, and a reversal inside
those five minutes could fill E8 short against FTMO's long: opposite exposure across accounts,
which the desk's hard rule forbids. The same holds the other way round (E8 fills first: FTMO's
follower runs every minute and cancels its own copy; this watch is what makes E8's side as fast).

WHAT IT DOES, ONCE A MINUTE (task MT5-E8-OcoWatch):
  1. names the E8 account by its keyed account key (`gold_oco.tradelocker_oco_key`; unnamed ->
     nothing at all, E8's own pass pages it);
  2. publishes E8's gold state from the venue and CLAIMS the day's direction from E8's own fills
     (`gold_oco.sync_lane`), so an E8 fill reaches FTMO's and Fusion's next pass within a minute,
     not five;
  3. CANCELS every resting E8 gold entry this lane placed (E8's intents journal and E8's own state)
     that is against the day's direction, whichever account's fill set it (`gold_oco.cancel_plan`,
     rules 2 and 7; a BLIND direction state cancels every one, exactly as E8's pass does);
  4. FLATTENS an E8 gold position opened today against the day's direction, if one filled before
     its twin could be cancelled (`gold_oco.positions_to_flatten`, rule 7) -- only this lane's own
     positions (opened by one of its legs), never another;
  5. republishes E8's state after any cancel or close.
It NEVER places, re-places, resizes or moves a stop: every write it makes reduces exposure. It
never writes E8's own state file (`e8_gold_state.json` stays the E8 pass's).

TRADING DATE. The desk dates gold days by the MT5 server clock (`gold_oco.trading_date`), which
is New York + 7 h (UTC+2 / UTC+3 with New York's DST); `server_date` derives it from the wall
clock, so the watch needs no terminal.

ARMED exactly when E8 is (`data/E8_GOLD_ARMED`): unarmed it reports what it would cancel or close
and sends nothing. Every write goes through the order door (caller "e8_gold:oco_watch", which the
FTMO follower reads as E8's own cancel).

    python prop/e8_oco_watch.py           one pass
"""
from __future__ import annotations

import json
import os
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

DESK = Path(__file__).resolve().parents[1]
ROOT = DESK.parent.parent
for _p in (str(DESK), str(ROOT)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from mt5desk import gold_oco as _oco  # noqa: E402

SYMBOL = "XAUUSD"
LANE = "e8"
CALLER = "e8_gold:oco_watch"
E8_STATE = DESK / "data" / "e8_gold_state.json"
E8_INTENTS = DESK / "data" / "e8_gold_intents.jsonl"
ARMED_MARKER = DESK / "data" / "E8_GOLD_ARMED"
OUT = DESK / "reports" / "E8_OCO_WATCH.json"
LOG = DESK / "logs" / "e8_oco_watch.log"
#: E8's legs older than this are not looked for (a bracket lives BRACKET_TTL_HOURS = 6 h).
LEG_LOOKBACK = timedelta(hours=24)
#: The end of E8's intents journal one pass reads.
TAIL_BYTES = 4_000_000
#: The MT5 server clock is New York + this (decision_core / the box's broker clock).
SERVER_OFFSET_FROM_NY = timedelta(hours=7)


def log(msg: str) -> None:
    line = f"{datetime.now(tz=UTC).isoformat(timespec='seconds')} {msg}"
    print(line)
    try:
        LOG.parent.mkdir(parents=True, exist_ok=True)
        with LOG.open("a", encoding="utf-8") as fh:
            fh.write(line + "\n")
    except OSError:
        pass


def server_date(now: datetime) -> str:
    """The trading date on the MT5 server clock (New York + 7 h), as every gold lane dates it."""
    from zoneinfo import ZoneInfo
    ny = now.astimezone(ZoneInfo("America/New_York"))
    return (ny.replace(tzinfo=None) + SERVER_OFFSET_FROM_NY).date().isoformat()


def _journal_tail(path: Path, max_bytes: int = TAIL_BYTES) -> list[dict[str, Any]] | None:
    try:
        with open(path, "rb") as fh:
            fh.seek(0, os.SEEK_END)
            size = fh.tell()
            fh.seek(max(0, size - max_bytes))
            data = fh.read()
    except FileNotFoundError:
        return []
    except OSError:
        return None
    lines = data.decode("utf-8", "replace").splitlines()
    if size > max_bytes and lines:
        lines = lines[1:]
    out: list[dict[str, Any]] = []
    for ln in lines:
        try:
            row = json.loads(ln)
        except ValueError:
            continue
        if isinstance(row, dict):
            out.append(row)
    return out


def own_legs(journal: list[dict[str, Any]] | None, state: Any, *,
             now: datetime) -> dict[int, dict[str, Any]]:
    """{order id: {"side", "window"}} of every gold entry leg E8-Gold sent recently: its intents
    journal (SENT rows, written at send time) and its own state's window orders. Pure."""
    out: dict[int, dict[str, Any]] = {}
    for r in journal or []:
        if r.get("status") != "SENT" or r.get("order_id") is None:
            continue
        try:
            at = datetime.fromisoformat(str(r.get("at")))
            oid = int(r["order_id"])
        except (TypeError, ValueError):
            continue
        if at.tzinfo is None or now - at > LEG_LOOKBACK:
            continue
        out[oid] = {"side": r.get("side"), "window": r.get("window")}
    windows = (state or {}).get("windows") if isinstance(state, dict) else None
    for name, w in (windows or {}).items():
        for side, leg in ((w or {}).get("orders") or {}).items():
            try:
                if leg.get("id") is not None:
                    out.setdefault(int(leg["id"]), {"side": side, "window": name})
            except (AttributeError, TypeError, ValueError):
                continue
    return out


def _write_out(doc: dict[str, Any]) -> None:
    try:
        OUT.parent.mkdir(parents=True, exist_ok=True)
        tmp = OUT.with_suffix(".tmp")
        tmp.write_text(json.dumps(doc, indent=1, default=str), "utf-8")
        os.replace(tmp, OUT)
    except OSError as exc:
        log(f"report not written ({type(exc).__name__}: {exc})")


def run(venue: Any, *, armed: bool = False, now: datetime | None = None) -> dict[str, Any]:
    """One pass against the connected TradeLocker `venue`. Never raises past its own report."""
    from mt5desk import order_door
    venue = order_door.guard_venue(venue, caller=CALLER, log=log)
    now = now or datetime.now(tz=UTC)
    today = server_date(now)
    doc: dict[str, Any] = {"at": now.isoformat(timespec="seconds"), "armed": bool(armed),
                           "trading_date": today, "cancelled": [], "flattened": [],
                           "actions": [], "alerts": []}
    try:
        key = _oco.tradelocker_oco_key(venue)
    except _oco.IdentityUnavailable as exc:
        doc.update({"status": "ACCOUNT_UNNAMED", "why": str(exc)})
        _write_out(doc)
        return doc
    try:
        iid = int(venue.instrument_id(SYMBOL))
    except Exception as exc:
        doc.update({"status": "VENUE_UNREADABLE", "why": f"{type(exc).__name__}: {exc}"[:200]})
        _write_out(doc)
        return doc

    def rows() -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
        return _oco.tradelocker_gold_rows(venue.positions(), venue.orders(), iid)

    # Publish E8's book and claim the direction from E8's own fills, under the placement lock.
    sync = _oco.sync_lane(LANE, key, rows, date=today, holder="e8_oco_watch")
    doc["sync"] = {"published": sync.get("published"), "why": sync.get("why"),
                   "claims": sync.get("claims")}
    for c in sync.get("claims") or []:
        if c.get("won"):
            log(f"gold OCO: an E8 fill set {today}'s direction {c.get('direction')}")
    try:
        positions, orders = venue.positions(), venue.orders()
    except Exception as exc:
        doc.update({"status": "VENUE_UNREADABLE", "why": f"{type(exc).__name__}: {exc}"[:200]})
        _write_out(doc)
        return doc
    state: Any = None
    try:
        state = json.loads(E8_STATE.read_text("utf-8-sig"))
    except (OSError, ValueError):
        doc["e8_state_unreadable"] = True
    mine = own_legs(_journal_tail(E8_INTENTS), state, now=now)
    entries = _oco.tradelocker_entry_orders(positions, orders)
    resting = [{"id": int(o["id"]), "side": o.get("side"), "window": mine[int(o["id"])]["window"]}
               for o in entries if o.get("id") is not None and int(o["id"]) in mine]
    entry, why = _oco.day_entry(today)
    plan, reason = _oco.cancel_plan(LANE, entry, why, resting)
    if why is not None and plan:
        doc["alerts"].append(f"gold OCO blind: {why}; every resting E8 gold leg cancelled")
    touched = False
    for leg in plan:
        act: dict[str, Any] = {"act": "oco_direction_cancel", "order_id": leg["id"],
                               "side": _oco.side_of(leg["side"]), "window": leg["window"],
                               "why": reason, "ok": False}
        if armed:
            try:
                act["ok"] = bool(venue.cancel(int(leg["id"])))
            except Exception as exc:
                act["why"] += f"; cancel FAILED: {type(exc).__name__}: {exc}"[:160]
            if act["ok"] and entry is not None:
                _oco.note_cancelled(today, LANE, key, leg["id"], leg["side"],
                                    holder="e8_oco_watch")
            touched = touched or act["ok"]
        else:
            act["shadow"] = True
        if act["ok"]:
            doc["cancelled"].append(leg["id"])
        log(f"[{leg['window']}] cancel {act['side']} order {leg['id']}: "
            f"{'shadow' if act.get('shadow') else ('ok' if act['ok'] else 'NOT acknowledged')}; "
            f"{act['why']}")
        doc["actions"].append(act)
    # Rule 7: a fill against the direction (the twin filled before its cancel) is closed now.
    if why is None and entry is not None:
        filled: dict[int, int] = {}
        try:
            hist = venue._api.get_all_orders(history=True, lookback_period="2D")
            for o in (hist.to_dict("records") if hasattr(hist, "to_dict") else list(hist)):
                if str(o.get("status") or "").lower() == "filled" and o.get("positionId"):
                    filled[int(o["id"])] = int(o["positionId"])
        except Exception as exc:
            doc["history_unreadable"] = f"{type(exc).__name__}: {exc}"[:160]
        own_pos = {p for o, p in filled.items() if o in mine}
        for w in ((state or {}).get("windows") or {}).values() if isinstance(state, dict) else []:
            if isinstance(w, dict) and w.get("position_id") is not None:
                own_pos.add(int(w["position_id"]))
        gold = [{"id": int(p["id"]), "side": p.get("side"),
                 "opened_date": _oco.ms_trading_date(p.get("openDate"))}
                for p in positions if p.get("id") is not None
                and int(p.get("tradableInstrumentId") or 0) == iid]
        for row in _oco.positions_to_flatten(entry, gold, date=today):
            what = (f"E8 gold {_oco.side_of(row['side'])} position {row['id']} against {today}'s "
                    f"direction {entry.get('direction')} (first fill on "
                    f"{entry.get('first_fill_lane')})")
            doc["alerts"].append(what)
            if row["id"] not in own_pos:
                log(f"ALERT {what}; not this lane's position, not closed")
                continue
            act = {"act": "oco_direction_flatten", "position_id": row["id"], "why": what,
                   "ok": False}
            if armed:
                try:
                    act["ok"] = bool(venue.close(int(row["id"])))
                except Exception as exc:
                    act["why"] += f"; close FAILED: {type(exc).__name__}: {exc}"[:160]
                touched = touched or act["ok"]
            else:
                act["shadow"] = True
            if act["ok"]:
                doc["flattened"].append(row["id"])
            log(f"{'' if act['ok'] else 'ALERT '}FLATTEN {what}: "
                f"{'shadow' if act.get('shadow') else ('ok' if act['ok'] else 'NOT acknowledged')}")
            doc["actions"].append(act)
    if touched:
        res = _oco.sync_lane(LANE, key, rows, date=today, holder="e8_oco_watch:after")
        doc["republished"] = bool(res.get("published"))
    doc["direction"] = None if entry is None else {k: entry.get(k) for k in
                                                   ("direction", "first_fill_lane")}
    doc["status"] = "OK" if why is None else "DIRECTION_UNREADABLE"
    _write_out(doc)
    return doc


def main(argv: list[str] | None = None) -> int:
    armed = ARMED_MARKER.exists()
    try:
        from prop.tradelocker_venue import TradeLockerVenue, load_credentials
        venue = TradeLockerVenue(creds=load_credentials()).connect()
    except Exception as exc:
        log(f"venue unavailable ({type(exc).__name__}: {exc}); nothing done")
        _write_out({"at": datetime.now(tz=UTC).isoformat(timespec="seconds"),
                    "status": "VENUE_UNAVAILABLE", "armed": armed,
                    "why": f"{type(exc).__name__}: {exc}"[:200]})
        return 1
    doc = run(venue, armed=armed)
    log(f"e8 oco watch: {'ARMED' if armed else 'SHADOW'} status={doc.get('status')} "
        f"cancelled={doc.get('cancelled')} flattened={doc.get('flattened')}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
