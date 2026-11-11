"""The execution surface learns from the desk's own fills, not from a prior forever.

`FillSurface.fit` learns slippage only from rows carrying `intended` AND `fill`. No intent ever
carried `fill`: the gateway fitted on bare intents and `run` joined on a `markout.json["rows"]`
key nothing writes, so the surface priced every execution choice on its half-spread prior for
its whole life -- about zero, where the measured gold fills cost 1.24bps.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

_DESK = Path(__file__).resolve().parents[1]
if str(_DESK) not in sys.path:
    sys.path.insert(0, str(_DESK))

from mt5desk import fill_surface as fs  # noqa: E402


def _intent(ticket: int, intended: float, hour: int) -> dict:
    return {"ticket": ticket, "intended": intended, "side": "buy_stop", "sl": intended - 10.0,
            "tp": intended + 20.0, "lot": 0.01, "symbol": "XAUUSD", "sleeve": "gold_asia",
            "time": f"2026-11-0{1 + ticket % 9}T{hour:02d}:00:00+00:00"}


def _deal(ticket: int, fill: float, login: int = 1) -> dict:
    return {"entry_order": ticket, "position_id": ticket, "entry_price": fill,
            "fill_price": fill + 5.0, "sl": fill - 10.0, "risk_quote": 10.0, "side": 1,
            "symbol": "XAUUSD", "sleeve": "gold_asia", "deal": ticket * 10,
            "login": login, "server": "Fusion-Live", "account_kind": "live"}


def test_each_intent_gets_its_own_entry_fill_and_nothing_else():
    intents = [_intent(1, 2000.0, 4), _intent(2, 2100.0, 5), _intent(3, 2200.0, 6)]
    deals = [_deal(1, 2000.3), _deal(2, 2099.9)]
    assert fs.join_fills(intents, deals) == 2
    assert [i.get("fill") for i in intents] == [2000.3, 2099.9, None], (
        "the ENTRY fill, never the exit; an unfilled intent stays unfilled")


def test_a_ledger_holding_two_accounts_still_joins_each_ticket():
    """`markout.compute` refuses a mixed ledger for STATISTICS; a fill is a fact about its own
    ticket, so each account's deals are joined on their own and the facts merged."""
    intents = [_intent(1, 2000.0, 4), _intent(2, 2100.0, 5)]
    assert fs.join_fills(intents, [_deal(1, 2000.3, login=1), _deal(2, 2100.4, login=2)]) == 2


def test_the_surface_fits_on_joined_fills_where_it_never_could_before(tmp_path):
    intents = [_intent(t, 2000.0 + t, 3 + t % 8) for t in range(1, fs.MIN_FILLS + 6)]
    deals = [_deal(t, 2000.0 + t + 0.2 + 0.01 * (t % 5)) for t in range(1, fs.MIN_FILLS + 6)]
    ip, lp = tmp_path / "order_intents.jsonl", tmp_path / "live_ledger.jsonl"
    ip.write_text("\n".join(json.dumps(r) for r in intents), "utf-8")
    lp.write_text("\n".join(json.dumps(r) for r in deals), "utf-8")

    bare = fs.FillSurface().fit([dict(r) for r in intents])
    assert bare.slip_w is None and bare.n_fills == 0

    joined = fs.FillSurface().fit(fs.load_joined(ip, lp))
    assert joined.n_fills == len(intents)
    assert joined.slip_w is not None
    assert joined.mean_slip_measured is not None and joined.mean_slip_measured > 0


def test_the_gateway_fits_its_surface_on_joined_rows():
    src = (_DESK / "mt5desk" / "gateway.py").read_text("utf-8")
    body = src.split("def _fill_surface():", 1)[1].split("\ndef ", 1)[0]
    assert "fill_surface.load_joined(" in body
