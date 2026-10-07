"""THE REAL GATEWAY UNDER A FAULTY MT5 DOUBLE, IN A SANDBOX (Tier S layer 42).

The protocol twin (`chaos.campaign`) and the process-kill drill exercise models and a journal
writer. This exercises the gateway's OWN code -- `desks/mt5/mt5desk/gateway.py`, the file that
sends orders -- against a MetaTrader5 double that misbehaves the way a real terminal does.

SANDBOXED BY CONSTRUCTION, three ways:
  * each fault runs in a SEPARATE PYTHON PROCESS, so no module state leaks into the caller;
  * that process installs the double as `sys.modules["MetaTrader5"]` BEFORE the gateway is
    imported, so the real terminal package is never imported and no terminal is reached;
  * `MT5_DESK_ROOT` points the gateway's every path (state, intents, decisions, refusals, logs)
    at a fresh temporary directory (`mt5desk.config.desk_root`'s documented override).
Nothing here kills or disconnects the live terminal; the principal's rule stands.

WHAT IS CHECKED, per fault, on the gateway's real `connect`, `place_bracket` and
`expire_stale_brackets`:
  NO_CRASH          no exception escapes the gateway call
  BOUNDED_SENDS     one bracket call sends at most its two legs (no retry storm)
  EVERY_SEND_JOURNALED  every `order_send` the double saw has an intent row on disk
  REJECTION_COUNTED a rejected or empty send is not recorded as `placed`
  NO_SEND_BLIND     no order is sent when the double has no quote for the symbol
  DOWN_IS_FALSE     `connect()` answers False while the terminal is down and will not start
  RECONCILE_BEFORE_EXPOSURE  a pass whose broker state could not be read (the restart reconcile
                    finds the venue unreadable) or whose terminal is running but DISCONNECTED
                    from the broker opens no new risk; a healthy pass still may. Asked of the
                    gateway's `new_risk_gate`; a gateway without one is the finding itself
                    (recovery drills, 2026-10-06: the pass opened new risk on top of an unread
                    book, and `connect()` only asks whether `terminal_info()` exists).
                    `stale_positions` belongs here too: the venue lists a position as open
                    after its own closing deal (a lagging terminal), and the gateway's
                    `book_order_check` must turn that into a refusal before the gate is asked
  PARTIAL_FILL_RECORDED  a scalp entry the broker fills only in part (retcode 10010) is a
                    position: the basket records the FILLED volume and the residual, and the
                    residual is not sent again in the same pass (`run_scalp_sleeves`)
  CLOSE_PARTIAL_RECORDED  a close the broker fills only in part leaves its residual in
                    `st["close_residual"]` and is not resent in the same pass (`close_positions`)
  REFUSED_FOR_THE_RIGHT_REASON  a refusal must name the fault that caused it (`EXPECTED_WHY`):
                    a gate that refuses for an unrelated reason would pass every refusal fault
                    while hiding the one it was built for
  FAMILY_PARTIAL_RECORDED  the family lane's 10010: one send, the filled half booked, the
                    residual recorded with an expiry and retired by `expire_family_residuals`
  BRACKET_PARTIAL_BOOKED  a pending stop filled in part: the book holds what the venue filled,
                    not the bracket's lot (`_book_bracket_lane`)
  PARTIAL_CLOSE_IS_HEALTHY  a position partly closed (OUT volume < IN volume) is OPEN, and a
                    book holding one is not refused new risk (`book_order_check`)
  NETTING_ROUTED    with data/NETTING_ENABLED, opposite same-pass intents on one symbol go out
                    as ONE order for the net and each sleeve is booked its own fill
  NETTING_UNARMED_UNCHANGED  without the flag, every sleeve sends its own order, as before
  SESSION_GATE      a symbol the broker has made close-only opens no new risk -- no bracket,
                    no market order -- and the per-symbol gate names why
A breach is a FINDING about the gateway, reported with the fault that produced it; the drill
never edits the gateway.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
DESK = ROOT / "desks" / "mt5"

FAULTS: tuple[str, ...] = ("healthy", "send_none", "reject_10015", "requote_10004",
                           "send_raises", "tick_none", "terminal_down", "orders_get_raises",
                           "terminal_disconnected", "reconcile_unreadable",
                           "partial_fill", "close_partial", "stale_positions",
                           "family_partial", "bracket_partial", "healthy_partial_close",
                           "in_doubt_unreadable", "netting_armed", "netting_unarmed",
                           "session_closed")
#: The faults after which the pass must refuse NEW exposure (RECONCILE_BEFORE_EXPOSURE).
REFUSE_NEW_RISK: frozenset[str] = frozenset({"terminal_disconnected", "reconcile_unreadable",
                                             "stale_positions", "orders_get_raises",
                                             "in_doubt_unreadable"})
#: The words each refusal must carry (REFUSED_FOR_THE_RIGHT_REASON), taken from the gateway's own
#: `new_risk_gate` wording for that cause.
EXPECTED_WHY: dict[str, tuple[str, ...]] = {
    "terminal_disconnected": ("not connected",),
    "reconcile_unreadable": ("restart reconcile UNMEASURED",),
    "orders_get_raises": ("restart reconcile UNMEASURED", "orders_get failed"),
    "stale_positions": ("book_inconsistent", "listed open after their closing deal"),
    "in_doubt_unreadable": ("in-doubt send", "could not be settled"),
}
#: Faults whose book is healthy and must therefore still be allowed new risk.
MUST_TRADE: frozenset[str] = frozenset({"healthy", "healthy_partial_close"})
TIMEOUT_S = 90

#: The child's program. It reads its fault from argv, builds the double, imports the gateway
#: against it and prints one JSON line of observations. Kept as source so the child needs
#: nothing from this module and cannot share its state.
_CHILD = r'''
import json, sys, types, traceback
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace as NS
fault = sys.argv[1]
desk = sys.argv[2]
calls = {"order_send": [], "initialize": 0}
# WHICH STEP OF THE CHILD IS RUNNING. The partial-fill faults touch only market DEALs and the
# held/stale position exists only in its own phase, so the bracket invariants above are judged
# on exactly the venue they always were.
phase = {"now": "bracket", "magic": 0, "tag": ""}
held = {"volume": 0.04}
PARTIAL = ("partial_fill", "close_partial", "family_partial")
m = types.ModuleType("MetaTrader5")
def _const(name):
    if name.isupper():
        # MetaTrader5's own values where a gateway path compares a raw integer (the book reads
        # `int(position.type) == 0` for a buy); every other constant is an opaque distinct int.
        return {"TRADE_RETCODE_DONE": 10009, "TRADE_RETCODE_PLACED": 10008,
                "POSITION_TYPE_BUY": 0, "POSITION_TYPE_SELL": 1}.get(
            name, 1000 + (sum(map(ord, name)) % 5000))
    raise AttributeError(name)
m.__getattr__ = _const
def terminal_info():
    return None if fault == "terminal_down" else NS(connected=fault != "terminal_disconnected")
def initialize(**kw):
    calls["initialize"] += 1
    return fault != "terminal_down"
def last_error():
    return (-10004, "No IPC connection") if fault == "terminal_down" else (1, "ok")
def symbol_info_tick(symbol):
    return None if fault == "tick_none" else NS(bid=100.0, ask=100.05, time=0)
def symbol_info(symbol):
    # trade_mode 3 = CLOSEONLY, 4 = FULL (MQL5 ENUM_SYMBOL_TRADE_MODE).
    return NS(point=0.01, trade_stops_level=0, expiration_mode=0, volume_min=0.01,
              volume_step=0.01, volume_max=100.0, trade_contract_size=100.0, digits=2,
              trade_mode=3 if fault == "session_closed" else 4)
def account_info():
    return NS(login=1, equity=1000.0, balance=1000.0, margin_free=900.0, currency="EUR",
              server="sandbox")
def order_calc_margin(*a):
    return 1.0
def order_send(req):
    calls["order_send"].append(dict(req))
    if req.get("action") == m.TRADE_ACTION_DEAL and fault in PARTIAL:
        filled = round(float(req.get("volume") or 0.0) / 2.0, 8)
        if req.get("position"):
            held["volume"] = round(held["volume"] - filled, 8)
        return NS(retcode=10010, order=9000 + len(calls["order_send"]), deal=0,
                  volume=filled, price=float(req.get("price") or 0.0), comment="partial",
                  request_id=0)
    if fault == "send_raises":
        raise RuntimeError("IPC timeout")
    if fault == "send_none":
        return None
    code = {"reject_10015": 10015, "requote_10004": 10004}.get(fault, 10009)
    return NS(retcode=code, order=(0 if code != 10009 else 5000 + len(calls["order_send"])),
              comment="sandbox", request_id=0)
def _unreadable_in_doubt(kw):
    return fault == "in_doubt_unreadable" and phase["now"] == "gate" and "symbol" in kw
def orders_get(**kw):
    if fault == "orders_get_raises" or _unreadable_in_doubt(kw):
        raise RuntimeError("orders_get failed")
    return ()
def _held(ticket, volume=None, comment=""):
    return NS(ticket=ticket, symbol="EURUSD",
              volume=held["volume"] if volume is None else volume, type=m.POSITION_TYPE_BUY,
              magic=phase["magic"], comment=comment, sl=99.0, tp=101.0, price_open=100.0,
              price_current=100.0, profit=0.0, time=0, time_msc=0, time_update_msc=1000,
              identifier=ticket, swap=0.0)
def positions_get(**kw):
    if fault == "reconcile_unreadable" or _unreadable_in_doubt(kw):
        raise RuntimeError("positions_get failed")
    if fault == "close_partial" and phase["now"] == "close" and held["volume"] > 0:
        return (_held(777),)
    if fault == "stale_positions" and phase["now"] == "gate":
        t = kw.get("ticket")
        return (_held(888),) if t in (None, 888) else ()
    if fault == "healthy_partial_close" and phase["now"] == "gate":
        t = kw.get("ticket")
        return (_held(888, volume=0.02),) if t in (None, 888) else ()
    if fault == "bracket_partial" and phase["now"] == "bpartial":
        return (_held(555, volume=0.02, comment=phase["tag"]),)
    return ()
def history_deals_get(*a, **kw):
    if fault == "in_doubt_unreadable" and phase["now"] == "gate":
        raise RuntimeError("history_deals_get failed")
    if fault not in ("stale_positions", "healthy_partial_close") or phase["now"] != "gate":
        return ()
    base = dict(symbol="EURUSD", position_id=888, magic=phase["magic"], price=100.0,
                profit=0.0, commission=0.0, swap=0.0, comment="", type=0, time=0)
    # stale: the whole 0.04 closed while the venue still lists it. Healthy partial close: 0.02
    # of the 0.04 closed and the venue lists the 0.02 that remains -- an OPEN position.
    out_vol = 0.04 if fault == "stale_positions" else 0.02
    return (NS(ticket=1, order=1, entry=m.DEAL_ENTRY_IN, time_msc=1000, volume=0.04, **base),
            NS(ticket=2, order=2, entry=m.DEAL_ENTRY_OUT, time_msc=2000, volume=out_vol, **base))
for f in (terminal_info, initialize, last_error, symbol_info_tick, symbol_info, account_info,
          order_calc_margin, order_send, orders_get, positions_get, history_deals_get):
    setattr(m, f.__name__, f)
sys.modules["MetaTrader5"] = m
sys.path.insert(0, desk)
sys.path.insert(0, sys.argv[3])
out = {"fault": fault}
FAR = "2099-01-01T00:00:00+00:00"
def _lanes(gateway, *, netting_flag=False):
    """The market lanes armed in the sandbox: the arm switch's flag file in the sandbox root, a
    release identity that permits new risk, and the bookkeeping the drill does not judge stubbed.
    THE NETTING BOOK IS IN MEMORY (`persist=False`): `netting.NETTING_LEDGER` resolves from the
    module's own location, not MT5_DESK_ROOT, and the first run of the partial-fill fault
    (2026-10-06) appended a sandbox fill to the real desk's ledger. In memory it can be judged
    and can touch nothing."""
    from mt5desk import netting
    gateway.NEW_RISK_OK = True
    gateway.GENERIC_EXEC_ENABLED.parent.mkdir(parents=True, exist_ok=True)
    gateway.GENERIC_EXEC_ENABLED.write_text("", encoding="utf-8")
    if netting_flag:
        gateway.NETTING_ENABLED.write_text("", encoding="utf-8")
    gateway.margin_ok = lambda *a, **k: True
    gateway._record_exec_outcome = lambda *a, **k: None
    gateway._policy_advice = lambda *a, **k: None
    gateway._exec_route = lambda *a, **k: {"routed": False}
    gateway._BOOK = netting.TheoreticalBook(persist=False)
    return gateway._BOOK
def _scalp(side, per, price, stop, tp):
    plan = NS(side=side, stop=stop, target=tp, atr=0.3, entry_ref=price,
              bar_time="2026-10-06T10:00:00+00:00", ttl_until=FAR)
    return {"ok": True, "stage": "ok", "why": "", "mark": False, "forming": None,
            "per": per, "side": side, "price": price, "stop": stop, "tp": tp,
            "sym": symbol_info("EURUSD"), "tick": symbol_info_tick("EURUSD"), "desc": "drill",
            "kind": "new", "basis": "drill", "dist": abs(price - stop), "plan": plan,
            "family": "drill", "mode": "drill", "target_atr": 2.0}
def _basket_lots(st, name):
    b = ((st.get("scalp") or {}).get(name) or {}).get("basket") or {}
    return round(sum(float(u) for _, u in b.get("entries") or []), 8)
def _sent(n0):
    return [{"volume": r.get("volume"),
             "side": "buy" if r.get("type") == m.ORDER_TYPE_BUY else "sell"}
            for r in calls["order_send"][n0:]]
try:
    from mt5desk import gateway
    out["root"] = str(gateway.BASE)
    try:
        out["connect"] = bool(gateway.connect())
    except Exception as exc:
        out["connect_exc"] = f"{type(exc).__name__}: {exc}"
    spec = {"buy_stop": {"price": 100.60, "sl": 100.10, "tp": 101.60},
            "sell_stop": {"price": 99.40, "sl": 99.90, "tp": 98.40}, "window": None}
    st = {"armed": True, "brackets": {}, "position": None}
    try:
        res = gateway.place_bracket(st, spec, "sandbox_sleeve", "EURUSD", 0.01)
        out["orders"] = res.get("orders")
        out["bracket_stage"] = res.get("stage")
    except Exception as exc:
        out["place_exc"] = f"{type(exc).__name__}: {exc}"
    try:
        out["expired"] = gateway.expire_stale_brackets(st)
    except Exception as exc:
        out["expire_exc"] = f"{type(exc).__name__}: {exc}"
    out["sends"] = len(calls["order_send"])     # the bracket invariants judge these only
    phase["magic"] = int(getattr(gateway, "MAGIC", 0) or 0)
    if fault in ("partial_fill", "session_closed"):
        # THE SCALP EXECUTOR, handed a plan the pre-cap phase would have resolved, armed.
        phase["now"] = "scalp"
        n0 = len(calls["order_send"])
        try:
            book = _lanes(gateway)
            sst = {"armed": True, "brackets": {}, "position": None}
            s = {"name": "sandbox_scalp", "symbol": "EURUSD", "exec": "scalp_market",
                 "pending_order": _scalp(1, 0.04, 100.05, 99.5, 101.0)}
            gateway.run_scalp_sleeves(sst, [s], 1000.0)
            out["scalp_basket"] = ((sst.get("scalp") or {}).get("sandbox_scalp")
                                   or {}).get("basket")
            out["scalp_send_volumes"] = [r["volume"] for r in _sent(n0)]
            out["scalp_book"] = {"target": book.theoretical("EURUSD").get("sandbox_scalp", 0.0),
                                 "filled": book.filled("EURUSD").get("sandbox_scalp", 0.0)}
        except Exception as exc:
            out["scalp_exc"] = f"{type(exc).__name__}: {exc}"
        out["scalp_sends"] = len(calls["order_send"]) - n0
    if fault == "session_closed":
        try:
            out["session_refusal"] = gateway.symbol_risk_refusal("EURUSD", 1)
            from mt5desk import sessions
            sess = sessions.symbol_session(m, "EURUSD", side=1)
            ok, why = gateway.new_risk_gate(True, "armed", {"verdict": "OK"}, NS(connected=True),
                                            session=sess)
            out["session_gate"] = bool(ok)
            out["session_gate_why"] = str(why)
        except Exception as exc:
            out["session_exc"] = f"{type(exc).__name__}: {exc}"
    if fault == "family_partial":
        phase["now"] = "family"
        n0 = len(calls["order_send"])
        try:
            book = _lanes(gateway)
            fst = {"armed": True, "brackets": {}, "position": None}
            g = NS(stop=99.5, target=101.0, runner_trail_k=0.0, ttl_bars=12)
            plan = {"ok": True, "stage": "ok", "why": "resolved", "considered": True,
                    "lot": 0.04, "dist": 0.55, "sym": symbol_info("EURUSD"),
                    "tick": symbol_info_tick("EURUSD"), "entry_ref": 100.05, "signal": g,
                    "side": 1, "tf": "H1", "last_bar": "2026-10-06 10:00", "mark": False,
                    "note": None, "ttl_until": FAR}
            s = {"name": "sandbox_family", "symbol": "EURUSD", "exec": "family_market",
                 "family": "drill", "selector": "drill", "pending_order": plan}
            gateway.run_family_sleeves(fst, [s], 1000.0)
            srec = (fst.get("generic") or {}).get("sandbox_family") or {}
            out["fam_sends"] = len(calls["order_send"]) - n0
            out["fam_residual"] = srec.get("residual")
            out["fam_ttl"] = srec.get("open_ttl_until")
            out["fam_book"] = {"target": book.theoretical("EURUSD").get("sandbox_family", 0.0),
                               "filled": book.filled("EURUSD").get("sandbox_family", 0.0)}
            # THE BACKSTOP: past its expiry, the residual is retired (nothing rests here).
            if isinstance(srec.get("residual"), dict):
                srec["residual"]["expires"] = "2000-01-01T00:00:00+00:00"
            out["fam_retired"] = gateway.expire_family_residuals(fst)
            out["fam_residual_after"] = srec.get("residual")
        except Exception as exc:
            out["family_exc"] = f"{type(exc).__name__}: {exc}\n{traceback.format_exc()[-400:]}"
    if fault == "bracket_partial":
        # A PENDING STOP FILLED IN PART: the venue holds 0.02 of a 0.04 bracket under the
        # sleeve's own tag; the book must hold what was filled.
        phase["now"] = "bpartial"
        try:
            book = _lanes(gateway)
            phase["tag"] = gateway.order_comment("sandbox_sleeve")
            bst = {"armed": True, "brackets": {"sandbox_sleeve": {"lot": 0.04}}, "position": None}
            gateway._book_bracket_lane(bst, [{"name": "sandbox_sleeve", "symbol": "EURUSD"}])
            out["bp_book"] = {"target": book.theoretical("EURUSD").get("sandbox_sleeve", 0.0),
                              "filled": book.filled("EURUSD").get("sandbox_sleeve", 0.0)}
        except Exception as exc:
            out["bpartial_exc"] = f"{type(exc).__name__}: {exc}"
    if fault in ("netting_armed", "netting_unarmed"):
        # TWO SLEEVES, OPPOSITE SIDES, ONE SYMBOL, ONE PASS: long 0.04 and short 0.01.
        phase["now"] = "net"
        n0 = len(calls["order_send"])
        try:
            book = _lanes(gateway, netting_flag=(fault == "netting_armed"))
            nst = {"armed": True, "brackets": {}, "position": None}
            a = {"name": "net_long", "symbol": "EURUSD", "exec": "scalp_market",
                 "pending_order": _scalp(1, 0.04, 100.05, 99.5, 101.0)}
            b = {"name": "net_short", "symbol": "EURUSD", "exec": "scalp_market",
                 "pending_order": _scalp(-1, 0.01, 100.0, 100.5, 99.0)}
            gateway._net_market_intents(nst, [a, b])
            gateway.run_scalp_sleeves(nst, [a, b], 1000.0)
            out["net_sent"] = _sent(n0)
            out["net_filled"] = book.filled("EURUSD")
            out["net_account"] = book.account_position("EURUSD")
            out["net_long_basket"] = _basket_lots(nst, "net_long")
        except Exception as exc:
            out["net_exc"] = f"{type(exc).__name__}: {exc}\n{traceback.format_exc()[-400:]}"
    if fault == "close_partial":
        phase["now"] = "close"
        n0 = len(calls["order_send"])
        cst = {"armed": True, "brackets": {}, "position": None}
        try:
            gateway.close_positions(cst, "EURUSD")
        except Exception as exc:
            out["close_exc"] = f"{type(exc).__name__}: {exc}"
        out["close_sends"] = len(calls["order_send"]) - n0
        out["close_residual"] = cst.get("close_residual")
    phase["now"] = "gate"
    # RECONCILE BEFORE EXPOSURE: the pass-level verdict the gateway would take on this venue,
    # with a release identity that permits new risk, so only the venue can refuse it.
    gate = getattr(gateway, "new_risk_gate", None)
    if gate is None:
        out["new_risk"] = "NO_GATE"
    else:
        try:
            from mt5desk import order_door
            if fault == "in_doubt_unreadable":
                # A SEND THAT TIMED OUT LAST PASS, which the venue cannot now be read to settle.
                order_door.save_in_doubt({"drill-in-doubt": {
                    "at": datetime.now(tz=UTC).isoformat(timespec="seconds"),
                    "symbol": "EURUSD", "comment": "DWsandbox_sleeve", "magic": 1, "type": 0,
                    "volume": 0.01, "price": 100.0, "why": "drill: send timed out"}})
            rr = order_door.restart_reconcile(m, magic=1, armed=False)
        except Exception as exc:
            rr = {"verdict": "FAILED", "why": f"{type(exc).__name__}: {exc}"}
        # OUT-OF-ORDER READS: the gateway's own book-versus-deals check, when it has one, takes
        # the reconcile's place exactly as `main` does. A gateway without it is judged on the
        # reconcile alone, which is the finding for `stale_positions`.
        check = getattr(gateway, "book_order_check", None)
        if check is not None:
            try:
                bst = {"armed": True, "brackets": {}, "position": None}
                verdict = check(bst)
                if verdict is not None:
                    rr = verdict
                out["book_inconsistent"] = bst.get("book_inconsistent")
            except Exception as exc:
                out["book_exc"] = f"{type(exc).__name__}: {exc}"
        try:
            ok, why = gate(True, "armed", rr, m.terminal_info())
            out["new_risk"] = bool(ok)
            out["new_risk_why"] = str(why)[:200]
        except Exception as exc:
            out["gate_exc"] = f"{type(exc).__name__}: {exc}"
except Exception as exc:
    out["import_exc"] = f"{type(exc).__name__}: {exc}"
    out["trace"] = traceback.format_exc()[-800:]
out.setdefault("sends", len(calls["order_send"]))
out["initialize_calls"] = calls["initialize"]
print("DRILL_JSON " + json.dumps(out, default=str))
'''


def _jsonl(p: Path) -> list[dict[str, Any]]:
    try:
        return [json.loads(x) for x in p.read_text("utf-8").splitlines() if x.strip()]
    except (OSError, ValueError):
        return []


def run_fault(fault: str, *, desk: Path = DESK) -> dict[str, Any]:
    """One fault against the real gateway in a child process rooted in a temp directory."""
    with tempfile.TemporaryDirectory(prefix="gw_drill_") as tmp:
        root = Path(tmp)
        (root / "data").mkdir()
        (root / "logs").mkdir()
        # The child runs from the temp directory, so neither the repository root (for `libs`)
        # nor the desk (for `mt5desk`) is on its path unless it is put there: a clean worktree
        # has no installed package to fall back on (audit 2026-09-30: ModuleNotFoundError).
        path = os.pathsep.join([str(ROOT), str(desk),
                                *filter(None, [os.environ.get("PYTHONPATH", "")])])
        env = {**os.environ, "MT5_DESK_ROOT": str(root), "PYTHONDONTWRITEBYTECODE": "1",
               "PYTHONPATH": path}
        try:
            proc = subprocess.run([sys.executable, "-c", _CHILD, fault, str(desk), str(ROOT)],
                                  capture_output=True, text=True, timeout=TIMEOUT_S, env=env,
                                  cwd=str(root))
        except subprocess.TimeoutExpired:
            return {"fault": fault, "status": "UNMEASURED", "why": f"timed out at {TIMEOUT_S}s"}
        line = next((x for x in proc.stdout.splitlines() if x.startswith("DRILL_JSON ")), "")
        if not line:
            return {"fault": fault, "status": "UNMEASURED",
                    "why": f"child printed no result (rc={proc.returncode}): "
                           f"{proc.stderr.strip()[-300:]}"}
        obs = json.loads(line[len("DRILL_JSON "):])
        obs["intents"] = len(_jsonl(root / "data" / "order_intents.jsonl"))
        obs["decisions"] = [r.get("reason") for r in
                            _jsonl(root / "data" / "decision_ledger.jsonl")]
    if obs.get("import_exc"):
        return {"fault": fault, "status": "UNMEASURED",
                "why": f"gateway did not import: {obs['import_exc']}"}
    if not str(obs.get("root", "")).startswith(str(Path(tempfile.gettempdir()))) and \
            "gw_drill_" not in str(obs.get("root", "")):
        return {"fault": fault, "status": "ABORTED",
                "why": f"gateway root {obs.get('root')} is not the sandbox"}
    return {"fault": fault, "status": "MEASURED", "observed": obs,
            "breaches": judge(fault, obs)}


def judge(fault: str, obs: dict[str, Any]) -> list[str]:
    """The invariants the module docstring names, checked on one observation."""
    out: list[str] = []
    for k in ("connect_exc", "place_exc", "expire_exc", "gate_exc", "scalp_exc", "close_exc",
              "book_exc", "family_exc", "bpartial_exc", "net_exc", "session_exc"):
        if obs.get(k):
            out.append(f"NO_CRASH: {k.split('_')[0]} raised {obs[k]}")
    sends = int(obs.get("sends") or 0)
    if sends > 2:
        out.append(f"BOUNDED_SENDS: {sends} order_send calls for one two-leg bracket")
    if sends and int(obs.get("intents") or 0) < sends and not obs.get("place_exc"):
        out.append(f"EVERY_SEND_JOURNALED: {sends} sends, {obs.get('intents')} intent rows")
    if fault in ("send_none", "reject_10015", "requote_10004"):
        placed = sum(1 for r in obs.get("decisions") or [] if r == "placed")
        if placed:
            out.append(f"REJECTION_COUNTED: {placed} failed send(s) recorded as placed")
    if fault == "tick_none" and sends:
        out.append(f"NO_SEND_BLIND: {sends} order(s) sent with no quote for the symbol")
    if fault == "terminal_down" and obs.get("connect") is not False:
        out.append(f"DOWN_IS_FALSE: connect() returned {obs.get('connect')} with the terminal "
                   "down")
    if fault in REFUSE_NEW_RISK and "new_risk" in obs:
        if obs["new_risk"] == "NO_GATE":
            out.append("RECONCILE_BEFORE_EXPOSURE: the gateway has no new-risk gate; this pass "
                       "would open new exposure on a broker state it could not read")
        elif obs["new_risk"] is not False:
            out.append(f"RECONCILE_BEFORE_EXPOSURE: new risk allowed after {fault}")
        else:
            why = str(obs.get("new_risk_why") or "")
            missing = [w for w in EXPECTED_WHY.get(fault, ()) if w not in why]
            if missing:
                out.append(f"REFUSED_FOR_THE_RIGHT_REASON: {fault} refused with {why!r}, "
                           f"which does not name {missing}")
    if fault == "partial_fill":
        out += _judge_partial_fill(obs)
    if fault == "close_partial":
        res = obs.get("close_residual") or {}
        if int(obs.get("close_sends") or 0) != 1:
            out.append(f"CLOSE_PARTIAL_RECORDED: {obs.get('close_sends')} close send(s) for one "
                       f"position in one pass (a partial close must not be resent in the pass)")
        if res.get("777") is None or not 0 < float(res["777"]) < 0.04:
            out.append(f"CLOSE_PARTIAL_RECORDED: the residual of a 10010 close was not recorded "
                       f"(close_residual={res})")
    if fault in MUST_TRADE and obs.get("new_risk") is False:
        rule = "RECONCILE_BEFORE_EXPOSURE" if fault == "healthy" else "PARTIAL_CLOSE_IS_HEALTHY"
        out.append(f"{rule}: a healthy pass was refused new risk ({obs.get('new_risk_why')})")
    if fault == "family_partial":
        out += _judge_family_partial(obs)
    if fault == "bracket_partial":
        out += _judge_bracket_partial(obs)
    if fault in ("netting_armed", "netting_unarmed"):
        out += _judge_netting(fault, obs)
    if fault == "session_closed":
        out += _judge_session(obs)
    return out


def _close(a: object, b: float) -> bool:
    try:
        return abs(float(a) - b) <= 1e-9  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return False


def _judge_family_partial(obs: dict[str, Any]) -> list[str]:
    """FAMILY_PARTIAL_RECORDED: one send of the asked 0.04, the filled 0.02 booked as target and
    fill, the 0.02 residual recorded with an expiry, a time exit kept, and the residual retired
    by the backstop once past its expiry."""
    out: list[str] = []
    if obs.get("family_exc"):
        return out                                    # NO_CRASH already names it
    if int(obs.get("fam_sends") or 0) != 1:
        out.append(f"FAMILY_PARTIAL_RECORDED: {obs.get('fam_sends')} family send(s) for one "
                   f"order (the residual must not be resent in the same pass)")
    res = obs.get("fam_residual") or {}
    if not _close(res.get("lots"), 0.02) or not res.get("expires"):
        out.append(f"FAMILY_PARTIAL_RECORDED: residual {res} -- 0.02 lots with an expiry "
                   f"expected")
    book = obs.get("fam_book") or {}
    if not (_close(book.get("filled"), 0.02) and _close(book.get("target"), 0.02)):
        out.append(f"FAMILY_PARTIAL_RECORDED: book {book}, the venue filled 0.02")
    if not obs.get("fam_ttl"):
        out.append("FAMILY_PARTIAL_RECORDED: the filled part has no time exit")
    if obs.get("fam_residual_after") is not None or int(obs.get("fam_retired") or 0) != 1:
        out.append(f"FAMILY_PARTIAL_RECORDED: an expired residual was not retired "
                   f"({obs.get('fam_residual_after')})")
    return out


def _judge_bracket_partial(obs: dict[str, Any]) -> list[str]:
    """BRACKET_PARTIAL_BOOKED: the book holds the 0.02 the venue filled of a 0.04 stop."""
    if obs.get("bpartial_exc"):
        return []
    book = obs.get("bp_book") or {}
    if _close(book.get("filled"), 0.02) and _close(book.get("target"), 0.02):
        return []
    return [f"BRACKET_PARTIAL_BOOKED: book {book}, the venue filled 0.02 of a 0.04 stop"]


def _judge_netting(fault: str, obs: dict[str, Any]) -> list[str]:
    """NETTING_ROUTED / NETTING_UNARMED_UNCHANGED on long 0.04 + short 0.01, one symbol."""
    if obs.get("net_exc"):
        return []
    out: list[str] = []
    sent = obs.get("net_sent") or []
    filled = obs.get("net_filled") or {}
    if not (_close(filled.get("net_long"), 0.04) and _close(filled.get("net_short"), -0.01)):
        rule = "NETTING_ROUTED" if fault == "netting_armed" else "NETTING_UNARMED_UNCHANGED"
        out.append(f"{rule}: per-sleeve attribution lost (book filled {filled}; want long +0.04, "
                   f"short -0.01)")
    if not _close(obs.get("net_account"), 0.03):
        out.append(f"NETTING: the book's account position {obs.get('net_account')} is not the "
                   f"+0.03 the venue holds")
    if fault == "netting_armed":
        if len(sent) != 1 or sent[0].get("side") != "buy" or not _close(sent[0].get("volume"),
                                                                          0.03):
            out.append(f"NETTING_ROUTED: sent {sent}; want ONE buy of the net 0.03")
        if not _close(obs.get("net_long_basket"), 0.03):
            out.append(f"NETTING_ROUTED: the anchor's basket holds {obs.get('net_long_basket')}, "
                       f"the venue position is 0.03")
    else:
        want = [{"side": "buy", "volume": 0.04}, {"side": "sell", "volume": 0.01}]
        got = sorted((x.get("side"), round(float(x.get("volume") or 0.0), 8)) for x in sent)
        if got != sorted((w["side"], w["volume"]) for w in want):
            out.append(f"NETTING_UNARMED_UNCHANGED: sent {sent}; unarmed, each sleeve sends its "
                       f"own order ({want})")
    return out


def _judge_session(obs: dict[str, Any]) -> list[str]:
    """SESSION_GATE: a CLOSEONLY symbol gets no bracket, no market order, and a named refusal."""
    out: list[str] = []
    if int(obs.get("sends") or 0) or obs.get("bracket_stage") != "session_closed":
        out.append(f"SESSION_GATE: bracket on a close-only symbol -> {obs.get('sends')} send(s), "
                   f"stage {obs.get('bracket_stage')}")
    if int(obs.get("scalp_sends") or 0):
        out.append(f"SESSION_GATE: {obs.get('scalp_sends')} market order(s) on a close-only "
                   f"symbol")
    if "CLOSEONLY" not in str(obs.get("session_refusal") or ""):
        out.append(f"SESSION_GATE: per-symbol refusal {obs.get('session_refusal')!r} does not "
                   f"name CLOSEONLY")
    if obs.get("session_gate") is not False or "session:" not in str(
            obs.get("session_gate_why") or ""):
        out.append(f"SESSION_GATE: new_risk_gate(session=closed) -> {obs.get('session_gate')} "
                   f"({obs.get('session_gate_why')})")
    return out


def _judge_partial_fill(obs: dict[str, Any]) -> list[str]:
    """PARTIAL_FILL_RECORDED: one send of the asked 0.04, a basket holding exactly the filled
    0.02 and its 0.02 residual, and -- when the book was observed -- target and fill at 0.02."""
    out: list[str] = []
    vols = obs.get("scalp_send_volumes")
    if vols is not None and (len(vols) != 1 or not _close(vols[0], 0.04)):
        out.append(f"PARTIAL_FILL_RECORDED: sent {vols}; one order of the asked 0.04 expected")
    book = obs.get("scalp_book")
    if book is not None and not (_close(book.get("filled"), 0.02)
                                 and _close(book.get("target"), 0.02)):
        out.append(f"PARTIAL_FILL_RECORDED: book {book}; the venue filled 0.02")
    if int(obs.get("scalp_sends") or 0) != 1:
        out.append(f"PARTIAL_FILL_RECORDED: {obs.get('scalp_sends')} scalp send(s) for one "
                   f"slice (the residual must not be resent in the same pass)")
    basket = obs.get("scalp_basket")
    if not isinstance(basket, dict):
        out.append("PARTIAL_FILL_RECORDED: a 10010 entry left no basket; the filled position "
                   "runs without the lane's stop management and time exit")
        return out
    lots = sum(float(u) for _, u in basket.get("entries") or [])
    if abs(lots - 0.02) > 1e-9:
        out.append(f"PARTIAL_FILL_RECORDED: basket holds {lots} lots, the broker filled 0.02")
    if abs(float(basket.get("residual") or 0.0) - 0.02) > 1e-9:
        out.append(f"PARTIAL_FILL_RECORDED: residual {basket.get('residual')} recorded, "
                   f"0.02 was left unfilled")
    return out


def campaign(faults: tuple[str, ...] = FAULTS, *, desk: Path = DESK) -> dict[str, Any]:
    rows = [run_fault(f, desk=desk) for f in faults]
    measured = [r for r in rows if r["status"] == "MEASURED"]
    breaches = [f"{r['fault']}: {b}" for r in measured for b in r["breaches"]]
    return {"faults": rows, "n_faults": len(rows), "n_measured": len(measured),
            "breaches": breaches,
            "status": "MEASURED" if measured else "UNMEASURED",
            "sandbox": "child process per fault; MetaTrader5 replaced by a double before import; "
                       "MT5_DESK_ROOT = a temp directory"}
