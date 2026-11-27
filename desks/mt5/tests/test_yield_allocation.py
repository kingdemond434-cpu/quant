"""The yield rule (principal 2026-11-25): a floor for every region, the rest by marginal yield."""
from __future__ import annotations

import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path
from types import SimpleNamespace

DESK = Path(__file__).resolve().parents[1]
for _p in (str(DESK), str(DESK / "research"), str(DESK.parent.parent)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import deep_forest_miner as dfm  # noqa: E402
import source_registry as sr  # noqa: E402

from libs.research import country_census as cc  # noqa: E402

NOW = datetime(2026, 11, 25, 12, tzinfo=UTC)


def _c(**kw):
    c = sr._blank()
    c.update(kw)
    return c


def test_ten_refindings_of_one_edge_credit_less_than_one_uncorrelated_edge_each() -> None:
    same = _c(n_leads=100, n_certified=10, _cert_w=10.0, _cert_keys={("timing", "XAUUSD")})
    spread = _c(n_leads=100, n_certified=10, _cert_w=10.0,
                _cert_keys={(f"f{i}", "XAUUSD") for i in range(10)})
    e_same, t_same = sr.yield_terms(same, 0.01, 0.1)
    e_spread, t_spread = sr.yield_terms(spread, 0.01, 0.1)
    assert t_same["orthogonal"] == 0.1 and t_spread["orthogonal"] == 1.0
    assert e_spread > e_same


def test_a_mined_out_source_decays() -> None:
    fresh = _c(n_leads=100, n_certified=6, _cert_w=6.0, _cert_keys={(str(i), "") for i in range(6)})
    stale = _c(n_leads=100, n_certified=6, _cert_w=6 * sr._recency(
        (datetime.now(tz=UTC) - timedelta(days=120)).isoformat()),
        _cert_keys={(str(i), "") for i in range(6)})
    assert sr.yield_terms(stale, 0.01, 0.1)[0] < sr.yield_terms(fresh, 0.01, 0.1)[0]


def test_leading_indicators_carry_a_source_until_certifications_arrive() -> None:
    compiling = _c(n_leads=100, n_testable=40)
    silent = _c(n_leads=100, n_testable=0)
    e1, t1 = sr.yield_terms(compiling, 0.0, 0.2)
    assert t1["certified_weight"] == 0.0 and e1 > sr.yield_terms(silent, 0.0, 0.2)[0]


def test_exotic_certifications_are_not_yield() -> None:
    assert sr._exotic("USDTRY") and not sr._exotic("EURUSD") and not sr._exotic(None)


def test_the_budget_is_held_between_daily_recomputes_and_moves_are_capped() -> None:
    rows = {"a": {"n_certified": 1}, "b": {"n_certified": 1}}
    first, st = sr.settle({"a": 0.5, "b": 0.5}, rows, None, NOW)
    assert first == {"a": 0.5, "b": 0.5} and not st["held"]
    held, st2 = sr.settle({"a": 0.9, "b": 0.1}, rows, st, NOW + timedelta(hours=3))
    assert held == {"a": 0.5, "b": 0.5} and st2["held"]
    moved, st3 = sr.settle({"a": 0.99, "b": 0.01}, rows, st, NOW + timedelta(hours=25))
    assert st3["why"].startswith("DAILY") and moved["b"] >= 0.25 * 0.99 / 1.0 - 1e-6
    assert moved["a"] < 0.99


def test_a_certification_burst_rebalances_out_of_turn() -> None:
    rows = {"a": {"n_certified": 1}, "b": {"n_certified": 1}}
    _, st = sr.settle({"a": 0.5, "b": 0.5}, rows, None, NOW)
    rows["b"]["n_certified"] = 1 + sr.BURST_CERTS
    _, st2 = sr.settle({"a": 0.3, "b": 0.7}, rows, st, NOW + timedelta(hours=2))
    assert st2["why"].startswith("EVENT") and not st2["held"]


def test_exploration_is_never_below_the_relayed_band() -> None:
    assert sr.EXPLORATION_SHARE >= 0.15


def test_an_unimportable_exotic_classifier_is_published_unmeasured(monkeypatch) -> None:
    import builtins
    real = builtins.__import__

    def boom(name, *a, **k):
        if name == "research" or name.startswith("research."):
            raise ImportError("no research package")
        return real(name, *a, **k)

    monkeypatch.setattr(sr, "_EXOTIC_UNMEASURED", [])
    monkeypatch.setattr(builtins, "__import__", boom)
    assert sr._exotic("USDTRY") is False
    monkeypatch.setattr(builtins, "__import__", real)
    _, terms = sr.yield_terms(_c(n_leads=30), 0.0, 0.0)
    assert str(terms["exotic_certified_excluded"]).startswith("UNMEASURED")


def test_an_unreached_region_is_scheduled_before_a_reached_one() -> None:
    recent = (datetime.now(tz=UTC) - timedelta(hours=1)).isoformat()
    state = SimpleNamespace(vectors={"cn1": SimpleNamespace(last_attempt=recent, outcome="EMPTY")})
    grounds = [{"name": "cn1", "region": "cn", "weight": 9.0, "route": "http"},
               {"name": "cn2", "region": "cn", "weight": 9.0, "route": "http"},
               {"name": "vn1", "region": "vn", "weight": 0.1, "route": "http"}]
    reached = dfm._regions_reached(grounds, state, datetime.now(tz=UTC))
    assert reached == frozenset({"cn"})


def test_the_census_names_countries_below_the_daily_floor() -> None:
    old = (datetime.now(tz=UTC) - timedelta(hours=40)).isoformat()
    new = (datetime.now(tz=UTC) - timedelta(hours=2)).isoformat()
    grounds = {"grounds": [{"region": "cn", "name": "a", "kind": "macro"},
                           {"region": "vn", "name": "b", "kind": "macro"}]}
    out = cc.census({"countries": [{"alpha2": "CN"}, {"alpha2": "VN"}]}, grounds,
                    {"vectors": {"a": {"outcome": "EMPTY", "last_attempt": new},
                                 "b": {"outcome": "EMPTY", "last_attempt": old}}})
    assert out["floor_breach_list"] == ["VN"] and out["floor_breaches"] == 1
    assert cc.census({"countries": []}, grounds, None)["floor_breaches"] is None


def test_yield_allocation_is_a_view_of_the_same_pass_and_says_what_is_declared() -> None:
    reg = {"sources": {"a": {"share": 0.6, "kind": "paper", "n_certified": 3, "n_leads": 40,
                             "yield_terms": {"lam": 0.6}, "cost": 2.0},
                       "b": {"share": 0.4, "kind": "forest"},
                       "c": {"share": 0.0, "kind": "forest"}}}
    rep = {"at": "t", "exploration_floor": 0.2, "roi_regime": "PRIOR_AND_PRICE",
           "cadence": {"held": True}, "rule": "r"}
    out = sr.yield_allocation(reg, rep)
    assert out["n_sources"] == 3 and out["n_funded"] == 2
    assert out["sum_of_shares"] == 1.0 and out["exploration_share"] == 0.2
    assert list(out["sources"]) == ["a", "b"]
    assert "DECLARED" in out["cost_basis"] and "UNMEASURED" in out["cost_basis"]
