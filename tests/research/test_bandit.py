"""The tree of bandits: two levels, a protected floor at every node, and the temperature ladder.

Four properties the flat eleven-arm allocator could not state, each measured absent on
2026-09-23 (Tier-1 W15):

  * THE ALLOCATION IS A TREE. GLOBAL -> {exploit, adjacent, cold} -> arms. Both levels carry
    floors and both hold at the same time; the split always totals one, with the rounding
    residual handed to the highest-scoring node rather than evaporating.
  * THE SCORE IS WRITTEN OUT. Score_j = E[dg_j] + beta.sqrt(ln N / n_j) + lambda.Novelty_j, with
    every term published. A never-pulled arm draws the largest UCB bonus there is, and a
    higher-novelty arm with the SAME expected gain is funded above its twin.
  * NOVELTY IS READ, NOT INVENTED. It comes from the novelty gate's own artifact, and when the
    gate publishes no attribution every arm carries 0.0 -- neutral, so an unmeasured term can
    never reorder a budget.
  * THE SIX DISCOVERY TEMPERATURES ARE COUNTED. Proposals and measured compute seconds per
    temperature, an IDLE verdict when a temperature produced neither, and unclassified sources
    named rather than bucketed into a temperature that would inflate the concurrency count.

Floors ratchet UP only (L1.50): every floor the flat allocator protected is still protected
here, and a policy that declares a LOWER arm floor cannot lower it.
"""
from __future__ import annotations

import json
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import numpy as np
import pytest

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from libs.research import bandit  # noqa: E402


def _flat_evidence(**over: dict[str, Any]) -> dict[str, dict[str, Any]]:
    ev: dict[str, dict[str, Any]] = {
        a: {"born": 0, "failed": 0, "certified": 0, "alpha": 1.9, "beta": 20.1,
            "p_survivor": 0.0864, "worth": 1.0, "cost": float(sum(bandit.COST[a])),
            "score_mean": round(1.0 * 0.0864 / float(sum(bandit.COST[a])), 5)}
        for a in bandit.ARMS}
    for a, patch in over.items():
        ev[a].update(patch)
    return ev


def _uniform_gain() -> dict[str, float]:
    return dict.fromkeys(bandit.ARMS, 1.0 / len(bandit.ARMS))


# ------------------------------------------------------------------------ the tree and its floors
def test_the_policys_group_floors_are_all_still_there_and_the_arm_node_has_its_own() -> None:
    """Every floor the flat allocator protected survives, and the arm level gains its own."""
    nf = bandit.node_floors(bandit.allocation_policy())
    assert nf["status"] == "DECLARED"
    assert nf["groups"] == {"exploit": 0.4, "exploration": 0.4, "cold": 0.1, "adjacent": None}
    assert set(nf["arms"]) == set(bandit.ARMS)
    assert all(v == pytest.approx(bandit.EXPLORE / len(bandit.ARMS)) for v in nf["arms"].values())
    # No ceiling is ever applied: the declared upper bounds are reported and never enforced.
    assert nf["ceilings_declared_not_enforced"] == {"exploit": 0.6, "exploration": 0.6}


def test_a_declared_arm_floor_can_only_raise_it() -> None:
    policy = dict(bandit.allocation_policy())
    policy["arm_floors"] = {"new_mechanism": 0.25, "external_screen": 0.0001}
    nf = bandit.node_floors(policy)
    assert nf["arms"]["new_mechanism"] == pytest.approx(0.25)
    assert nf["arms"]["external_screen"] == pytest.approx(bandit.ARM_FLOOR)   # not lowered
    assert nf["arm_floors_raised_by_policy"] == ["new_mechanism"]


def test_the_tree_respects_every_floor_at_both_levels_and_allocates_all_of_it() -> None:
    """Evidence piled on one exploit arm and a graveyard on both cold arms would starve the
    cold group and every unfunded arm; both levels of floor hold, and the budget totals one."""
    ev = _flat_evidence(
        exit_improvement={"failed": 20, "certified": 30, "alpha": 31.9, "beta": 21.1},
        new_mechanism={"failed": 400, "certified": 0, "alpha": 1.9, "beta": 420.1},
        alt_data_hypothesis={"failed": 400, "certified": 0, "alpha": 1.9, "beta": 420.1},
    )
    audit: dict[str, Any] = {}
    sh = bandit.allocate(ev, np.random.default_rng(0), novelty={}, audit=audit)
    tree = audit["tree"]
    groups = bandit.group_shares(sh)
    assert groups["cold"] >= 0.1 - 1e-6
    assert groups["exploration"] >= 0.4 - 1e-6
    assert groups["exploit"] >= 0.4 - 1e-6
    assert all(sh[a] >= bandit.ARM_FLOOR - 1e-6 for a in bandit.ARMS), sh
    assert sum(sh.values()) == pytest.approx(1.0, abs=1e-3)
    assert tree["allocated"] == pytest.approx(1.0, abs=1e-6)
    assert tree["status"] == "LIFTED_TO_FLOOR"
    assert {x["group"] for x in tree["group_lifts"]} >= {"cold", "exploration"}
    assert sh["exit_improvement"] == max(sh.values())            # evidence still leads
    # The group budgets and the arm shares are the SAME allocation seen at two levels.
    for g in bandit.GROUPS:
        members = [a for a in bandit.ARMS if bandit.group_of(a) == g]
        assert tree["groups"][g]["share"] == pytest.approx(sum(sh[a] for a in members), abs=2e-3)


def test_the_residual_goes_to_the_best_node_so_nothing_is_left_unallocated() -> None:
    scores = bandit.tree_scores(_uniform_gain(), _flat_evidence(), novelty={})
    scores["failure_derived"]["score"] = 0.5                    # the unambiguous best node
    share, tree = bandit.allocate_tree(scores, bandit.allocation_policy())
    assert tree["residual_to"] == "failure_derived"
    assert sum(share.values()) == pytest.approx(1.0, abs=1e-9)
    assert tree["allocated"] == pytest.approx(1.0, abs=1e-9)


def test_an_infeasible_arm_floor_set_is_reported_never_silently_dropped() -> None:
    """Floors that cannot all fit inside a node's budget split it by the floors and say so."""
    alloc, lifted = bandit._split_with_floors({"a": 1.0, "b": 3.0}, 0.10, {"a": 0.08, "b": 0.08})
    assert sum(alloc.values()) == pytest.approx(0.10)
    assert len(lifted) == 2 and all("exhaust" in str(x["why"]) for x in lifted)


# ------------------------------------------------------------------------------- the score's terms
def test_a_never_pulled_arm_draws_the_largest_ucb_bonus_there_is() -> None:
    ev = _flat_evidence(external_screen={"failed": 900, "certified": 100},
                        mutate_survivor={"failed": 90, "certified": 10})
    sc = bandit.tree_scores(_uniform_gain(), ev, novelty={})
    cold = sc["new_mechanism"]                                   # nothing has judged it
    assert cold["never_pulled"] is True and cold["n_pulls"] == 0
    assert cold["ucb_bonus"] > sc["mutate_survivor"]["ucb_bonus"] > 0.0
    assert sc["mutate_survivor"]["ucb_bonus"] > sc["external_screen"]["ucb_bonus"] > 0.0
    assert cold["ucb_bonus"] == max(r["ucb_bonus"] for r in sc.values())
    # sqrt(ln N / n_j), in units of the mean gain -- the formula, not an approximation of it.
    import math
    gbar = 1.0 / len(bandit.ARMS)
    n_total = 1100
    assert sc["mutate_survivor"]["ucb_bonus"] == pytest.approx(
        bandit.BETA_UCB * math.sqrt(math.log(n_total) / 100) * gbar, abs=1e-6)
    assert sc["new_mechanism"]["score"] > sc["external_screen"]["score"]


def test_no_pulls_anywhere_means_no_ucb_bonus_for_anyone() -> None:
    sc = bandit.tree_scores(_uniform_gain(), _flat_evidence(), novelty={})
    assert {r["ucb_bonus"] for r in sc.values()} == {0.0}
    assert all(r["never_pulled"] for r in sc.values())


def test_a_higher_novelty_arm_with_the_same_expected_gain_gets_more() -> None:
    """Two arms in the SAME group with identical gain and identical pulls; only novelty differs."""
    ev = _flat_evidence()
    gain = _uniform_gain()
    nov = dict.fromkeys(bandit.ARMS, 0.0)
    nov["new_mechanism"] = 0.9                       # cold group; its twin is alt_data_hypothesis
    sc = bandit.tree_scores(gain, ev, novelty=nov)
    assert sc["new_mechanism"]["novelty"] == 0.9
    assert sc["new_mechanism"]["novelty_bonus"] > 0.0
    assert sc["alt_data_hypothesis"]["novelty_bonus"] == 0.0
    assert sc["new_mechanism"]["expected_gain"] == sc["alt_data_hypothesis"]["expected_gain"]
    assert sc["new_mechanism"]["score"] > sc["alt_data_hypothesis"]["score"]
    share, _ = bandit.allocate_tree(sc, bandit.allocation_policy())
    assert share["new_mechanism"] > share["alt_data_hypothesis"]
    flat, _ = bandit.allocate_tree(
        bandit.tree_scores(gain, ev, novelty={}), bandit.allocation_policy())
    assert share["new_mechanism"] > flat["new_mechanism"]        # novelty ADDS, never subtracts


def test_the_score_is_the_sum_of_its_three_published_terms() -> None:
    ev = _flat_evidence(external_screen={"failed": 40, "certified": 10})
    nov = dict.fromkeys(bandit.ARMS, 0.5)
    sc = bandit.tree_scores(_uniform_gain(), ev, novelty=nov)
    for row in sc.values():
        assert row["score"] == pytest.approx(
            row["expected_gain"] + row["ucb_bonus"] + row["novelty_bonus"], abs=1e-6)


# ------------------------------------------------------------------------------------- novelty
def test_novelty_is_read_from_the_gates_own_artifact_per_arm(tmp_path: Path) -> None:
    doc = {"n_screened": 100, "n_novel": 40,
           "by_source": {"orthogonal_sweep": 0.9, "deepening": 0.1}}
    got = bandit.novelty_by_arm(doc)
    assert got["status"] == "MEASURED" and "by_source" in got["basis"]
    assert got["by_arm"]["new_mechanism"] == pytest.approx(0.9)   # orthogonal_sweep -> new_mech
    assert got["by_arm"]["mutate_survivor"] == pytest.approx(0.1)
    assert got["by_arm"]["external_screen"] == pytest.approx(0.4)  # the pooled rate, named
    assert got["arms_on_pooled"] and "external_screen" in got["arms_on_pooled"]
    # a by_arm block wins over by_source
    assert bandit.novelty_by_arm({"by_arm": {"failure_derived": 1.0}})["by_arm"][
        "failure_derived"] == 1.0
    # per-cell rows carrying a source are counted
    rows = {"rows": [{"source": "orthogonal_sweep", "verdict": "NOVEL"},
                     {"source": "orthogonal_sweep", "verdict": "REDUNDANT"}]}
    assert bandit.novelty_by_arm(rows)["by_arm"]["new_mechanism"] == pytest.approx(0.5)


def test_an_unattributable_gate_is_neutral_and_never_reorders_an_allocation(
        tmp_path: Path) -> None:
    """The gate as it is published TODAY: a pooled rate and no per-arm column."""
    gate = tmp_path / "NOVELTY_GATE.json"
    gate.write_text(json.dumps({"n_screened": 5000, "n_novel": 3117,
                                "sample": [{"cell": "x", "verdict": "REDUNDANT"}]}), "utf-8")
    got = bandit.novelty_by_arm(path=gate)
    assert got["status"] == "UNMEASURED"
    assert set(got["by_arm"].values()) == {0.0}
    assert got["pooled_novel_rate"] == pytest.approx(0.6234)
    assert "cannot be attributed to an arm" in got["why"]
    ev, gain = _flat_evidence(), _uniform_gain()
    with_it = bandit.allocate_tree(bandit.tree_scores(gain, ev, novelty=got["by_arm"]),
                                   bandit.allocation_policy())[0]
    without = bandit.allocate_tree(bandit.tree_scores(gain, ev, novelty={}),
                                   bandit.allocation_policy())[0]
    assert with_it == without


def test_a_missing_gate_is_unmeasured_and_never_raises(tmp_path: Path) -> None:
    got = bandit.novelty_by_arm(path=tmp_path / "nope.json")
    assert got["status"] == "UNMEASURED" and set(got["by_arm"].values()) == {0.0}
    assert got["pooled_novel_rate"] is None


# --------------------------------------------------------------------- the temperature ladder
def test_every_temperature_has_a_role_and_every_mapped_source_lands_on_one() -> None:
    assert bandit.TEMPERATURES == ("T0", "T1", "T2", "T3", "T4", "T5")
    assert set(bandit.TEMPERATURE_ROLE) == set(bandit.TEMPERATURES)
    assert set(bandit.SOURCE_TEMPERATURE.values()) == set(bandit.TEMPERATURES)
    assert bandit.temperature_of("qd_frontier:exploiter") == "T0"
    assert bandit.temperature_of("qd_frontier:connector") == "T1"
    assert bandit.temperature_of("qd_frontier:explorer") == "T2"
    assert bandit.temperature_of("standing_questions:Q3") == "T4"
    assert bandit.temperature_of("unseen_frontier") == "T5"
    assert bandit.temperature_of("deep_forest_jp") == "T5"
    assert bandit.temperature_of("fund_playbook:Renaissance:A") == "T5"
    assert bandit.temperature_of("") is None


def test_every_leg_the_ladder_charges_is_a_real_costed_hourly_leg() -> None:
    """A leg name here that the hourly cycle never costs would price a temperature off nothing."""
    src = (ROOT / "desks" / "mt5" / "research" / "hourly_cycle.py").read_text("utf-8")
    named = [(t, leg) for t, legs in bandit.TEMP_RUNS.items() for leg in legs]
    named += [(t, leg) for leg, temps in bandit.TEMP_SHARED_RUNS.items() for t in temps]
    for t, leg in named:
        assert t in bandit.TEMPERATURES
        assert f'_costed("{leg}"' in src, f"{t}: leg {leg!r} is not a costed hourly leg"


def test_all_six_temperatures_appear_with_their_proposals_and_their_compute() -> None:
    rows = [
        {"id": "1", "source": "qd_frontier:exploiter", "fate": "BORN"},
        {"id": "2", "source": "qd_frontier:connector", "fate": "BORN"},
        {"id": "3", "source": "qd_frontier:explorer", "fate": "CERTIFIED"},
        {"id": "4", "source": "orthogonal_sweep:carry", "fate": "BORN"},
        {"id": "5", "source": "standing_questions:Q3", "fate": "BORN"},
        {"id": "6", "source": "unseen_frontier", "fate": "BORN"},
        {"id": "7", "source": "a_source_no_table_claims", "fate": "BORN"},
    ]
    costs = {"deepen": {"runs": 2, "wall_s": 600.0}, "sweep": {"runs": 1, "wall_s": 300.0},
             "qd_frontier": {"runs": 1, "wall_s": 90.0}}
    lad = bandit.temperature_ladder(rows, costs)
    assert set(lad["ladder"]) == set(bandit.TEMPERATURES)
    assert lad["status"] == "MEASURED"
    assert lad["all_six_running"] is True and lad["n_running"] == 6
    assert [lad["ladder"][t]["proposals"] for t in bandit.TEMPERATURES] == [1, 1, 1, 1, 1, 1]
    assert lad["ladder"]["T2"]["certified"] == 1
    assert lad["ladder"]["T0"]["compute_s"] == pytest.approx(600.0 + 30.0)   # deepen + 1/3 of qd
    assert lad["ladder"]["T3"]["compute_s"] == pytest.approx(300.0 + 0.0)
    assert "qd_frontier" in lad["shared_leg_basis"][0]
    assert all(r["role"] for r in lad["ladder"].values())
    # A stranger is NAMED, never bucketed -- otherwise concurrency is inflated by accident.
    assert lad["unclassified"]["n"] == 1
    assert lad["unclassified"]["sources"][0]["source"] == "a_source_no_table_claims"
    assert sum(r["proposals"] for r in lad["ladder"].values()) == 6


def test_a_temperature_with_nothing_reads_idle_and_says_why() -> None:
    lad = bandit.temperature_ladder([{"id": "1", "source": "unseen_frontier"}], {})
    assert lad["ladder"]["T5"]["status"] == "RUNNING"
    assert lad["ladder"]["T1"]["status"] == "IDLE"
    assert "idle, which is a measurement" in lad["ladder"]["T1"]["why"]
    assert lad["all_six_running"] is False and lad["idle"] == ["T0", "T1", "T2", "T3", "T4"]
    assert lad["ladder"]["T1"]["legs_uncosted"]


def test_the_window_excludes_an_old_proposal_and_says_how_many() -> None:
    rows = [{"id": "old", "source": "unseen_frontier", "at": "2020-01-01T00:00:00+00:00"},
            {"id": "new", "source": "unseen_frontier",
             "at": datetime.now(tz=UTC).isoformat()}]
    lad = bandit.temperature_ladder(rows, {}, window_h=24.0)
    assert lad["ladder"]["T5"]["proposals"] == 1
    assert lad["rows_out_of_window"] == 1


# ------------------------------------------------------------------------------- the consumers
def test_the_report_keeps_the_flat_shares_its_consumers_read(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """`shares` is additive-compatible: research_budget.budget_s must keep working unchanged."""
    doc = bandit.run(seed=0, write=False)
    assert set(doc["shares"]) == set(bandit.ARMS)
    assert sum(doc["shares"].values()) == pytest.approx(1.0, abs=1e-3)
    assert doc["tree"]["allocated"] == pytest.approx(1.0, abs=1e-6)
    assert set(doc["temperatures"]["ladder"]) == set(bandit.TEMPERATURES)
    assert doc["novelty"]["status"] in ("MEASURED", "UNMEASURED")
    sys.path.insert(0, str(ROOT / "desks" / "mt5" / "research"))
    import research_budget  # type: ignore[import-not-found]
    report = tmp_path / "RESEARCH_BANDIT.json"
    report.write_text(json.dumps(doc), "utf-8")
    monkeypatch.setattr(research_budget, "BANDIT", report)
    seconds, rec = research_budget.budget_s("deepen", 300.0)
    assert rec["applied"] is True and seconds > 0
    assert rec["arms"] == list(research_budget.LEG_ARMS["deepen"])
