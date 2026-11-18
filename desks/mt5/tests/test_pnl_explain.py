"""Tier-1 K4 + P1: daily per-account P&L explain and the per-fill cost tape."""
from __future__ import annotations

import json
import sys
from datetime import UTC, datetime
from pathlib import Path

DESK = Path(__file__).resolve().parents[1]
for _p in (str(DESK), str(DESK / "research"), str(DESK.parents[1])):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import pnl_explain as pe  # noqa: E402

GW = {"server": "FusionMarkets-Live", "account_kind": "live", "account_key": "abcdef123456",
      "entry_side": 0, "entry_price": 2000.0, "fill_price": 2010.0, "volume": 0.1,
      "contract_size": 100.0, "pl_quote": 93.0, "commission": -5.0, "swap": -2.0,
      "exit_fee": 0.0, "deal": 77, "exit_time": "2026-11-17T10:00:00+00:00"}
PROP = {"server": "FTMO", "account_kind": "prop", "account_key": "ffff0000aaaa",
        "entry_side": 1, "entry_price": 2010.0, "fill_price": 2000.0, "volume": 0.2,
        "contract_size": 100.0, "pl_quote": 200.0, "pl_basis": "gross of fees",
        "commission": -6.0, "swap": 0.0, "exit_time": "2026-11-17T12:00:00+00:00"}
SLIP = {"status": "FILLED", "deal": 77, "slip_points": 50.0, "point": 0.01, "lots": 0.1,
        "quote_mid_at_decision": 1999.9, "fill_price": 2000.5, "direction": 1,
        "spread_points_at_decision": 20.0}


def test_account_label_reads_the_firm_off_the_server():
    assert pe.account_label(GW).startswith("Fusion|live|")
    assert pe.account_label(PROP).startswith("FTMO|prop|")
    assert pe.account_label({"server": "E8Markets"}).startswith("E8|")


def test_decompose_identity_and_slippage():
    c = pe.decompose(GW, SLIP)
    assert c["gross"] == 100.0 and c["net"] == 93.0
    assert c["fx_basis"] == "measured_from_trade" and abs(c["fx_rate"] - 1.0) < 1e-9
    assert abs(c["slippage"] - (-5.0)) < 1e-9          # 50 pts x 0.01 x 100 x 0.1, adverse
    assert abs(c["signal"] - 105.0) < 1e-9
    total = sum(c[x] for x in pe.COMPONENTS)
    assert abs(total - c["net"]) < 1e-9
    p = pe.decompose(PROP, None)
    assert p["gross"] == 200.0 and p["net"] == 194.0 and not p["slip_joined"]


def test_explain_splits_accounts_and_days():
    out = pe.explain([GW, PROP, {"pl_quote": None}], [SLIP])
    assert out["identity_ok"] and out["n_unpriced"] == 1
    assert len(out["accounts"]) == 2
    fus = next(v for k, v in out["accounts"].items() if k.startswith("Fusion"))
    assert fus["per_fill"]["mean_slip_points_vs_decision"] == 50.0
    assert abs(fus["per_fill"]["mean_slip_points_vs_mid"] - 60.0) < 1e-6
    assert fus["totals"]["net"] == 93.0


def test_build_unmeasured_off_box(tmp_path, monkeypatch):
    for n in ("LEDGER", "PROP_LEDGER", "CORPUS"):
        monkeypatch.setattr(pe, n, tmp_path / f"{n}.jsonl")
    doc = pe.build(datetime(2026, 11, 18, tzinfo=UTC))
    assert doc["status"] == "UNMEASURED" and doc["report_only"] and doc["consumer"] is None


def test_build_on_ledgers(tmp_path, monkeypatch):
    for n, rows in (("LEDGER", [GW]), ("PROP_LEDGER", [PROP]), ("CORPUS", [SLIP])):
        p = tmp_path / f"{n}.jsonl"
        p.write_text("\n".join(json.dumps(r) for r in rows), encoding="utf-8")
        monkeypatch.setattr(pe, n, p)
    doc = pe.build(datetime(2026, 11, 18, tzinfo=UTC))
    assert doc["status"] == "OK" and doc["n_accounts"] == 2
