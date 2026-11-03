"""TRADE ATTRIBUTION (AC7): slip and markout per live fill, five R layers, UNMEASURED never 0."""
from __future__ import annotations

import json
import sys
from datetime import UTC, datetime
from pathlib import Path

import pandas as pd

DESK = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(DESK / "research"))

import trade_attribution as ta  # noqa: E402

NOW = datetime(2026, 11, 3, 12, tzinfo=UTC)


def _world(tmp: Path, *, mfe: bool, bars: bool) -> dict[str, Path]:
    uni = tmp / "universe"
    uni.mkdir()
    (uni / "universe.json").write_text(json.dumps(
        {"XAUUSD": {"digits": 2, "median_spread_pts": 20.0}}))
    if bars:
        idx = pd.date_range("2026-11-02T10:00", periods=120, freq="1min", tz="UTC")
        pd.DataFrame({"close": [4001.0] * 120}, index=idx).to_parquet(uni / "XAUUSD_M1.parquet")
    row = {"time": "2026-11-02T12:00:00+00:00", "exit_time": "2026-11-02T12:00:00+00:00",
           "entry_time": "2026-11-02T10:00:00+00:00", "sleeve": "s1", "symbol": "XAUUSD",
           "pl_quote": -10.0, "r_multiple": -1.0, "volume": 0.02, "commission": -0.1,
           "swap": 0.0, "deal": 1, "entry_price": 4000.0, "sl": 3990.0, "tp": 4020.0,
           "risk_quote": -10.0, "entry_order": 77, "account_kind": "live"}
    if mfe:
        row.update(mfe_r=2.5, mae_r=-0.5)
    live = tmp / "live.jsonl"
    live.write_text(json.dumps(row) + "\n")
    dec = tmp / "dec.jsonl"
    dec.write_text(json.dumps({"outcome": "EXECUTED", "ticket": 77, "price": 3999.5,
                               "lot": 0.01, "decision_id": "d1",
                               "decided_at": "2026-11-02T09:59:00+00:00"}) + "\n")
    sl = tmp / "sleeves.json"
    sl.write_text(json.dumps({"sleeves": [{"name": "s1", "shadow_exp": 0.2}]}))
    return {"live": live, "decisions": dec, "sleeves": sl, "universe": uni,
            "out": tmp / "r" / "TA.json", "loss_out": tmp / "ll" / "AB.json"}


def _run(p: dict[str, Path]) -> dict:
    return ta.run(now=NOW, grid_paths=(), **p)


def test_chain_and_layers(tmp_path: Path) -> None:
    p = _world(tmp_path, mfe=True, bars=True)
    doc = _run(p)
    t = doc["trades"][0]
    assert t["entry_slip_points"] == 50.0                  # 0.5 adverse at 0.01 point
    assert t["markout_points"] == {"+1m": 100.0, "+5m": 100.0, "+60m": 100.0}
    L = t["layers"]
    assert L["signal_edge"] == 0.2
    assert L["entry_timing"] == -0.05
    assert L["execution_cost"] == round(-0.02 - 0.01, 4)
    assert L["exit_policy"] == -3.0                        # TP=2R reached, realised -1
    assert L["sizing"] == -1.0                             # 2x the decided lot
    assert isinstance(t["residual_r"], float)
    assert t["exit_vs_best_grid"] == ta.UNMEASURED
    wk = doc["weekly_by_sleeve"]["s1"]
    assert wk["n_trades"] == 1 and wk["leak_layer"] == "exit_policy"
    assert json.loads(p["loss_out"].read_text())["sleeves"]["s1"]["leak_layer"] == "exit_policy"


def test_absent_inputs_are_unmeasured_never_zero(tmp_path: Path) -> None:
    p = _world(tmp_path, mfe=False, bars=False)
    t = _run(p)["trades"][0]
    assert set(t["markout_points"].values()) == {ta.UNMEASURED}
    assert t["layers"]["exit_policy"] == ta.UNMEASURED
    assert t["residual_r"] == ta.UNMEASURED


def test_absent_ledgers(tmp_path: Path) -> None:
    doc = ta.run(now=NOW, live=tmp_path / "x.jsonl", decisions=tmp_path / "y.jsonl",
                 sleeves=tmp_path / "z.json", universe=tmp_path, out=tmp_path / "o.json",
                 loss_out=tmp_path / "l.json", grid_paths=())
    assert doc["n_trades"] == 0
    assert doc["inputs"]["live_ledger"].startswith(ta.UNMEASURED)
    assert doc["weekly_by_sleeve"] == {}


def _gateway_row(**kw: object) -> dict:
    """A closed-deal row in the shape `gateway.py` writes to the live ledger."""
    row = {"time": "2026-11-02T12:00:05+00:00", "sleeve": "s1", "symbol": "XAUUSD",
           "entry_side": 0, "entry_time": "2026-11-02T10:00:00+00:00",
           "exit_time": "2026-11-02T12:00:00+00:00", "timestamp_basis": "broker_deal_epoch",
           "side": 1, "pl_quote": -10.0, "r_multiple": -1.0, "volume": 0.02,
           "commission": -0.4, "swap": -0.6, "deal": 9001, "entry_cost_allocated": -0.4,
           "net_cost_status": "MEASURED", "exit_fee": 0.0, "fill_price": 3990.0,
           "entry_price": 4000.0, "sl": 3990.0, "tp": 4020.0, "r_unreconstructible": False,
           "order": 8801, "position_id": 77, "entry_order": 77, "entry_deal": 7701,
           "risk_quote": -10.0, "account_kind": "live"}
    row.update(kw)
    return row


def test_fees_are_signed_in_quote_like_pl_quote() -> None:
    meta = {"digits": 2, "median_spread_pts": 0.0}
    dec = {"price": 4000.0, "lot": 0.02, "decision_id": "d1"}
    t = ta.attribute(_gateway_row(), dec, meta, {}, None, None)
    # Debits arrive negative, as pl_quote's loss does: -(0.4 + 0.6) / |risk 10| = -0.1 R.
    assert t["layers"]["execution_cost"] == -0.1
    # A swap CREDIT reduces the cost, with the same sign convention as a profit.
    t2 = ta.attribute(_gateway_row(swap=0.6), dec, meta, {}, None, None)
    assert t2["layers"]["execution_cost"] == 0.02


def test_sizing_unmeasured_across_accounts() -> None:
    meta = {"digits": 2, "median_spread_pts": 0.0}
    dec = {"price": 4000.0, "lot": 0.01, "decision_id": "d1", "account_key": "fusion:1"}
    same = ta.attribute(_gateway_row(account_key="fusion:1"), dec, meta, {}, None, None)
    assert same["layers"]["sizing"] == -1.0
    other = ta.attribute(_gateway_row(account_key="ftmo:2"), dec, meta, {}, None, None)
    assert other["layers"]["sizing"] == ta.UNMEASURED
    bare = {k: v for k, v in dec.items() if k != "account_key"}
    assert ta.attribute(_gateway_row(), bare, meta, {}, None, None,
                        single_account=True)["layers"]["sizing"] == -1.0
    assert ta.attribute(_gateway_row(), bare, meta, {}, None, None,
                        single_account=False)["layers"]["sizing"] == ta.UNMEASURED
