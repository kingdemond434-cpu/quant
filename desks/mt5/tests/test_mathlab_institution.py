"""The institution: acceptance B-I on the cards, the reviewers, the null factory, the ledger,
the lockbox, replication, credit, the Pareto front and the wiring proof -- on synthetic data,
under tmp_path, with no LLM anywhere.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

import numpy as np
import pytest

DESK = Path(__file__).resolve().parents[1]
for _p in (str(Path(__file__).resolve().parent), str(DESK / "research"), str(DESK),
           str(DESK.parents[1])):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from research.mathlab import burden as B  # noqa: E402
from research.mathlab import engines as E  # noqa: E402
from research.mathlab import grammar as G  # noqa: E402
from research.mathlab import institution as I  # noqa: E402
from research.mathlab import physics as P  # noqa: E402
from research.mathlab.objects import MathObject  # noqa: E402
from test_mathlab_physics import PHYSICS, make_panel  # noqa: E402

SEED = 5


def judged_objects(panel, permutations: int = 20) -> list[MathObject]:
    """Objects from three physics traditions, judged, so cards can be built from them."""
    rng = np.random.default_rng(SEED)
    out: list[MathObject] = []
    for cls in (P.Renormalisation, P.Turbulence, P.FieldContinuum):
        sci = cls()
        objects = sci.propose(panel, 5.0, rng)
        for obj in objects:
            B.judge(obj, panel, distinct_forms=max(1, len(sci.distinct)), rng=rng,
                    permutations=permutations)
        out.extend(objects)
    return out


def cards_for(panel, objects: list[MathObject], civilization: str = "A"
              ) -> list[I.MathHypothesisCard]:
    return [I.card_from_object(o, domain="physics", method=o.tradition,
                               civilization=civilization, seed=11, compute_s=0.1)
            for o in objects]


@pytest.fixture(scope="module")
def world() -> dict[str, Any]:
    panel = make_panel(51)
    objects = judged_objects(panel)
    cards = cards_for(panel, objects)
    return {"panel": panel, "objects": objects, "cards": cards}


@pytest.fixture(scope="module")
def full_run(tmp_path_factory: pytest.TempPathFactory) -> dict[str, Any]:
    """ONE end-to-end pass of physics_lab with every physics tradition, kept for the tests that
    read the artifact (acceptance D, E, G, I)."""
    from libs.moat import registry as R
    from libs.ops import events
    from research import math_lab as ML
    from research import physics_lab as PL
    from research import proposer_common as PC
    tmp = tmp_path_factory.mktemp("physics_lab")
    mp = pytest.MonkeyPatch()
    mp.setattr(R, "BACKUP", tmp / "no_backup", raising=False)
    R.set_path(tmp / "alpha_registry.sqlite")
    panels = [make_panel(61), make_panel(62, target="GBPUSD")]
    mp.setattr(ML, "build_panels", lambda max_targets=4: (
        panels, {"unmeasured": [], "targets": ["EURUSD", "GBPUSD"]}))
    mp.setattr(PL, "OUT", tmp / "reports" / "PHYSICS_LAB.json")
    mp.setattr(PL, "METHODS", tmp / "data" / "method_allocation.json")
    mp.setattr(PL, "DONATED", tmp / "data" / "donated.json")
    mp.setattr(PL, "MEMORY_DIR", tmp / "data" / "mathlab")
    mp.setattr(events, "PATH", tmp / "events.jsonl")
    donated: list[dict[str, Any]] = []
    mp.setattr(PC, "donate", lambda source, candidates, tests_run: donated.extend(candidates)
               or tmp / "intel.json")
    mp.setattr(PC, "donation_counts", lambda: {"donated": len(donated)})
    try:
        report = PL.run(budget_s=60.0, permutations=20, maths=["spectral", "control_theory"])
        second = PL.run(budget_s=20.0, permutations=20, physics=["turbulence"], maths=[])
    finally:
        R.set_path(None)
        mp.undo()
    return {"report": report, "second": second, "tmp": tmp, "panels": panels,
            "donated": donated}


# ------------------------------------------------------------------ B: falsifiers
def test_B_every_card_has_a_falsifier(world: dict[str, Any], full_run: dict[str, Any]) -> None:
    for card in world["cards"]:
        assert card.falsifier.strip(), card.card_id
        assert card.domain == "physics" and card.lineage["method"] == card.tradition
        assert set(card.units) == set(G.variables_in(card.expression))
    report = full_run["report"]
    assert report["cards"]["with_falsifier"] == report["cards"]["total"] > 0
    assert all(row["falsifier"] for row in report["cards"]["rows"])
    # an object whose interpretation names its own falsifier keeps it
    obj = world["objects"][0]
    obj.interpretation.falsifier = "the 24-bar dispersion ratio stops predicting on the next era"
    card = I.card_from_object(obj, domain="physics", method="t", civilization="A", seed=1)
    assert card.falsifier == obj.interpretation.falsifier


# ------------------------------------------------------------------ C: null factory
def test_C_the_null_factory_rejects_planted_nulls(world: dict[str, Any]) -> None:
    rows = I.null_factory(world["panel"], np.random.default_rng(3), n=9, permutations=30)
    judged = [r for r in rows if "passed" in r]
    assert len(judged) == 9
    rejected = sum(1 for r in judged if r["passed"] is False)
    assert rejected >= 8, rows
    fake = [r for r in judged if r["null"] == "fake_law"]
    assert all(abs(r["ic_in_sample"]) > 0.5 and r["passed"] is False for r in fake)


# ------------------------------------------------------------------ D: multiplicity
def test_D_multiplicity_is_charged_through_the_trial_ledger(world: dict[str, Any],
                                                            full_run: dict[str, Any]) -> None:
    cards = world["cards"]
    census = I.multiplicity_ledger(cards, {c.tradition: 12 for c in cards})
    assert census["status"] == "MEASURED" and census["n_raw"] == len(cards)
    assert census["n_families"] == 3
    for card in cards:
        charge = card.multiplicity_charge
        assert charge["n_effective"] > 0 and charge["charge_sigma"] > 0
        assert charge["declared_width"] == 12
        assert charge["ledger"].endswith("trial_ledger.py")
    report = full_run["report"]
    assert report["multiplicity"]["status"] == "MEASURED"
    assert report["multiplicity"]["n_effective"] >= 1.0
    assert all(row["multiplicity_charge"]["charge_sigma"] > 0 for row in report["cards"]["rows"])
    assert report["registry"]["trials"] and all(t["status"] == "RECORDED"
                                                for t in report["registry"]["trials"])


# ------------------------------------------------------------------ E: lockbox
def test_E_the_lockbox_is_sealed_before_and_verified_after(full_run: dict[str, Any]) -> None:
    panel = full_run["panels"][0]
    working, box = I.Lockbox.seal(panel)
    assert (working.n == panel.n - box.rows and box.rows == int(panel.n * I.LOCKBOX_SHARE)) or \
        working.n + box.rows == panel.n
    assert box.verify(panel)["untouched"] is True
    tampered = make_panel(61)
    tampered.epsilon = tampered.epsilon.copy()
    tampered.epsilon[-1] += 1.0
    assert box.verify(tampered)["untouched"] is False
    report = full_run["report"]
    assert report["lockbox"]["untouched"] is True
    assert all(p["rows_sealed"] > 0 for p in report["lockbox"]["panels"])
    assert report["lockbox"]["cards"]["respected"] is True
    assert report["lockbox"]["cards"]["breaches"] == []
    for row in report["cards"]["rows"]:
        assert row["evidence"]["n_train"] + row["evidence"]["n_test"] <= working.n


# ------------------------------------------------------------------ F: replication
def test_F_a_card_needs_a_second_independent_run_before_forward(world: dict[str, Any]) -> None:
    panel = world["panel"]
    passed = [c for c in world["cards"] if c.passed]
    card = passed[0] if passed else world["cards"][0]
    assert card.status == "PROPOSED", "no card is born FORWARD"
    I.consequence_engine(card, panel)
    I.peer_review(card, panel, seed=1, permutations=20)
    assert card.status in ("REVIEWED", "FAILED")
    card.status = "REVIEWED"
    card.passed = True
    # second run fails -> PROVISIONAL, never FORWARD
    import research.mathlab.institution as inst
    original = inst.B.judge

    def failing_judge(obj: Any, *a: Any, **k: Any) -> Any:
        out = original(obj, *a, **k)
        obj.passed = False
        return out

    inst.B.judge = failing_judge  # type: ignore[assignment]
    try:
        rep = I.replicate(card, panel, seed=2, permutations=20)
    finally:
        inst.B.judge = original  # type: ignore[assignment]
    assert rep["second"]["passed"] is False and rep["replicated"] is False
    assert card.status == "PROVISIONAL"
    # the other civilization found and passed the same canonical form -> replicated -> FORWARD
    card.status = "REVIEWED"
    rep = I.replicate(card, panel, seed=3, permutations=20,
                      other_civilization_passed={card.canonical})
    assert rep["cross_civilization"] is True and rep["replicated"] is True
    assert card.status == "FORWARD" and rep["runs"] == 2


def test_F_the_report_never_marks_forward_without_replication(full_run: dict[str, Any]) -> None:
    for row in full_run["report"]["cards"]["rows"]:
        if row["status"] == "FORWARD":
            assert row["replication"]["replicated"] is True
            assert row["review"]["verdict"] == "ACCEPT"
        if row["status"] == "PROVISIONAL":
            assert row["replication"]["replicated"] is False


# ------------------------------------------------------------------ G: credit
def test_G_credit_flows_back_to_the_methods(world: dict[str, Any], full_run: dict[str, Any]
                                            ) -> None:
    cards = world["cards"]
    for c in cards[:2]:
        c.status = "FORWARD"
        c.passed = True
    credit = I.credit_methods(cards, {c.tradition: 10 for c in cards}, {c.tradition: 3.0
                                                                         for c in cards})
    assert set(credit) == {c.tradition for c in cards}
    winner = cards[0].tradition
    assert credit[winner]["forward"] >= 1 and credit[winner]["trials"] == 10
    evolved = I.evolve_methods(credit, None)
    shares = {m: v["share"] for m, v in evolved["methods"].items()}
    assert sum(shares.values()) == pytest.approx(1.0, abs=1e-6)
    assert all(v >= evolved["floor"] for v in shares.values())
    assert shares[winner] >= max(shares.values()) - 1e-9
    tour = E.method_tournament(credit)
    assert tour.findings[0]["method"] == winner
    report = full_run["report"]
    assert set(report["method_credit"]) >= set(PHYSICS)
    alloc = json.loads((full_run["tmp"] / "data" / "method_allocation.json").read_text("utf-8"))
    assert alloc["pass_index"] == 2
    assert all(v["lifetime_trials"] >= 0 for v in alloc["methods"].values())
    assert report["engines"]["method_tournament"]["counts"]["methods"] >= len(PHYSICS)


# ------------------------------------------------------------------ H: Pareto
def test_H_the_pareto_front_is_non_dominated(world: dict[str, Any], full_run: dict[str, Any]
                                             ) -> None:
    cards = world["cards"]
    front = I.pareto_front(cards)
    rank0 = [c for c in cards if c.pareto["rank"] == 0]
    assert rank0 and front
    for a in rank0:
        for b in cards:
            dominated = (b.pareto["evidence_t"] >= a.pareto["evidence_t"]
                         and b.pareto["mdl_bits"] <= a.pareto["mdl_bits"]
                         and (b.pareto["evidence_t"] > a.pareto["evidence_t"]
                              or b.pareto["mdl_bits"] < a.pareto["mdl_bits"]))
            assert not dominated
    assert full_run["report"]["pareto_front"]
    assert any(r["rank"] == 0 for r in full_run["report"]["pareto_front"])


# ------------------------------------------------------------------ I: wiring proof
def test_I_the_wiring_proof_lists_every_scientist_and_engine(full_run: dict[str, Any]) -> None:
    proof = full_run["report"]["wiring_proof"]
    assert proof["complete"] is True
    assert set(proof["scientists"]) >= set(PHYSICS) | {"spectral", "control_theory"}
    assert set(proof["engines"]) == set(E.ENGINE_NAMES)
    assert proof["missing_scientists"] == [] and proof["missing_engines"] == []
    assert all(v["evaluated"] >= 0 and "status" in v for v in proof["scientists"].values())
    assert all(v["trials"] >= 0 for v in proof["engines"].values())
    # an organ that did not run is NAMED, never hidden
    partial = I.wiring_proof({"turbulence": {"proposed": 1}}, {}, list(PHYSICS),
                             list(E.ENGINE_NAMES))
    assert partial["complete"] is False and "criticality" in partial["missing_scientists"]
    assert len(partial["missing_engines"]) == len(E.ENGINE_NAMES)
    assert full_run["second"]["wiring_proof"]["complete"] is True


# ------------------------------------------------------------------ the rest of the institution
def test_consequence_engine_derives_and_tests_five_consequences(world: dict[str, Any]) -> None:
    card = world["cards"][0]
    out = I.consequence_engine(card, world["panel"])
    assert len(out) == 5 and card.predicted_consequences == [c["consequence"] for c in out]
    assert {c["status"] for c in out} <= {"PASS", "FAIL", "UNMEASURED"}


def test_peer_review_uses_independent_scorers_and_the_destroyer_kills_a_fake_law() -> None:
    panel = E.synthetic_panel(np.random.default_rng(4), planted="fake")
    fake = MathObject(kind="relationship", tradition="fake", expression=["z", "range", 24],
                      target=panel.target, horizon=panel.horizon, statement="fake")
    B.judge(fake, panel, distinct_forms=1, rng=np.random.default_rng(1), permutations=20)
    card = I.card_from_object(fake, domain="physics", method="fake", civilization="A", seed=1)
    card.passed = True                       # pretend the judge was fooled
    review = I.peer_review(card, panel, seed=1, permutations=30)
    assert review["independent_streams"] is True
    assert review["destroyer"]["kills"], review
    assert review["verdict"] == "REJECT" and card.status == "FAILED"
    assert review["discoverer"]["role"] == "discoverer"


def test_theorem_memory_persists_and_the_failure_scientist_writes_negative_knowledge(
        tmp_path: Path, world: dict[str, Any]) -> None:
    memory = I.TheoremMemory(tmp_path / "mem")
    cards = world["cards"]
    for card in cards:
        card.status = "FAILED"
        memory.record(card)
    # A region is (tradition, kind, target): the LAST card's region is failed a second time, so
    # the failure scientist has a region that only ever fails and nothing proven in it.
    repeat = cards[-1]
    memory.record(repeat)
    proven = cards[0]
    proven.status = "FORWARD"
    assert memory.record(proven) == "proven"
    assert memory.known(proven.canonical) in ("PROVEN", "FAILED")
    assert memory.known("nothing(never, 1)") is None
    graph = memory.graph()
    assert graph["edges"] == len(cards) + 2 and graph["failed"] == len(cards) + 1
    negative = I.failure_scientist(memory, min_failures=2)
    region = (repeat.tradition, repeat.kind, repeat.target)
    assert [r for r in negative if (r["tradition"], r["kind"], r["target"]) == region], negative
    assert all(r["verdict"] == "EXHAUSTED_REGION" for r in negative)
    assert all(r["failures"] >= 2 for r in negative)
    again = I.failure_scientist(memory, min_failures=2)
    assert again == [], "negative knowledge is written once per region"
    assert (tmp_path / "mem" / "lineage.jsonl").exists()


def test_pit_states_transfer_causal_and_experiment_design(world: dict[str, Any]) -> None:
    panel = world["panel"]
    card = world["cards"][0]
    pit = I.pit_check(card, panel)
    assert pit["clean"] is True and all(v != "UNMEASURED" for v in pit["stamps"].values())
    labels = I.state_discovery(panel, k=3)
    assert set(labels.tolist()) <= {0, 1, 2}
    states = I.states_of(card, panel, labels)
    assert "ic_by_state" in states
    transfer = I.cross_market(card, [make_panel(52, target="GBPUSD")])
    assert transfer["status"] == "MEASURED"
    causal = I.causal_scientist(card, panel, seed=1, n_perm=20)
    assert causal.get("verdict") or causal.get("status") == "UNMEASURED"
    design = I.experiment_design(world["cards"], {"era": 1, "regime": "low", "session": "ny"})
    assert design["next_card"]["card_id"] and design["next_slice"]["era"] == 1


def test_event_row_and_second_pass_rotate_and_accumulate(full_run: dict[str, Any]) -> None:
    rows = [json.loads(line) for line in
            (full_run["tmp"] / "events.jsonl").read_text("utf-8").splitlines()]
    assert any(r["kind"] == "MATH_CARDS_JUDGED" and r["leg"] == "physics_lab" for r in rows)
    second = full_run["second"]
    assert second["method_allocation"]["pass_index"] == 2
    assert second["theorem_memory"]["failed"] + second["theorem_memory"]["proven"] >= \
        full_run["report"]["cards"]["total"]
    assert second["null_factory"]["rejection_rate"] >= 0.5
