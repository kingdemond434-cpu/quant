"""Executable book (ALLOC-05/06/15/17/18/23): continuous vs venue-executable heat and growth,
labelled exposures, order reservation, sessions. Report only."""
from __future__ import annotations

import json
import sys
from datetime import UTC, datetime
from pathlib import Path

import numpy as np
import pytest

_DESK = Path(__file__).resolve().parents[1]
_ROOT = _DESK.parent.parent
for _p in (str(_DESK), str(_DESK / "research"), str(_ROOT)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from libs.portfolio import executable_book as xb  # noqa: E402

xbr = pytest.importorskip("research.executable_book", reason="ships with the desk")


def _spec(name: str = "s", **kw: object) -> xb.SleeveSpec:
    base: dict = {"name": name, "symbol": "EURUSD", "side": 1.0, "stop_dist": 0.0050,
                  "tick_value": 1.0, "tick_size": 0.00001, "volume_min": 0.01,
                  "volume_step": 0.01, "contract_size": 100_000.0, "price": 1.10,
                  "asset_class": "Forex"}
    base.update(kw)
    return xb.SleeveSpec(**base)


def test_rounding_matches_the_gateway_arithmetic() -> None:
    # per-lot risk = 0.005 / 0.00001 * 1 = 500; heat 1% of 100k = 1000 -> 2.0 lots exactly
    r = xb.executable(0.01, 100_000.0, _spec())
    assert r["status"] == "EXACT" and r["lots_executable"] == pytest.approx(2.0)
    r = xb.executable(0.0123, 100_000.0, _spec())
    assert r["status"] == "STEP_RESIDUE" and r["lots_executable"] == pytest.approx(2.46)
    assert r["heat_executable"] <= 0.0123
    r = xb.executable(0.00001, 100_000.0, _spec())               # 0.002 lots < 0.01 minimum
    assert r["status"] == "BELOW_MINIMUM" and r["lots_executable"] == 0.0
    assert xb.executable(0.01, 100_000.0, _spec(stop_dist=None))["status"] == "UNPRICED"


def test_growth_gap_prices_discreteness() -> None:
    rng = np.random.default_rng(0)
    r = rng.normal(0.05, 1.0, (500, 2))
    g = xb.growth_gap(r, ["a", "b"], {"a": 0.02, "b": 0.02}, {"a": 0.02, "b": 0.0})
    assert g["status"] == "MEASURED" and g["discreteness_cost_per_day"] > 0
    same = xb.growth_gap(r, ["a", "b"], {"a": 0.02}, {"a": 0.02})
    assert same["discreteness_cost_per_day"] == pytest.approx(0.0)


def test_exposures_are_five_distinct_labels() -> None:
    rows = {"s": xb.executable(0.01, 100_000.0, _spec())}
    ex = xb.labelled_exposures(rows, {"s": _spec()}, 100_000.0, 5_000.0)
    t = ex["total"]
    assert t["stop_risk_heat"] == pytest.approx(0.01) and t["margin_usage"] == pytest.approx(0.05)
    # 2 lots x 100k x 1.10 = 220k quote; tick economics convert at 1.0/(1e-5*1e5) = 1 -> 2.2x
    assert t["notional_exposure"] == pytest.approx(2.2)
    assert ex["per_sleeve"]["s"]["equity_allocation"] == pytest.approx(1.0)
    assert set(ex["definitions"]) == {"risk_budget", "stop_risk_heat", "equity_allocation",
                                      "notional_exposure", "margin_usage"}


def test_an_oco_bracket_reserves_one_leg() -> None:
    state = {"brackets": {"gold_asia": {"lot": 0.1, "spec": {
        "buy_stop": {"price": 2010.0, "sl": 2000.0}, "sell_stop": {"price": 1990.0, "sl": 1996.0}},
        "result": {"orders": [{"side": "buy_stop", "retcode": 10009},
                              {"side": "sell_stop", "retcode": 10009}]}}}}
    orders = xb.bracket_orders(state, {"gold_asia": "XAUUSD"})
    assert len(orders) == 2
    res = xb.reserved_heat(orders, {"XAUUSD": (1.0, 0.01)}, 100_000.0)
    # worse leg: 10 price x 0.1 lot x 100 per price unit = 100 -> 0.001 of equity
    assert res["reserved_heat"] == pytest.approx(0.001) and res["n_groups"] == 1
    state["brackets"]["gold_asia"]["result"]["orders"][0]["blocked"] = True
    state["brackets"]["gold_asia"]["result"]["orders"][1]["retcode"] = None
    assert xb.bracket_orders(state, {"gold_asia": "XAUUSD"}) == []


def test_sessions_name_closed_instruments() -> None:
    from libs.research import market_constitution as mc
    specs = {"fx": _spec("fx"), "eq": _spec("eq", symbol="3M", asset_class="Equities")}
    ts = datetime(2026, 11, 11, 3, 0, tzinfo=UTC)                 # 05:00 Athens: US cash shut
    out = xb.session_states(specs, mc.venue_fusion(), ts, mc.instrument_class_of, mc.state_at)
    assert out["per_sleeve"]["fx"] == "CONTINUOUS"
    if out["per_sleeve"]["eq"] != "UNCLASSIFIED":
        assert "eq" in out["outside_session"]


def test_build_end_to_end_without_bars(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(xbr, "_bars", lambda _s: (1.10, 0.005))
    alloc = {"book": {"EURUSD_a": 0.01, "EURUSD_b": 0.00001},
             "heat": {"envelope": {"operative_ceiling": 0.30}}}
    sleeves = {"EURUSD_a": {"symbol": "EURUSD", "side": "LONG"},
               "EURUSD_b": {"symbol": "EURUSD", "side": "SHORT"}}
    reg = {"EURUSD": {"tick_value": 1.0, "tick_size": 0.00001, "volume_min": 0.01,
                      "volume_step": 0.01, "contract_size": 100000, "asset_class": "Forex"}}
    rng = np.random.default_rng(1)
    doc = xbr.build(alloc, sleeves, reg, {"equity": 100_000.0},
                    daily=(rng.normal(0, 1, (100, 2)), ["EURUSD_a", "EURUSD_b"], ""),
                    turnover={"status": "UNMEASURED"})
    assert doc["status"] == "MEASURED" and doc["n_booked"] == 2
    assert doc["status_counts"] == {"EXACT": 1, "BELOW_MINIMUM": 1}
    assert doc["heat"]["free_after_reservation"] == pytest.approx(0.29)
    assert doc["growth"]["status"] == "MEASURED"
    assert json.loads(json.dumps(doc, default=str))["netting"]["n_directional"] == 1
    assert xbr.build({}, {}, {}, {})["status"] == "UNMEASURED"


def test_the_leg_is_on_the_hourly_clock() -> None:
    src = (_DESK / "research" / "hourly_cycle.py").read_text(encoding="utf-8")
    assert '"research/executable_book.py"' in src and '"executable_book": xbk' in src
    from libs.research import layers
    assert layers.LEG_LAYER["executable_book"] == "execution"
