"""S01 and S12 at the gates: the constitution IN FORCE sets the gauntlet's thresholds, and the
judge's runtime firewall refuses (never passes) at the gates and before a lockbox opens."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import numpy as np
import pytest

from libs.tiers import firewall, truth_kernel

ROOT = Path(__file__).resolve().parents[3]
CONST = {"dsr_threshold": 0.95, "gates_required": 10.0, "lockbox_min_fraction": 0.2}


def _root(tmp_path: Path, rules: dict[str, float] | None = None,
          ratified: bool = False) -> Path:
    d = tmp_path / "docs" / "research"
    d.mkdir(parents=True, exist_ok=True)
    if rules is not None:
        doc = truth_kernel.constitution_doc()
        for k, v in rules.items():
            doc["rules"][k]["value"] = v
        doc["hash"] = truth_kernel.sha256(truth_kernel.canon(doc["rules"]))
        (d / "tier_s_constitution.json").write_text(json.dumps(doc), "utf-8")
        if ratified:
            (d / "tier_s_ratifications.jsonl").write_text(
                json.dumps({"hash": doc["hash"], "by": "principal"}) + "\n", "utf-8")
    return tmp_path


def test_the_sealed_default_binds_when_no_live_file(tmp_path: Path) -> None:
    got = truth_kernel.gauntlet_thresholds(_root(tmp_path), **CONST)
    assert got["status"] == "SEALED_DEFAULT"
    assert (got["dsr_threshold"], got["gates_required"], got["lockbox_min_fraction"]) == (
        0.95, 10.0, 0.2)


def test_the_repository_constitution_is_in_force_as_sealed() -> None:
    got = truth_kernel.gauntlet_thresholds(ROOT, **CONST)
    assert got["status"] in ("SEALED", "SEALED_DEFAULT", "TIGHTENED", "RATIFIED"), got
    assert got["dsr_threshold"] >= 0.95 and got["gates_required"] >= 10.0


def test_a_tightening_binds_without_ratification(tmp_path: Path) -> None:
    got = truth_kernel.gauntlet_thresholds(
        _root(tmp_path, {"cert.dsr_threshold": 0.97, "lockbox.min_fraction": 0.3}), **CONST)
    assert got["status"] == "TIGHTENED"
    assert got["dsr_threshold"] == 0.97 and got["lockbox_min_fraction"] == 0.3


def test_an_unratified_loosening_never_reaches_the_gauntlet(tmp_path: Path) -> None:
    got = truth_kernel.gauntlet_thresholds(
        _root(tmp_path, {"cert.dsr_threshold": 0.5, "cert.gates_required": 6.0}), **CONST)
    assert got["status"] == "VIOLATION"
    assert got["dsr_threshold"] == 0.95 and got["gates_required"] == 10.0


def test_a_ratified_loosening_is_the_law(tmp_path: Path) -> None:
    got = truth_kernel.gauntlet_thresholds(
        _root(tmp_path, {"cert.dsr_threshold": 0.9}, ratified=True), **CONST)
    assert got["status"] == "RATIFIED" and got["dsr_threshold"] == 0.9


def test_the_law_never_loosens_a_stricter_gauntlet_constant(tmp_path: Path) -> None:
    got = truth_kernel.gauntlet_thresholds(_root(tmp_path), dsr_threshold=0.99,
                                           gates_required=10.0, lockbox_min_fraction=0.2)
    assert got["dsr_threshold"] == 0.99


@pytest.mark.parametrize("body", ["{torn", "[1, 2]", json.dumps({"rules": [1]})])
def test_an_unreadable_constitution_leaves_the_constants(tmp_path: Path, body: str) -> None:
    d = tmp_path / "docs" / "research"
    d.mkdir(parents=True)
    (d / "tier_s_constitution.json").write_text(body, "utf-8")
    got = truth_kernel.gauntlet_thresholds(tmp_path, dsr_threshold=0.95, gates_required=10.0,
                                           lockbox_min_fraction=0.2)
    assert got["status"] == "UNREADABLE"
    assert (got["dsr_threshold"], got["gates_required"]) == (0.95, 10.0)


def test_damaged_ratifications_leave_the_constants(tmp_path: Path) -> None:
    root = _root(tmp_path, {"cert.dsr_threshold": 0.5})
    (root / "docs" / "research" / "tier_s_ratifications.jsonl").write_text("{torn\n", "utf-8")
    got = truth_kernel.gauntlet_thresholds(root, **CONST)
    assert got["status"] == "UNREADABLE" and got["dsr_threshold"] == 0.95


# ------------------------------------------------------------------------ S12: the firewall


def test_the_judge_reads_the_docket_and_bars() -> None:
    for ok in ("desks/mt5/data/hypotheses/external_survivors.json",
               "desks/mt5/data/universe/EURUSD_H1.parquet",
               "desks/mt5/reports/hunt17.json"):
        assert firewall.judge_refusal("read", ok) is None, ok
    assert firewall.judge_refusal("write", "desks/mt5/reports/universal_gates_x.json") is None


def test_the_judge_is_refused_raw_hypotheses_and_sealed_lockboxes() -> None:
    for bad in ("desks/mt5/data/intelligence/kimi/discoveries_1.json",
                "desks/mt5/data\\intelligence\\deepseek\\x.json",
                "data/hypothesis_graph.jsonl", "data/suggestion_ledger.jsonl",
                "reports/LOCKBOX_RESULTS.json", "data/lockbox_vault/abc"):
        why = firewall.judge_refusal("read", bad) or ""
        assert why.startswith("FIREWALL:"), bad
    assert (firewall.judge_refusal("write", "desks/mt5/data/sleeves.json") or "").startswith(
        "FIREWALL:")


def test_a_firewall_that_cannot_run_refuses(monkeypatch: Any) -> None:
    def boom(*a: Any, **k: Any) -> None:
        raise RuntimeError("role table unreadable")

    monkeypatch.setattr(firewall, "may", boom)
    assert (firewall.judge_refusal("read", "anything") or "").startswith("FIREWALL_ERROR")


def _hyp_and_box() -> tuple[Any, Any]:
    from libs.autodiscovery.models import Family, Hypothesis
    from libs.validation.economic_prior import MechanismType
    from libs.validation.lockbox import LockedHoldout
    hyp = Hypothesis(family=Family.TREND, subtype="t", symbol="EURUSD", params={"n": 20.0},
                     mechanism=MechanismType.BEHAVIORAL, edge_source="x")
    return hyp, LockedHoldout(np.linspace(-1.0, 1.0, 400), holdout_fraction=0.2)


def test_the_lockbox_opens_only_for_a_frozen_candidate_the_firewall_clears(
        monkeypatch: Any) -> None:
    from libs.autodiscovery import orchestrator as orch
    hyp, box = _hyp_and_box()
    assert orch.frozen_lockbox_refusal(hyp, box) is None
    assert not box.is_opened, "the freeze step never opens the box itself"
    monkeypatch.setattr(firewall, "judge_refusal", lambda *a, **k: "FIREWALL: no")
    assert orch.frozen_lockbox_refusal(hyp, box) == "FIREWALL: no"

    def refuse(_c: Any) -> str:
        raise firewall.FirewallError("lockbox refuses an unfrozen candidate")

    monkeypatch.setattr(firewall, "lockbox_accepts", refuse)
    assert (orch.frozen_lockbox_refusal(hyp, box) or "").startswith("FIREWALL_ERROR")
    assert not box.is_opened


def test_the_orchestrator_opens_its_lockbox_only_after_the_freeze() -> None:
    import inspect

    from libs.autodiscovery import orchestrator as orch
    src = inspect.getsource(orch.AutoDiscoveryLab._validate_and_archive)
    assert src.index("frozen_lockbox_refusal(") < src.index("open_lockbox()")
    audit = firewall.lockbox_audit(ROOT, ("libs/autodiscovery/orchestrator.py",))
    assert audit["openers"] >= 1 and audit["violations"] == [], audit
