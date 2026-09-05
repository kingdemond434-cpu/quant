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
    DONE_MARKER,
    DSR_THRESHOLD,
    GATES,
    PBO_THRESHOLD,
    SPA_ALPHA,
    TRIALS_MULTIPLIER,
    WF_MIN_STABILITY,
    all_ten_pass,
    charged_trial_count,
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
    assert "preregistered point-in-time regime" in ATTESTATION["regime_admission_unit"]
    assert "unknown or incompatible live regime is OFF" in ATTESTATION["regime_control"]
    assert DONE_MARKER == "DONE_qquant_gates_original10_v2"
    # THE BAR IS FIXED (principal, standing instruction): it never raises and never gets
    # harsher. The attestation must say so, because it is the field that pins what a certificate
    # was judged under.
    assert ATTESTATION["trial_count_basis"].startswith("fixed_campaign_trials(597)")


def test_charge_is_fixed_and_never_scales_with_sweep_size() -> None:
    """The same charge for every cell, whatever else shares its sweep.

    This replaces a test that pinned `ceil(effective_cells * 7)`. Under that rule a candidate was
    judged against the accident of its scheduling: measured 2026-08-28, sr0 was 0.3786 at 597
    charged trials and 1.3593 at 5,963 -- same gate, same policy, same cell, and the only thing
    that changed was how many other cells the docket happened to hold that hour. 506 cells
    cleared every VALIDITY gate and failed only the deflated Sharpe against the inflated bar.
    """
    expected = (597, "fixed_campaign_trials(597)")
    # Two orders of magnitude of sweep size, one charge.
    assert charged_trial_count(17, 17.0, "null_calibrated_participation_ratio") == expected
    assert charged_trial_count(368, 277.40, "null_calibrated_participation_ratio") == expected
    assert charged_trial_count(6270, 6000.0, "null_calibrated_participation_ratio") == expected
    # And it does not move when the dependence census is absent or unusable either: an
    # unmeasurable census used to make the bar HARSHER (raw_cells * 7), which is the one
    # direction it may never move.
    assert charged_trial_count(368, 246.46, "participation_ratio") == expected
    assert charged_trial_count(368, None, "unmeasurable") == expected


def test_a_bad_census_can_never_make_the_bar_harsher() -> None:
    """Malformed, missing or hand-tuned census inputs must not raise the charge.

    The old rule failed closed to `raw_cells * 7`, which is FAIL-HARSHER: a census this desk
    could not measure made every candidate in that sweep harder to certify. Failing closed is
    right when the failure protects against a false pass; here it protected against nothing and
    penalised the candidate for a measurement problem it had no part in.
    """
    expected = (597, "fixed_campaign_trials(597)")
    assert charged_trial_count(368, 1.0, "null_calibrated_participation_ratio") == expected
    assert charged_trial_count(368, 246.46, "hand_tuned") == expected
    assert charged_trial_count(
        368, float("nan"), "null_calibrated_participation_ratio") == expected
    # The charge is bounded above by the fixed count no matter what is passed in.
    for raw in (2, 368, 99_999):
        n, _basis = charged_trial_count(raw, None, "unmeasurable")
        assert n <= 597


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
    """The original ten gates are the sole shadow-admission certificate.

    Conditional cells are evaluated as their exact preregistered strategy-regime unit, so this
    does not require an edge to earn money in incompatible regimes. Later batteries and harsher
    overlays remain diagnostic and cannot veto an exact canonical certificate.
    """
    qquant = (DESK / "research" / "qquant_gates.py").read_text(encoding="utf-8")
    shadow = (DESK / "research" / "shadow_forward.py").read_text(encoding="utf-8")
    promoter = (DESK / "research" / "promoter.py").read_text(encoding="utf-8")
    assert 'rows = sv["real_survivors"]' not in qquant
    assert 'for r in all12' in qquant and 'for r in all16' in qquant
    # The admission door was rebuilt as `authorized_runs` when params became certificate
    # identity (2026-08-26); the LAW is unchanged -- every enrolment must come through
    # shadow_admission, which requires the exact policy attestation and all ten gates.
    assert "from shadow_admission import authorized_runs" in shadow, (
        "shadow admission must require the exact original-ten-gate certificate")
    admission = (DESK / "research" / "shadow_admission.py").read_text(encoding="utf-8")
    assert "all_ten_pass" in admission and "is_exact_policy" in admission, (
        "the admission door itself must verify the certificate, not trust the file")
    assert "gate_spec not in gate_authority" in promoter, (
        "live promotion must still independently require a real certificate")
    supervisor = (DESK / "research" / "research_supervisor.py").read_text(encoding="utf-8")
    assert DONE_MARKER in supervisor


def test_hunt16_stage_one_rejects_remain_in_universal_trial_ledger() -> None:
    source = (DESK / "research" / "run_hunt16.py").read_text(encoding="utf-8")
    reject_append = source.index("stage1_passed=False")
    reject_continue = source.index("continue", reject_append)
    assert reject_append < reject_continue
    assert '"all": results' in source[reject_append:reject_continue]


def test_every_hunt_uses_the_same_calibrated_cost_and_trial_policy() -> None:
    source = (DESK / "research" / "universal_gate.py").read_text(encoding="utf-8")
    assert "calibrated_census_report" in source
    assert "charged_trial_count" in source
    assert "Costs.from_symbol" in source
    assert "commission_per_lot * COST_SCENARIO" not in source
    assert "pd.DataFrame(cols).sort_index().fillna(0.0)" in source
    assert '"curve_compendium"' in source
    assert "stress_x3_return" in source
