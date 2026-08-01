"""THE SEVEN ANCESTOR ORGANS -- genealogy, breeding, theory, lab, benchmarks, invention, markets.

WHY THESE EXIST BEFORE THERE ARE ANCESTORS. Furniture before moving in: the 420 dead candidates
already carry parentage, and provenance is never recorded retroactively. Every day the graph is
missing is a day of lineage written into a log nobody structured.

WHAT THE TESTS DEFEND. Each of these organs has one failure mode that produces confident,
plausible output instead of an error, and that is what is pinned here:

  genealogy   ranking lines by RAW survivor count measures the generator's habits, not the market
  breeding    two near-identical parents make a paraphrase that spends a gauntlet slot to prove it
  theory      inducing a principle from zero survivors is prose that reads exactly like a theory
  laboratory  power with no false-positive rate makes a permissive screen look sensitive
  invention   a 20- and a 24-period z-score of one quantity is ONE bet the desk will count twice
  markets     majority vote caps panel accuracy at the average seat's, permanently
"""

from __future__ import annotations

import numpy as np
import pytest

from libs.hypmax.genealogy import (
    BREEDING_MIN_STAGE,
    INCEST_MAX,
    Lineage,
    Specimen,
    breed,
    diversity,
    effective_population,
    fertility,
    induce_theory,
    lineage_report,
    similarity,
)
from libs.hypmax.invention import (
    PRIMITIVES,
    Feature,
    invent,
    is_degenerate,
    redundant_with,
)
from libs.hypmax.laboratory import (
    detection_floor,
    measure_screen,
    no_edge_path,
    planted_edge_path,
)

# ============================================================== 1. ALPHA GENEALOGY


def _pop() -> Lineage:
    lin = Lineage()
    for i in range(200):                       # a prolific but barren family
        lin.add(Specimen(f"a{i}", family="momentum", lens="crowded", stage=1))
    for i in range(2):
        lin.add(Specimen(f"a2{i}", family="momentum", lens="crowded", stage=4))
    for i in range(6):                         # a small family that keeps getting somewhere
        lin.add(Specimen(f"m{i}", family="microstructure", lens="moat", stage=4 if i < 2 else 1))
    return lin


def test_a_small_fertile_line_outranks_a_prolific_barren_one() -> None:
    """THE ADJUSTMENT THAT MATTERS. Raw survivor count hands the top spot to whatever the
    generator emitted most of -- a measure of its habits, not of the market."""
    rows = {r["family"]: r for r in fertility(_pop())}
    assert rows["microstructure"]["fertility"] > rows["momentum"]["fertility"]
    assert rows["microstructure"]["n"] < rows["momentum"]["n"]


def test_one_lucky_first_attempt_does_not_become_the_most_fertile_ground() -> None:
    """Shrinkage toward the population rate. Without it a single deep run on a single attempt
    reads as a 100% hit rate and captures the whole generation budget."""
    lin = _pop()
    lin.add(Specimen("lucky", family="oneshot", stage=9))
    rows = {r["family"]: r for r in fertility(lin)}
    assert rows["oneshot"]["raw_rate"] == 1.0
    assert rows["oneshot"]["fertility"] < rows["microstructure"]["fertility"]


def test_zero_survivors_is_reported_as_a_fact_about_the_ground() -> None:
    """With no survivors the graph still ranks by how FAR lines got, which is the only signal
    available and is strictly better than allocating generation uniformly."""
    r = lineage_report(_pop())
    assert r["survivors"] == 0
    assert "MEASUREMENT of the ground" in r["note"]
    assert r["reached_breeding_stage"] == 4


def test_ancestry_survives_a_cycle_in_the_graph() -> None:
    """A malformed import that makes a specimen its own ancestor must not hang the report."""
    lin = Lineage()
    lin.add(Specimen("x", parents=("y",)))
    lin.add(Specimen("y", parents=("x",)))
    assert set(lin.ancestors("x")) == {"x", "y"}


# ============================================================== 2. BREEDING


def _parent(i: int, *, terms: tuple[str, ...], stage: int = 5) -> Specimen:
    return Specimen(f"p{i}", family="f", mechanism=f"m{i}", terms=terms, stage=stage)


def test_near_identical_parents_are_refused() -> None:
    """A child of two paraphrases is a third paraphrase, and it costs a gauntlet slot to learn
    that. The refusal is returned, not silently dropped."""
    a = Specimen("a", mechanism="m", terms=("funding", "basis", "carry"), stage=5)
    b = Specimen("b", mechanism="m", terms=("funding", "basis", "carry"), stage=5)
    assert similarity(a, b) > INCEST_MAX
    out = breed([a, b])
    assert out["children"] == []
    assert out["n_rejected"] == 1
    assert "paraphrase" in out["rejected_pairings"][0]["reason"]


def test_breeding_rights_are_earned() -> None:
    """Without a stage floor the population converges on whatever the generator emits most."""
    shallow = [_parent(i, terms=(f"t{i}", "shared"), stage=BREEDING_MIN_STAGE - 1)
               for i in range(4)]
    assert breed(shallow)["children"] == []
    assert breed(shallow)["ineligible"] == 4


def test_a_child_inherits_no_credibility_whatsoever() -> None:
    """THE LAUNDERING RISK. Both parents reaching stage 5 says nothing about the child; carrying
    stage forward would let a breeding programme walk a weak idea past the funnel."""
    kids = breed([_parent(1, terms=("depth", "queue")),
                  _parent(2, terms=("funding", "basis"))])["children"]
    assert kids
    assert all(k.stage == 0 and not k.survived for k in kids)
    assert all(k.generation == 1 for k in kids)


def test_breeding_is_deterministic_so_the_same_pool_never_re_bills() -> None:
    pool = [_parent(i, terms=(f"t{i}", f"u{i}")) for i in range(4)]
    a = [c.id for c in breed(pool)["children"]]
    b = [c.id for c in breed(pool)["children"]]
    assert a == b and len(set(a)) == len(a)


def test_a_converged_population_raises_a_diversity_warning() -> None:
    """The failure mode of every breeding programme, and it arrives gradually."""
    pool = [Specimen(f"s{i}", mechanism="m", terms=("funding", "basis", "carry"), stage=5)
            for i in range(8)]
    out = breed(pool)
    assert out["children"] == []
    assert out["n_rejected"] == 28, "every pairing of a converged pool is a paraphrase"
    assert out["diversity_warning"]


def test_effective_population_sees_through_paraphrases() -> None:
    """200 paraphrases have an effective size near 1. A desk counting 200 believes it explores."""
    clones = [Specimen(f"c{i}", terms=("a", "b", "c")) for i in range(20)]
    varied = [Specimen(f"v{i}", terms=(f"a{i}", f"b{i}", f"c{i}")) for i in range(20)]
    assert effective_population(clones) < effective_population(varied)
    assert diversity(clones) < diversity(varied)


# ============================================================== 3. THEORY INDUCTION


def test_theory_is_dormant_with_no_survivors_and_names_what_arms_it() -> None:
    """Inducing a principle from zero edges is not induction. It produces confident prose that
    reads exactly like a theory, which is worse than saying nothing."""
    d = induce_theory([Specimen(f"s{i}", survived=False) for i in range(50)])
    assert d["state"] == "DORMANT"
    assert "Arms automatically" in d["note"]


def test_theory_arms_on_a_data_condition_and_separates_invariant_from_varying() -> None:
    survivors = [Specimen(f"s{i}", mechanism="forced_flow", survived=True,
                          terms=("constraint", "deadline", f"venue{i}")) for i in range(3)]
    d = induce_theory(survivors)
    assert d["state"] == "ACTIVE"
    t = d["theories"][0]
    assert set(t["invariant_terms"]) == {"constraint", "deadline"}
    assert t["next_predictions"]
    assert "enter the funnel at the full bar" in t["caution"]


def test_two_survivors_are_a_pair_not_a_principle() -> None:
    survivors = [Specimen(f"s{i}", mechanism="x", survived=True, terms=("a",)) for i in range(2)]
    assert induce_theory(survivors)["state"] == "DORMANT"


# ============================================================== 4-5. THE LABORATORY


def _ic_screen(threshold: float):
    """A screen that fires when |Pearson correlation| clears a threshold."""
    def screen(sig: np.ndarray, fwd: np.ndarray) -> bool:
        if sig.std() == 0 or fwd.std() == 0:
            return False
        return abs(float(np.corrcoef(sig, fwd)[0, 1])) > threshold
    return screen


def test_the_null_world_really_has_no_edge() -> None:
    """A generator that leaked signal into the null would make every false-positive rate a lie."""
    sig, fwd = no_edge_path(20_000, seed=3)
    assert abs(float(np.corrcoef(sig, fwd)[0, 1])) < 0.03


def test_a_planted_edge_is_present_at_the_strength_requested() -> None:
    """Strength is stated in return-variance terms so the detection floor is interpretable:
    strength 0.04 should show up as an IC near 0.2."""
    sig, fwd = planted_edge_path(20_000, strength=0.04, seed=3)
    assert float(np.corrcoef(sig, fwd)[0, 1]) == pytest.approx(0.2, abs=0.03)


def test_power_and_false_positive_rate_are_always_measured_together() -> None:
    """A screen that says yes to everything has power 1.0 and is worthless. Reporting power
    alone is how a desk convinces itself a permissive screen is a sensitive one."""
    always = measure_screen(lambda s, f: True, strength=0.2, trials=30, n=200)
    assert always.power == 1.0
    assert always.false_positive_rate == 1.0
    assert not always.usable


def test_a_real_screen_detects_a_strong_edge_and_not_a_null() -> None:
    r = measure_screen(_ic_screen(0.10), strength=0.30, trials=40, n=400)
    assert r.power > 0.9 and r.false_positive_rate < 0.15 and r.usable


def test_the_detection_floor_is_the_weakest_edge_reliably_found() -> None:
    """THE UNGAMEABLE PROGRESS METRIC. Hypothesis count rises by generating more; survivor count
    rises by lowering the bar. This falls only when the desk genuinely gets better."""
    d = detection_floor(_ic_screen(0.10), trials=30, n=400)
    assert d["detection_floor"] is not None
    assert d["blatant_check"] == ""
    assert "INVISIBLE to this screen" in d["note"]
    strengths = [row["strength"] for row in d["sweep"] if row["usable"]]
    assert d["detection_floor"] == min(strengths)


def test_a_screen_that_finds_nothing_is_named_as_a_broken_instrument() -> None:
    """THE 420/420 QUESTION. 'The candidates were worthless' and 'the gauntlet cannot detect an
    edge it is handed' fit the same observation and demand opposite responses."""
    d = detection_floor(lambda s, f: False, trials=10, n=200)
    assert d["detection_floor"] is None
    assert "defect in the instrument" in d["note"]
    assert "FAILS ON THE EASIEST CASE" in d["blatant_check"]


def test_the_lab_is_deterministic_under_a_seed() -> None:
    a = measure_screen(_ic_screen(0.1), strength=0.1, trials=20, n=200, seed=7)
    b = measure_screen(_ic_screen(0.1), strength=0.1, trials=20, n=200, seed=7)
    assert a == b


# ============================================================== 6. FEATURE INVENTION


def test_the_guards_refuse_a_large_share_of_the_composed_space() -> None:
    """The screen's time is the scarcest thing here, so a candidate that cannot possibly work
    must never reach it. Nearly half the composed space is refused on arithmetic alone, before
    any data is touched -- the cross-class rule doing most of the work."""
    out = invent()
    assert out["composed"] > 3000
    assert out["n_degenerate"] / out["composed"] > 0.40
    same_class = [d for d in out["degenerate_examples"] + [{"reason": ""}]
                  if "same observation read twice" in d.get("reason", "")]
    assert out["n_degenerate"] > 1000 or same_class


def test_moat_derived_features_lead_the_ranking() -> None:
    """Ranked by REPLICATION COST, not novelty: two equally novel compositions are not equally
    defensible once a competitor reads the same public feed."""
    kept = invent()["kept"]
    assert kept[0].moat_derived
    assert sum(1 for f in kept[:20] if f.moat_derived) >= 18


def test_degenerate_compositions_are_caught_before_any_data_is_touched() -> None:
    assert is_degenerate(Feature("x", "imbalance", "zscore", 1))
    assert is_degenerate(Feature("x", "imbalance", "accel", 2))
    assert is_degenerate(Feature("x", "imbalance", "rank", 20, interaction="basis"))
    assert is_degenerate(Feature("x", "imbalance", "delta", 20, interaction="imbalance"))
    assert not is_degenerate(Feature("x", "imbalance", "zscore", 20))


def test_an_adjacent_window_is_a_duplicate_not_a_new_horizon() -> None:
    """A 20- and a 24-period z-score of one quantity is ONE bet. The screen will find the same
    edge in both and the desk will believe it has a diversified pair."""
    have = [Feature("a", "imbalance", "zscore", 20)]
    assert redundant_with(Feature("b", "imbalance", "zscore", 24), have) is not None
    assert redundant_with(Feature("c", "imbalance", "zscore", 240), have) is None


def test_an_interaction_is_symmetric_under_its_operands() -> None:
    """A x B and B x A are one feature. Fingerprinting them apart doubles the candidate count
    with no new information at all."""
    ab = Feature("ab", "imbalance", "zscore", 20, interaction="basis")
    ba = Feature("ba", "basis", "zscore", 20, interaction="imbalance")
    assert ab.fingerprint == ba.fingerprint


def test_the_rare_transforms_are_ranked_above_the_common_ones() -> None:
    """accel and persistence are the two nobody computes, which is exactly where an unclaimed
    edge would still be sitting."""
    kept = invent()["kept"]
    assert kept[0].transform in ("accel", "persistence")


def test_every_primitive_declares_whether_it_is_proprietary() -> None:
    """Replication cost is the ranking key, so an unlabelled primitive would silently rank as
    public and the moat advantage would leak away one omission at a time."""
    assert all(isinstance(c, str) and isinstance(m, bool) for c, m in PRIMITIVES.values())
    assert sum(m for _, m in PRIMITIVES.values()) == 7, "the seven moat reconstructions"
