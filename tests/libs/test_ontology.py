"""The research ontology and the four emergence levers.

WHY AN ONTOLOGY AND NOT A CHECKLIST. A checklist is consumed as it is worked; a search space that
spawns new regions per discovery compounds. The desk has generated 420 hypotheses and cannot say
which regions they covered, so it cannot tell "we tested this and it failed" from "we never
looked" -- and those demand opposite responses. Coverage is the single piece of information that
makes 420 failures INFORMATIVE rather than merely discouraging.

The load-bearing test here is the coverage/exhaustion distinction. Conflating them is the trap:
30 attempts with 2 survivors is a RICH region worth mining harder, 30 with none is barren, and a
system that suppressed both equally would abandon its best ground.
"""

from __future__ import annotations

import pytest

from libs.hypmax.emergence import (
    CLUSTER_MIN,
    Observation,
    PropagationRule,
    WeakSignalRegistry,
    cluster_weak_signals,
    counterfactual_ready,
    opportunity_cost_of_ignorance,
    propagate,
)
from libs.hypmax.ontology import (
    DOMAINS,
    SEED_QUESTIONS,
    Ontology,
    coverage,
    exhaustion,
    map_dataset,
    priority,
    rank_frontier,
    record_outcome,
    spawn_second_order,
)

# ------------------------------------------------------------------ the question set


def test_the_seed_set_covers_every_declared_domain() -> None:
    used = {q.domain for q in SEED_QUESTIONS}
    assert used == set(DOMAINS), f"domains with no questions: {set(DOMAINS) - used}"


def test_question_ids_are_unique() -> None:
    ids = [q.id for q in SEED_QUESTIONS]
    assert len(ids) == len(set(ids))


def test_the_frontier_is_large_enough_to_be_a_space_not_a_list() -> None:
    assert len(SEED_QUESTIONS) > 150


# ------------------------------------------------------------------ coverage vs exhaustion


def test_coverage_saturates_rather_than_growing_linearly() -> None:
    """The 1st attempt at untouched ground teaches more than the 30th. Linear coverage would keep
    an over-mined region looking fresh long after it stopped paying."""
    assert coverage(0) == 0.0
    assert coverage(5) < coverage(25) < coverage(100) < 1.0
    assert coverage(25) - coverage(20) < coverage(5) - coverage(0)


def test_a_rich_region_is_never_marked_exhausted() -> None:
    """THE DISTINCTION THAT MATTERS. Explored is not the same as barren, and a system that
    suppressed both would abandon exactly the ground that is paying."""
    assert exhaustion(30, survivors=2) == 0.0
    assert exhaustion(30, survivors=0) > 0.5


def test_a_rich_region_outranks_a_barren_one_after_equal_effort() -> None:
    state: dict = {}
    for _ in range(30):
        record_outcome(state, "ML.1", survived=False)
    for _ in range(28):
        record_outcome(state, "STRUCT.7", survived=False)
    for _ in range(2):
        record_outcome(state, "STRUCT.7", survived=True)
    rows = {r["id"]: r for r in rank_frontier(state=state)}
    assert rows["STRUCT.7"]["priority"] > rows["ML.1"]["priority"] * 5


def test_exhaustion_never_reaches_zero_priority() -> None:
    """A region can be reopened by a new dataset -- negative knowledge is reversible here."""
    q = next(q for q in SEED_QUESTIONS if q.id == "ML.1")
    assert priority(q, attempts=10_000, survivors=0) > 0.0


# ------------------------------------------------------------------ ranking


def test_data_questions_lead_an_unexplored_frontier() -> None:
    """Optionality is why: one new dataset can spawn a whole family of hypotheses that were
    previously impossible to even state. A desk ranking on EV alone under-invests in exactly the
    questions that grow its future capacity."""
    assert rank_frontier(limit=5)[0]["id"].startswith("DATA.")


def test_ev_and_optionality_are_scored_separately() -> None:
    """Execution: high EV, low optionality -- saves money forever, opens no new space.
    Data inverts it. Collapsing them into one number would lose the distinction."""
    _, ev_exec, opt_exec = DOMAINS["EXEC"]
    _, _, opt_data = DOMAINS["DATA"]
    assert ev_exec > 0.5 and opt_exec < 0.5
    assert opt_data > opt_exec * 2


def test_priority_is_multiplicative_so_novelty_alone_is_not_a_reason() -> None:
    low = next(q for q in SEED_QUESTIONS if q.domain == "ML")
    high = next(q for q in SEED_QUESTIONS if q.domain == "DATA")
    assert priority(high, 0, 0) > priority(low, 0, 0)


# ------------------------------------------------------------------ self-expansion


def test_a_survivor_spawns_regions_that_did_not_exist() -> None:
    """This is what makes it compound rather than deplete."""
    o = Ontology()
    before = len(o)
    o.add(spawn_second_order(SEED_QUESTIONS[0], "depth replenishment asymmetry"))
    assert len(o) == before + 4
    assert all(q.generation == 1 for q in o.questions[-4:])
    assert all(q.parent == SEED_QUESTIONS[0].id for q in o.questions[-4:])


def test_spawned_questions_are_prioritised_higher_for_the_same_state() -> None:
    """A second-order question was EARNED: the desk already has evidence its neighbourhood
    contains something."""
    parent = SEED_QUESTIONS[0]
    child = spawn_second_order(parent, "x")[0]
    assert priority(child, 0, 0) > priority(parent, 0, 0)


def test_spawning_is_idempotent_by_id() -> None:
    o = Ontology()
    qs = spawn_second_order(SEED_QUESTIONS[0], "x")
    o.add(qs)
    n = len(o)
    o.add(qs)
    assert len(o) == n


def test_a_new_dataset_maps_to_the_questions_it_reopens() -> None:
    """Arrival of data must automatically revive questions -- a missed match means a dataset
    lands and nobody notices it reopens ground written off as exhausted."""
    hits = map_dataset("moat_depth", "order book depth snapshots, hidden liquidity, queue")
    assert len(hits) >= 5
    assert any(h.startswith("EXEC.") for h in hits)


def test_an_unrelated_dataset_maps_to_little() -> None:
    assert len(map_dataset("zzz_unrelated", "nothing to do with anything")) < 5


def test_failures_update_the_region_they_came_from() -> None:
    """The more valuable update, and the one a naive design drops: failures are what turn
    'we never looked' into 'we looked and it is barren'."""
    st: dict = {}
    record_outcome(st, "ALPHA.1", survived=False)
    record_outcome(st, "ALPHA.1", survived=True)
    assert st["ALPHA.1"] == {"attempts": 2, "survivors": 1}


# ------------------------------------------------------------------ weak signals


def test_converging_weak_signals_cluster_into_something_promotable() -> None:
    """Individually weak observations are exactly what a per-observation significance bar
    destroys by construction."""
    obs = [Observation(f"obs {i}", ("liquidity",), f"src{i}") for i in range(4)]
    c = cluster_weak_signals(obs)
    assert c and c[0]["n"] == 4
    assert "INDEPENDENT sources" in c[0]["note"]


def test_one_observer_repeating_is_not_a_pattern() -> None:
    obs = [Observation(f"obs {i}", ("liquidity",), "same_source") for i in range(5)]
    assert "may be one observer repeating" in cluster_weak_signals(obs)[0]["note"]


def test_a_lone_observation_never_clusters() -> None:
    assert cluster_weak_signals([Observation("x", ("y",), "s")]) == []
    assert CLUSTER_MIN >= 3


def test_silence_counts_as_information() -> None:
    """A repo that stopped, a topic that vanished, a market that went quiet. Systematically
    under-recorded because nobody files a report saying 'it stopped happening'."""
    obs = [Observation(f"stopped {i}", ("negative",), f"s{i}", negative=True) for i in range(3)]
    c = cluster_weak_signals(obs)[0]
    assert c["n_negative"] == 3
    assert "ABSENCES" in c["silence"]


def test_registry_accumulates_and_is_never_pruned() -> None:
    r = WeakSignalRegistry()
    for i in range(4):
        r.add(Observation(f"o{i}", ("t",), f"s{i}"))
    assert len(r.observations) == 4 and r.clusters()[0]["n"] == 4


# ------------------------------------------------------------------ propagation


def test_a_rule_reaches_every_digger_but_its_discoverer() -> None:
    """One digger learning is linear; seven inheriting is the only reason a fleet beats one good
    miner."""
    fleet = [f"d{i}" for i in range(7)]
    p = propagate([PropagationRule("op", "d0", measured_lift=0.4)], fleet)
    assert p["pending_adoptions"] == 6
    assert "d0" not in p["assignments"]


def test_an_unmeasured_rule_is_flagged_not_hidden() -> None:
    """An unproven rule must not pass as proven just because it propagated widely."""
    p = propagate([PropagationRule("guess", "d0")], ["d0", "d1"])
    assert p["unmeasured_rules"] == ["guess"]
    assert "adopted on reasoning alone" in p["caution"]


# ------------------------------------------------------------------ ignorance & counterfactual


def test_deferral_is_not_free_and_compounds_linearly() -> None:
    """A queue ranked only by what to test treats waiting as costless. On a desk whose north star
    reads 0.00 per 45 days, deferral is the dominant term."""
    a = opportunity_cost_of_ignorance(0.149, days_deferred=1)["cost_of_ignorance"]
    b = opportunity_cost_of_ignorance(0.149, days_deferred=30)["cost_of_ignorance"]
    assert b == pytest.approx(a * 30, rel=1e-3)


def test_counterfactual_is_dormant_until_a_discovery_exists() -> None:
    """Answering 'was this inevitable?' from zero discoveries is fabrication dressed as
    diligence. It arms from a DATA condition, not a human remembering."""
    d = counterfactual_ready(0)
    assert d["state"] == "DORMANT" and "Arms automatically" in d["note"]
    assert counterfactual_ready(3)["state"] == "ACTIVE"
