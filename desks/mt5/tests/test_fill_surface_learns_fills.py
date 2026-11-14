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


_KEYS = {1: "sha256:" + "a" * 16, 2: "sha256:" + "b" * 16}
_SERVERS = {1: "Fusion-Live", 2: "FTMO-Server"}


def _acct(n: int) -> dict:
    return {"account_key": _KEYS[n], "server": _SERVERS[n], "account_kind": "live"}


def _intent(ticket: int, intended: float, hour: int, acct: int = 1) -> dict:
    return {"ticket": ticket, "intended": intended, "side": "buy_stop", "sl": intended - 10.0,
            "tp": intended + 20.0, "lot": 0.01, "symbol": "XAUUSD", "sleeve": "gold_asia",
            "time": f"2026-11-0{1 + ticket % 9}T{hour:02d}:00:00+00:00", **_acct(acct)}


def _deal(ticket: int, fill: float, acct: int = 1) -> dict:
    return {"entry_order": ticket, "position_id": ticket, "entry_price": fill,
            "fill_price": fill + 5.0, "sl": fill - 10.0, "risk_quote": 10.0, "side": 1,
            "symbol": "XAUUSD", "sleeve": "gold_asia", "deal": ticket * 10, **_acct(acct)}


def test_each_intent_gets_its_own_entry_fill_and_nothing_else():
    intents = [_intent(1, 2000.0, 4), _intent(2, 2100.0, 5), _intent(3, 2200.0, 6)]
    deals = [_deal(1, 2000.3), _deal(2, 2099.9)]
    assert fs.join_fills(intents, deals) == 2
    assert [i.get("fill") for i in intents] == [2000.3, 2099.9, None], (
        "the ENTRY fill, never the exit; an unfilled intent stays unfilled")


def test_a_ledger_holding_two_accounts_still_joins_each_ticket():
    """`markout.compute` refuses a mixed ledger for STATISTICS; a fill is a fact about its own
    ticket, so each account's deals are joined on their own and the facts merged."""
    intents = [_intent(1, 2000.0, 4, acct=1), _intent(2, 2100.0, 5, acct=2)]
    assert fs.join_fills(intents, [_deal(1, 2000.3, acct=1), _deal(2, 2100.4, acct=2)]) == 2


def test_the_same_ticket_on_two_brokers_never_trades_fills():
    """Ticket numbers are per broker. Fusion ticket 7 and FTMO ticket 7 are different orders;
    a join on the bare number would give one the other's fill and invent a $500 slip."""
    fusion, ftmo = _intent(7, 2000.0, 4, acct=1), _intent(7, 2500.0, 4, acct=2)
    n = fs.join_fills([fusion, ftmo], [_deal(7, 2000.3, acct=1), _deal(7, 2500.2, acct=2)])
    assert n == 2
    assert (fusion["fill"], ftmo["fill"]) == (2000.3, 2500.2)

    lone = _intent(7, 2500.0, 4, acct=2)
    assert fs.join_fills([lone], [_deal(7, 2000.3, acct=1)]) == 0
    assert lone.get("fill") is None


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


def test_an_intent_from_before_provenance_joins_only_an_unambiguous_ticket():
    legacy = {k: v for k, v in _intent(9, 2000.0, 4).items()
              if k not in ("account_key", "server", "account_kind")}
    assert fs.join_fills([legacy], [_deal(9, 2000.4, acct=1)]) == 1
    assert legacy["fill"] == 2000.4

    shared = {k: v for k, v in _intent(9, 2000.0, 4).items()
              if k not in ("account_key", "server", "account_kind")}
    assert fs.join_fills([shared], [_deal(9, 2000.4, acct=1), _deal(9, 2000.6, acct=2)]) == 0
    assert shared.get("fill") is None, "a ticket two accounts share was guessed"
