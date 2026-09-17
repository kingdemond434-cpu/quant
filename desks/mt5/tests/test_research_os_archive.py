"""The archive's own falsifiers: the wall holds, and an absent ledger is never a zero.

THE TWO TESTS THAT MATTER are `test_the_wall_refuses_*`. Everything else here is arithmetic that
could be re-derived from the report; the wall is the only thing standing between a search that is
graded on its own output and the files that grade it. A variant that could name
`desks/mt5/research/promoter.py` or the heat floor would eventually discover that moving the bar
is cheaper than clearing it, so the refusal is asserted from BOTH directions -- an IMMUTABLE path
and a FORBIDDEN_KNOBS class -- and asserted again on the write path, because a hand-edited archive
is the obvious way around a check that only guards its own mutations.

THE SECOND CONCERN is L1.28a. `test_unmeasured_fields_stay_null_and_are_named` runs the whole
organ against EMPTY ledgers and asserts all six fitness fields come back `None` with a named
reason. A research system that reports 0.0 survivor yield when no hypothesis was born is making a
much stronger claim than its data supports, and the composite would then quietly rank a variant
that measured nothing against one that measured badly.

Every path constant is pointed at tmp_path, derived from the module rather than listed, so a
source added later cannot keep reading the live box's ledgers while this suite believes it is
sandboxed.
"""
from __future__ import annotations

import json
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

_DESK = Path(__file__).resolve().parents[1]
for _p in (str(_DESK), str(_DESK / "research"), str(_DESK.parent.parent)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import research_os_archive as roa  # noqa: E402

NOW = datetime(2026, 9, 17, 12, 0, tzinfo=UTC)

#: Every ledger and artifact the organ touches, derived so a new source cannot escape the sandbox.
PATH_ATTRS = sorted(n for n, v in vars(roa).items()
                    if n.isupper() and isinstance(v, Path) and n not in ("DESK", "ROOT"))


@pytest.fixture
def sandbox(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Each artifact gets its OWN subdirectory, not a flat tmp_path.

    Measured here first: `data/research_os_archive.json` and `reports/RESEARCH_OS_ARCHIVE.json`
    differ only in case, and this box's filesystem is case-insensitive -- flattened into one
    directory the report silently overwrote the archive and every read came back missing its
    `variants`. The real tree separates them by directory; so does the sandbox.
    """
    for name in PATH_ATTRS:
        monkeypatch.setattr(roa, name, tmp_path / name / Path(getattr(roa, name)).name)
    return tmp_path


def _stamp(hours_ago: float) -> str:
    return (NOW - timedelta(hours=hours_ago)).isoformat(timespec="seconds")


def _jsonl(path: Path, rows: list[dict[str, object]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(r) + "\n" for r in rows), encoding="utf-8")


def seed_ledgers(independence: bool = True) -> None:
    """Synthetic ledgers with arithmetic a reader can check by hand, inside a 6h window ending NOW.

        forward_valid_alpha_per_cost  1 INDEPENDENT of 2 born / 7200s  = 0.000138889
        survivor_yield       2 CERTIFIED / 10 BORN                     = 0.2
        delta_n_eff          2.5 (in window) - 2.0 (last before it)    = 0.5
        novel_mechanism_rate 60 / (60 + 40)                            = 0.6
        false_discovery_rate 1 certified clock retired / 2 touched     = 0.5
        compute_per_survivor 7200 wall-seconds / 2 survivors           = 1.0 h
        forward_success      1 promoted / 4 touched clocks             = 0.25
    """
    rows: list[dict[str, object]] = [{"id": f"h{i}", "fate": "BORN", "at": _stamp(3)}
                                     for i in range(10)]
    rows += [{"id": f"c{i}", "fate": "CERTIFIED", "at": _stamp(2)} for i in range(2)]
    rows += [{"id": "old", "fate": "BORN", "at": _stamp(30)}]          # outside the window
    _jsonl(roa.GRAPH, rows)

    _jsonl(roa.BREADTH_HIST, [{"at": _stamp(9), "effective_breadth": 2.0},
                              {"at": _stamp(1), "effective_breadth": 2.5}])

    roa.NOVELTY.parent.mkdir(parents=True, exist_ok=True)
    roa.NOVELTY.write_text(json.dumps(
        {"at": _stamp(2), "n_novel": 60, "n_redundant": 40}), encoding="utf-8")

    _jsonl(roa.COMPUTE, [{"at": _stamp(4), "wall_s": 3600.0},
                         {"at": _stamp(2), "wall_s": 3600.0},
                         {"at": _stamp(48), "wall_s": 99999.0}])       # outside the window

    roa.SHADOW.parent.mkdir(parents=True, exist_ok=True)
    roa.SHADOW.write_text(json.dumps({
        # certified and retired inside the window -> the FDR numerator, and NOT forward-valid
        "A.asia": {"status": "RETIRED_ORPHAN", "gate_admission": roa.CERTIFIED_ADMISSION,
                   "promotion_authority": False, "last_attempt_at": _stamp(2),
                   "retired_at": _stamp(2), "forward_start": _stamp(5)},
        # certified, still running, born in the window -> forward-valid survivor #1
        "B.asia": {"status": "ACTIVE", "gate_admission": roa.CERTIFIED_ADMISSION,
                   "promotion_authority": False, "last_attempt_at": _stamp(2),
                   "forward_start": _stamp(5), "sleeve_id": "sleeve_b"},
        # touched but never certified: not forward-valid
        "C.asia": {"status": "ACTIVE", "gate_admission": "VALIDITY_PASS_POWER_DEFICIENT",
                   "promotion_authority": False, "last_attempt_at": _stamp(2),
                   "forward_start": _stamp(5)},
        # the one promotion in the window -> forward-valid survivor #2, but a TWIN of sleeve_b
        "D.asia": {"status": "PROMOTION CANDIDATE",
                   "gate_admission": "VALIDITY_PASS_POWER_DEFICIENT",
                   "promotion_authority": False, "last_attempt_at": _stamp(3),
                   "forward_start": _stamp(4), "sleeve_id": "sleeve_b_twin"},
        # blocked: attempted nothing, so it is not a forward denominator
        "E.asia": {"status": "BLOCKED_NO_BARS", "gate_admission": None,
                   "promotion_authority": False, "last_attempt_at": _stamp(2),
                   "forward_start": _stamp(5)},
        # outside the window entirely
        "F.asia": {"status": "ACTIVE", "gate_admission": roa.CERTIFIED_ADMISSION,
                   "promotion_authority": True, "last_attempt_at": _stamp(200),
                   "forward_start": _stamp(200), "sleeve_id": "sleeve_f"},
    }), encoding="utf-8")

    if independence:
        roa.EXPOSURE.parent.mkdir(parents=True, exist_ok=True)
        roa.EXPOSURE.write_text(json.dumps({
            "at": _stamp(1),
            "sleeves": [{"name": "sleeve_b"}, {"name": "sleeve_b_twin"}, {"name": "sleeve_f"}],
            "duplicate_heat": [{"a": "sleeve_b", "b": "sleeve_b_twin", "cosine": 1.0}],
        }), encoding="utf-8")


def _variant(vid: str, policy: dict[str, object], composites: list[float]) -> dict[str, object]:
    return {"variant_id": vid, "parent": "incumbent", "born_at": _stamp(100), "why": "fixture",
            "policy": policy, "fitness": dict.fromkeys(roa.FITNESS_FIELDS),
            "active_windows": [{"from": _stamp(20), "to": _stamp(14), "hours": 6.0,
                                "fitness": {}, "composite": c, "n_measured": 6}
                               for c in composites]}


def _policy(**over: object) -> dict[str, object]:
    p = roa.incumbent_policy()
    p.update(over)
    return p


# ------------------------------------------------------------------------------------ the seed
def test_first_run_seeds_the_incumbent_with_unit_factors(sandbox: Path) -> None:
    rep = roa.run(now=NOW)
    assert rep["active"] == "incumbent"
    assert rep["n_variants"] >= 1
    arch = json.loads(roa.ARCHIVE.read_text(encoding="utf-8"))
    inc = next(v for v in arch["variants"] if v["variant_id"] == "incumbent")
    pol = inc["policy"]
    assert set(pol["leg_budget_factors"].values()) == {1.0}
    assert set(pol["arm_weights"].values()) == {1.0}
    assert set(pol["department_factors"].values()) == {1.0}
    assert abs(sum(pol["population_mix"].values()) - 1.0) < 1e-9
    assert inc["parent"] is None and inc["active_windows"] == []
    assert json.loads(roa.OUT.read_text(encoding="utf-8"))["rule"] == roa.RULE


# --------------------------------------------------------------------------------- measurement
def test_fitness_is_measured_from_the_fixtures(sandbox: Path) -> None:
    seed_ledgers()
    fit, unmeasured, counts = roa.measure_fitness(NOW - timedelta(hours=6), NOW)
    assert fit == {"forward_valid_alpha_per_cost": round(1 / 7200, 9),
                   "survivor_yield": 0.2, "delta_n_eff": 0.5, "novel_mechanism_rate": 0.6,
                   "false_discovery_rate": 0.5, "compute_per_survivor": 1.0,
                   "forward_success": 0.25}
    assert unmeasured == []
    assert counts["born"] == 10 and counts["certified"] == 2      # the old row stayed outside
    assert counts["compute_hours"] == 2.0                         # the 48h-old row did too
    assert counts["cost"]["total_s"] == 7200.0 and counts["cost"]["data_s"] == 0.0
    comp, n_meas, terms = roa.composite_of(fit)
    assert n_meas == 7
    assert comp == pytest.approx(0.5 + 0.2 + 0.5 + 0.6 - 0.5 - 0.1 + 0.25)
    assert terms["false_discovery_rate"] < 0 and terms["compute_per_survivor"] < 0


def test_the_headline_term_leads_the_fitness_and_the_composite() -> None:
    assert roa.FITNESS_FIELDS[0] == "forward_valid_alpha_per_cost"
    assert next(iter(roa.COMPOSITE_TERMS)) == "forward_valid_alpha_per_cost"
    assert roa.COMPOSITE_TERMS["forward_valid_alpha_per_cost"] == (+1.0, roa.ALPHA_COST_SCALE)


def test_alpha_per_cost_counts_a_twin_once(sandbox: Path) -> None:
    seed_ledgers()
    _, _, counts = roa.measure_fitness(NOW - timedelta(hours=6), NOW)
    d = counts["alpha_per_cost"]
    assert d["n_born"] == 2, "A (retired), C (uncertified) and E (blocked) are not forward-valid"
    assert d["n_independent"] == 1, "D is a cosine-1.0 twin of B: one bet, not two"
    assert d["basis"] == roa.EXPOSURE.name and d["counted"] == ["sleeve_b"]


def test_alpha_per_cost_is_unmeasured_without_an_independence_basis(sandbox: Path) -> None:
    seed_ledgers(independence=False)
    fit, unmeasured, counts = roa.measure_fitness(NOW - timedelta(hours=6), NOW)
    assert fit["forward_valid_alpha_per_cost"] is None, "never a zero: independence is unproven"
    why = next(u["why"] for u in unmeasured if u["field"] == "forward_valid_alpha_per_cost")
    assert roa.EXPOSURE.name in why and roa.CREDIT.name in why
    assert counts["alpha_per_cost"]["n_born"] == 2      # the survivors are still counted and shown


def test_alpha_per_cost_is_unmeasured_without_a_denominator(sandbox: Path) -> None:
    seed_ledgers()
    _jsonl(roa.COMPUTE, [{"at": _stamp(48), "wall_s": 99999.0}])     # no spend inside the window
    fit, unmeasured, _ = roa.measure_fitness(NOW - timedelta(hours=6), NOW)
    assert fit["forward_valid_alpha_per_cost"] is None
    why = next(u["why"] for u in unmeasured if u["field"] == "forward_valid_alpha_per_cost")
    assert "denominator" in why


def test_alpha_per_cost_is_zero_when_the_window_bought_nothing(sandbox: Path) -> None:
    """Zero survivors against a real spend IS a measurement -- the spend happened."""
    seed_ledgers()
    roa.SHADOW.write_text(json.dumps({}), encoding="utf-8")
    fit, unmeasured, _ = roa.measure_fitness(NOW - timedelta(hours=6), NOW)
    assert fit["forward_valid_alpha_per_cost"] == 0.0
    assert "forward_valid_alpha_per_cost" not in {u["field"] for u in unmeasured}


def test_unmeasured_fields_stay_null_and_are_named(sandbox: Path) -> None:
    fit, unmeasured, _ = roa.measure_fitness(NOW - timedelta(hours=6), NOW)
    assert set(fit) == set(roa.FITNESS_FIELDS)
    assert all(v is None for v in fit.values()), "an absent ledger must never read as a zero"
    assert {u["field"] for u in unmeasured} == set(roa.FITNESS_FIELDS)
    assert all(u["why"] for u in unmeasured)
    assert roa.composite_of(fit) == (None, 0, {})
    rep = roa.run(now=NOW)
    assert rep["fitness_active"]["composite"] is None
    assert {u["field"] for u in rep["unmeasured"]} == set(roa.FITNESS_FIELDS)


def test_compute_per_survivor_is_null_rather_than_zero_with_no_survivor(sandbox: Path) -> None:
    seed_ledgers()
    _jsonl(roa.GRAPH, [{"id": "h", "fate": "BORN", "at": _stamp(3)}])
    fit, unmeasured, counts = roa.measure_fitness(NOW - timedelta(hours=6), NOW)
    assert fit["compute_per_survivor"] is None
    assert counts["compute_hours"] == 2.0
    why = next(u["why"] for u in unmeasured if u["field"] == "compute_per_survivor")
    assert "denominator" in why


# ------------------------------------------------------------------------------------ rotation
def _two_variant_archive() -> dict[str, object]:
    return {"variants": [_variant("incumbent", roa.incumbent_policy(), [0.1, 0.1, 0.1]),
                         _variant("challenger", _policy(retrieval_depth=12), [0.9, 0.9])],
            "active": "incumbent", "active_since": _stamp(7), "history": []}


def test_a_better_measured_variant_takes_the_seat_after_the_window(sandbox: Path) -> None:
    arch = _two_variant_archive()
    arch["variants"][0]["parent"] = None
    roa.save_archive(arch)
    rep = roa.run(window_hours=6.0, now=NOW)
    assert rep["rotation"]["rotated"] is True
    assert rep["active"] == "challenger"
    assert rep["active_since"] == NOW.isoformat(timespec="seconds")
    written = json.loads(roa.ARCHIVE.read_text(encoding="utf-8"))
    assert written["active"] == "challenger"
    assert any(h["event"] == "ROTATE" and h["to"] == "challenger" for h in written["history"])


def test_rotation_respects_the_window(sandbox: Path) -> None:
    arch = _two_variant_archive()
    arch["variants"][0]["parent"] = None
    arch["active_since"] = _stamp(1)              # one hour into a six-hour window
    roa.save_archive(arch)
    rep = roa.run(window_hours=6.0, now=NOW)
    assert rep["rotation"]["rotated"] is False
    assert rep["active"] == "incumbent"
    assert "window" in rep["rotation"]["why"]
    # and the in-progress window was NOT banked as a completed one
    written = json.loads(roa.ARCHIVE.read_text(encoding="utf-8"))
    inc = next(v for v in written["variants"] if v["variant_id"] == "incumbent")
    assert len(inc["active_windows"]) == 3


# ------------------------------------------------------------------------------------ mutation
def test_a_descendant_changes_exactly_one_knob_within_bounds(sandbox: Path) -> None:
    arch = roa.seed_archive(NOW)
    parent = arch["variants"][0]["policy"]
    seen_knobs, tried = set(), 0
    for seed in range(60):
        child, why = roa.propose_descendant(arch, NOW, seed=seed)
        if child is None:
            assert not why.startswith("REFUSED"), why
            continue
        tried += 1
        roa.assert_constitution(child["policy"])          # inside every declared bound
        changed = [k for k in roa.POLICY_KNOBS
                   if child["policy"].get(k) != parent.get(k)]
        assert changed == [child["mutated_knob"]], f"seed {seed} moved {changed}"
        seen_knobs.add(child["mutated_knob"])
        assert child["parent"] == "incumbent" and child["born_at"]
        knob = child["mutated_knob"]
        if roa.POLICY_KNOBS[knob]["kind"] == "factors":
            moved = [n for n, f in child["policy"][knob].items() if f != parent[knob][n]]
            assert len(moved) == 1, f"{knob} moved {moved}, not one entry"
    assert tried >= 20 and len(seen_knobs) >= 3, "the mutation operator reaches several knobs"


def test_a_descendant_is_lineage_not_a_fork(sandbox: Path) -> None:
    roa.run(now=NOW)
    arch = json.loads(roa.ARCHIVE.read_text(encoding="utf-8"))
    kids = [v for v in arch["variants"] if v["variant_id"] != "incumbent"]
    assert kids and all(k["parent"] == "incumbent" for k in kids)
    assert all(k["fitness"] == dict.fromkeys(roa.FITNESS_FIELDS) for k in kids)
    assert any(h["event"] == "PROPOSE" for h in arch["history"])


# --------------------------------------------------------------------------- diverse archive
def test_the_diverse_archive_rule_keeps_one_variant_per_cluster(sandbox: Path) -> None:
    arch = {"variants": [
        _variant("incumbent", roa.incumbent_policy(), [0.1]),
        _variant("a1", _policy(retrieval_depth=12), [0.9]),
        _variant("a2", _policy(retrieval_depth=11), [0.8]),
        _variant("b1", _policy(prompt_template="mechanism_first"), [0.7]),
        _variant("b2", _policy(prompt_template="falsifier_first"), [0.6]),
        _variant("c1", _policy(exploration_floor=0.4), [0.05]),
    ], "active": "incumbent", "active_since": _stamp(7), "history": []}
    arch["variants"][0]["parent"] = None
    dropped = roa.prune(arch, keep=4)
    kept = {v["variant_id"] for v in arch["variants"]}
    clusters = {roa.cluster_of(v["policy"]) for v in arch["variants"]}
    assert clusters == {"incumbent", "retrieval_depth", "prompt_template", "exploration_floor"}
    assert {"incumbent", "a1", "b1", "c1"} == kept
    # c1 is the WORST variant in the archive and survives anyway: it is the only member of its
    # cluster, and an archive that drops its last explorer of a knob has collapsed to a champion.
    assert set(dropped) == {"a2", "b2"}


# ---------------------------------------------------------------------------------- the wall
def test_the_wall_accepts_the_incumbent(sandbox: Path) -> None:
    roa.assert_constitution(roa.incumbent_policy())


# ------------------------------------------------------------------------------- the miner block
def test_the_miner_block_is_seeded_inside_its_declared_bounds(sandbox: Path) -> None:
    m = roa.incumbent_policy()["miner"]
    assert set(m) == {"retrieval", "ranking", "ontology_version", "search_mix"}
    assert m["retrieval"] in roa.MINER_RETRIEVAL and m["ranking"] in roa.MINER_RANKING
    assert set(m["search_mix"]) == set(roa.MINER_SEARCH_LANES)
    assert abs(sum(m["search_mix"].values()) - 1.0) < 1e-9
    assert m["search_mix"]["cold"] >= roa.COLD_SEARCH_FLOOR
    rep = roa.run(now=NOW)
    assert rep["wall"]["cold_search_floor"] == roa.COLD_SEARCH_FLOOR
    assert roa.active_policy()["miner"] == m


def test_the_wall_refuses_a_cold_lane_below_the_floor(sandbox: Path) -> None:
    for cold in (0.0, 0.05, 0.099):
        bad = _policy(miner={"retrieval": "bm25", "ranking": "score", "ontology_version": "v1",
                             "search_mix": {"exploration": 0.4, "exploitation": 0.6 - cold,
                                            "cold": cold}})
        with pytest.raises(roa.ConstitutionBreach, match="COLD-SEARCH FLOOR"):
            roa.assert_constitution(bad)
    ok = _policy(miner={"retrieval": "hybrid", "ranking": "roi_first", "ontology_version": "v3",
                        "search_mix": {"exploration": 0.4, "exploitation": 0.5, "cold": 0.1}})
    roa.assert_constitution(ok)                      # exactly at the floor is admissible


def test_the_wall_refuses_a_malformed_miner_block(sandbox: Path) -> None:
    for bad in ({"retrieval": "grep", "ranking": "score", "ontology_version": "v1",
                 "search_mix": {"exploration": 0.4, "exploitation": 0.45, "cold": 0.15}},
                {"retrieval": "bm25", "ranking": "whatever", "ontology_version": "v1",
                 "search_mix": {"exploration": 0.4, "exploitation": 0.45, "cold": 0.15}},
                {"retrieval": "bm25", "ranking": "score", "ontology_version": "a" * 40,
                 "search_mix": {"exploration": 0.4, "exploitation": 0.45, "cold": 0.15}},
                {"retrieval": "bm25", "ranking": "score", "ontology_version": "v1",
                 "search_mix": {"exploration": 0.9, "exploitation": 0.9, "cold": 0.9}},
                {"retrieval": "bm25", "ranking": "score", "ontology_version": "v1"}):
        with pytest.raises(roa.ConstitutionBreach):
            roa.assert_constitution(_policy(miner=bad))


def test_a_miner_mutation_stays_in_bounds_and_never_dips_below_the_cold_floor(
        sandbox: Path) -> None:
    import numpy as np
    seen = set()
    for seed in range(120):
        m, detail = roa._mutate_miner(dict(roa.incumbent_policy()["miner"]),
                                      np.random.default_rng(seed))
        roa.assert_constitution(_policy(miner=m))    # bounds AND the cold floor, every time
        assert m["search_mix"]["cold"] >= roa.COLD_SEARCH_FLOOR - 1e-9
        sub = detail.split()[0].split(".")[0]
        assert sub in ("retrieval", "ranking", "ontology_version", "search_mix"), detail
        seen.add(sub)
    assert {"retrieval", "ranking", "ontology_version", "search_mix"} <= seen


def test_a_descendant_can_move_the_miner_knob(sandbox: Path) -> None:
    arch = roa.seed_archive(NOW)
    parent = arch["variants"][0]["policy"]
    kids = [roa.propose_descendant(arch, NOW, seed=s)[0] for s in range(80)]
    miner_kids = [k for k in kids if k is not None and k["mutated_knob"] == "miner"]
    assert miner_kids, "the mutation operator must be able to reach the miner block"
    for k in miner_kids:
        assert [j for j in roa.POLICY_KNOBS if k["policy"].get(j) != parent.get(j)] == ["miner"]
        assert k["policy"]["miner"]["search_mix"]["cold"] >= roa.COLD_SEARCH_FLOOR - 1e-9
        assert roa.cluster_of(k["policy"]) == "miner"


def test_the_wall_refuses_a_forbidden_knob(sandbox: Path) -> None:
    with pytest.raises(roa.ConstitutionBreach, match="forbidden knob class"):
        roa.assert_constitution(_policy(department_factors={"heat_floor": 1.5}))
    with pytest.raises(roa.ConstitutionBreach, match="forbidden knob class"):
        roa.assert_constitution(_policy(prompt_template="gate_threshold_relax"))
    assert "heat floor" in roa.forbidden_tokens()
    assert roa.forbidden_knobs(), "meta_rnd.FORBIDDEN_KNOBS must be reachable"


def test_the_wall_refuses_every_moat_knob(sandbox: Path) -> None:
    """The second list: what the desk KNOWS, not what it risks. A miner graded on alpha per unit
    of cost has a cheapest path through every one of these and none of it is research."""
    named = {"source_provenance": "provenance", "pit_rules": "pit rule",
             "trial_accounting": "trial accounting", "sealed_holdout": "sealed holdout",
             "forward_clock_length": "forward clock", "actual_fills": "actual fill",
             "actual_costs": "actual cost", "point_in_time_relaxation": "point in time"}
    for knob_name, token in named.items():
        with pytest.raises(roa.ConstitutionBreach, match="forbidden knob class"):
            roa.assert_constitution(_policy(leg_budget_factors={knob_name: 1.2}))
        assert token in roa.forbidden_tokens(), f"{token!r} must be a refusal token"
    # and as a VALUE, not only as a key
    with pytest.raises(roa.ConstitutionBreach, match="forbidden knob class"):
        roa.assert_constitution(_policy(prompt_template="holdout_peek"))
    assert set(roa.FORBIDDEN_MOAT_KNOBS) and all(roa.FORBIDDEN_MOAT_KNOBS.values())
    rep = roa.run(now=NOW)
    assert rep["wall"]["forbidden_moat_classes"] == sorted(roa.FORBIDDEN_MOAT_KNOBS)


def test_the_wall_refuses_an_immutable_path(sandbox: Path) -> None:
    immutable = roa.immutable_paths()
    assert immutable and "desks/mt5/research/promoter.py" in immutable
    with pytest.raises(roa.ConstitutionBreach, match="IMMUTABLE"):
        roa.assert_constitution(_policy(
            leg_budget_factors={"desks/mt5/research/promoter.py": 1.2}))
    with pytest.raises(roa.ConstitutionBreach, match="IMMUTABLE"):
        roa.assert_constitution(_policy(arm_weights={"universal_gate.py": 1.1}))


def test_the_wall_refuses_out_of_bounds_and_unknown_knobs(sandbox: Path) -> None:
    for bad in (_policy(retrieval_depth=21), _policy(retrieval_depth=-1),
                _policy(exploration_floor=0.9), _policy(prompt_template="freeform"),
                _policy(department_factors={"discovery": 4.0}),
                _policy(population_mix=dict.fromkeys(roa.POPULATIONS, 0.5)),
                _policy(meta_knobs={"research_tree.BEAM": 900})):
        with pytest.raises(roa.ConstitutionBreach):
            roa.assert_constitution(bad)
    extra = _policy()
    extra["gate_threshold"] = 0.1
    with pytest.raises(roa.ConstitutionBreach):
        roa.assert_constitution(extra)


def test_every_archive_write_goes_through_the_wall(sandbox: Path) -> None:
    arch = roa.seed_archive(NOW)
    arch["variants"].append(_variant("rogue", _policy(prompt_template="heat_floor_lift"), [9.9]))
    with pytest.raises(roa.ConstitutionBreach):
        roa.save_archive(arch)
    assert not roa.ARCHIVE.exists(), "a breaching archive must not reach disk at all"


# ------------------------------------------------------------------------------- the consumer
def test_active_policy_shape(sandbox: Path) -> None:
    roa.run(now=NOW)
    pol = roa.active_policy()
    assert set(roa.POLICY_KNOBS) <= set(pol)
    assert pol["variant_id"] == "incumbent" and pol["source"] == "archive"
    assert isinstance(pol["retrieval_depth"], int)
    assert isinstance(pol["leg_budget_factors"], dict)
    assert roa.retrieval_depth() == pol["retrieval_depth"]
    assert roa.leg_factor(next(iter(pol["leg_budget_factors"]))) == 1.0
    assert roa.leg_factor("a_leg_no_variant_has_ever_named") == 1.0


def test_active_policy_falls_back_rather_than_raising(sandbox: Path) -> None:
    missing = roa.active_policy()
    assert missing["source"] == "incumbent_fallback" and missing["variant_id"] == "incumbent"
    assert set(roa.POLICY_KNOBS) <= set(missing)
    # a hand-edited archive that breaches is refused at READ time too, not just at write time
    roa.ARCHIVE.parent.mkdir(parents=True, exist_ok=True)
    roa.ARCHIVE.write_text(json.dumps({
        "variants": [_variant("tampered", _policy(prompt_template="min_lot_override"), [])],
        "active": "tampered"}), encoding="utf-8")
    pol = roa.active_policy()
    assert pol["source"] == "incumbent_fallback"
    assert "refused by the wall" in pol["why"]
    assert roa.retrieval_depth() == roa.DEFAULT_RETRIEVAL_DEPTH


# --------------------------------------------------------------------------------------- cli
def test_cli_dry_run_writes_nothing(sandbox: Path, capsys: pytest.CaptureFixture[str]) -> None:
    assert roa.main(["--dry-run", "--window-hours", "6"]) == 0
    assert not roa.ARCHIVE.exists() and not roa.OUT.exists()
    out = capsys.readouterr().out
    assert "--dry-run; nothing written" in out
    assert "immutable_checked=True" in out


def test_cli_writes_both_artifacts(sandbox: Path, capsys: pytest.CaptureFixture[str]) -> None:
    seed_ledgers()
    assert roa.main([]) == 0
    assert roa.ARCHIVE.exists() and roa.OUT.exists()
    rep = json.loads(roa.OUT.read_text(encoding="utf-8"))
    assert rep["status"] == "OK"
    assert rep["wall"]["immutable_checked"] is True and rep["wall"]["refused"] == []
    assert rep["rule"] == roa.RULE
    assert rep["leaderboard"] and "cluster" in rep["leaderboard"][0]
    assert capsys.readouterr().out.strip()
