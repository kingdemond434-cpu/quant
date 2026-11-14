"""A halted gateway keeps the ruin rail's view of the account current, and touches nothing else.

MEASURED 2026-11-11 (scripts/check_halt_rail_integrity.py): `gateway.main` returned on a halt
before it connected, so `gateway_state.json` froze at the halt instant and the Fusion ruin rail,
which reads its whole view of the account from that file, had five of seven rails unreachable for
eleven days. These drive the REAL `paused_snapshot` / `main` against a stub terminal in a
subprocess and pin: the rail's inputs are refreshed, no order call is made, and a dead terminal
leaves the file untouched.
"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

_DESK = Path(__file__).resolve().parents[1]
_ROOT = _DESK.parent.parent

_CHILD = r"""
import json, sys, types
from types import SimpleNamespace as NS
root, desk, mode = sys.argv[1], sys.argv[2], sys.argv[3]
calls = []
stub = types.ModuleType("MetaTrader5")
def _forbidden(name):
    def f(*a, **k):
        calls.append(name)
        raise AssertionError(name + " called while paused")
    return f
def _getattr(name):
    if name in ("order_send", "order_check", "Close", "positions_close"):
        return _forbidden(name)
    return 0
stub.__getattr__ = _getattr
stub.symbol_info_tick = lambda sym: NS(bid=2400.0, ask=2400.3, time=1_800_000_000)
stub.account_info = (lambda: None) if mode == "dead" else (
    lambda: NS(equity=512.345, balance=500.0, margin_free=480.4))
pos = NS(ticket=7, type=0, volume=0.01, price_open=1.1, sl=1.0, tp=1.2, profit=3.0,
         symbol="EURUSD")
stub.positions_get = lambda *a, **k: (pos,) if k.get("symbol") == "EURUSD" else ()
stub.orders_get = lambda *a, **k: ()
stub.shutdown = lambda: None
sys.modules["MetaTrader5"] = stub
sys.path[:0] = [root, desk]
import mt5desk.gateway as gw
saved, logs = [], []
gw.gateway_paused = lambda: True
gw.connect = lambda: mode != "noterm"
gw.load_state = lambda: {"armed": False, "equity": 266.01, "position": None,
                         "day_start_equity": {"date": "2026-10-30", "equity": 266.01}}
gw.load_sleeves = lambda: [{"symbol": "EURUSD"}]
gw.save_state = lambda st: saved.append(json.loads(json.dumps(st, default=str)))
gw.log = logs.append
gw.main()
print(json.dumps({"saved": saved, "logs": logs, "calls": calls}))
"""


def _run(mode: str) -> dict:
    out = subprocess.run([sys.executable, "-c", _CHILD, str(_ROOT), str(_DESK), mode],
                         capture_output=True, text=True, timeout=120, check=False)
    assert out.returncode == 0, out.stderr[-2000:]
    return json.loads(out.stdout.strip().splitlines()[-1])


def test_a_paused_pass_refreshes_what_the_ruin_rail_reads() -> None:
    doc = _run("live")
    assert doc["calls"] == []
    (st,) = doc["saved"]
    assert st["equity"] == 512.35 and st["margin_free"] == 480.4
    assert st["position"][0]["ticket"] == 7 and st["last_reconcile"]
    assert st["day_start_equity"]["date"] != "2026-10-30"     # the frozen day is rolled
    assert st["armed"] is False                                # nothing is armed
    assert "rail view refreshed" in doc["logs"][0] and "no trading" in doc["logs"][0]


def test_a_dead_terminal_or_account_leaves_the_file_as_it_was() -> None:
    for mode in ("noterm", "dead"):
        doc = _run(mode)
        assert doc["saved"] == [] and doc["calls"] == []
        assert "stays as last saved" in doc["logs"][0]
