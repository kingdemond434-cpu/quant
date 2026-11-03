"""THE ACCOUNT PARITY GATE: every live account runs the same mechanisms (zuck 2026-11-03).

Three claims, each a CI failure when it stops being true:

  1. every file that can send an order belongs to an account in `mt5desk.account_parity`, so a
     new account or lane cannot trade outside this gate;
  2. every account carries every mechanism in that registry (no exemptions: firm rule caps are
     parameters, not a reason to skip a mechanism);
  3. the shared MetaTrader ratchet FTMO now runs natively sends the SAME stop the Fusion gateway
     sends, on the same terminal and bars, for the trailed and the fixed-bracket case.
"""
from __future__ import annotations

import ast
import contextlib
import hashlib
import json
import os
import re
import sys
import tempfile
import time
from datetime import UTC, datetime, timedelta
from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pandas as pd
import pytest

_DESK = Path(__file__).resolve().parents[1]
_ROOT = _DESK.parent.parent
for _p in (str(_DESK), str(_DESK / "research"), str(_ROOT)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from mt5desk import account_parity as ap  # noqa: E402
from mt5desk import decision_core as dc  # noqa: E402
from mt5desk import mt5_ratchet  # noqa: E402
from mt5desk import position_manager as _pm  # noqa: E402

_SENDS = re.compile(r"order_send\(|\.modify_stop\(|\.place\(")
_LIVE_DIRS = ("mt5desk", "prop")


def _src(rel: str) -> str:
    return (_DESK / rel).read_text(encoding="utf-8")


# ---------------------------------------------------------------- 1. no lane outside the gate

def test_every_order_sender_belongs_to_a_registered_account() -> None:
    known = {f for lanes in ap.LIVE_ACCOUNTS.values() for f in lanes} | set(ap.SHARED_SENDERS)
    senders = {str(p.relative_to(_DESK)).replace("\\", "/")
               for d in _LIVE_DIRS for p in (_DESK / d).glob("*.py")
               if _SENDS.search(p.read_text(encoding="utf-8"))}
    stray = sorted(senders - known)
    assert not stray, (f"{stray} can send orders but belong to no account in "
                       f"mt5desk/account_parity.LIVE_ACCOUNTS, so the parity gate cannot see them")
    for lanes in ap.LIVE_ACCOUNTS.values():
        for f in lanes:
            assert (_DESK / f).is_file(), f"registered lane {f} does not exist"


# ---------------------------------------------------------------- 2. every mechanism everywhere

@pytest.mark.parametrize("account", sorted(ap.LIVE_ACCOUNTS))
def test_every_account_runs_every_mechanism(account: str) -> None:
    text = "\n".join(_src(f) for f in ap.LIVE_ACCOUNTS[account])
    missing = [m for m, markers in ap.MECHANISMS.items()
               if not any(mk in text for mk in markers)]
    assert not missing, (f"account {account!r} does not run {missing}; every live account must "
                         f"run the same mechanisms (zuck 2026-11-03)")


def test_ftmo_runs_the_ratchet_natively_and_not_only_as_a_mirror() -> None:
    """The drift this gate was built for: FTMO's gold copy only mirrored E8's acknowledged
    stop (it never fired), and its sleeve executor never moved a stop at all."""
    assert "_ratchet.wanted_stop(" in _src("prop/ftmo_follower.py")
    ex = ast.parse(_src("prop/ftmo_executor.py"))
    manage = next(n for n in ex.body if isinstance(n, ast.FunctionDef) and n.name == "manage")
    assert "_manage_stop(" in ast.unparse(manage)


# ---------------------------------------------------------------- 3. same stop, same terminal

_GW_TREE = ast.parse(_src("mt5desk/gateway.py"))


def _gateway(names: tuple[str, ...], ns: dict) -> dict:
    """Exec the gateway's own management functions (the module imports MetaTrader5 and cannot
    be imported here) over the real decision core, as tests/test_gateway_adapter.py does."""
    seed = {k: v for k, v in vars(dc).items() if not k.startswith("__")}
    seed.update({"contextlib": contextlib, "hashlib": hashlib, "json": json, "time": time,
                 "os": os, "tempfile": tempfile, "datetime": datetime, "UTC": UTC,
                 "timedelta": timedelta, "Path": Path, "pd": pd, "np": np, "_pm": _pm})
    for node in _GW_TREE.body:
        if isinstance(node, ast.Assign) and len(node.targets) == 1 \
                and isinstance(node.targets[0], ast.Name):
            with contextlib.suppress(ValueError, SyntaxError, TypeError):
                seed.setdefault(node.targets[0].id, ast.literal_eval(node.value))
    seed.update(ns)
    keep = [n for n in _GW_TREE.body if isinstance(n, ast.FunctionDef) and n.name in names]
    assert {n.name for n in keep} == set(names)
    exec(compile(ast.Module(body=keep, type_ignores=[]),
                 str(_DESK / "mt5desk" / "gateway.py"), "exec"), seed)
    return seed


def _terminal(*, comment: str, run_up: float, sent: list) -> SimpleNamespace:
    """A gold long opened 30 H1 bars ago at 4000 with a 20-point stop, then a steady run-up."""
    t0 = 1_800_000_000 - 400 * 3600
    rows = []
    for i in range(400):
        base = 3990.0 + (0.0 if i < 370 else (i - 370) * run_up)
        rows.append({"time": t0 + i * 3600, "open": base, "high": base + 6.0,
                     "low": base - 6.0, "close": base + 1.0})
    opened = t0 + 370 * 3600
    last = rows[-1]["close"]
    pos = SimpleNamespace(ticket=7001, type=0, price_open=4000.0, sl=3980.0, tp=0.0,
                          comment=comment, time=opened, symbol="XAUUSD", volume=1.0)

    def rates(symbol, tf, start, count):
        if tf == 1:                                  # M1: the same path at minute resolution
            return [{**r, "time": opened + j * 60} for j, r in enumerate(rows[370:])]
        return rows[-count:]

    return SimpleNamespace(
        POSITION_TYPE_BUY=0, TIMEFRAME_H1=16385, TIMEFRAME_M1=1, TRADE_ACTION_SLTP=6,
        positions_get=lambda symbol=None, ticket=None: [pos],
        symbol_info=lambda symbol: SimpleNamespace(
            trade_stops_level=0, trade_tick_size=0.01, trade_tick_value=1.0, spread=20,
            point=0.01),
        symbol_info_tick=lambda symbol: SimpleNamespace(bid=last, ask=last + 0.2),
        copy_rates_from_pos=rates,
        history_deals_get=lambda position=None: [],
        order_send=lambda req: sent.append(req) or SimpleNamespace(retcode=10009, comment=""))


@pytest.mark.parametrize(("comment", "generic", "floor_only", "run_up"), [
    ("gold", {}, False, 2.0),                              # trailed: chandelier + floor
    ("DWfam_x", {"fam_x": {"trail_k": 0.0}}, True, 2.0),   # fixed bracket: floor only
    ("gold", {}, False, 0.0),                              # no run-up: nothing moves
])
def test_the_shared_ratchet_sends_the_gateways_stop(comment, generic, floor_only,
                                                    run_up) -> None:
    from libs.portfolio.fusion_cost import COMMISSION_PER_LOT_PER_SIDE

    sent_gw: list = []
    mt5 = _terminal(comment=comment, run_up=run_up, sent=sent_gw)
    ns = _gateway(("manage_open_positions", "order_comment", "_original_stop_distance",
                   "_rates_since_position", "_round_trip_per_price_unit"),
                  {"mt5": mt5, "log": lambda m: None, "MAGIC": 1})
    sleeves = ([{"name": "fam_x", "exec": "family_market", "symbol": "XAUUSD"}]
               if generic else [])
    ns["manage_open_positions"]({"armed": True, "generic": generic}, sleeves)

    want = mt5_ratchet.wanted_stop(_terminal(comment=comment, run_up=run_up, sent=[]),
                                   mt5.positions_get()[0], store={}, floor_only=floor_only,
                                   per_side=COMMISSION_PER_LOT_PER_SIDE)
    gw_stop = sent_gw[0]["sl"] if sent_gw else None
    assert want.get("new_stop") == gw_stop, (want, sent_gw)
    if run_up:
        assert gw_stop is not None and gw_stop > 3980.0


def test_the_commission_is_the_accounts_own_and_falls_back_high() -> None:
    deal = SimpleNamespace(entry=0, volume=0.5, commission=-1.25)
    mt5 = SimpleNamespace(history_deals_get=lambda position=None: [deal])
    assert mt5_ratchet.commission_per_side(mt5, 1)[0] == pytest.approx(2.5)
    none = SimpleNamespace(history_deals_get=lambda position=None: [])
    assert mt5_ratchet.commission_per_side(none, 1)[0] == mt5_ratchet.FALLBACK_COMMISSION_PER_SIDE
    from libs.portfolio.fusion_cost import COMMISSION_PER_LOT_PER_SIDE
    assert mt5_ratchet.FALLBACK_COMMISSION_PER_SIDE > COMMISSION_PER_LOT_PER_SIDE


def test_the_captured_r_survives_until_the_position_closes() -> None:
    store: dict = {}
    assert mt5_ratchet.original_stop_distance(store, 5, 100.0, 98.0) == 2.0
    assert mt5_ratchet.original_stop_distance(store, 5, 100.0, 99.5) == 2.0   # moved stop
    mt5_ratchet.prune(store, {6})
    assert store == {}
