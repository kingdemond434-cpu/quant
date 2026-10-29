"""The fence-aware planner, the fence's counterfactual bill, and their hourly wiring.

THE CASE (2026-10-29 04:24Z): E8 held or rested a gold short, the fence refused Fusion's gold_asia
buy_stop and let its sell_stop place, so Fusion carried half a bracket nobody chose.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pandas as pd

DESK = Path(__file__).resolve().parent.parent
for _p in (str(DESK), str(DESK / "research"), str(DESK.parent.parent)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from research import fence_missed_trades as fmt  # noqa: E402
from research import fence_planner as fp  # noqa: E402

DAY = "2026-10-29"
BUY = {"time": "2026-10-29T04:24:28+00:00", "sleeve": "gold_asia", "symbol": "XAUUSD",
       "side": "buy_stop", "price": 4069.31, "sl": 4035.92, "tp": 4135.69, "lot": 0.01,
       "execution": "pending_stop", "taken": False, "reason": "cross_account_opposite",
       "outcome": "VALIDATION_REJECTED"}
SELL = {"time": "2026-10-29T04:24:44+00:00", "sleeve": "gold_asia", "symbol": "XAUUSD",
        "side": "sell_stop", "price": 4036.12, "sl": 4069.51, "tp": 3969.74, "lot": 0.01,
        "execution": "pending_stop", "taken": True, "outcome": "EXECUTED", "reason": "placed"}
E8_SHORT = {"e8": {"symbols": {"XAUUSD": {"long": False, "short": True}}}}


def _plan(sleeves: list, risk: float | None = 0.006) -> dict:
    cert = {"fusion": {"gold_asia": risk}} if risk is not None else {}
    return fp.build(DAY, decisions=[BUY, SELL], e8=[], ftmo=[], cert=cert, sleeves=sleeves,
                    books=E8_SHORT)["plans"]["XAUUSD|2026-10-29"]


def test_e8_short_resting_fusion_never_ends_with_half_bracket_by_accident():
    p = _plan([{"name": "gold_asia", "edge_r": 0.3}])
    assert p["plan"]["assignment"]["fusion:gold_asia"] in ("short", "none")
    assert p["plan"]["assignment"]["fusion:gold_asia"] == "none"     # lone short unmeasured
    # no alternative ever takes the long or the whole bracket against E8's short
    for a in [p["plan"], *p["alternatives"]]:
        assert a["assignment"]["fusion:gold_asia"] in ("short", "none")
    act = {a["key"]: a for a in p["actual"]}["fusion:gold_asia"]
    assert act["actual"] == "short" and act["actual_half_bracket"]


def test_measured_short_edge_makes_short_only_the_plan():
    p = _plan([{"name": "gold_asia", "edge_r": 0.3, "edge_r_short": 0.2}])
    assert p["plan"]["assignment"]["fusion:gold_asia"] == "short"
    assert p["plan"]["delta_elogw"] > 0
    assert p["alternatives"][0]["delta_vs_plan"] < 0


def test_missing_inputs_read_unmeasured():
    doc = fp.build(DAY, decisions=[], e8=[], ftmo=[], cert={}, sleeves=[], books={})
    assert doc["verdict"] == "UNMEASURED"
    assert "CERT_BOOK_LIVE" in doc["missing_inputs"]


def test_whole_bracket_chosen_when_no_other_account_has_a_side():
    doc = fp.build(DAY, decisions=[BUY, SELL], e8=[], ftmo=[],
                   cert={"fusion": {"gold_asia": 0.006}},
                   sleeves=[{"name": "gold_asia", "edge_r": 0.3}], books={})
    assert doc["plans"]["XAUUSD|2026-10-29"]["plan"]["assignment"]["fusion:gold_asia"] == "both"


def _bars(rows: list[tuple[str, float, float, float]]) -> pd.DataFrame:
    idx = pd.DatetimeIndex([pd.Timestamp(t, tz="UTC") for t, *_ in rows])
    return pd.DataFrame({"open": [r[3] for r in rows], "high": [r[1] for r in rows],
                         "low": [r[2] for r in rows], "close": [r[3] for r in rows]}, index=idx)


def test_counterfactual_r_fill_then_target_and_never_filled(tmp_path):
    ev = fmt.events(decisions=[BUY], e8=[], ftmo=[])[0]
    bars = _bars([("2026-10-29 04:30", 4060, 4050, 4055),
                  ("2026-10-29 05:00", 4070, 4060, 4069),     # buy stop fills
                  ("2026-10-29 06:00", 4140, 4068, 4138),     # target
                  ("2026-10-29 19:30", 4100, 4090, 4095)])
    cf = fmt.counterfactual(ev, bars)
    assert cf["status"] == "MEASURED" and cf["exit"] == "tp"
    assert abs(cf["r"] - (4135.69 - 4069.31) / (4069.31 - 4035.92)) < 1e-6
    flat = _bars([("2026-10-29 05:00", 4060, 4050, 4055), ("2026-10-29 19:30", 4060, 4050, 4055)])
    assert fmt.counterfactual(ev, flat)["r"] == 0.0
    out, summ = tmp_path / "m.jsonl", tmp_path / "s.json"
    doc = fmt.run(evs=[ev], bars_for=lambda s: bars, out=out, summary=summ)
    assert doc["appended"] == 1
    assert abs(doc["sum_missed_usd"] - cf["r"] * (4069.31 - 4035.92) * 0.01 * 100) < 1e-3
    assert fmt.run(evs=[ev], bars_for=lambda s: bars, out=out, summary=summ)["appended"] == 0
    from research import missed_growth as mg
    line = mg.cross_account_fence_line(out)
    assert line["verdict"] == mg.COSTS and line["missed_usd"] > 0
    assert mg.cross_account_fence_line(tmp_path / "absent.jsonl")["verdict"] == mg.UNMEASURED


def test_short_bars_stay_pending_and_e8_rows_without_geometry_are_named():
    ev = fmt.events(decisions=[BUY], e8=[], ftmo=[])[0]
    early = _bars([("2026-10-29 05:00", 4070, 4060, 4069)])
    assert fmt.counterfactual(ev, early)["status"] == "PENDING"
    e8 = fmt.events(decisions=[], ftmo=[], e8=[{"at": "2026-10-29T04:20:00+00:00",
                                               "window": "gold_asia", "side": "buy_stop",
                                               "status": "RAIL_BLOCKED",
                                               "rail": "cross_account_opposite"}])
    assert fmt.counterfactual(e8[0], early)["status"] == "UNMEASURED_NO_GEOMETRY"


def test_legs_are_wired_hourly_and_contracted():
    src = (DESK / "research" / "hourly_cycle.py").read_text("utf-8")
    for leg in ("fence_planner", "fence_missed_trades"):
        assert f'_producer(\n        "{leg}", "research/{leg}.py")' in src
        assert (DESK / "research" / f"{leg}.py").exists()
    from research import hourly_cycle as hc
    assert {"fence_planner", "fence_missed_trades"} <= hc.CORE_LEGS
    contracts = json.loads((DESK.parent.parent / "docs" / "research" /
                            "experiment_contracts.json").read_text("utf-8"))["legs"]
    assert {"fence_planner", "fence_missed_trades"} <= set(contracts)
    mg_src = (DESK / "research" / "missed_growth.py").read_text("utf-8")
    assert '"cross_account_fence": cross_account_fence_line()' in mg_src
