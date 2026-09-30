"""Tier-1 audit #17: the live/backtest calibration posterior per producer, closed into research
credit (bandit) and never into capital."""
from __future__ import annotations

import json
import sys
from pathlib import Path

DESK = Path(__file__).resolve().parents[1]
ROOT = DESK.parents[1]
for p in (str(DESK / "research"), str(DESK), str(ROOT)):
    if p not in sys.path:
        sys.path.insert(0, p)

import live_calibration_posterior as lcp  # noqa: E402

from libs.research import bandit  # noqa: E402


def test_no_evidence_is_the_prior_and_moves_nothing():
    k = lcp.posterior_kappa([])
    assert k["kappa_mean"] == 1.0 and k["credit_factor"] == 1.0 and k["verdict"] == "NO_EVIDENCE"


def test_overstating_producer_is_downweighted_and_understating_one_upweighted():
    over = lcp.posterior_kappa([{"expected": 0.4, "realised": 0.05, "n_days": 200}] * 3)
    under = lcp.posterior_kappa([{"expected": 0.1, "realised": 0.2, "n_days": 300}] * 3)
    assert over["verdict"] == "OVERSTATES" and over["credit_factor"] < 1.0
    assert under["verdict"] == "UNDERSTATES" and under["credit_factor"] > 1.0
    assert lcp.CREDIT_CLIP[0] <= over["credit_factor"] <= lcp.CREDIT_CLIP[1]


def test_thin_evidence_barely_moves_the_posterior():
    thin = lcp.posterior_kappa([{"expected": 0.4, "realised": 0.0, "n_days": 2}])
    assert thin["kappa_mean"] > 0.8 and thin["verdict"] != "OVERSTATES"


def test_clocks_of_one_certificate_are_not_counted_as_independent_evidence():
    rows = [{"certificate": "c1", "expected": 0.3, "realised": 0.1, "n_days": 50,
             "basis": "forward"}] * 5
    merged = lcp.per_certificate(rows)
    assert len(merged) == 1 and merged[0]["n_days"] == 50 and merged[0]["n_clocks"] == 5


def test_claimed_sharpe_prefers_the_most_out_of_sample_reading():
    gates = {"in_sample_screen": {"sharpe": 0.9}, "walk_forward": {"oos_sharpe": 0.3}}
    assert lcp.claimed_sharpe(gates) == (0.3, "walk_forward.oos_sharpe")
    assert lcp.claimed_sharpe({})[0] is None


def test_capital_side_is_off():
    assert lcp.CAPITAL_SIDE_FEEDS_LIVE is False
    for rel in ("desks/mt5/mt5desk/gateway.py", "desks/mt5/mt5desk/decision_core.py",
                "desks/mt5/research/pf_allocator.py"):
        assert "LIVE_CALIBRATION_POSTERIOR" not in (ROOT / rel).read_text("utf-8"), rel


def test_bandit_reads_the_calibration_factor_and_multiplies_it_into_worth(monkeypatch, tmp_path):
    monkeypatch.setattr(bandit, "DESK", tmp_path)
    (tmp_path / "reports").mkdir()
    assert bandit.calibration_credit()["applied"] is False
    arm = sorted(bandit.ARMS)[0]
    doc = {"at": "2026-09-29T00:00:00+00:00", "pooled": {"kappa_mean": 0.8},
           "credit": {"by_arm": {arm: 0.6, "not_an_arm": 5.0}}}
    (tmp_path / "reports" / "LIVE_CALIBRATION_POSTERIOR.json").write_text(json.dumps(doc),
                                                                           "utf-8")
    cc = bandit.calibration_credit()
    assert cc["applied"] is True and cc["by_arm"] == {arm: 0.6}
    ev = bandit.evidence([], credit={arm: 0.6})
    assert abs(ev[arm]["worth"] - 0.6) < 1e-9


def test_build_publishes_producer_posteriors_from_forward_clocks(monkeypatch, tmp_path):
    import credit_assignment as ca
    surv = {"survivors": {"h.EURUSD cell": {
        "sym": "EURUSD", "hunt": "h", "gates": {"walk_forward": {"oos_sharpe": 0.4}},
        "shadow_spec": {"symbol": "EURUSD", "family": "f", "selector": "asia"}}}}
    (tmp_path / "surv.json").write_text(json.dumps(surv), "utf-8")
    (tmp_path / "docket.json").write_text(json.dumps([{"symbol": "EURUSD", "family": "f",
                                                        "source": "kimi"}]), "utf-8")
    clocks = {"EURUSD.asia": {"n": 40, "exp_r": 0.01, "forward_t": 0.1, "days_active": 60,
                              "max_dd_r": -3.0, "status": "ACTIVE"}}
    (tmp_path / "shadow.json").write_text(json.dumps(clocks), "utf-8")
    monkeypatch.setattr(ca, "SURVIVORS", tmp_path / "surv.json")
    monkeypatch.setattr(ca, "DOCKET", tmp_path / "docket.json")
    monkeypatch.setattr(ca, "SLEEVES", tmp_path / "none.json")
    monkeypatch.setattr(lcp, "SHADOW", (tmp_path / "shadow.json",))
    for name in ("LEDGER", "INTENTS", "SLEEVES", "ALLOCATION", "WORLDS"):
        monkeypatch.setattr(lcp, name, tmp_path / f"none_{name}")
    doc = lcp.build()
    assert doc["status"] == "MEASURED"
    assert "kimi" in doc["by_producer"]
    row = doc["sleeves"][0]
    assert row["basis"] == "forward" and row["expected"] == 0.4 and "drawdown" in row
    assert doc["capital_side"]["feeds_live"] is False
