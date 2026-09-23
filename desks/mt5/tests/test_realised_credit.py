"""Delayed truth: realised R credited back through sleeves reaches the bandit's worth and the
generator weights, bounded, and the closed-loop flag reads the basis rather than a label."""
from __future__ import annotations

import json
import sys
from pathlib import Path

DESK = Path(__file__).resolve().parents[1]
for p in (str(DESK / "research"), str(DESK), str(DESK.parents[1])):
    if p not in sys.path:
        sys.path.insert(0, p)

import credit_assignment as ca  # noqa: E402
import mutation_yield as my  # noqa: E402

from libs.research import bandit  # noqa: E402


def test_credit_factor_is_shrunk_and_clipped():
    assert bandit._credit_factor(0.0, 0) == 1.0
    assert bandit._credit_factor(7.5, 30) == 1.25          # +0.25R/trade x 30/(30+30) x 2
    assert bandit._credit_factor(-100.0, 30) == bandit.CREDIT_CLIP[0]
    assert bandit._credit_factor(1000.0, 300) == bandit.CREDIT_CLIP[1]
    assert 0.99 < bandit._credit_factor(0.3, 1) < 1.02       # one trade moves nothing far


def test_realised_credit_maps_scientists_to_arms(monkeypatch, tmp_path):
    monkeypatch.setattr(bandit, "DESK", tmp_path)
    (tmp_path / "reports").mkdir()
    assert bandit.realised_credit()["applied"] is False
    doc = {"evidence_source": "live", "n_live_deals": 52,
           "by_scientist": [{"source": "kimi", "realised_r": 15.0, "n_trades": 30},
                            {"source": "deepseek", "realised_r": -9.0, "n_trades": 30}]}
    (tmp_path / "reports" / "CREDIT_ASSIGNMENT.json").write_text(json.dumps(doc), encoding="utf-8")
    rc = bandit.realised_credit()
    assert rc["applied"] is True and rc["basis"] == "live"
    arms = {bandit.arm_of("kimi"), bandit.arm_of("deepseek")}
    assert set(rc["by_arm"]) == arms
    for f in rc["by_arm"].values():
        assert bandit.CREDIT_CLIP[0] <= f <= bandit.CREDIT_CLIP[1]
    ev = bandit.evidence([], dict.fromkeys(bandit.ARMS, 1.0), credit=rc["by_arm"])
    for a in arms:
        assert ev[a]["worth"] == ev[a]["realised_credit"] == rc["by_arm"][a]


def test_live_deals_are_credited_through_sleeves(monkeypatch, tmp_path):
    sleeves = {"sleeves": [{"name": "gold_asia_srb", "symbol": "XAUUSD",
                            "family": "session_range_breakout", "session": "asia"}]}
    (tmp_path / "sleeves.json").write_text(json.dumps(sleeves), encoding="utf-8")
    monkeypatch.setattr(ca, "SLEEVES", tmp_path / "sleeves.json")
    certs = [{"certificate": "c1", "symbol": "XAUUSD", "family": "session_range_breakout",
              "selector": "asia", "source": "kimi", "lane": "seat"}]
    live = [{"sleeve": "gold_asia_srb", "symbol": "XAUUSD", "realised_r": 1.5},
            {"sleeve": "gold_asia_srb", "symbol": "XAUUSD", "realised_r": -1.0},
            {"sleeve": "unknown_sleeve", "symbol": "EURUSD", "realised_r": 3.0}]
    rows = ca._credit_live(live, certs)
    assert [r["realised_r"] for r in rows] == [1.5, -1.0]
    assert all(r["source"] == "kimi" and r["n"] == 1 and r["lane"] == "live" for r in rows)


def test_generator_weights_carry_realised_credit(monkeypatch, tmp_path):
    doc = {"evidence_source": "forward",
           "by_scientist": [{"source": "kimi", "realised_r": 15.0, "n_trades": 30}]}
    (tmp_path / "CREDIT_ASSIGNMENT.json").write_text(json.dumps(doc), encoding="utf-8")
    monkeypatch.setattr(my, "CREDIT", tmp_path / "CREDIT_ASSIGNMENT.json")
    rows = {"a": {"generator": "gflow", "source": "kimi"},
            "b": {"generator": "symreg", "source": "nobody"}}
    credit, why = my.realised_credit_by_generator(rows)
    assert credit == {"gflow": 1.5} and "forward" in why
