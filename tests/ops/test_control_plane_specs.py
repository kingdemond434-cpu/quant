"""The ComponentSpec: mandatory fields, derived silence, and a registry that cannot lie."""
from __future__ import annotations

from pathlib import Path

import pytest

from libs.ops.control_plane.specs import (
    CRITICALITY,
    MIN_SILENCE_S,
    STATES,
    UNMEASURED,
    ComponentSpec,
    Registry,
    derive_max_silence,
    spec,
)


def test_state_model_is_exactly_the_law():
    assert STATES == ("DECLARED", "STARTING", "HEALTHY", "DEGRADED", "STALE", "STALLED",
                      "BROKEN", "REPAIRING", "QUARANTINED", "RETIRED")
    assert CRITICALITY == ("required", "optional")


def test_max_silence_is_derived_never_flat():
    assert derive_max_silence(None) is None
    assert derive_max_silence(3600) == 7200                      # 2x cadence
    assert derive_max_silence(600, 10_800) == 11_400             # timeout + cadence wins
    assert derive_max_silence(600, 1_920) == 2_520
    assert derive_max_silence(10) == MIN_SILENCE_S               # never below the floor
    # the old flat four hours is not what any cadence in the desk derives to by accident
    assert derive_max_silence(600) != 4 * 3600


def test_spec_derives_silence_and_slas_and_refuses_bad_vocabulary():
    s = ComponentSpec("resident:x", kind="resident", host="box", cadence_s=600,
                      timeout_s=10_800, criticality="required", schedule="MT5-X")
    assert s.max_silence_s == 11_400 and s.detection_sla_s == 11_400
    assert s.repair_sla_s == 600 + 10_800 and s.sla_s == 11_400 + 11_400
    assert s.scheduled
    u = ComponentSpec("exe:y")
    assert u.cadence_s is None and u.max_silence_s is None and u.sla_s is None
    assert not u.scheduled and u.progress_metric == UNMEASURED
    with pytest.raises(ValueError):
        ComponentSpec("bad", criticality="sometimes")
    with pytest.raises(ValueError):
        ComponentSpec("bad", kind="thing")
    with pytest.raises(ValueError):
        ComponentSpec("bad", host="laptop")


def test_code_identity_separates_code_from_config(tmp_path: Path):
    (tmp_path / "a.py").write_text("print(1)\n", encoding="utf-8")
    s1 = spec("exe:a", code_paths=["a.py"], cadence_s=60, schedule="t")
    s2 = spec("exe:a", code_paths=["a.py"], cadence_s=120, schedule="t")
    assert s1.code_sha(tmp_path) == s2.code_sha(tmp_path)          # same bytes
    assert s1.config_hash() != s2.config_hash()                     # different declaration
    ident = s1.code_identity(tmp_path)
    assert set(ident) == {"code_sha", "config_hash"}
    assert spec("exe:gone", code_paths=["nope.py"]).code_sha(tmp_path) == UNMEASURED
    d = s1.to_dict(root=tmp_path)
    assert d["code_paths"] == ["a.py"] and d["code_identity"]["code_sha"] == ident["code_sha"]


def test_registry_refuses_duplicates_and_names_its_own_lies(tmp_path: Path):
    (tmp_path / "ok.py").write_text("x = 1\n", encoding="utf-8")
    reg = Registry([spec("a", code_paths=["ok.py"], cadence_s=60, schedule="A")])
    with pytest.raises(ValueError):
        reg.add(spec("a"))
    reg.add(spec("b", code_paths=["missing.py"], criticality="required"))
    reg.add(spec("c", cadence_s=600, max_silence_s=100, schedule="C"))
    problems = reg.problems(tmp_path)
    assert any("missing.py does not exist" in p for p in problems)
    assert any("b: required but no schedule" in p for p in problems)
    assert any("b: required but max_silence is UNMEASURED" in p for p in problems)
    assert any("c: max_silence 100s is shorter" in p for p in problems)
    assert reg.owners_of("ok.py")[0].component_id == "a"
    assert reg.claimed_paths() == {"ok.py", "missing.py"}
    assert [s.component_id for s in reg.required()] == ["b"]
    c = reg.census(tmp_path)
    assert c["components"] == 3 and c["scheduled"] == 2 and c["unscheduled"] == 1
    assert "a" in reg and len(reg) == 3 and reg.get("zzz") is None
