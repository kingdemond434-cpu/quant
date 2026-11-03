"""COST_BASIS: real fills joined to decisions by ticket; LIVE rows get a basis; report only."""
from __future__ import annotations

import sys
from pathlib import Path

DESK = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(DESK))

from research import cost_basis as cb  # noqa: E402

UNIVERSE = {"symbols": {"XAUUSD": {"tick_size": 0.01, "tick_value": 1.0}}}


def _deal(i: int, sleeve: str = "s1") -> dict:
    return {"symbol": "XAUUSD", "sleeve": sleeve, "entry_time": "2026-10-30T08:00:00+00:00",
            "entry_price": 4000.10, "sl": 3990.0, "tp": 4020.0, "pl_quote": 10.0,
            "r_multiple": 0.5, "commission": -0.2, "entry_cost_allocated": -0.2,
            "exit_fee": 0.0, "entry_order": 500 + i}


def _dec(i: int) -> dict:
    return {"outcome": "EXECUTED", "ticket": 500 + i, "price": 4000.0, "sl": 3990.0,
            "symbol": "XAUUSD", "decision_id": f"d{i}", "sleeve": "s1"}


SLEEVES = {"sleeves": [{"name": "s1", "symbol": "XAUUSD", "status": "LIVE",
                        "risk_frac": 0.01, "shadow_exp": 0.2},
                       {"name": "s2", "symbol": "EURUSD", "status": "LIVE", "shadow_exp": 0.1},
                       {"name": "s3", "symbol": "XAUUSD", "status": "RETIRED"}]}


def _build(n: int = 4, decisions: list | None = None) -> dict:
    return cb.build(ledger=[_deal(i) for i in range(n)],
                    decisions=[_dec(i) for i in range(n)] if decisions is None else decisions,
                    corpus=[], sleeves=SLEEVES, universe=UNIVERSE, surface={})


def test_match_measures_slip_and_commission() -> None:
    doc = _build()
    assert doc["n_matched"] == 4 and doc["matched_share"] == 1.0
    t = doc["real_surface"]["by_symbol"]["XAUUSD"]["terms"]
    assert abs(t["slippage_points"]["value"] - 10.0) < 1e-6
    assert abs(t["slippage_r"]["value"] - 0.1 / 10.1) < 1e-5
    assert abs(t["commission_r"]["value"] - 0.01) < 1e-6
    assert "XAUUSD|london" in doc["real_surface"]["by_symbol_session"]


def test_unmatched_and_unmeasured_is_never_zero() -> None:
    doc = _build(decisions=[])
    assert doc["n_matched"] == 0
    rows = {r["name"]: r for r in doc["live_rows"]}
    assert set(rows) == {"s1", "s2"}
    assert rows["s1"]["cost_basis"]["status"] == "UNMEASURED"
    assert rows["s1"]["cost_basis"]["drift_r"] is None
    assert rows["s1"]["sizing_view"]["delta_elogw_at_current_f"] is None
    empty = cb.build(ledger=[], decisions=[], corpus=[], sleeves=SLEEVES, universe=UNIVERSE,
                     surface={})
    assert empty["matched_share"] == "UNMEASURED"


def test_live_row_basis_and_report_only_views() -> None:
    doc = _build()
    s1 = next(r for r in doc["live_rows"] if r["name"] == "s1")
    b = s1["cost_basis"]
    assert b["source"] == "own_fills" and b["n"] == 4 and b["status"] == "MEASURED"
    net = s1["admission_view"]["cert_net_exp_r"]
    assert net is not None and net < 0.2
    assert s1["sizing_view"]["delta_elogw_at_current_f"] < 0
    s2 = next(r for r in doc["live_rows"] if r["name"] == "s2")
    assert s2["cost_basis"]["status"] == "UNMEASURED"
    assert doc["report_only"] is True
    assert any(c["function"].startswith("desks/mt5/research/promoter.py")
               for c in doc["signed_consumers"])


def test_shrinkage_toward_modelled() -> None:
    out = cb._shrink([1.0] * 10, 0.0)
    assert out["status"] == "SHRUNK" and abs(out["value"] - 0.5) < 1e-9
    assert cb._shrink([1.0], None)["status"] == "UNMEASURED"


def test_main_writes_both_reports(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(cb, "build", lambda: _build())
    out, srf = tmp_path / "COST_BASIS.json", tmp_path / "S.json"
    assert cb.main(["--once", "--out", str(out), "--surface-out", str(srf)]) == 0
    assert out.exists() and srf.exists()
