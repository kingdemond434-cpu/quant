"""The E8 bracket re-cut on LIVE (v2, 2026-11-13): every LIVE path the re-cut met keeps working
and leaves a decision row under its OWN reason code.

#411 moved the concurrent-risk budget out of the blocker into sizing (so a leg the lot ceiling
shrank is fitted to the budget, not deferred at its unshrunk risk) and read the whole account's
order book. LIVE had grown three paths since #411 was cut, none of which had a code in the
`e8_evidence` taxonomy:

  * the adopter's hold (`libs.ops.new_risk_hold`) -- was noted as `one_at_risk`;
  * the deferred grace (`venue_read`: only an unreadable ORDER BOOK earns the extra pass) -- was
    noted as the generic `risk_unmeasurable`;
  * an abandoned send that had LANDED (`landed_abandoned`) -- was noted as `venue_rejected`.

And the budget check LIVE ran at the blocker must still hold for every leg the ceiling did not
shrink, and must still DEFER (not spend the window for the day) when it is the committed risk,
not the ceiling, that leaves no room.
"""
from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path
from typing import Any

import pytest

_DESK = Path(__file__).resolve().parents[1]
_ROOT = _DESK.parent.parent
for _p in (str(_DESK), str(_ROOT), str(_DESK / "tests")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from prop import e8_evidence as ev  # noqa: E402
from prop import e8_gold as g  # noqa: E402
from test_e8_gold_guard_and_open_risk import (  # noqa: E402
    _ENTRY,
    _MT5,
    _sandbox,
    _short,
    _Venue,
)
from test_e8_placement_evidence import (  # noqa: E402
    _LEG,
    _outcomes,
    _retry,
    _retry_state,
    _RetryVenue,
)

_SPEC = importlib.util.spec_from_file_location(
    "check_placement_interlock_recut", _ROOT / "scripts" / "check_placement_interlock.py")
assert _SPEC and _SPEC.loader
fence = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(fence)


def _rows(window: str | None = None) -> list[dict[str, Any]]:
    path = ev.decisions_path()
    if not path.exists():
        return []
    rows = [json.loads(x) for x in path.read_text("utf-8").splitlines() if x.strip()]
    return [r for r in rows if window is None or r.get("window") == window]


def _intents() -> list[dict[str, Any]]:
    if not g.INTENTS.exists():
        return []
    return [json.loads(x) for x in g.INTENTS.read_text("utf-8").splitlines() if x.strip()]


def _state() -> dict[str, Any]:
    return json.loads(g.STATE.read_text("utf-8"))


# ------------------------------------------------------------------ the taxonomy and the fence

def test_each_live_path_has_its_own_code_classified_non_exempt() -> None:
    codes = {ev.R_ADOPT_HOLD, ev.R_ORDERS_UNREADABLE, ev.R_LANDED_ABANDONED}
    assert len(codes) == 3 and not codes & {ev.R_ONE_AT_RISK, ev.R_RISK_UNMEASURABLE,
                                            ev.R_VENUE_REJECTED, ev.R_LEG_ABANDONED}
    assert codes == set(fence.E8_LIVE_PATH_REASONS)
    assert not codes & fence.E8_EXEMPT_REASONS and not codes & fence.E8_RAIL_REASONS
    # the adopter's hold is the rail name LIVE already bills on the missed-growth ledgers
    assert ev.R_ADOPT_HOLD == "adopt_new_risk_hold"


def test_abandon_reason_names_a_landed_send() -> None:
    assert ev.abandon_reason("the session is over", {}, landed=True) == ev.R_LANDED_ABANDONED
    assert ev.abandon_reason("the session is over", {}) == ev.R_VENUE_REJECTED
    # the window traded (its twin rests or filled): still the exempt leg_abandoned
    assert ev.abandon_reason("the other leg filled", {}, landed=True) == ev.R_LEG_ABANDONED
    assert ev.abandon_reason("late", {"orders": {"sell_stop": {"id": 3}}},
                             landed=True) == ev.R_LEG_ABANDONED


# ------------------------------------------------------------------ the adopter's hold

def test_the_adopters_hold_defers_under_its_own_code_and_is_billed(monkeypatch, tmp_path) -> None:
    from libs.ops import new_risk_hold as nrh
    _sandbox(monkeypatch, tmp_path, placed=("asia", "london_am"))
    monkeypatch.setattr(nrh, "reason", lambda *a, **k: "release 1234abcd is being adopted")
    doc = g.run(_Venue(), _MT5(), armed=False)
    assert [p["window"] for p in doc["placed"]] == []
    rows = _rows("afternoon")
    assert [(r["outcome"], r["reason"]) for r in rows] == [(ev.DEFERRED, ev.R_ADOPT_HOLD)], rows
    billed = [r for r in _intents() if r.get("rail") == "adopt_new_risk_hold"]
    assert len(billed) == 1 and billed[0]["window"] == "afternoon"
    assert "afternoon" not in (_state().get("windows") or {})       # not spent: placed later


def test_a_held_re_send_is_a_deferred_row_under_the_hold(monkeypatch, tmp_path) -> None:
    from libs.ops import new_risk_hold as nrh
    monkeypatch.setattr(nrh, "reason", lambda *a, **k: "release 1234abcd is being adopted")
    v = _RetryVenue()
    d = _retry(monkeypatch, tmp_path, v, _retry_state())
    assert v.sent == []
    assert _outcomes(d) == [("asia", ev.DEFERRED, ev.R_ADOPT_HOLD)]
    assert d.rows[0]["risk_usd"] == _LEG["risk_usd"]


def test_a_re_send_held_by_the_account_rail_is_a_refused_row(monkeypatch, tmp_path) -> None:
    d = _retry(monkeypatch, tmp_path, _RetryVenue(), _retry_state(),
               account_ok=(False, "E8_ACCOUNT.json names another account"))
    assert _outcomes(d) == [("asia", ev.REFUSED, ev.R_ACCOUNT_UNDECLARED)]


# ------------------------------------------------------------------ the deferred grace

class _BookDown(_Venue):
    def orders(self, symbol: str | None = None) -> list[dict]:
        raise ConnectionError("status 429, error 'Too Many Requests'")


def test_an_unreadable_order_book_earns_the_grace_under_its_own_code(
        monkeypatch, tmp_path) -> None:
    _sandbox(monkeypatch, tmp_path, placed=("asia", "london_am"))
    g.run(_BookDown(), _MT5(), armed=False)
    rows = _rows("afternoon")
    assert [(r["outcome"], r["reason"]) for r in rows] == [
        (ev.DEFERRED, ev.R_ORDERS_UNREADABLE)], rows
    assert _state()["deferred"] == ["afternoon"]
    bill = [r for r in _intents() if r.get("rail") == g.RISK_UNMEASURABLE_RAIL]
    assert len(bill) == 1 and bill[0]["reason"] == ev.R_ORDERS_UNREADABLE


def test_an_unreadable_journal_is_risk_unmeasurable_and_earns_no_grace(
        monkeypatch, tmp_path) -> None:
    _sandbox(monkeypatch, tmp_path, placed=("asia", "london_am"))
    g.INTENTS.write_text("{}\n", encoding="utf-8")
    reads = iter([None])
    monkeypatch.setattr(g, "_journal_read", lambda *a, **k: next(reads, []))
    g.run(_Venue(), _MT5(), armed=False)
    rows = _rows("afternoon")
    assert [(r["outcome"], r["reason"]) for r in rows] == [
        (ev.DEFERRED, ev.R_RISK_UNMEASURABLE)], rows
    assert not _state().get("deferred")


def test_the_budget_reads_the_whole_accounts_order_book(monkeypatch, tmp_path) -> None:
    _sandbox(monkeypatch, tmp_path, placed=("asia", "london_am"))
    seen: list[Any] = []

    class _Spy(_Venue):
        def orders(self, symbol: str | None = None) -> list[dict]:
            seen.append(symbol)
            return super().orders(symbol)
    g.run(_Spy(), _MT5(), armed=False)
    assert seen and seen[0] is None


# ------------------------------------------------------------------ the landed abandoned send

class _CancelVenue(_RetryVenue):
    def __init__(self) -> None:
        super().__init__()
        self.cancelled: list[int] = []

    def cancel(self, order_id: int) -> bool:
        self.cancelled.append(int(order_id))
        return True


def test_an_abandoned_send_that_had_landed_is_landed_abandoned(monkeypatch, tmp_path) -> None:
    sent_ms = g._iso_ms(_LEG["first_at"])
    book = [{"id": 42, "side": "buy", "stopPrice": 4340.0, "tradableInstrumentId": 316,
             "qty": 0.5, "type": "stop", "createdDate": sent_ms + 2_000}]
    v = _CancelVenue()
    st = _retry_state()
    d = _retry(monkeypatch, tmp_path, v, st, hour=13.5, open_orders=book)
    assert v.cancelled == [42] and v.sent == []
    assert _outcomes(d) == [("asia", ev.SKIPPED, ev.R_LANDED_ABANDONED)]
    assert not st.get("landed_abandoned")             # the cancel went through


def test_the_rollover_keeps_both_landed_abandoned_and_fx_open_seen() -> None:
    st = {"date": "2026-11-12", "windows": {}, "carried": {},
          "landed_abandoned": {"42": {"window": "asia"}}, "fx_open_seen": {"7": "x"}}
    out = g.rollover_state(st, "2026-11-13")
    assert out["landed_abandoned"] == {"42": {"window": "asia"}}
    assert out["fx_open_seen"] == {"7": "x"}


# ------------------------------------------------------------------ the budget, where LIVE needs it

def _two_break_even() -> _Venue:
    """Two positions with their stops at the entry: neither at risk, 2 x 1,206.5 USD of slip."""
    return _Venue([_short(100, 9100), _short(101, 9101)], {9100: _ENTRY, 9101: _ENTRY - 1.0})


def test_a_capped_window_the_committed_risk_starves_is_deferred_not_spent(
        monkeypatch, tmp_path) -> None:
    """On an empty book the capped legs (0.14 lot cut to 0.1) fit the budget; with 2,413 USD committed they
    do not fit even the venue minimum. That is the committed risk binding, not the ceiling:
    deferred under risk_budget (LIVE's answer), never SKIPPED for the day under lot_ceiling."""
    _sandbox(monkeypatch, tmp_path, placed=("asia", "london_am"))
    monkeypatch.setattr(g, "gold_max_lot", lambda *a, **k: (0.1, "test ceiling"))
    doc = g.run(_two_break_even(), _MT5(), armed=False)
    assert [p["window"] for p in doc["placed"]] == []
    rows = _rows("afternoon")
    assert [(r["outcome"], r["reason"]) for r in rows] == [(ev.DEFERRED, ev.R_RISK_BUDGET)], rows
    assert "afternoon" not in (_state().get("windows") or {})
    assert not [r for r in _intents() if r.get("rail") == g.LOT_CEILING_RAIL]


def test_a_capped_window_on_an_empty_book_is_shrunk_and_placed(monkeypatch, tmp_path) -> None:
    """The #411 intent stands: a capped leg is cut to the ceiling and sent, never deferred.
    (The afternoon legs size at 0.14 lot: 500 USD over a 33.5-point stop.)"""
    _sandbox(monkeypatch, tmp_path, placed=("asia", "london_am"))
    monkeypatch.setattr(g, "gold_max_lot", lambda *a, **k: (0.1, "test ceiling"))
    doc = g.run(_Venue([], {}), _MT5(), armed=False)
    assert [p["window"] for p in doc["placed"]] == ["afternoon"], doc["skipped"]
    shrunk = doc.get("shrunk") or []
    assert shrunk and shrunk[0]["rail"] == g.LOT_CEILING_RAIL, doc.get("shrunk")


def test_a_leg_the_ceiling_did_not_shrink_is_still_held_to_the_budget(
        monkeypatch, tmp_path) -> None:
    """One leg over the ceiling, the other under it, 1,600 USD committed: the capped leg alone
    would fit (cut further), but the uncapped leg's 500 USD fails LIVE's budget exactly as a
    window with no capped leg does -- so the window is deferred, as it was on LIVE."""
    from prop import e8_executor as ex
    _sandbox(monkeypatch, tmp_path, placed=("asia", "london_am"))
    monkeypatch.setattr(g, "gold_max_lot", lambda *a, **k: (0.75, "test ceiling"))
    real = ex.lot_for_risk
    calls: list[int] = []

    def lot_for_risk(venue: Any, symbol: str, dist: float, risk: float) -> Any:
        calls.append(1)
        return (1.0, "test: over the ceiling") if len(calls) == 1 else real(venue, symbol,
                                                                            dist, risk)
    monkeypatch.setattr(ex, "lot_for_risk", lot_for_risk)
    monkeypatch.setattr(g, "committed_risk",
                        lambda *a, **k: (1_600.0, {"positions": [], "pending_brackets": {}}))
    doc = g.run(_Venue([], {}), _MT5(), armed=False)
    assert [p["window"] for p in doc["placed"]] == []
    rows = _rows("afternoon")
    assert [(r["outcome"], r["reason"]) for r in rows] == [(ev.DEFERRED, ev.R_RISK_BUDGET)], rows
    assert "concurrent risk would reach today's floor" in " ".join(
        str(s.get("why")) for s in doc["skipped"] if s.get("window") == "afternoon")


@pytest.mark.parametrize("code", ["adopt_new_risk_hold", "orders_unreadable",
                                  "landed_abandoned"])
def test_the_lane_writes_each_live_path_code_the_fence_knows(code: str) -> None:
    assert code in {v for k, v in vars(ev).items() if k.startswith("R_")}
    assert code in fence.E8_LIVE_PATH_REASONS
