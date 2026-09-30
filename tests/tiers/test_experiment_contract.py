"""Every registered hourly leg declares hypothesis, metric, falsifier, budget and owner, or sits
on a grandfather list that may only shrink; the live registry passes its own fence."""
from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

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


def test_fence_fails_an_uncontracted_leg_and_a_growing_grandfather_list() -> None:
    legs = ["a", "b"]
    resolved = {leg: ec.resolve(leg, None, budget_s=60, department="meta") for leg in legs}
    probs, _ = ck.check({"legs": {}, "grandfathered": ["a"], "grandfathered_max": 1}, legs,
                        resolved)
    assert any("leg b: registered with no valid experiment contract" in p for p in probs)
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
    for leg in ("build_failure_bank", "trade_pathology", "experiment_contracts", "health_board"):
        assert leg in legs and not ec.problems(resolved[leg]), leg
    assert summary["contracted"] >= 10


def test_registry_is_valid_json_with_a_ratchet() -> None:
    d = json.loads(ec.REGISTRY.read_text("utf-8"))
    assert isinstance(d.get("grandfathered_max"), int)
    assert len(d["grandfathered"]) <= d["grandfathered_max"]
