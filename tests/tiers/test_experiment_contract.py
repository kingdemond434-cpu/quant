"""Every registered hourly leg declares hypothesis, metric, falsifier, budget and owner, or sits
on a grandfather list that may only shrink; the live registry passes its own fence."""
from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from libs.tiers import experiment_contract as ec  # noqa: E402

_SPEC = importlib.util.spec_from_file_location(
    "repo_check_experiment_contracts", ROOT / "scripts" / "check_experiment_contracts.py")
assert _SPEC is not None and _SPEC.loader is not None
ck = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(ck)

def test_resolve_derives_budget_owner_and_metric() -> None:
    c = ec.resolve("leg1", {"hypothesis": "h"}, budget_s=120, department="meta",
                   tier_s_metric={"organ": "report:Y.json"})
    assert c["budget"] == {"seconds": 120}
    assert c["owner"] == "department:meta"
    assert c["metric"] == {"organ": "report:Y.json"}
    assert set(c["derived"]) == {"budget", "owner", "metric"}


def test_problems_flag_every_missing_or_malformed_field() -> None:
    p = ec.problems({})
    assert {f"missing {f}" for f in ec.REQUIRED} <= set(p)
    bad = {"hypothesis": "short", "metric": {"organ": "file:x"},
           "falsifier": {"metric": "", "op": "~", "threshold": "n"},
           "budget": {"seconds": 0}, "owner": "x"}
    text = " | ".join(ec.problems(bad))
    for frag in ("hypothesis under", "organ must be report:", "falsifier: metric",
                 "falsifier: op", "threshold must be", "seconds must be positive"):
        assert frag in text


def test_judge_falsifier(tmp_path: Path) -> None:
    c = {"falsifier": {"metric": "n_failed", "op": ">", "threshold": 10}}
    assert ec.judge_falsifier(c, {"n_failed": 3})["verdict"] == ec.HOLDS
    assert ec.judge_falsifier(c, {"n_failed": 30})["verdict"] == ec.FALSIFIED
    assert ec.judge_falsifier(c, {})["verdict"] == ec.UNMEASURED
    doc, why = ec.report_for({"metric": {"organ": "report:ABSENT.json"}}, tmp_path)
    assert doc == {} and why.startswith("UNMEASURED")


def test_fence_names_a_new_uncontracted_leg_without_failing_on_it() -> None:
    """A new leg with no declaration is an OBLIGATION in the summary, never a breach by itself;
    a DECLARED contract that does not validate still fails the fence."""
    legs = ["a", "b"]
    resolved = {leg: ec.resolve(leg, None, budget_s=60, department="meta") for leg in legs}
    probs, summary = ck.check({"legs": {}, "grandfathered": ["a"], "grandfathered_max": 1}, legs,
                              resolved)
    assert probs == []
    assert summary["uncontracted_new"] == ["b"]
    declared = {"b": {"hypothesis": "short"}}
    resolved_b = {**resolved, "b": ec.resolve("b", declared["b"], budget_s=60,
                                              department="meta")}
    probs, summary = ck.check({"legs": declared, "grandfathered": ["a"],
                               "grandfathered_max": 1}, legs, resolved_b)
    assert any(p.startswith("leg b: ") for p in probs)
    assert summary["uncontracted_new"] == []


def test_fence_fails_a_vanished_or_growing_grandfather_list() -> None:
    legs = ["a", "b"]
    resolved = {leg: ec.resolve(leg, None, budget_s=60, department="meta") for leg in legs}
    probs, _ = ck.check({"grandfathered": ["a", "b", "gone"], "grandfathered_max": 2}, legs,
                        resolved)
    assert any("gone is no longer registered" in p for p in probs)
    assert any("above its ratchet" in p for p in probs)


def test_live_registry_passes_its_fence() -> None:
    reg = ec.load_registry()
    legs = ck.registered_legs()
    resolved = ck.contracts_for(legs, reg)
    probs, summary = ck.check(reg, legs, resolved)
    assert probs == [], probs[:5]
    for leg in ("build_failure_bank", "trade_pathology", "experiment_contracts", "health_board",
                "committees", "decay_monitor", "fill_markout", "kelly_survival"):
        assert leg in legs and not ec.problems(resolved[leg]), leg
    assert summary["contracted"] >= 14


def test_registry_is_valid_json_with_a_ratchet() -> None:
    d = json.loads(ec.REGISTRY.read_text("utf-8"))
    assert isinstance(d.get("grandfathered_max"), int)
    assert len(d["grandfathered"]) <= d["grandfathered_max"]


# ------------------------------------------- the uncontracted ratchet (audit 2026-10-06)


def _resolved(legs: list[str]) -> dict:
    return {leg: ec.resolve(leg, None, budget_s=60, department="meta") for leg in legs}


def test_ratchet_fails_a_new_uncontracted_leg_or_a_rising_count() -> None:
    """The fence exited 0 with 26 uncontracted and 354 grandfathered; with a committed baseline
    a leg uncontracted that the baseline does not name, or a count above it, is a breach."""
    reg = {"grandfathered": ["g"], "grandfathered_max": 1,
           "uncontracted_baseline": ["a"], "uncontracted_max": 1}
    probs, summary = ck.check(reg, ["g", "a"], _resolved(["g", "a"]))
    assert probs == [] and summary["uncontracted_new"] == ["a"]
    probs, _ = ck.check(reg, ["g", "a", "new"], _resolved(["g", "a", "new"]))
    assert any("not in the committed uncontracted baseline: new" in p for p in probs)
    assert any("rose to 2 above the ratchet 1" in p for p in probs)
    grown = {**reg, "grandfathered": ["g", "h"]}
    probs, _ = ck.check(grown, ["g", "h", "a"], _resolved(["g", "h", "a"]))
    assert any("above its ratchet" in p for p in probs)


def test_ratchet_tightens_when_counts_fall_and_never_rises() -> None:
    reg = {"legs": {"a": {"hypothesis": "x"}}, "grandfathered": ["g", "h"],
           "grandfathered_max": 2, "uncontracted_baseline": ["a", "b"], "uncontracted_max": 2}
    legs = ["g", "h", "b"]                         # `a` unregistered, nothing healed
    _probs, summary = ck.check({**reg, "legs": {}}, legs, _resolved(legs))
    summary["healed_awaiting_update"] = ["h"]      # h gained a contract
    moved = ck.tighten(reg, summary)
    assert reg["grandfathered"] == ["g"] and reg["grandfathered_max"] == 1
    assert reg["uncontracted_baseline"] == ["b"] and reg["uncontracted_max"] == 1
    assert moved
    assert ck.tighten(reg, {"uncontracted_new": ["b", "zz"],
                            "healed_awaiting_update": []}) == []
    assert reg["uncontracted_max"] == 1 and reg["uncontracted_baseline"] == ["b"]


def test_fence_main_writes_the_tightened_baseline(tmp_path: Path, monkeypatch: Any) -> None:
    reg_p = tmp_path / "reg.json"
    reg_p.write_text(json.dumps({"legs": {}, "grandfathered": ["g"], "grandfathered_max": 5,
                                 "uncontracted_baseline": ["a", "b"], "uncontracted_max": 2}),
                     "utf-8")
    monkeypatch.setattr(ck, "registered_legs", lambda root=None: ["g", "a"])
    monkeypatch.setattr(ck, "cycle_tables", lambda: ({}, {}, 60))
    assert ck.main(["--registry", str(reg_p)]) == 0
    after = json.loads(reg_p.read_text("utf-8"))
    assert after["grandfathered_max"] == 1
    assert after["uncontracted_baseline"] == ["a"] and after["uncontracted_max"] == 1
    monkeypatch.setattr(ck, "registered_legs", lambda root=None: ["g", "a", "c"])
    assert ck.main(["--registry", str(reg_p)]) == 1


def test_live_registry_commits_the_uncontracted_baseline() -> None:
    d = json.loads(ec.REGISTRY.read_text("utf-8"))
    assert isinstance(d.get("uncontracted_baseline"), list)
    assert d["uncontracted_max"] == len(d["uncontracted_baseline"])
