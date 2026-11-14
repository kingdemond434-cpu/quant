"""Idea 737: current vs growth-optimal limit per account, read off the prop solve's frontier."""
from __future__ import annotations

import sys
from datetime import UTC, datetime
from pathlib import Path

DESK = Path(__file__).resolve().parents[1]
for _p in (str(DESK), str(DESK / "research"), str(DESK.parents[1])):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import limit_optimality as lo  # noqa: E402

NOW = datetime(2026, 11, 14, 4, 0, tzinfo=UTC)


def _front(points):
    return [{"scale": s, "total_risk": round(0.01 * s, 4), "J_mix": j, "worst_p_fail": p}
            for s, j, p in points]


def _doc(front, phase="phase1", age_h=0.5):
    return {"generated_at": datetime.fromtimestamp(NOW.timestamp() - age_h * 3600,
                                                   tz=UTC).isoformat(),
            "account": {"phase": phase, "status": "active"}, "deployable": True,
            "phases": {phase: {"status": "OK", "total_risk": 0.01,
                               "validation": {"score": 0.30, "risk": 0.002},
                               "unconstrained": {"score": 0.5, "missed_score": 0.2},
                               "frontier": front}}}


def test_size_up_when_a_larger_scale_survives_with_higher_objective():
    f = _front([(0.5, 0.2, 0.0), (1.0, 0.30, 0.002), (1.5, 0.36, 0.004), (2.0, 0.40, 0.02)])
    r = lo.account_row("ftmo", _doc(f), NOW, 0.005, {})
    assert r["status"] == "OK"
    assert r["verdict"] == "SIZE_UP_SUPPORTED"
    assert r["growth_optimal"]["scale"] == 1.5
    assert r["delta"] == 0.06
    assert r["growth_optimal"]["p_breach"] <= 0.005


def test_at_optimum_when_bigger_breaches_the_margin():
    f = _front([(0.5, 0.2, 0.0), (1.0, 0.30, 0.004), (1.25, 0.33, 0.009)])
    r = lo.account_row("ftmo", _doc(f), NOW, 0.005, {})
    assert r["verdict"] == "AT_OPTIMUM" and r["delta"] == 0.0


def test_no_surviving_scale_is_named_not_zeroed():
    f = _front([(1.0, 0.30, 0.02), (2.0, 0.4, 0.05)])
    r = lo.account_row("ftmo", _doc(f), NOW, 0.005, {})
    assert r["verdict"].startswith("NO_SURVIVING_SCALE") and r["delta"] is None


def test_absent_artifact_and_stale_artifact():
    assert lo.account_row("e8", None, NOW, 0.005, {})["status"].startswith("UNMEASURED")
    f = _front([(1.0, 0.30, 0.0)])
    assert lo.account_row("ftmo", _doc(f, age_h=5), NOW, 0.005, {})["status"] == "STALE"


def test_funded_block_without_frontier_is_unmeasured():
    d = _doc(None, phase="funded")
    r = lo.account_row("ftmo", d, NOW, 0.005, {})
    assert r["objective"] == "elog_per_day"
    assert r["verdict"].startswith("UNMEASURED") and r["growth_optimal"] is None


def test_build_is_report_only(tmp_path, monkeypatch):
    monkeypatch.setattr(lo, "FTMO_SOLVE", tmp_path / "missing.json")
    monkeypatch.setattr(lo, "E8_SOLVE", tmp_path / "missing_e8.json")
    doc = lo.build(NOW, run_e8=False)
    assert doc["report_only"] is True and doc["consumer"] is None
    assert doc["n_measured"] == 0 and doc["status"] == "UNMEASURED"
    assert {r["account"] for r in doc["accounts"]} == {"ftmo", "e8", "fusion"}
    assert doc["accounts"][0]["firm_limits"]["daily_loss"] == 0.05
    assert doc["accounts"][1]["firm_limits"]["daily_loss"] == 0.025
