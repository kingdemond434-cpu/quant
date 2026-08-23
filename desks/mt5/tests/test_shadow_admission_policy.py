from __future__ import annotations

import json
import sys
from pathlib import Path

DESK = Path(__file__).resolve().parents[1]
for path in (DESK, DESK / "research", DESK.parent.parent):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

from gate_policy import (  # noqa: E402
    ATTESTATION,
    COST_SCENARIO,
    DSR_THRESHOLD,
    DONE_MARKER,
    GATES,
    PBO_THRESHOLD,
    SPA_ALPHA,
    TRIALS_MULTIPLIER,
    WF_MIN_STABILITY,
    all_ten_pass,
)
from shadow_admission import authorized_specs, partition_work  # noqa: E402


def _stages() -> dict:
    return {name: {"passed": True} for name in GATES}


def test_original_thresholds_are_one_fixed_policy() -> None:
    assert TRIALS_MULTIPLIER == 7.0
    assert DSR_THRESHOLD == 0.95
    assert PBO_THRESHOLD == 0.5
    assert SPA_ALPHA == 0.05
    assert WF_MIN_STABILITY == 0.5
    assert COST_SCENARIO == 3.0
    assert ATTESTATION["wf_test_size"] == "max(20,len//6)"
    assert DONE_MARKER == "DONE_qquant_gates_original10_v1"


def test_partial_extra_or_failed_gate_sets_never_admit() -> None:
    stages = _stages()
    assert all_ten_pass(stages)
    assert not all_ten_pass({k: v for k, v in stages.items() if k != "pbo"})
    assert not all_ten_pass({**stages, "harsher_overlay": {"passed": True}})
    stages["pbo"] = {"passed": False}
    assert not all_ten_pass(stages)


def test_only_exact_policy_certificate_enters_shadow(tmp_path: Path) -> None:
    reports = tmp_path / "reports"
    reports.mkdir()
    row = {
        "id": "XAUUSD breakout LONG asia UNCONDITIONED",
        "passed": True,
        "stages": _stages(),
        # A harsher diagnostic is deliberately irrelevant to admission.
        "battery": {"passed": False, "threshold": 999},
    }
    (reports / "QQUANT_GATES.json").write_text(
        json.dumps({"gate_policy": ATTESTATION, "verdicts": [row]}), encoding="utf-8")
    spec = ("XAUUSD", "asia", None, "session_range_breakout", False)
    other = ("USDJPY", "asia", None, "session_range_breakout", False)
    assert authorized_specs(tmp_path) == {spec}
    assert partition_work([spec, other], tmp_path) == ([spec], [other])

    (reports / "QQUANT_GATES.json").write_text(json.dumps({
        "gate_policy": {**ATTESTATION, "wf_min_stability": 0.58},
        "verdicts": [row],
    }), encoding="utf-8")
    assert authorized_specs(tmp_path) == set()


def test_production_path_has_no_harsher_prefilter() -> None:
    qquant = (DESK / "research" / "qquant_gates.py").read_text(encoding="utf-8")
    shadow = (DESK / "research" / "shadow_forward.py").read_text(encoding="utf-8")
    promoter = (DESK / "research" / "promoter.py").read_text(encoding="utf-8")
    assert 'rows = sv["real_survivors"]' not in qquant
    assert 'for r in all12' in qquant and 'for r in all16' in qquant
    assert "partition_work(_declared, BASE)" in shadow
    assert "gate_spec not in gate_authority" in promoter
    supervisor = (DESK / "research" / "research_supervisor.py").read_text(encoding="utf-8")
    assert DONE_MARKER in supervisor
