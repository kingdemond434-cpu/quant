"""Reconcile before exposure, partial fills and out-of-order broker reads (2026-10-06).

The recovery drills ran the real gateway against a faulty MT5 double and found the pass opening
new risk on a broker state it had not read (terminal disconnected, reconcile unreadable, a book
that still lists a position after its closing deal) and forgetting a partially filled position.
These pin the gateway pieces that close those findings; `libs.tiers.gateway_drill` exercises
them end to end in a sandbox.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path
from types import SimpleNamespace as NS

import pytest

_DESK = Path(__file__).resolve().parents[1]
for p in (str(_DESK), str(_DESK / "research")):
    if p not in sys.path:
        sys.path.insert(0, p)

# The gateway imports MetaTrader5, which only installs on Windows; CI runs these on the box.
pytest.importorskip("MetaTrader5")
from mt5desk import gateway  # noqa: E402

_OK = {"verdict": "OK", "in_doubt": []}
_UP = NS(connected=True)


def test_gate_refuses_every_unread_venue_and_admits_a_clean_one() -> None:
    assert gateway.new_risk_gate(True, "armed", _OK, _UP) == (True, "armed")
    assert gateway.new_risk_gate(False, "stale seal", _OK, _UP)[0] is False
    assert gateway.new_risk_gate(True, "armed", _OK, NS(connected=False))[0] is False
    assert gateway.new_risk_gate(True, "armed", _OK, None)[0] is False
    # A missing report is a refusal, never a licence.
    ok, why = gateway.new_risk_gate(True, "armed", None, _UP)
    assert ok is False and "MISSING" in why
    for verdict in ("UNMEASURED", "FAILED"):
        assert gateway.new_risk_gate(True, "armed", {"verdict": verdict}, _UP)[0] is False
    unread = {"verdict": "OK", "in_doubt": [{"key": "k1", "unreadable": True}]}
    assert gateway.new_risk_gate(True, "armed", unread, _UP)[0] is False
    settled = {"verdict": "OK", "in_doubt": [{"key": "k1", "landed": True}]}
    assert gateway.new_risk_gate(True, "armed", settled, _UP)[0] is True


class _Venue:
    """A positions/deals double for `book_order_check`; `lists` is the bulk positions read."""

    DEAL_ENTRY_IN, DEAL_ENTRY_OUT, DEAL_ENTRY_OUT_BY = 0, 1, 3

    def __init__(self, lists: list[list[int]], deals: list[tuple[int, int, float]],
                 open_by_ticket: set[int] | None = None) -> None:
        self.lists, self.deals = lists, deals
        self.open_by_ticket = open_by_ticket or set()
        self.reads = 0

    def positions_get(self, **kw):
        if "ticket" in kw:
            t = kw["ticket"]
            return (NS(ticket=t, volume=0.01),) if t in self.open_by_ticket else ()
        tickets = self.lists[min(self.reads, len(self.lists) - 1)]
        self.reads += 1
        return tuple(NS(ticket=t, magic=gateway.MAGIC, time_update_msc=10 * t, volume=0.01)
                     for t in tickets)

    def history_deals_get(self, *a, **kw):
        return tuple(NS(position_id=pid, entry=entry, volume=vol, magic=gateway.MAGIC,
                        time_msc=1000 + i) for i, (pid, entry, vol) in enumerate(self.deals))


@pytest.fixture
def quiet(monkeypatch):
    lines: list[str] = []
    monkeypatch.setattr(gateway, "log", lines.append)
    return lines


def test_a_position_listed_after_its_closing_deal_refuses_new_risk(monkeypatch, quiet) -> None:
    venue = _Venue([[888], [888]], [(888, 0, 0.04), (888, 1, 0.04)])
    monkeypatch.setattr(gateway, "mt5", venue)
    st: dict = {}
    rr = gateway.book_order_check(st)
    assert rr is not None and rr["verdict"] == "UNMEASURED" and "book_inconsistent" in rr["why"]
    assert venue.reads == 2                                  # re-read exactly once, no more
    assert st["book_inconsistent"]["persisted"] is True
    assert st["closed_position_ids"] == [888] and st["last_deal_msc"] == 1001
    assert gateway.new_risk_gate(True, "armed", rr, _UP)[0] is False


def test_a_lag_that_clears_on_the_re_read_is_not_a_refusal(monkeypatch, quiet) -> None:
    venue = _Venue([[888], []], [(888, 0, 0.04), (888, 1, 0.04)])
    monkeypatch.setattr(gateway, "mt5", venue)
    st: dict = {}
    assert gateway.book_order_check(st) is None
    assert st["book_inconsistent"]["cleared_on_reread"] is True


def test_a_partial_close_is_not_a_closed_position(monkeypatch, quiet) -> None:
    # OUT volume below IN volume: the position is legitimately still on.
    venue = _Venue([[888]], [(888, 0, 0.04), (888, 1, 0.02)])
    monkeypatch.setattr(gateway, "mt5", venue)
    st: dict = {}
    assert gateway.book_order_check(st) is None
    assert "book_inconsistent" not in st and venue.reads == 1


def test_an_open_position_missing_from_the_bulk_read_refuses(monkeypatch, quiet) -> None:
    venue = _Venue([[], []], [(999, 0, 0.01)], open_by_ticket={999})
    monkeypatch.setattr(gateway, "mt5", venue)
    assert gateway.book_order_check({})["verdict"] == "UNMEASURED"
    # ...and a position closed outside this desk's magic (no OUT read) is not confirmed open.
    venue = _Venue([[], []], [(999, 0, 0.01)])
    monkeypatch.setattr(gateway, "mt5", venue)
    assert gateway.book_order_check({}) is None


def test_an_unreadable_history_is_left_to_the_reconcile_verdict(monkeypatch, quiet) -> None:
    class _Broken(_Venue):
        def history_deals_get(self, *a, **kw):
            raise RuntimeError("history down")
    monkeypatch.setattr(gateway, "mt5", _Broken([[1]], []))
    assert gateway.book_order_check({}) is None
    assert any("BOOK CHECK unreadable" in x for x in quiet)


def test_a_partial_close_records_its_residual_and_a_full_one_does_not(monkeypatch,
                                                                        quiet) -> None:
    venue = NS(positions_get=lambda **kw: (NS(ticket=777, volume=0.02),))
    monkeypatch.setattr(gateway, "mt5", venue)
    st: dict = {}
    pos = NS(ticket=777, volume=0.04)
    gateway._note_close_residual(st, pos, NS(retcode=10010, volume=0.02))
    assert st["close_residual"] == {"777": 0.02}
    st2: dict = {}
    gateway._note_close_residual(st2, pos, NS(retcode=10009, volume=0.04))
    gateway._note_close_residual(st2, pos, None)
    assert "close_residual" not in st2


def test_the_consumed_allocation_decision_is_noted_or_its_absence_explained(
        tmp_path, monkeypatch) -> None:
    import libs.portfolio.allocator_proof as ap
    monkeypatch.setattr(gateway, "BASE", tmp_path)
    monkeypatch.setattr(gateway, "allocator_heat", lambda: (None, "no solve"))
    gateway.allocator_book()
    assert gateway.allocator_book.consumed["decision_id"] is None
    assert "no solve" in gateway.allocator_book.consumed["why"]

    monkeypatch.setattr(gateway, "allocator_heat", lambda: (0.2, "ok"))
    monkeypatch.setattr(ap, "read_certificate", lambda root: (None, "proof failed"))
    (tmp_path / "reports").mkdir()
    art = {"heat": {"total": 0.2}, "book": {"a": 0.2},
           "book_fallback": {"name": "inverse_vol", "book": {"a": 0.2}}}
    (tmp_path / "reports" / "pf_allocation.json").write_text(json.dumps(art), "utf-8")
    gateway.allocator_book()
    assert gateway.allocator_book.consumed["decision_id"] is None
    assert "no decision_id" in gateway.allocator_book.consumed["why"]
    (tmp_path / "reports" / "pf_allocation.json").write_text(
        json.dumps({**art, "decision_id": "d-42"}), "utf-8")
    gateway.allocator_book()
    assert gateway.allocator_book.consumed == {"decision_id": "d-42", "why": ""}
