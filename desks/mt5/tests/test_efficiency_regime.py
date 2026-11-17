"""Idea #8: the judge's zero-pass zones as a regime feature and a stand-down proposal."""
from __future__ import annotations

import json
import sys
from datetime import UTC, datetime
from pathlib import Path

DESK = Path(__file__).resolve().parents[1]
for _p in (str(DESK), str(DESK / "research"), str(DESK.parents[1])):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import efficiency_regime as er  # noqa: E402


def test_parse_cell_and_sleeve_zone():
    assert er.parse_cell("XTIUSD.cross_asset_residual.asia@M15") == (
        "XTIUSD", "cross_asset_residual", "asia")
    assert er.parse_cell("ZARJPY.ensemble.p=18a3") == ("ZARJPY", "ensemble", "ANY")
    assert er.parse_cell("") is None
    assert er.sleeve_zone("XAUUSD.asia#rr=2.5") == ("XAUUSD", "asia")
    assert er.sleeve_zone("gold_london_am", "XAUUSD") == ("XAUUSD", "london_am")


def _verdicts():
    v = {}
    for i in range(400):                    # USDSGD.asia: judged a lot, nothing passes -> DEAD
        v[f"USDSGD.f{i % 7}.asia@H1#{i}"] = False
    for i in range(400):                    # XAUUSD.asia: 10% pass
        v[f"XAUUSD.f{i % 7}.asia@H1#{i}"] = i % 10 == 0
    for i in range(5):                      # EURNOK.ny: too few cells to call
        v[f"EURNOK.f.ny@H1#{i}"] = False
    return v


def test_dead_needs_enough_cells_at_the_base_rate():
    z = er.zones(_verdicts())
    assert z["base_rate"] > 0
    ss = z["grains"]["symbol_session"]
    assert "USDSGD.asia" in ss["dead"]
    assert "XAUUSD.asia" not in ss["dead"]
    assert "EURNOK.ny" not in ss["dead"]
    states = {r["zone"]: r["state"] for r in ss["top"]}
    assert states["EURNOK.ny"] == "UNMEASURED"
    assert z["feature"]["XAUUSD.asia"] > z["feature"]["USDSGD.asia"]


def test_elog_test_with_and_without():
    z = er.zones(_verdicts())
    trades = [{"sleeve": "USDSGD.x.asia", "symbol": "USDSGD", "r_multiple": -1.0,
               "entry_time": "2026-11-10T01:00:00", "risk_frac": 0.01},
              {"sleeve": "XAUUSD.asia", "symbol": "XAUUSD", "r_multiple": 1.0,
               "entry_time": "2026-11-10T01:00:00", "risk_frac": 0.01}]
    t = er.elog_test(z, trades)
    assert t["status"] == "MEASURED" and t["n_removed"] == 1
    assert t["verdict"] == "FILTER_HELPS" and t["delta"] > 0
    assert er.elog_test(z, [])["status"] == "UNMEASURED"


def test_build_is_report_only_and_unmeasured_off_box(tmp_path, monkeypatch):
    monkeypatch.setattr(er, "LEDGER", tmp_path / "absent.jsonl")
    doc = er.build(datetime(2026, 11, 17, tzinfo=UTC))
    assert doc["report_only"] is True and doc["consumer"] is None
    assert doc["status"] == "UNMEASURED" and doc["n_dead_zones"] == 0


def test_build_on_a_ledger(tmp_path, monkeypatch):
    led = tmp_path / "gv.jsonl"
    led.write_text("\n".join(json.dumps({"cell": c, "passed": p})
                             for c, p in _verdicts().items()), encoding="utf-8")
    sh = tmp_path / "shadow"
    sh.mkdir()
    (sh / "shadow_state.json").write_text(json.dumps(
        {"USDSGD.ogd.asia": {"n": 9, "cum_r": -2.0, "exp_r": -0.2},
         "XAUUSD.asia": {"n": 30, "cum_r": 5.0, "exp_r": 0.17}}), encoding="utf-8")
    monkeypatch.setattr(er, "LEDGER", led)
    monkeypatch.setattr(er, "SHADOW_DIR", sh)
    monkeypatch.setattr(er, "LIVE_LEDGER", tmp_path / "none.jsonl")
    doc = er.build(datetime(2026, 11, 17, tzinfo=UTC))
    assert doc["status"] == "OK" and doc["n_dead_zones"] >= 1
    assert [p["sleeve"] for p in doc["proposal"]] == ["USDSGD.ogd.asia"]
    assert doc["test"]["status"] == "UNMEASURED"
