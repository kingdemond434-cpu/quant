"""R0071 money-path wiring -- the launch-day cluster, closed and pinned.

Four legs: (a) the capital-event reader refuses unverifiable equity instead of defaulting to
zero; (b) the executor persists venue-truth combined equity for that reader; (c) protective
stops are planned/reconciled without ever letting cancel_all near them, and the maker-pair
fill-inference filters stops out; (d) live_guard's graded outputs are consumed.
"""
from __future__ import annotations

import importlib
import json
from datetime import UTC, datetime, timedelta

import scripts.record_capital_event as rce

ex = importlib.import_module("scripts.run_cashcarry_executor")


# ---- (a) capital-event equity ladder ---------------------------------------------------------

def test_fresh_executor_persist_is_used():
    st = {"last_combined_equity": 1234.56,
          "last_combined_equity_at": datetime.now(tz=UTC).isoformat()}
    eq, src = rce._live_equity(st)
    assert eq == 1234.56
    assert "venue-truth" in src


def test_stale_persist_is_rejected_never_defaulted():
    st = {"last_combined_equity": 1234.56,
          "last_combined_equity_at": (datetime.now(tz=UTC) - timedelta(hours=7)).isoformat(),
          "start_futures_equity": 5000.0}
    eq, _src = rce._live_equity(st)
    # No venue keys in the test environment -> the ladder must land on refusal (None),
    # NEVER on the stale persist, the frozen inception, or zero.
    assert eq is None


def test_absent_state_refuses_not_zero():
    eq, _src = rce._live_equity({})
    assert eq is None


# ---- (c) protective stop plan + maker-path stop safety ---------------------------------------

def test_stop_plan_short_perp_buy_backstop_at_ruin_distance():
    pos = {"ETHUSDT": {"perp_qty": -2.0, "perp_entry": 1000.0, "spot_qty": 2.0,
                       "spot_cost": 999.0}}
    plan = ex._stop_plan(pos)
    assert plan["ETHUSDT"]["qty"] == 2.0
    assert plan["ETHUSDT"]["stop"] == 1350.0          # entry * (1 + 0.35), the ruin-line distance


def test_stop_plan_skips_unpriced_or_empty_positions():
    assert ex._stop_plan({"X": {"perp_qty": 0.0, "perp_entry": 100.0}}) == {}
    assert ex._stop_plan({"X": {"perp_qty": -1.0, "perp_entry": 0.0}}) == {}


def test_stop_matches_tolerances():
    want = {"qty": 2.0, "stop": 1350.0}
    assert ex._stop_matches({"origQty": "2.05", "stopPrice": "1360"}, want)      # inside 5%/2%
    assert not ex._stop_matches({"origQty": "3.0", "stopPrice": "1350"}, want)   # qty drift
    assert not ex._stop_matches({"origQty": "2.0", "stopPrice": "1450"}, want)   # price drift


def test_resting_quotes_filters_stop_market():
    class Mod:
        @staticmethod
        def open_orders(_sym):
            return [{"type": "LIMIT", "orderId": 1},
                    {"type": "STOP_MARKET", "orderId": 2}]
    resting = ex._resting_quotes(Mod, "ETHUSDT")
    assert [o["orderId"] for o in resting] == [1]
    # The stop never counts as a resting quote -- so a standing protective stop can no longer
    # break fill inference, force taker fallbacks, or get cancelled by quote cleanup.


def test_reconcile_places_missing_and_cancels_orphans(monkeypatch):
    calls = {"placed": [], "cancelled": []}

    class Fut:
        @staticmethod
        def has_keys():
            return True

        @staticmethod
        def open_orders(sym):
            return ([{"type": "STOP_MARKET", "orderId": 9, "origQty": "5.0",
                      "stopPrice": "1.0"}] if sym == "GONEUSDT" else [])

        @staticmethod
        def place_stop_market(sym, side, qty, stop):
            calls["placed"].append((sym, side, qty, stop))
            return {"orderId": 1}

        @staticmethod
        def cancel_order(sym, order_id):
            calls["cancelled"].append((sym, order_id))
            return {}

    monkeypatch.setattr(ex, "fut", Fut)
    pos = {"ETHUSDT": {"perp_qty": -2.0, "perp_entry": 1000.0}}
    state = {"protective_stops": {"GONEUSDT": {"qty": 5.0, "stop": 1.0}}}
    acts = ex._reconcile_protective_stops(pos, state)
    assert calls["placed"] == [("ETHUSDT", "BUY", 2.0, 1350.0)]
    assert calls["cancelled"] == [("GONEUSDT", 9)]
    assert set(state["protective_stops"]) == {"ETHUSDT"}
    assert any("ruin-line backstop" in a for a in acts)


# ---- (d) guard consumption -------------------------------------------------------------------

def test_guard_neutral_when_artifact_absent(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    ex._refresh_guard()
    assert ex._GUARD == {"size_frac": 1.0, "limit_only": False}


def test_guard_consumes_fresh_artifact(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    (tmp_path / "data").mkdir()
    (tmp_path / "data/live_guard.json").write_text(json.dumps({
        "generated": datetime.now(tz=UTC).isoformat(),
        "effective_size_fraction": 0.4,
        "canary": {"mode": "limit_only"},
    }), "utf-8")
    ex._refresh_guard()
    assert ex._GUARD["size_frac"] == 0.4
    assert ex._GUARD["limit_only"] is True


def test_guard_stale_artifact_is_neutral(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    (tmp_path / "data").mkdir()
    (tmp_path / "data/live_guard.json").write_text(json.dumps({
        "generated": (datetime.now(tz=UTC) - timedelta(hours=1)).isoformat(),
        "effective_size_fraction": 0.4,
        "canary": {"mode": "limit_only"},
    }), "utf-8")
    ex._refresh_guard()
    assert ex._GUARD == {"size_frac": 1.0, "limit_only": False}


# ---- (b) executor persists what the reader reads (source-level pin) --------------------------

def test_executor_writes_the_key_the_reader_reads():
    from pathlib import Path
    src = Path(ex.__file__).read_text("utf-8")
    assert 'state["last_combined_equity"]' in src
    assert 'state["last_combined_equity_at"]' in src
    # and the reporting site honours recorded capital events:
    assert src.count("effective_start_equity") >= 2
