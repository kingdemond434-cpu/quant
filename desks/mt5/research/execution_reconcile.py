#!/usr/bin/env python3
"""EXECUTION RECONCILIATION (ARCH-06): the venue's positions against the order door's ledger
against the gateway's intent ledger -- for partial fills, missing acknowledgements, restarts and
duplicate messages -- and the account record checked against itself.

    python desks/mt5/research/execution_reconcile.py         # hourly leg `execution_reconcile`
    python desks/mt5/research/execution_reconcile.py --json

WHY (PM delivery check 2026-10-07, ARCH-06). Each piece existed alone: the order door ledgers
every attempt (`data/order_door_ledger.jsonl`), the gateway journals every placement
(`data/order_intents.jsonl`), the restart reconcile settles in-doubt keys and restores orphaned
stops, and the account publisher wrote a balance and a position COUNT. Nothing joined them, so a
send with no intent row, a partial fill whose position is larger than the fill, an
acknowledgement lost and never settled, a stopless position left after a restart, or a deal
delivered twice was visible to no artifact.

TWO PARTS, ONE JOIN (`reconcile`):
  live   the box's own files: account_state.json (positions, cash, margin, financing, written by
         ops/publish_account_state.py), the door ledger, the intents and the deal ledger. A
         file that is absent here is UNMEASURED, never clean (L1.28a).
  drill  SHADOW: the same join run over ledgers the real `order_door.send` and
         `order_door.restart_reconcile` write against a broker double in a temp directory, and
         over the real gateway's ledgers under `libs.tiers.gateway_drill` faults. Each scenario
         names what the join must find -- a consistent book must reconcile, a planted break must
         be caught -- so the join itself is drilled, not only the box it reads.

A BREAK is a ledger inconsistency a human must look at; a NOTE is recorded and needs nothing.
Writes desks/mt5/reports/EXECUTION_RECONCILE.json, read by `recovery_drills` (rows
`account_ledger` and `reconciliation`) and the acceptance drills.
"""
from __future__ import annotations

import argparse
import contextlib
import itertools
import json
import math
import os
import sys
import tempfile
import time
from collections import Counter
from collections.abc import Callable, Iterator, Mapping
from datetime import UTC, datetime, timedelta
from pathlib import Path
from types import SimpleNamespace
from typing import Any

DESK = Path(__file__).resolve().parents[1]
ROOT = DESK.parent.parent
for _p in (str(DESK), str(ROOT)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

DATA = DESK / "data"
OUT = DESK / "reports" / "EXECUTION_RECONCILE.json"
ACCOUNT = DATA / "account_state.json"
DOOR = DATA / "order_door_ledger.jsonl"
INTENTS = DATA / "order_intents.jsonl"
DEALS = DATA / "live_ledger.jsonl"
#: How much of each ledger the live join reads (the tail): the hour's question is the recent
#: book, and the full door ledger grows without bound.
TAIL_ROWS = 5000
#: An in-doubt attempt older than this with no settlement is a BREAK: the door itself forgets
#: the key after its own TTL (order_door.IN_DOUBT_TTL, 45 min), so past it nothing guards the
#: resend any more. Kept equal to the door's, read from it when importable.
IN_DOUBT_TTL = timedelta(minutes=45)

BREAK, NOTE = "BREAK", "NOTE"
RECONCILED, BREAKS, UNMEASURED = "RECONCILED", "BREAKS", "UNMEASURED"


def _num(v: Any) -> float | None:
    try:
        f = float(v)
    except (TypeError, ValueError):
        return None
    return f if math.isfinite(f) else None


def _ts(v: Any) -> datetime | None:
    try:
        t = datetime.fromisoformat(str(v).replace("Z", "+00:00"))
    except ValueError:
        return None
    return t if t.tzinfo else t.replace(tzinfo=UTC)


def _jsonl_tail(p: Path, n: int = TAIL_ROWS) -> list[dict[str, Any]] | None:
    try:
        lines = p.read_text("utf-8-sig").splitlines()[-n:]
    except OSError:
        return None
    out: list[dict[str, Any]] = []
    for ln in lines:
        with contextlib.suppress(ValueError):
            r = json.loads(ln)
            if isinstance(r, dict):
                out.append(r)
    return out


def _key(req: Mapping[str, Any]) -> str:
    try:
        from mt5desk import order_door
        return str(order_door.dedupe_key(req))
    except Exception:
        return "|".join(str(req.get(k)) for k in ("symbol", "magic", "comment", "type",
                                                 "volume", "price"))


def _match_sig(symbol: Any, sl: Any, tp: Any, vol: Any) -> tuple[str, str, str, str]:
    def r(x: Any) -> str:
        f = _num(x)
        return f"{f:.8g}" if f is not None else "?"
    return (str(symbol or ""), r(sl), r(tp), r(vol))


def reconcile(door: list[dict[str, Any]], intents: list[dict[str, Any]] | None = None,
              positions: list[dict[str, Any]] | None = None,
              deals: list[dict[str, Any]] | None = None,
              account: Mapping[str, Any] | None = None, *,
              now: datetime | None = None, magic: int | None = None) -> dict[str, Any]:
    """The join. Pure over parsed rows; every input may be None (that part is UNMEASURED)."""
    now = now or datetime.now(tz=UTC)
    findings: list[dict[str, Any]] = []

    def find(kind: str, sev: str, detail: str, **kw: Any) -> None:
        findings.append({"check": kind, "severity": sev, "detail": detail, **kw})

    sent_opens = [r for r in door if r.get("kind") == "open" and r.get("door") == "sent"]
    measured: dict[str, bool] = {"door": bool(door), "intents": intents is not None,
                                 "positions": positions is not None, "deals": deals is not None,
                                 "account": account is not None}

    # 1. EVERY GATEWAY SEND HAS AN INTENT, EVERY INTENT WITH A TICKET WENT THROUGH THE DOOR.
    if intents is not None:
        want = Counter(_match_sig(r.get("symbol"), (r.get("request") or {}).get("sl"),
                                  (r.get("request") or {}).get("tp"),
                                  (r.get("request") or {}).get("volume"))
                       for r in sent_opens if r.get("caller") == "gateway")
        have = Counter(_match_sig(r.get("symbol"), r.get("sl"), r.get("tp"), r.get("lot"))
                       for r in intents)
        for sig, n in (want - have).items():
            find("send_without_intent", BREAK,
                 f"{n} gateway send(s) {sig} in the door ledger with no intent row", sig=sig)
        door_tickets = {int(_num(r.get("order")) or 0) for r in door} - {0}
        for r in intents:
            t = int(_num(r.get("ticket")) or 0)
            if t and door_tickets and t not in door_tickets:
                find("intent_without_door", BREAK,
                     f"intent ticket {t} ({r.get('sleeve')}) has no order-door row: an order "
                     "that did not pass the door", ticket=t)

    # 2. PARTIAL FILLS: the residual is recorded, and no position is larger than its fill.
    pos_by_ticket: dict[int, dict[str, Any]] = {}
    for p in positions or []:
        for k in ("ticket", "identifier"):
            t = int(_num(p.get(k)) or 0)
            if t:
                pos_by_ticket[t] = p
    residuals: list[dict[str, Any]] = []
    for r in sent_opens:
        v = r.get("validation")
        if v == "anomaly":
            find("fill_anomaly", BREAK, f"door validated an anomaly: {r.get('notes')}",
                 order=r.get("order"))
        if v != "partial":
            continue
        asked = _num((r.get("request") or {}).get("volume")) or 0.0
        got = _num(r.get("fill_volume")) or 0.0
        residuals.append({"order": r.get("order"), "symbol": r.get("symbol"),
                          "requested": asked, "filled": got,
                          "residual": round(asked - got, 8)})
        find("partial_fill", NOTE, f"order {r.get('order')} filled {got:g} of {asked:g}; "
                                   f"residual {asked - got:g} recorded, not re-sent")
        p = pos_by_ticket.get(int(_num(r.get("order")) or 0))
        if positions is not None and p is not None:
            pv = _num(p.get("volume")) or 0.0
            if pv > got + 1e-9:
                find("position_exceeds_fill", BREAK,
                     f"position {p.get('ticket')} holds {pv:g} lots against a {got:g} fill",
                     order=r.get("order"))

    # 3. MISSING ACKS: every in-doubt attempt is settled (landed or cleared) or still young.
    settled: set[str] = set()
    for r in door:
        if r.get("kind") == "restart_reconcile":
            for s in r.get("in_doubt") or []:
                if isinstance(s, dict) and (s.get("landed") or s.get("cleared")):
                    settled.add(str(s.get("key")))
        if r.get("in_doubt_resolved") or r.get("reason") == "duplicate_of_in_doubt":
            settled.add(_key(r.get("request") or {}))
    pending: list[dict[str, Any]] = []
    for r in sent_opens:
        if not r.get("in_doubt"):
            continue
        k = _key(r.get("request") or {})
        at = _ts(r.get("at"))
        if k in settled:
            find("missing_ack", NOTE, f"in-doubt attempt at {r.get('at')} settled", key=k)
            continue
        age = (now - at) if at else None
        if age is not None and age <= IN_DOUBT_TTL:
            pending.append({"key": k, "at": r.get("at")})
            find("missing_ack", NOTE, f"in-doubt attempt at {r.get('at')} pending settlement",
                 key=k)
        else:
            find("missing_ack_unsettled", BREAK,
                 f"in-doubt attempt at {r.get('at')} was never settled by a restart reconcile "
                 f"or a later send, and the door's own guard has expired", key=k)

    # 4. RESTARTS: every stopless position a restart found was acted on.
    restarts = [r for r in door if r.get("kind") == "restart_reconcile"]
    for r in restarts:
        if r.get("verdict") == "UNMEASURED":
            find("restart_unreadable", NOTE, f"restart reconcile at {r.get('at')} could not read "
                                             f"the venue: {r.get('why')}")
        for s in r.get("stopless") or []:
            act = str((s or {}).get("action") or "")
            if act.startswith(("restored", "shadow")):
                find("restart_stop", NOTE, f"stopless {s.get('ticket')}: {act}")
            else:
                find("restart_stopless", BREAK,
                     f"position {s.get('ticket')} {s.get('symbol')} held without a stop after a "
                     f"restart: {act}", ticket=s.get("ticket"))

    # 5. DUPLICATE MESSAGES: a deal delivered twice is counted once; two different deals under
    #    one ticket, or one order ticket acknowledged twice, is a break.
    n_dup_deals = 0
    if deals is not None:
        seen: dict[int, str] = {}
        for d in deals:
            t = int(_num(d.get("deal")) or 0)
            if not t:
                continue
            body = json.dumps({k: d.get(k) for k in ("symbol", "volume", "pl_quote", "fill_price",
                                                     "order")}, sort_keys=True, default=str)
            if t in seen:
                n_dup_deals += 1
                if seen[t] != body:
                    find("conflicting_duplicate_deal", BREAK,
                         f"deal {t} delivered twice with different contents", deal=t)
            else:
                seen[t] = body
        if n_dup_deals:
            find("duplicate_delivery", NOTE, f"{n_dup_deals} repeated deal message(s) counted "
                                             "once")
    acked = Counter(int(_num(r.get("order")) or 0) for r in sent_opens
                    if r.get("validation") in ("ok", "partial"))
    for t, n in acked.items():
        if t and n > 1:
            find("order_acked_twice", BREAK, f"order ticket {t} acknowledged {n} times", order=t)
    by_key: dict[str, list[dict[str, Any]]] = {}
    for r in sent_opens:
        by_key.setdefault(_key(r.get("request") or {}), []).append(r)
    for k, rows in by_key.items():
        rows = sorted(rows, key=lambda x: str(x.get("at")))
        for a, b in itertools.pairwise(rows):
            ta, tb = _ts(a.get("at")), _ts(b.get("at"))
            if a.get("in_doubt") and b.get("validation") in ("ok", "partial") and ta and tb \
                    and tb - ta <= IN_DOUBT_TTL and k not in settled:
                find("duplicate_execution", BREAK,
                     f"an identical send at {b.get('at')} went out while {a.get('at')} was "
                     "still in doubt and unsettled", key=k)

    # 6. THE ACCOUNT RECORD AGAINST ITSELF.
    if account is not None:
        lc = account.get("ledger_check") or {}
        if lc.get("consistent") is False:
            find("account_inconsistent", BREAK,
                 f"equity differs from balance + floating + swap by "
                 f"{lc.get('equity_minus_balance_floating_swap')}")
        rows_ = account.get("positions")
        if isinstance(rows_, list) and account.get("open_positions") not in (None, len(rows_)):
            find("account_count_mismatch", BREAK,
                 f"open_positions {account.get('open_positions')} vs {len(rows_)} rows")
        if magic is not None and isinstance(rows_, list) and door:
            known = {int(_num(r.get("order")) or 0) for r in door} - {0}
            for p in rows_:
                if int(_num(p.get("magic")) or 0) != magic:
                    continue
                t = int(_num(p.get("identifier")) or _num(p.get("ticket")) or 0)
                if t and t not in known:
                    find("position_without_door_row", NOTE,
                         f"desk position {t} {p.get('symbol')} opened outside the ledger tail "
                         "read here")

    breaks = [f for f in findings if f["severity"] == BREAK]
    any_input = bool(door) or bool(intents) or bool(positions) or bool(deals) or bool(account)
    return {"verdict": BREAKS if breaks else RECONCILED if any_input else UNMEASURED,
            "breaks": len(breaks), "findings": findings, "residuals": residuals,
            "pending_in_doubt": pending, "restarts": len(restarts),
            "duplicate_deal_messages": n_dup_deals, "measured": measured,
            "rows": {"door": len(door), "intents": None if intents is None else len(intents),
                     "positions": None if positions is None else len(positions),
                     "deals": None if deals is None else len(deals)}}


# ------------------------------------------------------------------------------ the live join
def _desk_magic() -> int | None:
    """The gateway's magic number, read from its SOURCE: research never imports the gateway
    (ARCH-12 -- the order path stays out of research processes)."""
    import re
    try:
        m = re.search(r"^MAGIC\s*=\s*(\d+)", (DESK / "mt5desk" / "gateway.py").read_text(
            "utf-8"), re.M)
    except OSError:
        return None
    return int(m.group(1)) if m else None


def live(now: datetime | None = None) -> dict[str, Any]:
    door = _jsonl_tail(DOOR)
    intents = _jsonl_tail(INTENTS)
    deals = _jsonl_tail(DEALS)
    try:
        account: dict[str, Any] | None = json.loads(ACCOUNT.read_text("utf-8-sig"))
    except (OSError, ValueError):
        account = None
    positions = (account or {}).get("positions") if isinstance(account, dict) else None
    res = reconcile(door or [], intents, positions if isinstance(positions, list) else None,
                    deals, account, now=now, magic=_desk_magic())
    absent = [str(p.relative_to(DESK)) for p, x in ((DOOR, door), (INTENTS, intents),
                                                    (ACCOUNT, account)) if x is None]
    if absent and res["verdict"] != BREAKS:
        res["verdict"] = UNMEASURED
    res["absent"] = absent
    res["account_fields"] = sorted(k for k in ("balance", "equity", "margin", "margin_free",
                                               "margin_level", "swap", "positions")
                                   if isinstance(account, dict) and account.get(k) is not None)
    res["account_updated_at"] = (account or {}).get("updated_at") if isinstance(account,
                                                                                dict) else None
    return res


# ------------------------------------------------------------------------------ the drill
class _Venue:
    """A broker double whose `order_send` answers from a script and records what landed."""

    TRADE_ACTION_DEAL = 1
    TRADE_ACTION_PENDING = 5
    TRADE_ACTION_SLTP = 6
    POSITION_TYPE_BUY = 0
    DEAL_ENTRY_IN = 0

    def __init__(self, plan: list[Any], fill: float | None = None, lands: bool = True) -> None:
        self.plan, self.fill, self.lands = list(plan), fill, lands
        self.sent: list[dict[str, Any]] = []
        self.orders: list[SimpleNamespace] = []
        self.positions: list[SimpleNamespace] = []

    def order_check(self, req: dict[str, Any]) -> SimpleNamespace:
        return SimpleNamespace(retcode=0, comment="ok")

    def order_send(self, req: dict[str, Any]) -> Any:
        self.sent.append(dict(req))
        step = self.plan.pop(0) if self.plan else 10009
        ticket = 9000 + len(self.sent)
        vol = float(req.get("volume") or 0.0)
        filled = self.fill if (self.fill is not None and step == 10010) else vol
        if self.lands and req.get("action") == self.TRADE_ACTION_DEAL:
            self.positions.append(SimpleNamespace(
                ticket=ticket, identifier=ticket, symbol=req.get("symbol"), volume=filled,
                magic=req.get("magic"), comment=req.get("comment"), sl=req.get("sl"),
                tp=req.get("tp"), type=0, time=int(time.time())))
        if step is None:
            return None
        return SimpleNamespace(retcode=step, order=ticket, deal=ticket + 50000,
                               volume=filled, price=req.get("price"), comment="double")

    def orders_get(self, **_: Any) -> tuple[SimpleNamespace, ...]:
        return tuple(self.orders)

    def positions_get(self, **_: Any) -> tuple[SimpleNamespace, ...]:
        return tuple(self.positions)

    def history_deals_get(self, *_: Any, **__: Any) -> tuple[()]:
        return ()

    def symbol_info_tick(self, symbol: str) -> SimpleNamespace:
        return SimpleNamespace(bid=1.1000, ask=1.1002, time=0)

    def last_error(self) -> tuple[int, str]:
        return (-10005, "IPC timeout")


MAGIC = 341953


def _req(volume: float = 0.10, comment: str = "DWdrill") -> dict[str, Any]:
    return {"action": 1, "symbol": "EURUSD", "volume": volume, "type": 0, "price": 1.1002,
            "sl": 1.0980, "tp": 1.1040, "magic": MAGIC, "comment": comment}


@contextlib.contextmanager
def _door_dir() -> Iterator[Path]:
    with tempfile.TemporaryDirectory(prefix="exec_recon_") as tmp:
        prev = os.environ.get("MT5_ORDER_DOOR_DIR")
        os.environ["MT5_ORDER_DOOR_DIR"] = tmp
        try:
            yield Path(tmp)
        finally:
            if prev is None:
                os.environ.pop("MT5_ORDER_DOOR_DIR", None)
            else:
                os.environ["MT5_ORDER_DOOR_DIR"] = prev


def _positions(v: _Venue) -> list[dict[str, Any]]:
    return [dict(vars(p)) for p in v.positions]


def _checks(res: dict[str, Any], sev: str | None = None) -> set[str]:
    return {f["check"] for f in res["findings"] if sev is None or f["severity"] == sev}


Scenario = Callable[[], tuple[bool, str, dict[str, Any]]]


def _scenarios() -> dict[str, tuple[str, Scenario]]:
    from mt5desk import order_door as door
    quiet: Callable[[str], None] = lambda _m: None  # noqa: E731

    def partial_ok() -> tuple[bool, str, dict[str, Any]]:
        with _door_dir() as d:
            v = _Venue([10010], fill=0.06)
            door.send(v, _req(), caller="drill", log=quiet)
            res = reconcile(door.read_ledger(d / door.LEDGER_NAME), None, _positions(v))
        ok = not res["breaks"] and res["residuals"] and \
            abs(res["residuals"][0]["residual"] - 0.04) < 1e-9
        return bool(ok), f"residual {res['residuals']}", res

    def partial_planted() -> tuple[bool, str, dict[str, Any]]:
        with _door_dir() as d:
            v = _Venue([10010], fill=0.06)
            door.send(v, _req(), caller="drill", log=quiet)
            pos = _positions(v)
            pos[0]["volume"] = 0.10                  # the venue book says more than was filled
            res = reconcile(door.read_ledger(d / door.LEDGER_NAME), None, pos)
        return "position_exceeds_fill" in _checks(res, BREAK), "planted overfill", res

    def ack_settled() -> tuple[bool, str, dict[str, Any]]:
        with _door_dir() as d:
            v = _Venue([None])
            door.send(v, _req(), caller="drill", log=quiet)
            door.restart_reconcile(v, magic=MAGIC, armed=False, log=quiet)
            res = reconcile(door.read_ledger(d / door.LEDGER_NAME), None, _positions(v),
                            now=datetime.now(tz=UTC) + timedelta(hours=2))
        return ("missing_ack_unsettled" not in _checks(res)
                and "missing_ack" in _checks(res)), "restart settled the lost ack", res

    def ack_unsettled() -> tuple[bool, str, dict[str, Any]]:
        with _door_dir() as d:
            v = _Venue([None], lands=False)
            door.send(v, _req(), caller="drill", log=quiet)
            res = reconcile(door.read_ledger(d / door.LEDGER_NAME), None, [],
                            now=datetime.now(tz=UTC) + timedelta(hours=2))
        return "missing_ack_unsettled" in _checks(res, BREAK), "planted: never settled", res

    def restart_restores() -> tuple[bool, str, dict[str, Any]]:
        with _door_dir() as d:
            v = _Venue([])
            v.positions.append(SimpleNamespace(ticket=4242, identifier=4242, symbol="EURUSD",
                                               volume=0.1, magic=MAGIC, comment="DWdrill",
                                               sl=0.0, tp=1.104, type=0, time=0))
            door.restart_reconcile(v, magic=MAGIC, armed=False,
                                   intents=[{"ticket": 4242, "sl": 1.0980}], log=quiet)
            res = reconcile(door.read_ledger(d / door.LEDGER_NAME), None, _positions(v))
        return (not res["breaks"] and "restart_stop" in _checks(res)), \
            "stopless position after restart: placement stop restored (shadow)", res

    def restart_planted() -> tuple[bool, str, dict[str, Any]]:
        with _door_dir() as d:
            v = _Venue([])
            v.positions.append(SimpleNamespace(ticket=4343, identifier=4343, symbol="EURUSD",
                                               volume=0.1, magic=MAGIC, comment="DWdrill",
                                               sl=0.0, tp=1.104, type=0, time=0))
            door.restart_reconcile(v, magic=MAGIC, armed=False, intents=[], log=quiet)
            res = reconcile(door.read_ledger(d / door.LEDGER_NAME), None, _positions(v))
        return "restart_stopless" in _checks(res, BREAK), "planted: no stop on record", res

    def dup_resend() -> tuple[bool, str, dict[str, Any]]:
        with _door_dir() as d:
            v = _Venue([None, 10009])
            door.send(v, _req(), caller="drill", log=quiet)
            second = door.send(v, _req(), caller="drill", log=quiet)
            res = reconcile(door.read_ledger(d / door.LEDGER_NAME), None, _positions(v))
        ok = (getattr(second, "door_reason", None) == "duplicate_of_in_doubt"
              and len(v.positions) == 1 and "duplicate_execution" not in _checks(res))
        return ok, f"resend refused; {len(v.positions)} position", res

    def dup_deals() -> tuple[bool, str, dict[str, Any]]:
        deal = {"deal": 777, "symbol": "EURUSD", "volume": 0.1, "pl_quote": 3.2,
                "fill_price": 1.1, "order": 9001}
        clean = reconcile([], None, None, [deal, dict(deal)])
        bad = reconcile([], None, None, [deal, {**deal, "pl_quote": 9.9}])
        ok = (not clean["breaks"] and clean["duplicate_deal_messages"] == 1
              and "conflicting_duplicate_deal" in _checks(bad, BREAK))
        return ok, "repeat counted once; a conflicting repeat is a break", clean

    out: dict[str, tuple[str, Scenario]] = {
        "partial_fill": ("partial fill reconciles, residual recorded", partial_ok),
        "partial_fill_planted": ("a position larger than its fill is caught", partial_planted),
        "missing_ack": ("a lost acknowledgement is settled by the restart reconcile",
                        ack_settled),
        "missing_ack_planted": ("an unsettled in-doubt attempt is caught", ack_unsettled),
        "restart": ("a stopless position after restart has its stop restored", restart_restores),
        "restart_planted": ("a stopless position with no stop on record is caught",
                            restart_planted),
        "duplicate_resend": ("an identical resend after a lost ack is not executed twice",
                             dup_resend),
        "duplicate_deals": ("a repeated deal message is counted once", dup_deals),
    }
    return out


#: gateway_drill faults, and what the join must say about the real gateway's ledgers under each.
GATEWAY_FAULTS: dict[str, str] = {
    "healthy": "clean",            # two sends, two intents, nothing in doubt
    "send_none": "in_doubt",       # two lost acks, journalled, pending settlement
    "send_raises": "in_doubt",
    "reject_10015": "clean",       # rejected sends still journalled both sides
}


def _gateway_scenarios() -> list[dict[str, Any]]:
    from libs.tiers import gateway_drill as gd
    out: list[dict[str, Any]] = []
    for fault, want in GATEWAY_FAULTS.items():
        r = gd.run_fault(fault, with_ledgers=True)
        if r.get("status") != "MEASURED":
            out.append({"scenario": f"gateway_{fault}", "verdict": UNMEASURED,
                        "why": str(r.get("why"))[:200]})
            continue
        led = (r.get("observed") or {}).get("ledgers") or {}
        res = reconcile(led.get("door") or [], led.get("intents") or [], [])
        joined = not ({"send_without_intent", "intent_without_door"} & _checks(res, BREAK))
        in_doubt = bool(res["pending_in_doubt"])
        ok = joined and (in_doubt == (want == "in_doubt")) and \
            not ({"order_acked_twice", "duplicate_execution"} & _checks(res, BREAK))
        out.append({"scenario": f"gateway_{fault}", "verdict": "PASS" if ok else "FAIL",
                    "why": (f"real gateway.py under {fault}: {res['rows']['door']} door rows, "
                            f"{res['rows']['intents']} intents, {len(res['pending_in_doubt'])} "
                            f"pending in doubt, breaks {sorted(_checks(res, BREAK))}")})
    return out


def drill() -> dict[str, Any]:
    rows: list[dict[str, Any]] = []
    for sid, (desc, fn) in _scenarios().items():
        try:
            ok, why, _res = fn()
            rows.append({"scenario": sid, "expect": desc, "verdict": "PASS" if ok else "FAIL",
                         "why": why})
        except Exception as exc:
            rows.append({"scenario": sid, "expect": desc, "verdict": UNMEASURED,
                         "why": f"{type(exc).__name__}: {exc}"[:200]})
    try:
        rows.extend(_gateway_scenarios())
    except Exception as exc:
        rows.append({"scenario": "gateway", "verdict": UNMEASURED,
                     "why": f"{type(exc).__name__}: {exc}"[:200]})
    n_pass = sum(1 for r in rows if r["verdict"] == "PASS")
    verdict = ("FAIL" if any(r["verdict"] == "FAIL" for r in rows) else
               "PASS" if n_pass == len(rows) else UNMEASURED)
    return {"mode": "shadow", "verdict": verdict, "scenarios": rows, "passed": n_pass,
            "n": len(rows)}


def build(now: datetime | None = None) -> dict[str, Any]:
    now = now or datetime.now(tz=UTC)
    d = drill()
    lv = live(now)
    status = ("FAIL" if d["verdict"] == "FAIL" or lv["verdict"] == BREAKS else
              "PASS" if d["verdict"] == "PASS" else UNMEASURED)
    return {"generated_utc": now.isoformat(timespec="seconds"), "status": status,
            "verdict": status, "completed_work": d["passed"], "drill": d, "live": lv,
            "rule": "the drill PASSes when every consistent book reconciles and every planted "
                    "break is caught; the live join is UNMEASURED where a ledger is absent "
                    "and BREAKS on any inconsistency",
            "valid_until": (now + timedelta(hours=3)).isoformat(timespec="seconds")}


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=(__doc__ or "").split("\n")[0])
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args(argv)
    doc = build()
    if not a.dry_run:
        OUT.parent.mkdir(parents=True, exist_ok=True)
        tmp = OUT.with_suffix(".json.tmp")
        tmp.write_text(json.dumps(doc, indent=1, default=str), "utf-8")
        os.replace(tmp, OUT)
    if a.json:
        print(json.dumps(doc, default=str))
    else:
        print(f"execution_reconcile: {doc['status']} drill {doc['drill']['passed']}/"
              f"{doc['drill']['n']} live {doc['live']['verdict']} "
              f"(breaks {doc['live']['breaks']}, absent {doc['live']['absent']})")
        for r in doc["drill"]["scenarios"]:
            print(f"  {r['verdict']:<10} {r['scenario']:<22} {str(r['why'])[:100]}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
