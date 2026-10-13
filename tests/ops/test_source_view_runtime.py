"""Copied runtime snapshots are not proof that a source checkout runs the desk."""
from __future__ import annotations

import copy
import json
from pathlib import Path

from scripts import check_birth_obligations as birth
from scripts import check_self_repair as repair
from scripts import run_law_gate as gate


def test_source_family_is_unmeasured_but_missing_code_still_fails(tmp_path, monkeypatch):
    monkeypatch.setenv("QUANT_LAWGATE_SOURCE_VIEW", "1")
    monkeypatch.setattr(birth, "AXES", (
        birth.Axis("family", "judge coverage", lambda root: ({"NEW_FAMILY"}, set(), "no verdict"),
                   None, "reports/JUDGE_COVERAGE.json"),
        birth.Axis("executable", "clock", lambda root: ({"NEW_TOOL"}, set(), "no clock"),
                   None, "docs/research/runtime_state.json"),
    ))
    monkeypatch.setattr(birth, "_is_trading_host", lambda root: True)
    source = birth.measure(tmp_path)
    assert source["axes"]["family"]["verdict"] == "UNMEASURED"
    assert source["axes"]["family"]["incomplete"] == 1
    assert any("NEW_TOOL" in f for f in source["failures"])
    assert not any("NEW_FAMILY" in f for f in source["failures"])
    runtime = birth.measure(tmp_path, require_state=True)
    assert runtime["axes"]["family"]["verdict"] == "measured"
    assert any("NEW_FAMILY" in f for f in runtime["failures"])


def _detector(tmp_path: Path, monkeypatch, *, present: bool):
    import self_repair_registry as reg
    p = tmp_path / "docs/research/self_repair_floor.json"
    p.parent.mkdir(parents=True)
    p.write_text(json.dumps({"manual": 0}))
    row = {"key": "CLOCK", "bucket": "MANUAL", "detector_present": present,
           "repair_declared": present, "owner": "department:meta", "why": "never ran here"}
    doc = {"rows": [row], "census": {b: int(b == "MANUAL") for b in reg.BUCKETS}, "manual": 1}
    monkeypatch.setattr(reg, "measure", lambda root: copy.deepcopy(doc))
    monkeypatch.setattr(repair, "_trading_host", lambda root: True)
    monkeypatch.setenv("QUANT_LAWGATE_SOURCE_VIEW", "1")


def test_copied_gateway_state_does_not_claim_a_local_detector(tmp_path, monkeypatch):
    _detector(tmp_path, monkeypatch, present=True)
    source = repair.measure(tmp_path)
    assert source["manual"] == 0
    assert source["rows"][0]["bucket"] == "UNMEASURED"
    assert source["failures"] == []
    assert repair.measure(tmp_path, require=True)["failures"]


def test_missing_detector_code_still_fails_in_source_context(tmp_path, monkeypatch):
    _detector(tmp_path, monkeypatch, present=False)
    assert any("no detector" in f for f in repair.measure(tmp_path)["failures"])


def test_actual_state_battery_explicitly_checks_family_birth_and_detector_state():
    assert ("check_self_repair.py", ("--require-state",)) in gate._STATE_FENCES
    assert ("check_birth_obligations.py", ("--require-state",)) in gate._STATE_FENCES


def test_a_clean_tree_laws_only_run_is_a_source_view_too(tmp_path, monkeypatch):
    """A clean tree skips the HEAD re-exec, and that path used to run every fence WITHOUT
    QUANT_LAWGATE_SOURCE_VIEW: the same commit read as live runtime only because it was clean."""
    monkeypatch.delenv("QUANT_LAWGATE_SOURCE_VIEW", raising=False)
    monkeypatch.setattr(gate, "_at_head", lambda root: (root, "cwd==HEAD (tree clean)", []))
    monkeypatch.setattr(gate, "_LAW_FENCES", (("check_x.py", ()),))
    (tmp_path / "scripts").mkdir()
    (tmp_path / "scripts" / "check_x.py").write_text("", "utf-8")
    seen: list[dict[str, str] | None] = []

    class _Done:
        returncode, stdout, stderr = 0, "ok", ""

    def _run(*a, **kw):
        seen.append(kw.get("env"))
        return _Done()

    monkeypatch.setattr(gate.subprocess, "run", _run)
    assert gate.full_gate(tmp_path, laws_only=True)["ok"]
    assert seen and seen[0] is not None and seen[0]["QUANT_LAWGATE_SOURCE_VIEW"] == "1"


def test_published_gateway_state_does_not_make_an_off_box_checkout_the_trading_host(
        tmp_path, monkeypatch):
    """The box publishes gateway_state.json to origin; fresh stamps in a copy are not this
    machine's gateway. Identity decides first, the gateway's age decides on the box."""
    from datetime import UTC, datetime

    from libs.ops import host_identity as hi
    cfg = {"hostname": "vmi3571445", "machine_id": "0123456789abcdef0123456789abcdef"}
    gs = tmp_path / "desks" / "mt5" / "data" / "gateway_state.json"
    gs.parent.mkdir(parents=True)
    gs.write_text(json.dumps({"last_reconcile": datetime.now(UTC).isoformat()}), "utf-8")
    monkeypatch.setattr(hi, "identify", lambda config_path=None: hi.classify(
        "fedcba9876543210fedcba9876543210", "runner", cfg))
    assert repair._trading_host(tmp_path) is False
    monkeypatch.setattr(hi, "identify", lambda config_path=None: hi.classify(
        cfg["machine_id"], "vmi3571445", cfg))
    assert repair._trading_host(tmp_path) is True
