"""Real netting, the per-symbol market-hours gate, the family partial fill, the probe bound and
retired-tag resolution (principal 2026-10-06 and the #261 re-audit).

The pure halves (`netting.plan_net`, `netting.net_fill_shares`, `sessions.symbol_session`) are
tested without the gateway; the gateway halves need the MetaTrader5 package to import and run
against doubles -- never a terminal. `libs.tiers.gateway_drill` runs the same paths end to end.
"""
from __future__ import annotations

import json
import sys
from datetime import UTC, datetime
from pathlib import Path
from types import SimpleNamespace as NS

import pytest

_DESK = Path(__file__).resolve().parents[1]
for p in (str(_DESK), str(_DESK / "research")):
    if p not in sys.path:
        sys.path.insert(0, p)

from mt5desk import netting, sessions  # noqa: E402


def _leg(name: str, side: int, lots: float, dist: float = 0.5, hedge: bool = False) -> dict:
    return {"sleeve": name, "side": side, "lots": lots, "dist": dist, "hedge": hedge}


# ------------------------------------------------------------------------------- netting, pure
def test_same_side_intents_do_not_net() -> None:
    assert netting.plan_net([_leg("a", 1, 0.02), _leg("b", 1, 0.03)]) is None


def test_opposite_intents_net_to_one_order_and_every_sleeve_keeps_its_fill() -> None:
    plan = netting.plan_net([_leg("a", 1, 0.04, dist=0.55), _leg("b", -1, 0.01)])
    assert plan is not None and plan["side"] == 1 and plan["lots"] == pytest.approx(0.03)
    assert plan["anchor"] == "a" and plan["netted_lots"] == pytest.approx(0.02)
    shares = netting.net_fill_shares(plan, 0.03)
    assert shares == {"a": pytest.approx(0.04), "b": pytest.approx(-0.01)}
    assert sum(shares.values()) == pytest.approx(0.03)            # = what the venue filled


def test_intents_that_cancel_send_nothing_and_cross_in_full() -> None:
    plan = netting.plan_net([_leg("a", 1, 0.02), _leg("b", -1, 0.02)])
    assert plan["lots"] == 0.0 and plan["anchor"] is None and "cancel" in plan["why"]
    assert netting.net_fill_shares(plan, 0.0) == {"a": 0.02, "b": -0.02}


def test_a_net_under_the_minimum_lot_is_not_sent_and_its_remainder_is_cancelled() -> None:
    plan = netting.plan_net([_leg("a", 1, 0.05), _leg("b", -1, 0.045)], lot_min=0.01)
    assert plan["lots"] == 0.0 and plan["side"] == 1
    shares = netting.net_fill_shares(plan, 0.0)
    assert shares["b"] == pytest.approx(-0.045) and shares["a"] == pytest.approx(0.045)
    assert sum(shares.values()) == pytest.approx(0.0)


def test_the_net_rounds_down_never_to_nearest() -> None:
    plan = netting.plan_net([_leg("a", 1, 0.049), _leg("b", -1, 0.01)])
    assert plan["lots"] == pytest.approx(0.03)                   # 0.039 -> 0.03, never 0.04


def test_the_anchor_is_the_tightest_majority_stop_so_venue_risk_never_exceeds_charged() -> None:
    legs = [_leg("wide", 1, 0.20, dist=2.0), _leg("tight", 1, 0.05, dist=0.5),
            _leg("short", -1, 0.03, dist=1.0)]
    plan = netting.plan_net(legs)
    assert plan["anchor"] == "tight" and plan["lots"] == pytest.approx(0.22)
    charged = 0.20 * 2.0 + 0.05 * 0.5
    assert plan["lots"] * 0.5 <= charged


def test_a_partial_venue_fill_is_shared_pro_rata_and_sums_to_the_fill() -> None:
    plan = netting.plan_net([_leg("a", 1, 0.06), _leg("c", 1, 0.02), _leg("b", -1, 0.02)])
    shares = netting.net_fill_shares(plan, 0.03)                 # asked 0.06, venue gave 0.03
    assert shares["b"] == pytest.approx(-0.02)
    assert sum(shares.values()) == pytest.approx(0.03)
    assert 0 < shares["a"] <= 0.06 and 0 < shares["c"] <= 0.02


def test_a_declared_hedge_is_never_netted() -> None:
    assert netting.is_hedge({"hedge_of": "gold_asia"}) and netting.is_hedge({"role": "hedge"})
    assert netting.is_hedge({"family": "xau_hedge_overlay"})
    assert not netting.is_hedge({"family": "session_range_breakout", "name": "x"})
    assert netting.plan_net([_leg("a", 1, 0.04), _leg("h", -1, 0.04, hedge=True)]) is None


# ------------------------------------------------------------------------------ sessions, pure
class _Venue:
    def __init__(self, mode: int | None = 4, tick_time: float | None = None) -> None:
        self.mode, self.tick_time = mode, tick_time

    def symbol_info(self, symbol):
        return NS(trade_mode=self.mode) if self.mode is not None else NS()

    def symbol_info_tick(self, symbol):
        return NS(bid=1.0, ask=1.1, time=self.tick_time) if self.tick_time is not None else NS(
            bid=1.0, ask=1.1)


_NOW = datetime(2026, 10, 7, 12, 0, tzinfo=UTC)


def test_trade_mode_refuses_opening_on_the_forbidden_side_only() -> None:
    assert sessions.symbol_session(_Venue(0), "X")["open"] is False
    assert "CLOSEONLY" in sessions.symbol_session(_Venue(3), "X")["why"]
    assert sessions.symbol_session(_Venue(1), "X", side=1)["open"] is True
    assert sessions.symbol_session(_Venue(1), "X", side=-1)["open"] is False
    assert sessions.symbol_session(_Venue(2), "X", side=-1)["open"] is True
    assert sessions.symbol_session(_Venue(2), "X", side=1)["open"] is False
    # a two-sided bracket cannot be opened under a one-sided mode
    assert sessions.symbol_session(_Venue(1), "X", side=None)["open"] is False
    assert sessions.symbol_session(_Venue(4), "X", side=None)["open"] is True


def test_a_stale_quote_is_a_closed_session_and_the_broker_offset_is_applied() -> None:
    fresh = _NOW.timestamp() - 60
    stale = _NOW.timestamp() - 3 * 3600
    assert sessions.symbol_session(_Venue(4, fresh), "X", now_utc=_NOW)["open"] is True
    closed = sessions.symbol_session(_Venue(4, stale), "X", now_utc=_NOW)
    assert closed["open"] is False and "session closed" in closed["why"]
    # A +3h server stamp of a fresh quote is fresh once the recorded offset is applied.
    server_fresh = fresh + 3 * 3600
    assert sessions.symbol_session(_Venue(4, server_fresh), "X", now_utc=_NOW,
                                   utc_offset_h=3)["open"] is True


def test_an_absent_field_is_unmeasured_and_does_not_refuse() -> None:
    got = sessions.symbol_session(_Venue(None, None), "X", now_utc=_NOW)
    assert got["open"] is True and "UNMEASURED" in got["why"]


def test_the_recorded_broker_offset_is_read_and_a_bad_one_is_zero(tmp_path: Path) -> None:
    (tmp_path / "data").mkdir()
    (tmp_path / "data" / "broker_clock.json").write_text('{"utc_offset_hours": 3}', "utf-8")
    assert sessions.recorded_utc_offset_h(tmp_path) == 3.0
    (tmp_path / "data" / "broker_clock.json").write_text("not json", "utf-8")
    assert sessions.recorded_utc_offset_h(tmp_path) == 0.0
    assert sessions.recorded_utc_offset_h(None) == 0.0


# ------------------------------------------------------------------------------- the gateway
@pytest.fixture
def gw(monkeypatch, tmp_path):
    pytest.importorskip("MetaTrader5")
    from mt5desk import gateway
    lines: list[str] = []
    monkeypatch.setattr(gateway, "log", lines.append)
    monkeypatch.setattr(gateway, "GENERIC_EXEC_ENABLED", tmp_path / "GENERIC_EXEC_ENABLED")
    monkeypatch.setattr(gateway, "NETTING_ENABLED", tmp_path / "NETTING_ENABLED")
    monkeypatch.setattr(gateway, "NEW_RISK_OK", True)
    monkeypatch.setattr(gateway, "_BOOK", netting.TheoreticalBook(persist=False))
    for name in ("_record_intent", "_record_decision", "_record_exec_outcome"):
        monkeypatch.setattr(gateway, name, lambda *a, **k: None)
    monkeypatch.setattr(gateway, "margin_ok", lambda *a, **k: True)
    gateway._test_lines = lines
    return gateway


class _Sends:
    ORDER_TYPE_BUY, ORDER_TYPE_SELL, TRADE_ACTION_DEAL = 0, 1, 1

    def __init__(self, mode: int = 4) -> None:
        self.sent: list[dict] = []
        self.mode = mode

    def symbol_info(self, symbol):
        return NS(volume_step=0.01, volume_min=0.01, volume_max=100.0, trade_mode=self.mode)

    def symbol_info_tick(self, symbol):
        return NS(bid=1.0, ask=1.0001)

    def order_send(self, req):
        self.sent.append(req)
        return NS(retcode=10009, order=1, volume=req["volume"], price=req["price"], deal=2)


def _scalp_row(name: str, side: int, per: float, price: float, stop: float) -> dict:
    plan = NS(ttl_until="2099-01-01T00:00:00+00:00", side=side, stop=stop, target=price,
              atr=0.1, entry_ref=price, bar_time="2026-10-07T10:00:00+00:00")
    return {"name": name, "symbol": "EURUSD", "exec": "scalp_market",
            "pending_order": {"ok": True, "kind": "entry", "per": per, "side": side,
                              "price": price, "stop": stop, "tp": price, "dist": abs(price - stop),
                              "plan": plan, "mode": "m", "target_atr": 2.0, "tick": None}}


def test_unarmed_netting_changes_nothing_and_says_what_it_would_net(gw, monkeypatch) -> None:
    venue = _Sends()
    monkeypatch.setattr(gw, "mt5", venue)
    gw.GENERIC_EXEC_ENABLED.write_text("", "utf-8")
    rows = [_scalp_row("a", 1, 0.04, 1.0, 0.99), _scalp_row("b", -1, 0.01, 1.0, 1.01)]
    before = [dict(r["pending_order"]) for r in rows]
    rep = gw._net_market_intents({"armed": True}, rows)
    assert venue.sent == [] and [r["pending_order"] for r in rows] == before
    assert rep["EURUSD"]["armed"] is False
    assert any("WOULD NET" in x and "NETTING_ENABLED absent" in x for x in gw._test_lines)


def test_armed_cancelling_intents_send_nothing_and_both_sleeves_are_attributed(gw,
                                                                               monkeypatch) -> None:
    venue = _Sends()
    monkeypatch.setattr(gw, "mt5", venue)
    gw.GENERIC_EXEC_ENABLED.write_text("", "utf-8")
    gw.NETTING_ENABLED.write_text("", "utf-8")
    rows = [_scalp_row("a", 1, 0.02, 1.0, 0.99), _scalp_row("b", -1, 0.02, 1.0, 1.01)]
    st: dict = {"armed": True}
    gw._net_market_intents(st, rows)
    assert venue.sent == []
    assert all(r["pending_order"]["stage"] == "netted" for r in rows)
    assert gw._BOOK.filled("EURUSD") == {"a": 0.02, "b": -0.02}
    assert gw._BOOK.account_position("EURUSD") == 0.0
    # each crossed leg keeps its time exit; neither holds a basket it has no position for
    assert st["scalp"]["a"]["open_ttl_until"] and "basket" not in st["scalp"]["a"]


def test_a_closed_session_falls_back_to_the_lanes_rather_than_netting(gw, monkeypatch) -> None:
    venue = _Sends(mode=3)
    monkeypatch.setattr(gw, "mt5", venue)
    gw.GENERIC_EXEC_ENABLED.write_text("", "utf-8")
    gw.NETTING_ENABLED.write_text("", "utf-8")
    rows = [_scalp_row("a", 1, 0.04, 1.0, 0.99), _scalp_row("b", -1, 0.01, 1.0, 1.01)]
    rep = gw._net_market_intents({"armed": True}, rows)
    assert venue.sent == [] and "CLOSEONLY" in rep["EURUSD"]["fallback"]
    assert all(r["pending_order"]["ok"] for r in rows)        # each lane refuses on its own


def test_the_session_folds_into_new_risk_gate_per_symbol(gw, monkeypatch) -> None:
    ok, why = gw.new_risk_gate(True, "armed", {"verdict": "OK"}, NS(connected=True),
                               session={"open": False, "why": "EURUSD trade_mode CLOSEONLY"})
    assert ok is False and why.startswith("session:")
    assert gw.new_risk_gate(True, "armed", {"verdict": "OK"}, NS(connected=True),
                            session={"open": True})[0] is True
    monkeypatch.setattr(gw, "mt5", _Sends(mode=3))
    assert "CLOSEONLY" in gw.symbol_risk_refusal("EURUSD", 1)
    monkeypatch.setattr(gw, "mt5", _Sends(mode=4))
    assert gw.symbol_risk_refusal("EURUSD", 1) is None


def test_family_residual_lives_one_bar_bounded_by_the_close_hour(gw) -> None:
    t = datetime(2026, 10, 7, 10, 5, tzinfo=UTC)
    assert gw.family_residual_expiry(t, 60) == "2026-10-07T11:05:00+00:00"
    late = datetime(2026, 10, 7, 19, 0, tzinfo=UTC)
    assert gw.family_residual_expiry(late, 60) == "2026-10-07T19:30:00+00:00"
    after = datetime(2026, 10, 7, 20, 0, tzinfo=UTC)
    assert gw.family_residual_expiry(after, 60) == after.isoformat()


def test_an_expired_residual_is_cancelled_where_it_rests_and_forgotten(gw, monkeypatch) -> None:
    removed: list[int] = []
    tag = gw.order_comment("fam")
    venue = NS(ORDER_TYPE_BUY=0, ORDER_TYPE_SELL=1, TRADE_ACTION_REMOVE=8,
               orders_get=lambda **kw: (NS(ticket=41, comment=tag, type=0),
                                        NS(ticket=42, comment=tag, type=4)),
               order_send=lambda req: removed.append(req["order"]) or NS(retcode=10009))
    monkeypatch.setattr(gw, "mt5", venue)
    st = {"armed": True, "generic": {"fam": {"residual": {
        "lots": 0.02, "symbol": "EURUSD", "expires": "2000-01-01T00:00:00+00:00"}}}}
    assert gw.expire_family_residuals(st) == 1
    assert removed == [41]                         # the market residual, never the stop order
    assert "residual" not in st["generic"]["fam"]
    live = {"armed": True, "generic": {"fam": {"residual": {
        "lots": 0.02, "symbol": "EURUSD", "expires": "2099-01-01T00:00:00+00:00"}}}}
    assert gw.expire_family_residuals(live) == 0 and "residual" in live["generic"]["fam"]


def test_candidates_beyond_the_probe_bound_refuse_rather_than_pass_unread(gw,
                                                                          monkeypatch) -> None:
    deals = tuple(NS(position_id=p, entry=0, volume=0.01, magic=gw.MAGIC, time_msc=p)
                  for p in range(1, 5))
    venue = NS(DEAL_ENTRY_IN=0, DEAL_ENTRY_OUT=1, DEAL_ENTRY_OUT_BY=3,
               positions_get=lambda **kw: (), history_deals_get=lambda *a, **k: deals)
    monkeypatch.setattr(gw, "mt5", venue)
    monkeypatch.setattr(gw, "BOOK_CHECK_MAX_PROBES", 2)
    rr = gw.book_order_check({})
    assert rr is not None and "beyond the 2-probe bound" in rr["why"]


def test_a_retired_sleeves_hashed_tag_resolves_to_its_ledger_key(gw, monkeypatch,
                                                                 tmp_path: Path) -> None:
    from mt5desk import decision_core as dc
    retired = "eurgbp_discovered_asia_p_8e61aa_retired_long_name"
    intents = tmp_path / "intents.jsonl"
    intents.write_text(json.dumps({"sleeve": retired, "symbol": "EURGBP"}) + "\n", "utf-8")
    for name, path in (("INTENTS", intents), ("LEDGER", tmp_path / "none.jsonl"),
                       ("RETIRED_CLOSE_QUEUE", tmp_path / "q.json"),
                       ("SLEEVES_FILE", tmp_path / "s.json"), ("BASE", tmp_path)):
        monkeypatch.setattr(gw, name, path)
    history = gw._tag_history_names()
    assert retired in history
    tag = dc.sleeve_tag(retired)
    assert "~" in tag
    # the roster alone cannot resolve it (the old defect: the stem became the ledger key) ...
    assert dc.sleeve_from_tag(tag, ["gold_asia"], "UNATTRIBUTED") != retired
    # ... the history does, by the same exact-tag rule.
    assert dc.sleeve_from_tag(tag, history, "") == retired
    src = Path(gw.__file__).read_text("utf-8")
    assert "_hist = sleeve_from_tag(comment, _history, \"\")" in src


def test_the_netting_pre_pass_runs_before_both_market_lanes() -> None:
    src = (_DESK / "mt5desk" / "gateway.py").read_text("utf-8")
    main = src[src.index("def main() -> None:"):]
    assert main.index('globals().get("_net_market_intents")') < main.index(
        "run_family_sleeves(st, sleeves, equity)")
    # nothing in the code arms it: the flag file is the principal's act
    assert "NETTING_ENABLED.write_text" not in src and "NETTING_ENABLED.touch" not in src


def test_shared_key_rows_are_walked_in_carrying_order_and_others_keep_their_seat(gw) -> None:
    rows = [{"name": "x"}, {"name": "k_v2"}, {"name": "y"}, {"name": "k_v3"}]
    joins = [("x", None), ("k_v2", "k"), ("y", "y"), ("k_v3", "k")]
    order = {"k": ["k_v3", "k_v2"], "y": ["y"]}
    walked = [r["name"] for r in gw._carrier_walk_order(rows, joins, order)]
    assert walked == ["x", "k_v3", "y", "k_v2"]


def test_a_row_carries_only_when_its_order_fires(gw) -> None:
    fam = {"exec": "family_market", "pending_order": {"ok": True, "lot": 0.02}}
    assert gw._row_fires(fam)
    assert not gw._row_fires({**fam, "pending_order": {"ok": False, "stage": "no_signal"}})
    assert not gw._row_fires({"exec": "scalp_market", "pending_order": {"ok": True, "per": 0}})
    assert gw._row_fires({"exec": None, "pending_bracket": {"ok": True}})
    assert not gw._row_fires({"exec": None, "pending_bracket": {"ok": False}})
