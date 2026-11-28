"""A paused gateway still writes the account's equity (2026-11-13).

The Fusion deadman judges its ruin rail on gateway_state.json's `equity`. A pause stopped every
write, so from 2026-10-30 the rail read the same 266.01 for two weeks and no recovery or deposit
could lift the halt it had written. The paused pass now reads the account, read-only.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

_DESK = Path(__file__).resolve().parents[1]
_ROOT = _DESK.parents[1]

_CHILD = r"""
import json, sys, types
from types import SimpleNamespace as NS
from unittest import mock
root, desk, equity = sys.argv[1], sys.argv[2], float(sys.argv[3])
stub = types.ModuleType("MetaTrader5")
stub.__getattr__ = lambda name: mock.MagicMock(name="MetaTrader5." + name)
stub.account_info = lambda: NS(equity=equity, balance=equity)
def order_send(*a, **k):
    raise AssertionError("a paused gateway sent an order")
stub.order_send = order_send
sys.modules["MetaTrader5"] = stub
sys.path[:0] = [root, desk]
import mt5desk.gateway as gw
saved, logs = [], []
gw.gateway_paused = lambda: True
gw.connect = lambda: True
gw.load_state = lambda: {"armed": True, "equity": 266.01, "brackets": {}}
gw.save_state = lambda st: saved.append(json.loads(json.dumps(st, default=str)))
gw.log = logs.append
gw.main()
print("RESULT " + json.dumps({"state": saved[-1] if saved else None, "logs": logs}))
"""


def _drive(tmp_path: Path, equity: float) -> dict:
    env = {**os.environ, "MT5_DESK_ROOT": str(tmp_path),
           "PYTHONPATH": os.pathsep.join([str(_ROOT), str(_DESK)])}
    proc = subprocess.run([sys.executable, "-c", _CHILD, str(_ROOT), str(_DESK), str(equity)],
                          capture_output=True, text=True, timeout=300, cwd=str(_ROOT), env=env)
    line = next((ln for ln in proc.stdout.splitlines() if ln.startswith("RESULT ")), None)
    assert line is not None, f"gateway.main did not finish:\n{proc.stderr[-4000:]}"
    out: dict = json.loads(line[len("RESULT "):])
    return out


def test_a_paused_pass_writes_the_live_equity(tmp_path: Path) -> None:
    out = _drive(tmp_path, 512.34)
    assert any("gateway paused" in str(m) for m in out["logs"])
    st = out["state"]
    assert st is not None and st["equity"] == 512.34
    assert st["armed"] is True and "paused_reading_at" in st


def test_a_withdrawn_account_reads_zero_not_the_old_snapshot(tmp_path: Path) -> None:
    out = _drive(tmp_path, 0.0)
    assert out["state"]["equity"] == 0.0
