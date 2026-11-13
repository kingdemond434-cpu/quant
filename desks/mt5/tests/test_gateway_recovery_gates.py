"""The recovery-drill gates in the gateway (docs/desktop_pass/recovery_drills/), unit by unit.

The whole gateway is drilled against a faulty terminal double in libs/tiers/gateway_drill.py;
these pin each helper's contract on its own: what refuses new risk, what a partial fill
records, what a partial close leaves, and when the open book disagrees with the deal history.
"""
from __future__ import annotations

import importlib.util
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path
from types import SimpleNamespace as NS

_DESK = Path(__file__).resolve().parents[1]
for _p in (str(_DESK), str(_DESK.parent.parent)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from mt5desk import order_door  # noqa: E402

_spec = importlib.util.spec_from_file_location("_recovery_adapter",
                                               _DESK / "tests" / "test_gateway_adapter.py")
assert _spec is not None and _spec.loader is not None
adapter = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(adapter)


def _ns(**fakes):
    return adapter._exec(("new_risk_gate", "scalp_fill", "note_close_result",
                          "book_consistency", "quote_age_s", "now"),
                         {"log": (logs := []).append, "_logs": logs, **fakes})


def test_the_filled_set_is_the_order_doors() -> None:
    ns = _ns()
    assert set(ns["FILLED_RETCODES"]) == set(order_door.SUCCESS)
    assert ns["RETCODE_DONE_PARTIAL"] == order_door.RETCODE_DONE_PARTIAL


def test_new_risk_needs_release_terminal_and_a_read_book() -> None:
    gate = _ns()["new_risk_gate"]
    up = NS(connected=True)
    ok = {"verdict": "OK", "in_doubt": []}
    assert gate(True, "sealed", ok, up) == (True, "sealed")
    assert gate(False, "mismatch", ok, up)[0] is False
    assert gate(True, "sealed", ok, None)[0] is False
    assert gate(True, "sealed", ok, NS(connected=False))[0] is False
    for bad in (None, {}, {"verdict": "UNMEASURED", "why": "x"}, {"verdict": "FAILED"}):
        assert gate(True, "sealed", bad, up)[0] is False
    doubt = {"verdict": "OK", "in_doubt": [{"key": "k", "unreadable": True}]}
    assert gate(True, "sealed", doubt, up)[0] is False


def test_a_partial_fill_is_a_position_at_the_filled_volume() -> None:
    fill = _ns()["scalp_fill"]
    assert fill(NS(retcode=10010, volume=0.01), 0.03) == (0.01, 0.02)
    assert fill(NS(retcode=10009, volume=0.03), 0.03) == (0.03, 0.0)
    # an absent, zero or oversized volume is read as the asked size: never a second entry
    for v in (None, 0.0, 0.05):
        assert fill(NS(retcode=10009, volume=v), 0.03) == (0.03, 0.0)


def test_a_partial_close_records_the_brokers_residual_and_sends_nothing() -> None:
    sent: list = []
    venue = NS(positions_get=lambda ticket=None: (NS(ticket=ticket, volume=0.01),),
               order_send=lambda req: sent.append(req))
    ns = _ns(mt5=venue)
    st: dict = {}
    p = NS(ticket=77, volume=0.03)
    assert ns["note_close_result"](st, p, NS(retcode=10010, volume=0.02), "t") == 0.01
    assert st["close_residual"]["77"]["residual"] == 0.01 and sent == []
    assert any("CLOSE PARTIAL ticket 77" in x for x in ns["_logs"])
    # a full close clears it; a rejected close records nothing
    assert ns["note_close_result"](st, p, NS(retcode=10009, volume=0.03), "t") == 0.0
    assert "77" not in st["close_residual"]
    assert ns["note_close_result"](st, p, NS(retcode=10019, volume=0.0), "t") is None
    # an old residual nobody cleared is dropped
    st["close_residual"]["9"] = {"residual": 1.0, "at": (datetime.now(tz=UTC)
                                                         - timedelta(days=9)).isoformat()}
    ns["note_close_result"](st, p, NS(retcode=10009, volume=0.03), "t")
    assert "9" not in st["close_residual"]


def _venue(listed, deals, by_ticket=()):
    return NS(DEAL_ENTRY_IN=0, DEAL_ENTRY_OUT=1, DEAL_ENTRY_OUT_BY=3,
              positions_get=lambda ticket=None: (
                  tuple(p for p in by_ticket if p.ticket == ticket) if ticket else tuple(listed)),
              history_deals_get=lambda a, b: tuple(deals))


def _deal(pid, entry, vol, magic=341953, t=1):
    return NS(position_id=pid, entry=entry, volume=vol, magic=magic, time_msc=t)


def test_a_position_listed_after_its_closing_deal_is_inconsistent() -> None:
    pos = NS(ticket=77, magic=341953, time_update_msc=5)
    deals = [_deal(77, 0, 0.02), _deal(77, 1, 0.02, magic=0, t=9)]  # broker stop-out: magic 0
    rep = _ns(mt5=_venue([pos], deals), MAGIC=341953)["book_consistency"]()
    assert rep["verdict"] == "INCONSISTENT" and rep["phantom"] == [77]
    assert rep["last_deal_msc"] == 9 and rep["position_snapshot_msc"] == 5


def test_a_partial_close_and_an_old_position_are_consistent() -> None:
    pos = NS(ticket=77, magic=341953, time_update_msc=5)
    deals = [_deal(77, 0, 0.02), _deal(77, 1, 0.01), _deal(88, 1, 0.02)]  # 88 opened long ago
    rep = _ns(mt5=_venue([pos], deals), MAGIC=341953)["book_consistency"]()
    assert rep["verdict"] == "OK", rep


def test_an_open_position_missing_from_the_bulk_read_is_inconsistent() -> None:
    held = NS(ticket=55, magic=341953, volume=0.02)
    deals = [_deal(55, 0, 0.02)]
    ns = _ns(mt5=_venue([], deals, by_ticket=[held]), MAGIC=341953)
    rep = ns["book_consistency"]()
    assert rep["verdict"] == "INCONSISTENT" and rep["missing"] == [55]
    # the ticket read agreeing with the bulk read (closed, deal not seen yet) is not a finding
    rep = _ns(mt5=_venue([], deals), MAGIC=341953)["book_consistency"]()
    assert rep["verdict"] == "OK"


def test_an_unreadable_history_is_unchecked_not_a_refusal() -> None:
    def boom(a, b):
        raise RuntimeError("history")
    v = NS(DEAL_ENTRY_IN=0, positions_get=lambda ticket=None: (), history_deals_get=boom)
    assert _ns(mt5=v, MAGIC=341953)["book_consistency"]()["verdict"] == "UNCHECKED"


def test_a_quote_with_no_stamp_has_no_age() -> None:
    age = _ns()["quote_age_s"]
    assert age(None) is None and age(NS(time=0)) is None
