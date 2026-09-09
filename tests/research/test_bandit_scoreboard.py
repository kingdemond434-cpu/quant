"""The research bandit prices arms from the ledger, keeps the policy's floors, and prices regret.

Four properties, each of which was measured absent on 2026-09-08 (inventory I14, I12, A7, A14):

  * COST IS MEASURED WHERE A LEG WAS COSTED. The compute ledger's wall/CPU seconds price the arm
    whose leg they belong to; an arm with no costed leg keeps the declared table and its
    `cost_basis` names the leg that is missing. A single measurement cannot reorder anything.
  * THE THREE GROUPS ARE FLOORED BY THE DESK'S OWN POLICY. exploit / adjacent / cold shares are
    asserted against ops/research_allocation_policy.json inside `allocate`; a starved group is
    lifted to its floor, every lift is reported, and the per-arm EXPLORE floor survives the lift.
  * FRONTIER_REGRET IS PUBLISHED, against what was known at allocation time.
  * THE BUDGET NAMES ITS CONTROLLER, so a second policy can run beside this one.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import pytest

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from libs.research import bandit  # noqa: E402


def _flat_evidence(**over) -> dict:
    ev = {a: {"born": 0, "failed": 0, "certified": 0, "alpha": 1.9, "beta": 20.1,
              "p_survivor": 0.0864, "worth": 1.0, "cost": float(sum(bandit.COST[a])),
              "score_mean": round(1.0 * 0.0864 / float(sum(bandit.COST[a])), 5)}
          for a in bandit.ARMS}
    for a, patch in over.items():
        ev[a].update(patch)
    return ev


# ------------------------------------------------------------------ I14: measured cost basis
def test_a_costed_leg_prices_its_arm_and_an_uncosted_arm_names_its_missing_leg() -> None:
    costs = {"search": {"runs": 2, "wall_s": 1440.0, "cpu_s": 0.3, "failures": 0},
             "deepen": {"runs": 1, "wall_s": 360.0, "cpu_s": 200.0, "failures": 1}}
    mc = bandit.measured_cost(costs)
    assert set(mc) == {"external_screen", "mutate_survivor"}, mc
    assert mc["external_screen"]["wall_s_per_pass"] == pytest.approx(720.0)
    assert mc["mutate_survivor"]["failures"] == 1
    assert mc["external_screen"]["basis"].startswith("measured:")
    ev = bandit.evidence([], measured=mc)
    assert ev["external_screen"]["cost"] == pytest.approx(mc["external_screen"]["cost"])
    assert ev["external_screen"]["cost_basis"].startswith("measured:")
    # An arm whose leg carries no row is priced from the table and says which leg is missing.
    assert ev["alt_data_hypothesis"]["cost"] == float(sum(bandit.COST["alt_data_hypothesis"]))
    assert "mine" in ev["alt_data_hypothesis"]["cost_basis"]
    assert ev["alt_data_hypothesis"]["cost_basis"].startswith("declared:")
    # An arm with no declared leg at all says THAT, not "zero".
    assert "ARM_RUNS" in ev["combine_survivors"]["cost_basis"]


def test_measured_seconds_decide_the_relative_compute_and_keep_the_declared_scale() -> None:
    """The ledger orders the costed arms; the table's mean compute over them is preserved, so a
    costed arm and an uncosted one remain on one scale."""
    costs = {"search": {"runs": 1, "wall_s": 3000.0, "cpu_s": 1.0, "failures": 0},
             "sweep": {"runs": 1, "wall_s": 300.0, "cpu_s": 1.0, "failures": 0}}
    mc = bandit.measured_cost(costs)
    ext, new = mc["external_screen"], mc["new_mechanism"]
    assert ext["compute_units"] > new["compute_units"]
    assert ext["compute_units"] / new["compute_units"] == pytest.approx(10.0, rel=1e-3)
    declared_mean = (bandit.COST["external_screen"][0] + bandit.COST["new_mechanism"][0]) / 2
    assert (ext["compute_units"] + new["compute_units"]) / 2 == pytest.approx(declared_mean,
                                                                              rel=1e-3)
    # Only the compute column moved: data + latency + multiplicity are untouched.
    rest = sum(bandit.COST["external_screen"][1:])
    assert ext["cost"] == pytest.approx(ext["compute_units"] + rest, rel=1e-3)


def test_one_costed_arm_keeps_its_declared_compute_exactly() -> None:
    mc = bandit.measured_cost(
        {"deepen": {"runs": 3, "wall_s": 90.0, "cpu_s": 9.0, "failures": 0}})
    declared = bandit.COST["mutate_survivor"]
    assert mc["mutate_survivor"]["compute_units"] == pytest.approx(declared[0])
    assert mc["mutate_survivor"]["cost"] == pytest.approx(sum(declared))


def test_an_empty_or_unreadable_ledger_prices_nothing_and_never_raises() -> None:
    assert bandit.measured_cost({}) == {}
    assert bandit.measured_cost({"search": {"runs": 0, "wall_s": 0.0}}) == {}
    ev = bandit.evidence([])                         # no `measured`: the declared table, as before
    assert all(ev[a]["cost"] == float(sum(bandit.COST[a])) for a in bandit.ARMS)


def test_every_costed_leg_in_the_map_is_a_real_hourly_leg() -> None:
    """A leg name here that the hourly cycle never costs would be a mapping to nothing."""
    src = (ROOT / "desks" / "mt5" / "research" / "hourly_cycle.py").read_text("utf-8")
    for arm, legs in bandit.ARM_RUNS.items():
        assert arm in bandit.ARMS
        for leg in legs:
            assert f'_costed("{leg}"' in src, f"{arm}: leg {leg!r} is not a costed hourly leg"


def test_the_orthogonal_sweep_routes_to_the_arm_its_leg_is_charged_to() -> None:
    assert bandit.arm_of("orthogonal_sweep:carry") == "new_mechanism"
    assert "sweep" in bandit.ARM_RUNS["new_mechanism"]


# ------------------------------------------------------------------ A7: exploit / adjacent / cold
def test_the_three_groups_partition_the_arms_as_declared() -> None:
    assert {bandit.group_of(a) for a in bandit.ARMS} == set(bandit.GROUPS)
    for a in ("mutate_survivor", "combine_survivors", "conditional_state_edge"):
        assert bandit.group_of(a) == "adjacent"
    for a in ("new_mechanism", "alt_data_hypothesis"):
        assert bandit.group_of(a) == "cold"
    assert bandit.group_of("external_screen") == "exploit"


def test_the_floors_come_from_the_desks_own_policy_file() -> None:
    policy = bandit.allocation_policy()
    assert policy, "ops/research_allocation_policy.json must be readable"
    gf = bandit.group_floors(policy)
    assert gf["status"] == "DECLARED"
    assert gf["floors"] == {"exploit": 0.4, "exploration": 0.4, "cold": 0.1, "adjacent": None}
    assert gf["unmapped"]["falsification"] == 0.05        # named, not silently dropped


def test_a_missing_policy_is_unmeasured_not_floorless() -> None:
    gf = bandit.group_floors({})
    assert gf["status"] == "UNMEASURED" and "research_allocation_policy" in gf["why"]
    s, check = bandit.enforce_floors({a: 1.0 / len(bandit.ARMS) for a in bandit.ARMS}, {})
    assert check["status"] == "UNMEASURED" and check["lifted"] == []
    assert sum(s.values()) == pytest.approx(1.0)


def test_a_starved_group_is_lifted_to_its_floor_and_the_lift_is_reported() -> None:
    policy = bandit.allocation_policy()
    # Everything on the exploit arms: cold at 0, exploration at 0.
    raw = {a: (1.0 / 6 if bandit.group_of(a) == "exploit" else 0.0) for a in bandit.ARMS}
    s, check = bandit.enforce_floors(raw, policy)
    g = bandit.group_shares(s)
    assert g["cold"] >= 0.1 - 1e-9 and g["exploration"] >= 0.4 - 1e-9
    assert g["exploit"] >= 0.4 - 1e-9
    assert sum(s.values()) == pytest.approx(1.0)
    assert check["status"] == "LIFTED_TO_FLOOR"
    assert {x["group"] for x in check["lifted"]} >= {"cold", "exploration"}
    assert check["groups_raw"]["exploration"] == 0.0     # what it was lifted FROM is kept


def test_an_allocation_inside_the_floors_is_not_touched() -> None:
    raw = {a: 1.0 / len(bandit.ARMS) for a in bandit.ARMS}
    s, check = bandit.enforce_floors(raw, bandit.allocation_policy())
    assert s == pytest.approx(raw)
    assert check["status"] == "WITHIN_FLOORS" and check["lifted"] == []


def test_allocate_asserts_the_floors_and_keeps_every_arm_above_the_explore_floor() -> None:
    """Strong evidence on one exploit arm and a graveyard of cold failures would starve the cold
    group; the floor holds, the audit says it was lifted, and the EXPLORE share is intact."""
    ev = _flat_evidence(
        exit_improvement={"failed": 20, "certified": 30, "alpha": 31.9, "beta": 21.1},
        new_mechanism={"failed": 400, "certified": 0, "alpha": 1.9, "beta": 420.1},
        alt_data_hypothesis={"failed": 400, "certified": 0, "alpha": 1.9, "beta": 420.1},
    )
    audit: dict = {}
    sh = bandit.allocate(ev, np.random.default_rng(0), audit=audit)
    check = audit["policy"]
    assert check["status"] == "LIFTED_TO_FLOOR", check
    assert check["groups"]["cold"] >= 0.1 - 1e-4
    assert check["groups"]["exploration"] >= 0.4 - 1e-4
    assert check["groups"]["exploit"] >= 0.4 - 1e-4
    floor = bandit.EXPLORE / len(bandit.ARMS)
    assert all(v >= floor - 1e-9 for v in sh.values()), sh
    assert sum(sh.values()) == pytest.approx(1.0, abs=1e-3)
    assert sh["exit_improvement"] == max(sh.values())        # evidence still leads


def test_allocate_with_no_policy_behaves_as_before() -> None:
    a = bandit.allocate(_flat_evidence(), np.random.default_rng(0), policy={})
    b = bandit.allocate(_flat_evidence(), np.random.default_rng(0))
    assert a == b                                    # uniform evidence is inside every floor


# ------------------------------------------------------------------ A14: frontier regret
def test_regret_is_the_best_known_score_minus_the_share_weighted_score() -> None:
    ev = _flat_evidence()
    ev["failure_derived"]["score_mean"] = 0.05
    shares = {a: 1.0 / len(bandit.ARMS) for a in bandit.ARMS}
    r = bandit.regret(ev, shares, worth_unmeasured=bandit.ARMS)
    selected = sum(shares[a] * ev[a]["score_mean"] for a in bandit.ARMS)
    assert r["best_arm"] == "failure_derived"
    assert r["best_known_surplus"] == pytest.approx(0.05, abs=1e-6)
    assert r["FRONTIER_REGRET"] == pytest.approx(0.05 - selected, abs=1e-6)
    assert r["by_category"] == {"RESEARCH_REGRET": pytest.approx(0.05 - selected, abs=1e-6)}
    assert r["status"] == "MEASURED"
    assert len(r["worth_unmeasured_arms"]) == len(bandit.ARMS)
    assert "1.0 E[dElogW] default" in r["basis"]


def test_regret_is_zero_when_the_whole_budget_sits_on_the_best_arm() -> None:
    ev = _flat_evidence()
    ev["failure_derived"]["score_mean"] = 0.05
    shares = dict.fromkeys(bandit.ARMS, 0.0)
    shares["failure_derived"] = 1.0
    r = bandit.regret(ev, shares)
    assert r["FRONTIER_REGRET"] == 0.0 and "no frontier regret" in r["headline"]


# ------------------------------------------------------------------ I12: the controller variant
def test_run_publishes_regret_groups_cost_basis_and_the_controller_variant(
        tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(bandit, "BUDGET", tmp_path / "research_budget.json")
    monkeypatch.setattr(bandit, "REPORT", tmp_path / "RESEARCH_BANDIT.json")
    doc = bandit.run(seed=0, write=True)
    assert doc["controller_variant"] == "A" == bandit.CONTROLLER_VARIANT
    assert set(doc["groups"]) == {"exploit", "adjacent", "cold", "exploration"}
    assert doc["policy"]["status"] in ("WITHIN_FLOORS", "LIFTED_TO_FLOOR", "UNMEASURED")
    assert doc["frontier_regret"]["FRONTIER_REGRET"] >= 0.0
    assert doc["frontier_regret"]["best_arm"] in bandit.ARMS
    assert set(doc["cost_basis"]["measured_arms"]) | set(doc["cost_basis"]["declared_arms"]) \
        == set(bandit.ARMS)
    for a in bandit.ARMS:
        assert doc["arms"][a]["cost_basis"].split(":")[0] in ("measured", "declared")
        assert doc["arms"][a]["group"] == bandit.group_of(a)
    budget = json.loads((tmp_path / "research_budget.json").read_text("utf-8"))
    assert budget["controller_variant"] == "A"
    assert set(budget["shares"]) == set(bandit.ARMS)
    report = json.loads((tmp_path / "RESEARCH_BANDIT.json").read_text("utf-8"))
    assert report["frontier_regret"]["by_category"].keys() == {"RESEARCH_REGRET"}


def test_a_named_variant_is_written_through() -> None:
    doc = bandit.run(seed=0, write=False, variant="B")
    assert doc["controller_variant"] == "B"
