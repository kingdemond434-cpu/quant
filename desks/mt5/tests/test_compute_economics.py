"""THE COMPUTE-ECONOMICS SCIENTIST: the split always sums to one, it moves two-sided off measured
survivors per hour, and an UNMEASURED policy reads exactly 1.0 in every downstream reader --
the departments' exchange and the forest allocator."""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

_DESK = Path(__file__).resolve().parents[1]
_ROOT = _DESK.parent.parent
for _p in (str(_ROOT), str(_DESK), str(_DESK / "research")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from libs.research import forests  # noqa: E402
from research import compute_economics as CE  # noqa: E402
from research import research_departments as rd  # noqa: E402


def _dept(hours: float, certified: int, novel: int) -> dict:
    return {"legs": [], "compute": {"hours": hours, "runs": 1.0, "timeouts": 0.0, "failed": 0.0},
            "yield": {"born": 5, "certified": certified, "failed": 1},
            "novelty": {"novel": novel, "screened": 5},
            "certified_per_hour": certified / hours, "novel_per_hour": novel / hours,
            "born_per_hour": 5 / hours, "status": "MEASURED"}


def test_learned_split_sums_to_one_and_moves_two_sided() -> None:
    hours = {"exploitation": {"wall_h": 10.0}, "exploration": {"wall_h": 5.0},
             "frontier": {"wall_h": 1.0}}
    split = CE.learn_split(hours, {"exploitation": 20, "exploration": 5, "frontier": 3})
    assert split["status"] == "MEASURED" and split["applied"] is True
    assert abs(sum(split["split"].values()) - 1.0) < 1e-9
    assert split["factors"]["frontier"] > 1.0 > split["factors"]["exploration"]
    assert split["split"]["exploration"] < CE.DEFAULT_SPLIT["exploration"]
    assert all(CE.POLICY_CLIP[0] <= f <= CE.POLICY_CLIP[1] for f in split["factors"].values())
    assert abs(sum(CE.DEFAULT_SPLIT.values()) - 1.0) < 1e-12


def test_unmeasured_split_keeps_the_default_and_reads_one_everywhere(tmp_path: Path) -> None:
    hours = {"exploitation": {"wall_h": 10.0}, "exploration": {"wall_h": 0.0},
             "frontier": {"wall_h": 1.0}}
    split = CE.learn_split(hours, {"exploitation": 20})
    assert split["status"] == "UNMEASURED" and split["applied"] is False
    assert split["split"] == CE.DEFAULT_SPLIT and set(split["factors"].values()) == {1.0}
    policy = CE.policy_doc(split, {"search": "discovery"}, ["discovery", "intel", "meta"])
    assert abs(sum(policy["split"].values()) - 1.0) < 1e-9
    assert set(policy["factors"]["departments"].values()) == {1.0}
    assert policy["factors"]["forests"] == 1.0 and policy["applied"] is False
    # downstream: the departments' exchange
    (tmp_path / "data").mkdir()
    (tmp_path / "reports").mkdir()
    (tmp_path / "data" / "compute_policy.json").write_text(json.dumps(policy), "utf-8")
    out = tmp_path / "reports" / "RESEARCH_DEPARTMENTS.json"
    depts = {"discovery": _dept(2.0, 2, 3), "intel": _dept(2.0, 1, 1)}
    pf = rd.policy_factors(depts, out)
    assert pf["applied"] is False and set(pf["factors"].values()) == {1.0}
    sp = rd.spend(depts, {"binding": "compute"}, 7, None, pf)
    assert sp["compute_policy"]["applied"] is False
    # downstream: the forest allocator
    factor, why = forests.policy_factor(tmp_path / "data" / "compute_policy.json")
    assert factor == 1.0 and "UNMEASURED" in why
    assert forests.policy_factor(tmp_path / "nowhere.json")[0] == 1.0
    alloc = forests.allocation_for("korea", tmp_path / "no_alloc.json",
                                   tmp_path / "data" / "compute_policy.json")
    assert alloc.policy_factor == 1.0 and alloc.budget_s == forests.DEFAULT_BUDGET_S


def test_measured_policy_moves_departments_and_forests_two_sided(tmp_path: Path) -> None:
    (tmp_path / "data").mkdir()
    (tmp_path / "reports").mkdir()
    policy = {"status": "MEASURED", "applied": True,
              "split": {"exploitation": 0.6, "exploration": 0.3, "frontier": 0.1},
              "factors": {"departments": {"discovery": 0.857, "intel": 1.5}, "forests": 1.5},
              "why": "planted"}
    (tmp_path / "data" / "compute_policy.json").write_text(json.dumps(policy), "utf-8")
    out = tmp_path / "reports" / "RESEARCH_DEPARTMENTS.json"
    depts = {"discovery": _dept(2.0, 2, 3), "intel": _dept(2.0, 1, 1), "meta": _dept(1.0, 0, 0)}
    pf = rd.policy_factors(depts, out)
    assert pf["applied"] is True
    assert pf["factors"] == {"discovery": 0.857, "intel": 1.5, "meta": 1.0}
    base = rd.spend(depts, {"binding": "compute"}, 7)
    moved = rd.spend(depts, {"binding": "compute"}, 7, None, pf)
    for d in depts:
        want = round(max(rd.SPEND_CLIP[0], min(rd.SPEND_CLIP[1],
                                                base["factors"][d] * pf["factors"][d])), 3)
        assert moved["factors"][d] == want
    assert moved["factors"]["intel"] > base["factors"]["intel"]
    assert moved["factors"]["discovery"] < base["factors"]["discovery"]
    factor, why = forests.policy_factor(tmp_path / "data" / "compute_policy.json")
    assert factor == 1.5 and "MEASURED" in why
    alloc = forests.allocation_for("korea", tmp_path / "no_alloc.json",
                                   tmp_path / "data" / "compute_policy.json")
    assert alloc.policy_factor == 1.5
    assert alloc.budget_s == round(forests.DEFAULT_BUDGET_S * 1.5)
    assert alloc.workers >= 1 and alloc.scout_floor is True


def test_fidelity_ladder_is_a_recommendation_from_the_gate_ledger() -> None:
    rows = [{"family": "f", "terminal_gate": CE.GATE_ORDER[0], "passed": False}] * 6 + \
           [{"family": "f", "terminal_gate": CE.GATE_ORDER[3], "passed": False}] * 2 + \
           [{"family": "f", "passed": True}] * 2
    lad = CE.fidelity_ladder(rows, None)
    assert lad["status"] == "MEASURED" and lad["families"]["f"]["cells"] == 10
    assert lad["families"]["f"]["cheap_rung_share"] == 0.6
    assert lad["gauntlet_compute_recoverable_share"] == 0.6
    assert "no gate, threshold or budget moves" in lad["rule"]
    assert CE.fidelity_ladder([], "absent: x")["status"] == "UNMEASURED"


def test_run_dry_run_writes_nothing_and_names_what_it_could_not_measure(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    for name in ("COMPUTE_LEDGER", "GRAPH", "GATE_LEDGER", "API_LEDGER", "FOREST_ALLOCATION",
                 "ROI_REPORT"):
        monkeypatch.setattr(CE, name, tmp_path / "absent" / name)
    monkeypatch.setattr(CE, "POLICY", tmp_path / "data" / "compute_policy.json")
    monkeypatch.setattr(CE, "OUT", tmp_path / "reports" / "COMPUTE_ECONOMICS.json")
    doc = CE.run(budget_s=30, dry_run=True)
    assert not CE.POLICY.exists() and not CE.OUT.exists()
    assert doc["policy"]["status"] == "UNMEASURED" and doc["policy"]["applied"] is False
    assert abs(sum(doc["policy"]["split"].values()) - 1.0) < 1e-9
    whats = {u["what"] for u in doc["unmeasured"]}
    assert {"compute ledger", "data pounds", "research ROI"} <= whats
    assert doc["data_pounds"]["gbp"] is None, "an absent pound is never 0"
    assert set(doc["by_tier"]) == {*CE.TIERS, "overhead"}
