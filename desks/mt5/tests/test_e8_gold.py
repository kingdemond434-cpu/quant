"""The gold windows on the prop account (2026-09-16): the pure decisions, without a venue."""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

_DESK = Path(__file__).resolve().parents[1]
for p in (str(_DESK), str(_DESK.parent.parent)):
    if p not in sys.path:
        sys.path.insert(0, p)

from mt5desk.decision_core import BRACKET_TTL_HOURS, CANCEL_HOUR, CLOSE_HOUR  # noqa: E402
from prop import e8_gold as g  # noqa: E402


def _bars(hours: int = 120) -> pd.DataFrame:
    """Hourly bars ending at 12:00 server on the last day, a 4300-4340 range that morning."""
    end = pd.Timestamp("2026-09-16 12:00", tz="UTC")
    idx = pd.date_range(end=end, periods=hours, freq="h")
    rng = np.random.default_rng(1)
    close = 4320.0 + np.cumsum(rng.normal(0, 3.0, hours))
    df = pd.DataFrame({"open": close, "high": close + 6.0, "low": close - 6.0, "close": close},
                      index=idx)
    day = df.index.date == end.date()
    df.loc[day, "high"] = np.minimum(df.loc[day, "high"], 4340.0)
    df.loc[day, "low"] = np.maximum(df.loc[day, "low"], 4300.0)
    return df


def test_failed_connection_replaces_stale_ok_report_but_keeps_window_state(tmp_path, monkeypatch):
    import json

    out = tmp_path / "E8_GOLD.json"
    state = tmp_path / "state.json"
    out.write_text('{"status":"OK"}', "utf-8")
    state.write_text('{"windows":{"asia":{"position_id":123}}}', "utf-8")
    before = state.read_bytes()
    monkeypatch.setattr(g, "OUT", out)
    monkeypatch.setattr(g, "STATE", state)
    g._failed_pass("MT5_UNAVAILABLE", armed=True)
    assert json.loads(out.read_text("utf-8"))["status"] == "MT5_UNAVAILABLE"
    assert state.read_bytes() == before


def test_main_uses_configured_terminal_and_never_runs_on_failed_attach(tmp_path, monkeypatch):
    from types import SimpleNamespace

    from mt5desk import config

    from research import mt5_session

    calls = []
    fake = SimpleNamespace(last_error=lambda: (-10005, "timeout"))
    monkeypatch.setitem(sys.modules, "MetaTrader5", fake)
    monkeypatch.setattr(config, "terminal_path", lambda: "canonical/terminal64.exe")
    monkeypatch.setattr(mt5_session, "attach_or_initialize",
                        lambda api, **kw: calls.append((api, kw)) or False)
    monkeypatch.setattr(g, "OUT", tmp_path / "report.json")
    monkeypatch.setattr(g, "LOG", tmp_path / "log")
    monkeypatch.setattr(g, "ARMED_MARKER", tmp_path / "unarmed")
    monkeypatch.setattr(g.time, "sleep", lambda _s: None)
    assert g.main([]) == 1
    # Every reconnect attempt uses the configured terminal; none of them reaches `run`.
    assert calls == [(fake, {"path": "canonical/terminal64.exe", "timeout": 15000})] * len(
        g.MT5_RETRY_WAITS_S)


def test_a_window_is_planned_once_at_or_after_its_signal_hour_before_the_cancel_hour() -> None:
    df = _bars()
    # 07:30 server: the Asia window (signal hour 7, range 00-07) is due; london_am (13) is not.
    due = g.plan(df, 7.5, {"windows": {}})
    assert [d["window"] for d in due] == ["asia"]
    spec = due[0]["spec"]
    assert spec["buy_stop"]["price"] == due[0]["hi"] and spec["sell_stop"]["price"] == due[0]["lo"]
    assert spec["buy_stop"]["sl"] < spec["buy_stop"]["price"] < spec["buy_stop"]["tp"]
    assert spec["sell_stop"]["tp"] < spec["sell_stop"]["price"] < spec["sell_stop"]["sl"]
    # Already placed today: not again.
    assert g.plan(df, 7.5, {"windows": {"asia": {}}}) == []
    # Past the cancel hour: nothing is placed.
    assert g.plan(df, CANCEL_HOUR + 0.1, {"windows": {}}) == []
    # Before the signal hour: nothing.
    assert g.plan(df, 6.9, {"windows": {}}) == []


def test_a_resting_leg_must_sit_on_the_right_side_of_the_quote() -> None:
    assert g.leg_is_legal("buy_stop", 4341.0, 4338.0, 4338.5)[0]
    assert not g.leg_is_legal("buy_stop", 4338.5, 4338.0, 4338.5)[0]
    assert g.leg_is_legal("sell_stop", 4300.0, 4338.0, 4338.5)[0]
    assert not g.leg_is_legal("sell_stop", 4338.0, 4338.0, 4338.5)[0]


def _state(placed_hour: float = 7.1, position_id: int | None = None) -> dict:
    return {"date": "2026-09-16", "windows": {"asia": {
        "placed_hour": placed_hour, "position_id": position_id,
        "orders": {"buy_stop": {"id": 11, "price": 4340.0},
                   "sell_stop": {"id": 12, "price": 4300.0}}}}}


def test_one_fill_cancels_the_other_leg_and_the_position_is_recorded() -> None:
    acts = g.manage_actions(_state(), 8.0, open_ids={12}, filled={11: 900}, position_ids={900})
    assert [a["act"] for a in acts] == ["record_position", "oco_cancel"]
    assert acts[0]["position_id"] == 900 and acts[1]["order_id"] == 12


def test_an_unfilled_pair_is_cancelled_after_the_ttl_and_at_the_end_of_day() -> None:
    both = {11, 12}
    # Asia's session ends at 13:00 server (london_am's signal hour), before the flat TTL.
    assert g.manage_actions(_state(7.1), 12.9, both, {}, set()) == []
    acts = g.manage_actions(_state(7.1), 13.0, both, {}, set())
    assert sorted(a["order_id"] for a in acts) == [11, 12]
    assert {a["act"] for a in acts} == {"ttl_cancel"}
    # A window the table does not know still falls back to the flat TTL.
    odd = {"windows": {"odd": _state(7.1)["windows"]["asia"]}}
    assert g.manage_actions(odd, 7.1 + BRACKET_TTL_HOURS - 0.1, both, {}, set()) == []
    acts = g.manage_actions(odd, 7.1 + BRACKET_TTL_HOURS, both, {}, set())
    assert sorted(a["order_id"] for a in acts) == [11, 12]
    assert {a["act"] for a in acts} == {"ttl_cancel"}
    acts = g.manage_actions(_state(CANCEL_HOUR - 1.0), CANCEL_HOUR, both, {}, set())
    assert {a["act"] for a in acts} == {"eod_cancel"}


def test_the_position_is_closed_at_the_close_hour_and_only_while_it_exists() -> None:
    acts = g.manage_actions(_state(7.1, position_id=900), CLOSE_HOUR, set(), {}, {900})
    assert [a["act"] for a in acts] == ["close"] and acts[0]["position_id"] == 900
    # Already gone at the venue (stop or target hit): nothing to close.
    assert g.manage_actions(_state(7.1, position_id=900), CLOSE_HOUR, set(), {}, set()) == []
    # Before the close hour a live position is left to its stop and target.
    assert g.manage_actions(_state(7.1, position_id=900), CLOSE_HOUR - 0.5, set(), {}, {900}) == []


def test_only_this_instrument_s_open_positions_block_another_gold_window() -> None:
    rows = [{"id": 1, "tradableInstrumentId": 6102, "side": "buy"},
            {"id": 2, "tradableInstrumentId": 99, "side": "sell"}]
    assert g.gold_positions(rows, 6102) == [rows[0]]
    assert g.gold_positions(rows, 7) == []


def test_e8_uses_the_same_profit_ratchet_as_the_fusion_gold_book() -> None:
    idx = pd.date_range("2026-09-16", periods=100, freq="h", tz="UTC")
    close = np.full(len(idx), 100.0)
    bars = pd.DataFrame({"open": close, "high": close + 1.0, "low": close - 1.0,
                         "close": close}, index=idx)
    # A profitable move after entry with a small live ATR must lift this stop; using openDate in
    # the broker clock is what selects the post-entry bars without a UTC conversion mismatch.
    bars.loc[idx[-4]:, "high"] = [106.0, 108.0, 110.0, 110.0]
    pos = {"id": 9, "side": "buy", "avgPrice": 100.0,
           "openDate": int(idx[-4].timestamp() * 1000)}
    window = {"orders": {"buy_stop": {"price": 100.0, "sl": 90.0}}}
    decision = g.trail_decision(pos, window, bars, current_stop=90.0)
    assert decision is not None and decision.moves
    assert decision.new_stop > 90.0 and decision.protected_r_after > decision.protected_r_before


def test_e8_gold_ratchet_accounts_for_its_own_round_trip_cost() -> None:
    idx = pd.date_range("2026-09-16", periods=100, freq="h", tz="UTC")
    close = np.full(len(idx), 100.0)
    bars = pd.DataFrame({"open": close, "high": close + 5.0, "low": close - 5.0,
                         "close": close}, index=idx)
    bars.loc[idx[-4]:, "high"] = [107.0, 108.0, 109.0, 109.0]
    pos = {"id": 9, "side": "buy", "avgPrice": 100.0,
           "openDate": int(idx[-4].timestamp() * 1000)}
    window = {"orders": {"buy_stop": {"price": 100.0, "sl": 90.0}}}
    free = g.trail_decision(pos, window, bars, current_stop=90.0)
    costed = g.trail_decision(
        pos, window, bars, current_stop=90.0, cost_per_unit=0.5, spread=0.2)
    assert free is not None and costed is not None
    assert costed.new_stop > free.new_stop
    assert costed.breakeven_floor


def test_terminal_dependent_e8_tasks_run_in_the_interactive_desktop() -> None:
    installer = (_DESK / "scripts" / "install_e8_tasks.ps1").read_text("utf-8")
    assert '[switch] $RequiresDesktop' in installer
    assert 'New-ScheduledTaskPrincipal -UserId $InteractiveUser -LogonType Interactive' in installer
    gold = installer[installer.index('Set-E8Task -Name "E8-Gold"'):]
    gold = gold[:gold.index('Set-E8Task -Name "E8-Spreads"')]
    assert "-RequiresDesktop" in gold
    spreads = installer[installer.index('Set-E8Task -Name "E8-Spreads"'):]
    assert "-RequiresDesktop" in spreads


def test_a_late_pass_never_places_a_window_whose_session_has_ended() -> None:
    """2026-09-21/23/24 on E8: windows placed hours late off stale ranges (-950 USD in one
    second on 09-24). Due inside its session, refused once the next window's hour arrives."""
    df = _bars()
    assert [d["window"] for d in g.plan(df, 12.9, {"windows": {}})] == ["asia"]
    assert "asia" not in [d["window"] for d in g.plan(df, 13.0, {"windows": {}})]
    # 20:29 server, the 09-21 catch-up pass: nothing at all.
    assert g.plan(df, 20.49, {"windows": {}}) == []


def test_a_london_am_leg_dies_when_the_afternoon_session_opens() -> None:
    """The 09-24 overlap: london_am's resting leg must be gone before afternoon places."""
    st = {"windows": {"london_am": {"placed_hour": 13.1, "position_id": None,
                                    "orders": {"sell_stop": {"id": 21, "price": 4250.93}}}}}
    assert g.manage_actions(st, 16.9, {21}, {}, set()) == []
    acts = g.manage_actions(st, 17.0, {21}, {}, set())
    assert [(a["act"], a["order_id"]) for a in acts] == [("ttl_cancel", 21)]
