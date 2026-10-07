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
                           "partial_fill", "close_partial", "stale_positions")
#: The faults after which the pass must refuse NEW exposure (RECONCILE_BEFORE_EXPOSURE).
REFUSE_NEW_RISK: frozenset[str] = frozenset({"terminal_disconnected", "reconcile_unreadable",
                                             "stale_positions"})
TIMEOUT_S = 90

#: The child's program. It reads its fault from argv, builds the double, imports the gateway
#: against it and prints one JSON line of observations. Kept as source so the child needs
#: nothing from this module and cannot share its state.
_CHILD = r'''
import json, sys, types, traceback
from types import SimpleNamespace as NS
fault = sys.argv[1]
desk = sys.argv[2]
calls = {"order_send": [], "initialize": 0}
# WHICH STEP OF THE CHILD IS RUNNING. The partial-fill faults touch only market DEALs and the
# held/stale position exists only in its own phase, so the bracket invariants above are judged
# on exactly the venue they always were.
phase = {"now": "bracket", "magic": 0}
held = {"volume": 0.04}
m = types.ModuleType("MetaTrader5")
def _const(name):
    if name.isupper():
        return {"TRADE_RETCODE_DONE": 10009, "TRADE_RETCODE_PLACED": 10008}.get(
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
    return NS(point=0.01, trade_stops_level=0, expiration_mode=0, volume_min=0.01,
              volume_step=0.01, trade_contract_size=100.0, digits=2)
def account_info():
    return NS(login=1, equity=1000.0, balance=1000.0, margin_free=900.0, currency="EUR",
              server="sandbox")
def order_calc_margin(*a):
    return 1.0
def order_send(req):
    calls["order_send"].append(dict(req))
    if req.get("action") == m.TRADE_ACTION_DEAL and fault in ("partial_fill", "close_partial"):
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
def orders_get(**kw):
    if fault == "orders_get_raises":
        raise RuntimeError("orders_get failed")
    return ()
def _held(ticket):
    return NS(ticket=ticket, symbol="EURUSD", volume=held["volume"], type=m.POSITION_TYPE_BUY,
              magic=phase["magic"], comment="", sl=99.0, tp=101.0, price_open=100.0,
              price_current=100.0, profit=0.0, time=0, time_msc=0, time_update_msc=1000,
              identifier=ticket, swap=0.0)
def positions_get(**kw):
    if fault == "reconcile_unreadable":
        raise RuntimeError("positions_get failed")
    if fault == "close_partial" and phase["now"] == "close" and held["volume"] > 0:
        return (_held(777),)
    if fault == "stale_positions" and phase["now"] == "gate":
        t = kw.get("ticket")
        return (_held(888),) if t in (None, 888) else ()
    return ()
def history_deals_get(*a, **kw):
    if fault != "stale_positions" or phase["now"] != "gate":
        return ()
    base = dict(symbol="EURUSD", position_id=888, magic=phase["magic"], volume=0.04,
                price=100.0, profit=0.0, commission=0.0, swap=0.0, comment="", type=0,
                time=0)
    return (NS(ticket=1, order=1, entry=m.DEAL_ENTRY_IN, time_msc=1000, **base),
            NS(ticket=2, order=2, entry=m.DEAL_ENTRY_OUT, time_msc=2000, **base))
for f in (terminal_info, initialize, last_error, symbol_info_tick, symbol_info, account_info,
          order_calc_margin, order_send, orders_get, positions_get, history_deals_get):
    setattr(m, f.__name__, f)
sys.modules["MetaTrader5"] = m
sys.path.insert(0, desk)
sys.path.insert(0, sys.argv[3])
out = {"fault": fault}
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
    except Exception as exc:
        out["place_exc"] = f"{type(exc).__name__}: {exc}"
    try:
        out["expired"] = gateway.expire_stale_brackets(st)
    except Exception as exc:
        out["expire_exc"] = f"{type(exc).__name__}: {exc}"
    out["sends"] = len(calls["order_send"])     # the bracket invariants judge these only
    phase["magic"] = int(getattr(gateway, "MAGIC", 0) or 0)
    if fault == "partial_fill":
        # THE SCALP EXECUTOR, handed a plan the pre-cap phase would have resolved, armed, with
        # the arm switch's flag file present in the sandbox root.
        phase["now"] = "scalp"
        n0 = len(calls["order_send"])
        try:
            gateway.NEW_RISK_OK = True
            gateway.GENERIC_EXEC_ENABLED.parent.mkdir(parents=True, exist_ok=True)
            gateway.GENERIC_EXEC_ENABLED.write_text("", encoding="utf-8")
            gateway.margin_ok = lambda *a, **k: True
            # THE NETTING BOOK AND THE EXECUTION-OUTCOME LEDGER ARE NOT UNDER MT5_DESK_ROOT
            # (`netting.NETTING_LEDGER`, `execution_registry.OUTCOMES` resolve from their own
            # module's location). Measured 2026-10-06: the first run of this fault appended a
            # sandbox fill to the real desk's data/theoretical_positions.jsonl. They are
            # bookkeeping beside the send, not the invariant judged here, so they are stubbed.
            for _name in ("_book_target", "_book_fill", "_record_exec_outcome"):
                setattr(gateway, _name, lambda *a, **k: None)
            gateway._policy_advice = lambda *a, **k: None
            tick = symbol_info_tick("EURUSD")
            plan = NS(side=1, stop=99.5, target=101.0, atr=0.3, entry_ref=100.05,
                      bar_time="2026-10-06T10:00:00+00:00",
                      ttl_until="2026-10-06T12:00:00+00:00")
            order = {"ok": True, "stage": "ok", "why": "", "mark": False, "forming": None,
                     "per": 0.04, "side": 1, "price": 100.05, "stop": 99.5, "tp": 101.0,
                     "sym": symbol_info("EURUSD"), "tick": tick, "desc": "drill",
                     "kind": "new", "basis": "drill", "dist": 0.55, "plan": plan,
                     "family": "drill", "mode": "drill", "target_atr": 2.0}
            sst = {"armed": True, "brackets": {}, "position": None}
            s = {"name": "sandbox_scalp", "symbol": "EURUSD", "exec": "scalp_market",
                 "pending_order": order}
            gateway.run_scalp_sleeves(sst, [s], 1000.0)
            out["scalp_basket"] = ((sst.get("scalp") or {}).get("sandbox_scalp")
                                   or {}).get("basket")
        except Exception as exc:
            out["scalp_exc"] = f"{type(exc).__name__}: {exc}"
        out["scalp_sends"] = len(calls["order_send"]) - n0
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
              "book_exc"):
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
    if fault == "healthy" and obs.get("new_risk") is False:
        out.append(f"RECONCILE_BEFORE_EXPOSURE: a healthy pass was refused new risk "
                   f"({obs.get('new_risk_why')})")
    return out


def _judge_partial_fill(obs: dict[str, Any]) -> list[str]:
    """PARTIAL_FILL_RECORDED: one send, and a basket holding the filled half and its residual."""
    out: list[str] = []
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
