"""MODEL DECISION ROLES (model_roles.py) AND THE FORECAST CONTRACT'S PROVENANCE CLAUSES.

Each test fences one way a forecast can manufacture conviction it never had:

  - a model moving a quantity outside its declared role (a volatility model tilting a mean);
  - two contradictory models pooling to a CONFIDENT average instead of a less confident one;
  - two correlated sources counted as two independent votes;
  - one unchanged observation updating the book twice because it was re-published;
  - a stale critical input adding risk;
  - a belief trained on, or fed features from, the window it is scored over.

None of these look wrong inside the arithmetic, which is why each is a test and not a docstring.
"""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest

_ROOT = Path(__file__).resolve().parent.parent.parent
_RESEARCH = _ROOT / "desks" / "mt5" / "research"


def _load(name: str):
    spec = importlib.util.spec_from_file_location("_" + name, _RESEARCH / f"{name}.py")
    assert spec and spec.loader, f"{name}.py is missing"
    mod = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture(scope="module")
def mr():
    return _load("model_roles")


@pytest.fixture(scope="module")
def fc():
    return _load("forecast_contract")


def _est(mr, **over):
    base = {"model_id": "edge_a", "family": "bayesian_edge", "subject": "XAUUSD.asia",
            "horizon_s": 86400.0, "role": "DIRECTION_MEAN", "mean": 0.10, "variance": 0.01,
            "inputs_as_of": "2026-10-05T00:00:00+00:00"}
    return mr.Estimate(**(base | over))


# --------------------------------------------------------------------------- registry
def test_the_registry_is_self_consistent(mr) -> None:
    assert mr.registry_defects() == []


def test_every_inventoried_family_has_a_role(mr) -> None:
    for fam in ("hmm_regime", "hsmm_regime", "bayesian_edge", "garch_vol", "change_point",
                "macro_state", "alt_data", "flows", "positioning", "liquidity",
                "execution_cost", "dependence"):
        s = mr.spec(fam)
        assert s is not None and s.roles, f"{fam} has no declared decision role"
        assert s.staleness_budget_s > 0 and s.horizon_s > 0


def test_only_the_edge_model_may_direct(mr) -> None:
    """Environment models (vol, regime, cost, liquidity, crowding) size; they never sign."""
    assert mr.families_with(mr.Role.DIRECTION_MEAN) == ["bayesian_edge"]


# --------------------------------------------------------------------------- (d) roles
def test_a_volatility_model_cannot_move_a_mean(mr) -> None:
    with pytest.raises(mr.RoleViolation):
        mr.enforce_role("garch_vol", "DIRECTION_MEAN")
    mr.enforce_role("garch_vol", "VOLATILITY_SCALE")
    with pytest.raises(mr.RoleViolation):
        mr.enforce_role("not_a_family", "COST")


def test_combine_excludes_an_out_of_role_estimate_and_the_mean_does_not_move(mr) -> None:
    edge = _est(mr)
    rogue = _est(mr, model_id="garch_1", family="garch_vol", mean=5.0, variance=1e-6)
    alone = mr.combine([edge])
    both = mr.combine([edge, rogue])
    assert both.mean == pytest.approx(alone.mean)
    assert both.variance == pytest.approx(alone.variance)
    assert [m for m, _ in both.excluded] == ["garch_1"]


def test_an_out_of_role_estimate_is_refused_at_update(mr) -> None:
    with pytest.raises(mr.RoleViolation):
        mr.update(mr.BeliefState(), _est(mr, family="hmm_regime"))


# --------------------------------------------------------------------------- (a) combine
def test_disagreement_shrinks_confidence_and_widens_variance(mr) -> None:
    a = _est(mr, model_id="a", mean=0.10)
    agree = mr.combine([a, _est(mr, model_id="b", mean=0.10)])
    clash = mr.combine([a, _est(mr, model_id="b", mean=-0.30)])
    assert clash.inflation > 1.0 == agree.inflation
    assert clash.confidence < agree.confidence
    assert clash.variance > agree.variance
    # a confident contradiction must be LESS certain than either source alone
    assert clash.variance > a.variance


def test_correlated_sources_are_not_independent_votes(mr) -> None:
    a, b = _est(mr, model_id="a"), _est(mr, model_id="b")
    indep = mr.combine([a, b], measured_rho={frozenset({"a", "b"}): 0.0})
    twins = mr.combine([a, b], measured_rho={frozenset({"a", "b"}): 1.0})
    assert indep.n_effective == pytest.approx(2.0)
    assert indep.variance == pytest.approx(a.variance / 2)
    assert twins.n_effective == pytest.approx(1.0)
    assert twins.variance == pytest.approx(a.variance), "two copies of one signal are one signal"


def test_same_family_defaults_to_partial_correlation(mr) -> None:
    pooled = mr.combine([_est(mr, model_id="a"), _est(mr, model_id="b")])
    assert 1.0 < pooled.n_effective < 2.0


def test_combine_refuses_mixed_subjects_or_horizons(mr) -> None:
    with pytest.raises(ValueError):
        mr.combine([_est(mr), _est(mr, model_id="b", subject="EURUSD")])
    with pytest.raises(ValueError):
        mr.combine([_est(mr), _est(mr, model_id="b", horizon_s=3600.0)])


def test_nothing_to_pool_is_unmeasured_not_neutral(mr) -> None:
    p = mr.combine([])
    assert p.mean is None and p.variance is None and "UNMEASURED" in p.why


# --------------------------------------------------------------------------- (b) idempotence
def test_an_unchanged_observation_never_updates_twice(mr) -> None:
    s0 = mr.BeliefState()
    e = _est(mr)
    s1, applied = mr.update(s0, e)
    assert applied
    s2, again = mr.update(s1, e)
    assert not again and s2 is s1
    # re-published later is still the same observation: `at` is not in the fingerprint
    assert e.fingerprint() == mr.fingerprint(e.model_id, e.subject, e.inputs_as_of,
                                             {"role": e.role, "horizon_s": e.horizon_s,
                                              "mean": e.mean, "variance": e.variance})


def test_a_new_observation_replaces_never_accumulates(mr) -> None:
    s, _ = mr.update(mr.BeliefState(), _est(mr))
    s, applied = mr.update(s, _est(mr, mean=0.2, inputs_as_of="2026-10-06T00:00:00+00:00"))
    assert applied
    ests = s.estimates("XAUUSD.asia", 86400.0, "DIRECTION_MEAN")
    assert len(ests) == 1 and ests[0].mean == 0.2, "one model, one vote"


def test_state_round_trips_and_stays_idempotent(mr) -> None:
    e = _est(mr)
    s, _ = mr.update(mr.BeliefState(), e)
    back = mr.BeliefState.from_json(s.to_json())
    assert mr.update(back, e)[1] is False


# --------------------------------------------------------------------------- (c) staleness
NOW = "2026-10-06T12:00:00+00:00"


def test_fresh_inputs_impose_no_clamp(mr) -> None:
    c = mr.staleness_clamp({"execution_cost": "2026-10-06T00:00:00+00:00"}, NOW)
    assert c.allow_adds and c.max_heat_multiplier is None and not c.active


@pytest.mark.parametrize("as_of", ["2026-09-01T00:00:00+00:00", None, "garbage",
                                   "2026-10-07T00:00:00+00:00"])
def test_a_stale_critical_input_can_only_hold_or_reduce(mr, as_of) -> None:
    c = mr.staleness_clamp({"execution_cost": as_of}, NOW)
    assert not c.allow_adds and c.max_heat_multiplier is not None
    assert c.max_heat_multiplier <= 1.0
    held = {"a": 0.05, "b": 0.05}
    proposed = {"a": 0.09, "b": 0.02, "c": 0.04}
    out = c.apply_to_book(proposed, held)
    assert "c" not in out, "no new adds on stale critical evidence"
    assert all(out[k] <= held[k] for k in out)
    assert out["b"] == pytest.approx(0.02), "a reduction the solve chose still goes through"
    assert sum(out.values()) <= sum(held.values()) + 1e-12


def test_a_stale_noncritical_input_is_dropped_not_clamped(mr) -> None:
    c = mr.staleness_clamp({"alt_data": "2026-08-01T00:00:00+00:00"}, NOW)
    assert c.allow_adds and c.ignored_noncritical == ("alt_data",)


def test_an_unregistered_input_is_treated_as_critical(mr) -> None:
    c = mr.staleness_clamp({"mystery_feed": None}, NOW)
    assert not c.allow_adds


# --------------------------------------------------------------------------- contract provenance
AT = "2026-10-06T02:00:00+00:00"


def _belief(fc, **over):
    base = {"model_id": "edge_a", "subject": "XAUUSD.asia/ret", "kind": "MAGNITUDE",
            "value": 0.001, "horizon_s": 86400, "at": AT, "family": "bayesian_edge",
            "role": "DIRECTION_MEAN", "training_cutoff": "2026-10-05T23:00:00+00:00",
            "features": ("h1_close",),
            "feature_available_at": (("h1_close", "2026-10-06T01:00:00+00:00"),)}
    return fc.Belief(**(base | over))


def test_a_fully_stamped_belief_is_verified(fc) -> None:
    assert fc.defects(_belief(fc)) == []
    assert fc.verification(_belief(fc)) == ("VERIFIED", [])


@pytest.mark.parametrize(("over", "must_mention"), [
    ({"training_cutoff": AT}, "strictly before"),
    ({"training_cutoff": "2026-10-07T00:00:00+00:00"}, "strictly before"),
    ({"training_cutoff": "nope"}, "training_cutoff"),
    ({"training_cutoff": None}, "no training_cutoff"),
    ({"outcome_start": "2026-10-06T01:00:00+00:00"}, "outcome window opens before"),
    ({"feature_available_at": (("h1_close", "2026-10-06T03:00:00+00:00"),)}, "lookahead"),
    ({"feature_available_at": ()}, "no available_at stamp"),
    ({"features": ()}, "declares no features"),
    ({"feature_available_at": (("h1_close", AT), ("dxy", AT))}, "undeclared feature"),
    ({"role": "VOLATILITY_SCALE"}, "role violation"),
    ({"role": "VIBES"}, "not a decision role"),
    ({"role": ""}, "must name the decision role"),
    ({"family": "astrology"}, "not registered"),
])
def test_every_provenance_breach_is_refused_with_its_reason(fc, over, must_mention) -> None:
    bad = fc.defects(_belief(fc, **over))
    assert any(must_mention in d for d in bad), f"{over} -> {bad}"
    assert fc.verification(_belief(fc, **over))[0] == "REFUSED"


def test_cutoff_must_precede_a_later_outcome_window_too(fc) -> None:
    b = _belief(fc, outcome_start="2026-10-06T06:00:00+00:00",
                training_cutoff="2026-10-06T01:00:00+00:00")
    assert fc.verification(b) == ("VERIFIED", [])


def test_a_feature_available_exactly_at_the_belief_is_not_lookahead(fc) -> None:
    assert fc.defects(_belief(fc, feature_available_at=(("h1_close", AT),))) == []


def test_a_legacy_belief_is_accepted_but_unverified(fc, tmp_path) -> None:
    legacy = fc.Belief(model_id="m1", subject="XAUUSD/up", kind="PROBABILITY", value=0.6,
                       horizon_s=3600, at=AT)
    assert fc.defects(legacy) == []
    status, why = fc.verification(legacy)
    assert status == "UNVERIFIED" and why
    reg = tmp_path / "r.jsonl"
    pub = fc.publish([legacy, _belief(fc)], register=reg)
    assert pub.counts() == {"accepted": 2, "refused": 0}
    rows = fc.read_register(reg)
    assert [r["verification"] for r in rows] == ["UNVERIFIED", "VERIFIED"]


def test_a_legacy_feature_without_stamp_is_refused(fc) -> None:
    b = fc.Belief(model_id="m1", subject="s", kind="PROBABILITY", value=0.5, horizon_s=60,
                  at=AT, features=("dxy",))
    assert any("no available_at stamp" in d for d in fc.defects(b))


def test_old_register_rows_read_as_unverified_never_verified(fc, tmp_path) -> None:
    """A row written before the clauses existed carries none of the fields."""
    import json
    reg = tmp_path / "old.jsonl"
    old = {"model_id": "m1", "subject": "s", "kind": "PROBABILITY", "value": 0.5,
           "horizon_s": 3600, "at": AT, "confidence": None, "features": [], "note": "",
           "rule": "brier", "bucket": "intraday", "published_at": AT, "status": "ACCEPTED"}
    reg.write_text(json.dumps(old) + "\n", "utf-8")
    assert fc.verify_row(old)[0] == "UNVERIFIED"
    doc = fc.contract_report(reg)
    assert doc["verification"] == {"VERIFIED": 0, "UNVERIFIED": 1, "REFUSED": 0}
    assert doc["model_roles"]["registry_defects"] == []


def test_a_round_tripped_verified_row_reverifies(fc, tmp_path) -> None:
    reg = tmp_path / "r.jsonl"
    fc.publish([_belief(fc)], register=reg)
    row = fc.read_register(reg)[0]
    assert fc.verify_row(row) == ("VERIFIED", [])


def test_leakage_reads_the_rows_own_stamps(fc) -> None:
    row = {"at": AT, "features": ["dxy"],
           "feature_available_at": [["dxy", "2026-10-06T03:00:00+00:00"]]}
    assert "lookahead" in (fc.leakage(row, {}) or "")
