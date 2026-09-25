"""The Tier-1 closed-loop B rows (B1-B13), each pinned where its own claim could rot.

One test per property the row's gap named. These are PROPERTY tests over pure functions and
monkeypatched paths: nothing here reads the box's real artifacts, writes a tracked file or runs
a gauntlet, so the suite's verdict is about the code and not about what happened to be on disk.
"""
from __future__ import annotations

import json
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path

import numpy as np
import pytest

ROOT = Path(__file__).resolve().parents[3]
DESK = ROOT / "desks" / "mt5"
for _p in (str(ROOT), str(DESK), str(DESK / "research")):
    if _p not in sys.path:
        sys.path.insert(0, _p)


# --------------------------------------------------------------------------------- B2: PIT
def test_lake_pit_withholds_a_future_series_and_keeps_the_unstamped(tmp_path: Path) -> None:
    from libs.data.lake_pit import usable_series
    now = datetime(2026, 9, 23, tzinfo=UTC)
    series = tmp_path / "series"
    series.mkdir()
    for sid, avail in (("future_src", now + timedelta(days=30)),
                       ("past_src", now - timedelta(days=1))):
        (series / f"{sid}.json").write_text("{}", encoding="utf-8")
        (series / f"{sid}.pit.json").write_text(
            json.dumps({"available_time": avail.isoformat()}), encoding="utf-8")
    (series / "unstamped_src.json").write_text("{}", encoding="utf-8")

    view = usable_series(series, now)
    assert "future_src" not in view.visible, "a row available in 30 days was readable today"
    assert "past_src" in view.visible
    # Withholding the unstamped would shrink the desk's data on the strength of a missing file.
    assert "unstamped_src" in view.visible
    assert "unstamped_src" in view.unstamped
    assert view.census()["n_withheld"] == 1


def test_lake_pit_row_level_join() -> None:
    from libs.data.lake_pit import rows_as_of
    now = datetime(2026, 9, 23, tzinfo=UTC)
    rows = [{"available_time": (now - timedelta(days=1)).isoformat(), "v": 1},
            {"available_time": (now + timedelta(days=1)).isoformat(), "v": 2},
            {"v": 3}]
    kept, withheld = rows_as_of(rows, now)
    assert withheld == 1
    assert [r["v"] for r in kept] == [1, 3]


# ------------------------------------------------------------------- B1: the one bit
def _write(p: Path, doc: dict) -> None:
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(doc), encoding="utf-8")


def test_release_authority_is_false_unless_all_three_clauses_hold(tmp_path: Path,
                                                                  monkeypatch) -> None:
    import release_authority as ra
    monkeypatch.setattr(ra, "ATTESTATION", tmp_path / "gate_attestation.json")
    monkeypatch.setattr(ra, "IDENTITY", tmp_path / "release_identity.json")
    monkeypatch.setattr(ra, "RELEASE", tmp_path / "RELEASE.json")
    monkeypatch.setattr(ra, "_code_hash", lambda ref: {"run": "AAA", "sealed": "AAA"}.get(ref, ""))
    _write(ra.ATTESTATION, {"result": "pass", "tested_code_hash": "AAA", "tested_sha": "run"})
    _write(ra.IDENTITY, {"running_sha": "run", "verdict": "OK"})
    _write(ra.RELEASE, {"code_sha": "sealed"})

    doc = ra.measure()
    assert doc["may_create_exposure"] is True
    assert all(c["ok"] for c in doc["clauses"].values())

    # A red gate voids the bit whatever the seal says.
    _write(ra.ATTESTATION, {"result": "fail", "tested_code_hash": "AAA", "tested_sha": "run"})
    assert ra.measure()["may_create_exposure"] is False
    # So does drift, with the identity's own verdict as the reason.
    _write(ra.ATTESTATION, {"result": "pass", "tested_code_hash": "AAA", "tested_sha": "run"})
    _write(ra.IDENTITY, {"running_sha": "run", "verdict": "REFUSED", "reason": "money path"})
    out = ra.measure()
    assert out["may_create_exposure"] is False
    assert "REFUSED" in out["clauses"]["undrifted"]["why"]


def test_gate_attestation_code_hash_ignores_state_paths() -> None:
    """The subject is the CODE tree: a state path can never change the hash."""
    import importlib
    sys.path.insert(0, str(ROOT / "scripts"))
    ga = importlib.import_module("gate_attestation")
    assert ga._is_state("desks/mt5/data/whatever.json") is True
    assert ga._is_state("desks/mt5/research/alpha_evolution.py") is False


# ------------------------------------------------------- B13: the three sameness channels
def _ev(name: str, **kw):
    from libs.portfolio.robust_elog import SleeveEvidence
    rng = np.random.default_rng(abs(hash(name)) % 2**32)
    return SleeveEvidence(name=name, daily_r=rng.normal(size=64), **kw)


def test_shared_inputs_raise_the_structural_correlation() -> None:
    from libs.portfolio.robust_elog import _structured_corr
    ev = [_ev("a", symbol="EURUSD", family="f1", inputs=("bars:EURUSD:H1",)),
          _ev("b", symbol="USDJPY", family="f2", inputs=("bars:EURUSD:H1",))]
    t, meta = _structured_corr(ev)
    assert meta["n_shared_input_pairs"] == 1
    assert t[0, 1] > 0.0, "two sleeves reading one file scored as independent"


def test_disjoint_trade_hours_relax_the_same_instrument_prior() -> None:
    """The two-sided half: measured evidence of no overlap BUYS breadth, it does not cost it."""
    from libs.portfolio.robust_elog import (
        SAME_SYMBOL_FAMILY_CORR,
        TIME_DISJOINT_FLOOR,
        _structured_corr,
    )
    blind = [_ev("a", symbol="XAUUSD", family="f"), _ev("b", symbol="XAUUSD", family="f")]
    apart = [_ev("a", symbol="XAUUSD", family="f", trade_hours=(1, 2, 3)),
             _ev("b", symbol="XAUUSD", family="f", trade_hours=(14, 15, 16))]
    t_blind, _ = _structured_corr(blind)
    t_apart, meta = _structured_corr(apart)
    assert t_blind[0, 1] == pytest.approx(SAME_SYMBOL_FAMILY_CORR)
    assert t_apart[0, 1] < t_blind[0, 1], "disjoint entry hours bought no breadth"
    assert t_apart[0, 1] >= TIME_DISJOINT_FLOOR, "one instrument's path is still shared"
    assert meta["n_time_relaxed_pairs"] == 1


def test_no_declared_channel_scores_exactly_as_before() -> None:
    from libs.portfolio.robust_elog import SAME_SYMBOL_CORR, _structured_corr, breadth_channels
    ev = [_ev("a", symbol="XAUUSD", family="f1"), _ev("b", symbol="XAUUSD", family="f2")]
    t, _ = _structured_corr(ev)
    assert t[0, 1] == pytest.approx(SAME_SYMBOL_CORR)
    census = breadth_channels(ev)
    assert census["declared"] == {"inputs": 0, "trade_hours": 0, "mechanism": 0}


# ------------------------------------------------------------- B3: the per-asset hierarchy
def test_regime_hierarchy_shrinks_toward_the_class_prior() -> None:
    import regime_hierarchy as rh
    own = [[0.9, 0.1], [0.2, 0.8]]
    pooled = [[0.5, 0.5], [0.5, 0.5]]
    few, w_few, l1 = rh._shrink(own, pooled, n_days=50)
    many, w_many, _ = rh._shrink(own, pooled, n_days=100_000)
    assert 0.0 < w_few < w_many <= 1.0, "a symbol with fewer days borrowed less from its class"
    assert abs(many[0][0] - 0.9) < 0.01, "a symbol with a long history is its own model"
    assert abs(few[0][0] - 0.9) > abs(many[0][0] - 0.9)
    assert l1 > 0.0
    for row in (*few, *many):
        assert sum(row) == pytest.approx(1.0, abs=1e-6)


# ------------------------------------------------- B4: the learned lane's stability probe
def test_temporal_stability_rejects_a_sign_flip() -> None:
    import representation_discovery as rd
    rng = np.random.default_rng(7)
    x = rng.normal(size=600)
    steady = np.concatenate([x[:300] * 1.0, x[300:] * 1.0]) + rng.normal(scale=0.2, size=600)
    flipped = np.concatenate([x[:300] * 1.0, -x[300:] * 1.0]) + rng.normal(scale=0.2, size=600)
    assert rd._stability(x, steady)["sign_agrees"] is True
    assert rd._stability(x, flipped)["sign_agrees"] is False
    assert rd._stability(x[:10], steady[:10])["status"] == "UNMEASURED"


# --------------------------------------------------------------- B5: the rest of the genome
def test_recipe_bounds_bracket_the_standing_recipe_on_both_sides() -> None:
    """A bound that only shrank would be the timid modifier the standing order forbids."""
    import alpha_evolution as ae
    for param, (lo, hi) in ae.RECIPE_BOUNDS.items():
        default = float(ae.RECIPE[param])
        assert lo < default < hi, f"{param} is not bracketed on both sides by its bounds"
    assert min(ae.RECIPE_STEPS) < 1.0 < max(ae.RECIPE_STEPS)


# ----------------------------------------------------------- B7: the scientists' standings
def test_standings_rank_on_live_growth_and_never_starve_the_unmeasured(tmp_path: Path,
                                                                      monkeypatch) -> None:
    import scientist_standings as ss
    monkeypatch.setattr(ss, "ATTRIBUTION", tmp_path / "attr.json")
    monkeypatch.setattr(ss, "CREDIT", tmp_path / "credit.json")
    _write(ss.ATTRIBUTION, {"information": {"basis": "t", "sources": {
        "earner": {"delta_elogw_per_day": 0.01}, "flat": {"delta_elogw_per_day": 0.0}}}})
    _write(ss.CREDIT, {"evidence_source": "live", "n_live_deals": 151, "by_scientist": [
        {"source": "earner", "realised_r": 12.0, "n_trades": 60},
        {"source": "newcomer", "realised_r": 0.0, "n_trades": 0}]})
    doc = ss.measure()
    ranks = {r["scientist"]: r["rank"] for r in doc["standings"]}
    assert ranks["earner"] == 1
    newcomer = next(r for r in doc["standings"] if r["scientist"] == "newcomer")
    assert newcomer["status"] == "UNMEASURED"
    assert newcomer["share"] > 0.0, "an unmeasured seat was starved of every hour"
    assert sum(r["share"] for r in doc["standings"]) == pytest.approx(1.0, abs=1e-3)


# ------------------------------------------------------------------- B8: the residual map
def test_residual_prior_floors_every_symbol(tmp_path: Path, monkeypatch) -> None:
    import residual_map as rm
    monkeypatch.setattr(rm, "ATTRIBUTION", tmp_path / "attr.json")
    for attr in ("RELIABILITY", "CONFIDENCE", "MARKOUT", "FILLS"):
        monkeypatch.setattr(rm, attr, tmp_path / f"{attr}.json")
    _write(rm.ATTRIBUTION, {"dlogw_per_day": {"value": 0.01},
                            "per_sleeve": {"sleeves": {
                                "XAUUSD_a_asia": {"value": 0.5, "n": 40},
                                "EURUSD_b_asia": {"value": 0.011, "n": 40}}}})
    doc = rm.build()
    prior = doc["prior"]["by_symbol"]
    assert prior["XAUUSD"] == pytest.approx(1.0)
    assert prior["EURUSD"] >= rm.FLOOR_W, "a well-explained symbol was dropped from the search"
    assert doc["n_residuals"] == 2


# ----------------------------------------------------------------- B10: the failure prior
def test_failure_prior_multiplier_is_two_sided_and_clipped(tmp_path: Path) -> None:
    import failure_prior as fp
    table = {"by_feature": {"family": {"reborn": {"odds_ratio": 1000.0},
                                       "dying": {"odds_ratio": 0.0001}}}}
    up, why = fp.multiplier_for({"family": "reborn", "symbol": "XAUUSD"}, table)
    down, _ = fp.multiplier_for({"family": "dying", "symbol": "XAUUSD"}, table)
    assert up == fp.MAX_MULT and down == fp.MIN_MULT
    assert "odds" in why
    # An unknown structure is never charged for being unknown.
    flat, _ = fp.multiplier_for({"family": "never_seen", "symbol": "XAUUSD"}, table)
    assert flat == 1.0


# ------------------------------------------------------------ B11: one acquisition function
def test_evig_leg_factor_is_never_a_cut(tmp_path: Path, monkeypatch) -> None:
    import evig_acquisition as ea
    monkeypatch.setattr(ea, "BANDIT", tmp_path / "bandit.json")
    monkeypatch.setattr(ea, "DOCKET", tmp_path / "docket.json")
    monkeypatch.setattr(ea, "TREE", tmp_path / "tree.json")
    monkeypatch.setattr(ea, "MAP", tmp_path / "map.json")
    _write(ea.BANDIT, {"arms": {"a": {"worth": 1.0, "p_survivor": 0.1, "cost": 1.0},
                                "b": {"worth": 0.1, "p_survivor": 0.1, "cost": 10.0}}})
    _write(ea.DOCKET, {"proposals": [{"id": "c1", "cost": "low", "rank": 1},
                                     {"id": "c2", "cost": "high", "rank": 9}]})
    _write(ea.TREE, {"frontier": [{"id": "n1", "info_gain_nats": 2.0, "posterior_value": 0.5}]})
    doc = ea.build()
    assert doc["n_families"] >= 3, "the acquisition priced fewer than three resource families"
    assert doc["leg_factor"], "no leg was priced by the frontier"
    assert all(1.0 <= f <= ea.MAX_FACTOR for f in doc["leg_factor"].values())
    # Every family is ranked inside itself, so the best of each family reaches 1.0.
    assert max(r["percentile"] for r in doc["ranked"]) == pytest.approx(1.0)


# -------------------------------------------------------------- the wiring, for all of them
def test_every_new_leg_has_a_clock_and_a_layer() -> None:
    """UNWIRED OR IDLE IS A DEFECT (LAWS III.16): a leg with no layer fails the suite already;
    this pins the other half -- that each organ is actually costed in the hourly cycle."""
    from libs.research.layers import LEG_LAYER
    src = (DESK / "research" / "hourly_cycle.py").read_text("utf-8")
    for leg in ("release_authority", "regime_hierarchy", "residual_map", "failure_prior",
                "scientist_standings", "frontier_ceo", "research_tree",
                "representation_discovery", "evig_acquisition"):
        assert f'_costed("{leg}"' in src, f"{leg} has no clock in hourly_cycle"
        assert leg in LEG_LAYER, f"{leg} joins no strategy layer"
