"""The co-evolution closure: residuals, failures, islands, self-play, synthetic worlds, queues.

Each test pins one of the principal's mandated properties, and each is written so that the
FAILURE MODE it guards against is what breaks it -- a silent zero where an UNMEASURED belongs,
a representation buried by one learner, a migration that homogenises the archipelago, a
candidate crowned without beating the simpler explanation.
"""
from __future__ import annotations

from typing import Any

import pytest

from libs.research import coevolution_lab as CL
from libs.research import model_families as MF


@pytest.fixture(autouse=True)
def _no_backend_probe(monkeypatch: pytest.MonkeyPatch) -> None:
    """A test never spawns the heavy-backend probe subprocess.

    `availability()` consults a measured health cache; leaving it unseeded would make the first
    test run fork a probe that deliberately waits out a hang. The seed says every backend is
    healthy, so nothing here is passing because a backend was quietly skipped.
    """
    monkeypatch.setattr(MF, "_health_cache",
                        {"measured_utc": 9e18, "probe_complete": True, "passes": 0,
                         "state": dict.fromkeys(MF.FAMILIES, "ok")})


# ------------------------------------------------------------------ item 18: synthetic worlds
def test_planted_structure_is_rediscovered_and_the_null_world_is_not() -> None:
    """A hidden linear structure is found; the control world with nothing planted is not."""
    world = CL.synthetic_world("linear", n=500, seed=3, noise=0.5)
    r = MF.walk_forward("linear", world["x"], world["y"], allow_heavy=False, min_rows=120)
    assert r["verdict"] == MF.POSITIVE, r
    assert r["net_gain"] > 0

    null = CL.synthetic_world("null", n=500, seed=3)
    rn = MF.walk_forward("linear", null["x"], null["y"], allow_heavy=False, min_rows=120)
    assert rn["net_gain"] <= r["net_gain"]
    assert null["hidden_features"] == []


def test_rediscovery_score_publishes_per_method_and_never_nets_false_positives() -> None:
    doc = CL.rediscovery_score(methods=("linear", "tree"), kinds=("linear", "null"),
                               n=360, seed=5, allow_heavy=False, min_rows=100)
    assert set(doc["per_method"]) == {"linear", "tree"}
    for row in doc["per_method"].values():
        assert row["of"] == 1                              # one structured world was planted
        assert "false_positives" in row                    # published beside, never netted in
        assert 0.0 <= (row["score"] or 0.0) <= 1.0
    assert doc["per_method"]["linear"]["score"] == 1.0, doc["per_method"]["linear"]
    assert doc["best_method"] in {"linear", "tree"}


# ------------------------------------------------------------------ item 2: planted pairing
def test_a_planted_factor_model_pairing_is_found_by_the_right_family() -> None:
    """An interaction world is invisible to a purely additive learner and visible to a tree."""
    w = CL.synthetic_world("interaction", n=700, p=4, seed=11, noise=0.5)
    lin = MF.walk_forward("linear", w["x"], w["y"], allow_heavy=False, min_rows=120)
    tree = MF.walk_forward("tree", w["x"], w["y"], allow_heavy=False, min_rows=120)
    assert tree["net_gain"] > lin["net_gain"], (lin, tree)
    assert tree["verdict"] == MF.POSITIVE

    grid = CL.compatibility_matrix([
        {"representation": "raw", "model": "linear", **lin},
        {"representation": "raw", "model": "tree", **tree}])
    assert CL.dead_representations(grid)["raw"]["verdict"] == "ALIVE"
    assert CL.dead_representations(grid)["raw"]["best_model"] == "tree"


# ------------------------------------------------------------------ item 7: R x M compatibility
def test_a_representation_is_never_dead_after_one_learner() -> None:
    one = CL.compatibility_matrix([{"representation": "rank", "model": "linear",
                                    "net_gain": -0.01, "verdict": MF.NEGATIVE, "n": 400}])
    assert CL.dead_representations(one)["rank"]["verdict"] == CL.UNMEASURED

    two = CL.compatibility_matrix([
        {"representation": "rank", "model": "linear", "net_gain": -0.01,
         "verdict": MF.NEGATIVE, "n": 400},
        {"representation": "rank", "model": "tree", "net_gain": -0.02,
         "verdict": MF.NEGATIVE, "n": 400}])
    assert CL.dead_representations(two)["rank"]["verdict"] == "DEAD"


# ------------------------------------------------------------------ item 3: residual research
def test_a_structured_residual_raises_a_typed_request() -> None:
    # The model is systematically wrong in the London session and right elsewhere.
    resid = ([0.4] * 40 + [0.0] * 40) * 3
    ctx = {"session": (["london"] * 40 + ["asia"] * 40) * 3,
           "state": (["high_vol"] * 40 + ["low_vol"] * 40) * 3}
    struct = CL.residual_structure(resid, ctx)
    assert struct["session"]["verdict"] == "STRUCTURED"
    assert "london" in struct["session"]["structured_levels"]
    # An axis nobody labelled is UNMEASURED -- never reported flat.
    assert struct["country"]["verdict"] == CL.UNMEASURED

    reqs = CL.residual_requests(struct, model="linear", symbol="XAUUSD", features=["r6"])
    kinds = {r.kind for r in reqs}
    assert "factor" in kinds                                   # session structure -> factor
    assert all(r.priority >= 1.0 for r in reqs)
    assert all(r.request_id.startswith("req_") for r in reqs)


def test_a_flat_residual_raises_nothing() -> None:
    struct = CL.residual_structure([0.0] * 60, {"session": ["asia"] * 30 + ["ny"] * 30})
    assert struct["session"]["verdict"] == "FLAT"
    assert CL.residual_requests(struct, model="linear", symbol="EURUSD") == []


# ------------------------------------------------------------------ item 10: descendants
@pytest.mark.parametrize(("result", "kind", "queue"), [
    ({"n": 400, "gain": -0.001, "net_gain": -0.001, "verdict": MF.NEGATIVE},
     "weak_ic", "representation"),
    ({"n": 400, "gross_gain": 0.004, "gain": 0.004, "net_gain": -0.001,
      "verdict": MF.NEGATIVE}, "cost_dead", "factor"),
    ({"n": 400, "gain": -0.001, "net_gain": -0.001, "state_dependent": True,
      "verdict": MF.NEGATIVE}, "state_dependent", "model"),
    ({"n": 400, "gain": -0.001, "net_gain": -0.001, "residual_structured": True,
      "verdict": MF.NEGATIVE}, "misspecified", "model"),
    ({"n": 0, "verdict": CL.UNMEASURED}, "no_data", "data"),
])
def test_every_failure_emits_the_descendant_its_kind_implies(
        result: dict[str, Any], kind: str, queue: str) -> None:
    assert CL.classify_failure(result) == kind
    kids = CL.descendants_for(result, symbol="XAUUSD")
    assert kids, "a dead cell that emits nothing is the defect this rule exists to stop"
    assert kids[0].kind == queue
    assert kids[0].payload["failure_kind"] == kind
    assert kids[0].payload["descendant_kind"] == CL.FAILURE_RULES[kind][1]
    if kind == "misspecified":
        # A challenger must be falsified against the incumbent, not quietly crowned.
        assert any(k.kind == "falsification" for k in kids)


# ------------------------------------------------------------------ item 15: islands
def test_only_strong_concepts_migrate() -> None:
    results = {
        "linear_prior": [{"concept": "strong", "net_gain": 0.01},
                         {"concept": "weak", "net_gain": 0.0001}],
        "nonlinear_prior": [{"concept": "local", "net_gain": 0.005}],
    }
    moves = CL.migrate(results)
    assert [m["concept"] for m in moves] == ["strong"]
    assert moves[0]["from"] == "linear_prior" and moves[0]["to"] == "nonlinear_prior"
    # Nothing migrates the other way: the destination's own best already beats the migrant.
    assert not [m for m in moves if m["from"] == "nonlinear_prior"]


def test_a_negative_concept_never_migrates_and_islands_differ() -> None:
    assert CL.migrate({"a": [{"concept": "dud", "net_gain": -0.01}], "b": []}) == []
    islands = CL.default_islands(10, seed=1)
    assert len({i.name for i in islands}) == len(islands)
    assert len({i.prior_models for i in islands}) > 1
    assert all(i.info_subset for i in islands)


# ------------------------------------------------------------------ item 17: self-play
def test_self_play_rejects_a_candidate_a_simpler_explanation_beats() -> None:
    candidate = {"model": "boosting", "net_gain": 0.0020, "complexity": 6, "fold_spread": 0.001}
    simpler = [{"model": "linear", "net_gain": 0.0019, "complexity": 2}]
    v = CL.self_play(candidate, simpler)
    assert v["verdict"] == "REJECTED"
    assert "simplifier" in v["rejected_by"]

    # The same candidate with a real margin over the simpler rival survives.
    good = CL.self_play({**candidate, "net_gain": 0.02}, simpler)
    assert good["verdict"] == "SURVIVES_SELF_PLAY", good


def test_self_play_records_unmeasured_roles_rather_than_crediting_them() -> None:
    v = CL.self_play({"model": "linear", "net_gain": 0.01, "complexity": 2}, [])
    roles = {r["role"]: r for r in v["roles"]}
    assert roles["attacker"]["verdict"] == CL.UNMEASURED
    assert roles["reimplementer"]["verdict"] == CL.UNMEASURED
    assert v["verdict"] == "SURVIVES_SELF_PLAY"
    # An independent rebuild that disagrees is fatal.
    bad = CL.self_play({"model": "linear", "net_gain": 0.01, "complexity": 2,
                        "reimplementation_net_gain": -0.01}, [])
    assert bad["verdict"] == "REJECTED" and "reimplementer" in bad["rejected_by"]


# ------------------------------------------------------------------ item 13: active design
def test_the_design_with_the_most_bits_per_second_is_chosen() -> None:
    doc = CL.design_discriminating_experiment(
        {"name": "H1"}, {"name": "H2"},
        [{"name": "discriminating", "cost_s": 100.0, "discriminations": [0.9, 0.8]},
         {"name": "blind_rerun", "cost_s": 100.0, "discriminations": [0.0, 0.0]}])
    assert doc["chosen"]["name"] == "discriminating"
    assert doc["saved_trials"] == 1
    blind = next(d for d in doc["designs"] if d["name"] == "blind_rerun")
    assert blind["expected_bits"] == 0.0, "a design both theories predict alike buys no bits"


# ------------------------------------------------------------------ item 14: seven queues
def test_idle_capacity_with_queued_work_is_reported_as_a_defect() -> None:
    q = CL.QueueSet()
    assert set(q.depth()) == set(CL.QUEUE_KINDS) and len(CL.QUEUE_KINDS) == 7
    q.push(CL.Request("model", "a challenger", "because", priority=3.0))
    assert q.idle_defect(free_slots=2, value_floor=1.5)["verdict"] == "DEFECT"
    assert q.idle_defect(free_slots=0, value_floor=1.5)["verdict"] == "BUSY"
    assert CL.QueueSet().idle_defect(free_slots=2)["verdict"] == "IDLE_AND_EMPTY"


def test_a_request_is_deduplicated_and_an_unknown_queue_is_refused() -> None:
    q = CL.QueueSet()
    r = CL.Request("data", "t", "w", payload={"a": 1})
    assert q.push(r) is True
    assert q.push(CL.Request("data", "t", "w", payload={"a": 1})) is False
    with pytest.raises(ValueError, match="unknown queue kind"):
        CL.Request("nonsense", "t", "w")


# ------------------------------------------------------------------ item 6: heavy libraries
def test_an_absent_heavy_library_reads_unmeasured_and_the_fallback_still_runs(
        monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(MF, "_import", lambda mod: None)
    avail = MF.availability()
    assert set(avail) == set(MF.FAMILIES)
    assert all(v["heavy_verdict"] == MF.UNMEASURED for v in avail.values())
    assert all(v["backend"] == "fallback" for v in avail.values())

    w = CL.synthetic_world("linear", n=400, seed=2, noise=0.5)
    r = MF.walk_forward("linear", w["x"], w["y"], allow_heavy=False, min_rows=120)
    assert r["heavy_verdict"] == MF.UNMEASURED
    assert r["backend"] == "fallback"
    assert r["verdict"] == MF.POSITIVE, "the pure-Python fallback must always carry the run"


def test_every_declared_family_runs_without_any_heavy_backend() -> None:
    w = CL.synthetic_world("linear", n=400, p=4, seed=7, noise=0.6)
    for fam in MF.ORDER:
        r = MF.walk_forward(fam, w["x"], w["y"], allow_heavy=False, min_rows=120)
        assert r["verdict"] in {MF.POSITIVE, MF.NEGATIVE}, (fam, r)
        assert r["backend"] == "fallback"
        assert r["tax"] == MF.FAMILIES[fam].tax
    assert len(MF.FAMILIES) == 10
    # Lineage is real: every declared parent is itself a family.
    assert all(f.parent in MF.FAMILIES or f.parent == "" for f in MF.FAMILIES.values())


def test_too_few_rows_is_unmeasured_never_a_zero() -> None:
    w = CL.synthetic_world("linear", n=40, seed=1)
    r = MF.walk_forward("linear", w["x"], w["y"], allow_heavy=False)
    assert r["verdict"] == MF.UNMEASURED and r.get("net_gain") is None


# ------------------------------------------------------------------ guarded shims
def test_the_shims_degrade_to_a_local_fallback_without_the_other_builders_modules() -> None:
    for doc in (CL.record_outcome("island:x", "SURVIVED"), CL.prior_for("island:x"),
                CL.to_campaign({"name": "x"}), CL.link_experiment("a", "b", "r")):
        assert doc["backend"] in {"local_fallback"} or doc["backend"].startswith(
            ("research_priors", "experiment_spec", "experiment_graph"))
    assert 0.0 <= CL.prior_for("unknown", 0.5)["prior"] <= 1.0


# ------------------------------------------------------------------ item 6: a backend that HANGS
def test_a_backend_that_imports_but_never_returns_is_unmeasured_not_used(
        monkeypatch: pytest.MonkeyPatch) -> None:
    """IMPORTABLE IS NOT USABLE. Measured on the build box: sklearn imports and
    HistGradientBoostingClassifier.fit never returns, so one `boosting` cell would eat a whole
    leg budget. A family whose probe row is still `started` is served by the fallback."""
    monkeypatch.setattr(MF, "_import", lambda mod: object())        # everything importable
    monkeypatch.setattr(MF, "_health_cache",
                        {"measured_utc": 9e18, "probe_complete": False, "passes": 2,
                         "state": {**dict.fromkeys(MF.FAMILIES, "ok"), "boosting": "started"}})
    avail = MF.availability()
    assert avail["boosting"]["backend"] == "fallback"
    assert avail["boosting"]["heavy_verdict"] == MF.UNMEASURED
    assert "DID NOT RETURN" in avail["boosting"]["why"]
    assert avail["linear"]["backend"] == "heavy"                    # the healthy one is used

    w = CL.synthetic_world("threshold", n=400, seed=4, noise=0.5)
    r = MF.walk_forward("boosting", w["x"], w["y"], min_rows=120)
    assert r["backend"] == "fallback", "a hanging backend is never called"
    assert r["verdict"] in {MF.POSITIVE, MF.NEGATIVE}


def test_a_family_the_probe_never_reached_is_unmeasured_rather_than_assumed_good(
        monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(MF, "_import", lambda mod: object())
    monkeypatch.setattr(MF, "_health_cache",
                        {"measured_utc": 9e18, "probe_complete": False, "passes": 1,
                         "state": {"linear": "ok"}})
    avail = MF.availability()
    assert avail["neural"]["heavy_verdict"] == MF.UNMEASURED
    assert avail["neural"]["probe_state"] == MF.UNMEASURED
    assert "never reached" in avail["neural"]["why"]
