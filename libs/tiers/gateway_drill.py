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
                    book, and `connect()` only asks whether `terminal_info()` exists)
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
                           "terminal_disconnected", "reconcile_unreadable")
#: The faults after which the pass must refuse NEW exposure (RECONCILE_BEFORE_EXPOSURE).
REFUSE_NEW_RISK: frozenset[str] = frozenset({"terminal_disconnected", "reconcile_unreadable"})
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
def positions_get(**kw):
    if fault == "reconcile_unreadable":
        raise RuntimeError("positions_get failed")
    return ()
for f in (terminal_info, initialize, last_error, symbol_info_tick, symbol_info, account_info,
          order_calc_margin, order_send, orders_get, positions_get):
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
        try:
            ok, why = gate(True, "armed", rr, m.terminal_info())
            out["new_risk"] = bool(ok)
            out["new_risk_why"] = str(why)[:200]
        except Exception as exc:
            out["gate_exc"] = f"{type(exc).__name__}: {exc}"
except Exception as exc:
    out["import_exc"] = f"{type(exc).__name__}: {exc}"
    out["trace"] = traceback.format_exc()[-800:]
out["sends"] = len(calls["order_send"])
out["initialize_calls"] = calls["initialize"]
print("DRILL_JSON " + json.dumps(out, default=str))
'''


def _jsonl(p: Path) -> list[dict[str, Any]]:
    try:
        return [json.loads(x) for x in p.read_text("utf-8").splitlines() if x.strip()]
    except (OSError, ValueError):
        return []


def run_fault(fault: str, *, desk: Path = DESK, with_ledgers: bool = False) -> dict[str, Any]:
    """One fault against the real gateway in a child process rooted in a temp directory.

    `with_ledgers` also returns the sandbox's own order-door ledger and intent rows (under
    `observed.ledgers`), read before the temp directory is removed -- the execution
    reconciliation (`desks/mt5/research/execution_reconcile.py`) joins them exactly as it joins
    the box's. Off by default, so the CHAOS artifact does not carry them."""
    with tempfile.TemporaryDirectory(prefix="gw_drill_") as tmp:
        root = Path(tmp)
        (root / "data").mkdir()
        (root / "logs").mkdir()
        # The child runs from the temp directory, so neither the repository root (for `libs`)
        # nor the desk (for `mt5desk`) is on its path unless it is put there: a clean worktree
        # has no installed package to fall back on (audit 2026-09-30: ModuleNotFoundError).
        path = os.pathsep.join([str(ROOT), str(desk),
                                *filter(None, [os.environ.get("PYTHONPATH", "")])])
        # The door's ledger goes INSIDE the sandbox too: an inherited MT5_ORDER_DOOR_DIR (a test
        # harness sets one) would send the child's door rows to the caller's directory.
        env = {**os.environ, "MT5_DESK_ROOT": str(root), "PYTHONDONTWRITEBYTECODE": "1",
               "PYTHONPATH": path, "MT5_ORDER_DOOR_DIR": str(root / "data")}
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
        if with_ledgers:
            obs["ledgers"] = {"door": _jsonl(root / "data" / "order_door_ledger.jsonl"),
                              "intents": _jsonl(root / "data" / "order_intents.jsonl")}
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
    for k in ("connect_exc", "place_exc", "expire_exc", "gate_exc"):
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
    if fault == "healthy" and obs.get("new_risk") is False:
        out.append(f"RECONCILE_BEFORE_EXPOSURE: a healthy pass was refused new risk "
                   f"({obs.get('new_risk_why')})")
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
