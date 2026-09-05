from __future__ import annotations

import ast
from pathlib import Path

from scripts import check_build_standard

# Explicit by design: check_build_standard requires each governed organ to be named by a test.
# Updating _GOVERNED without extending this contract must fail.
#
# ROTTED AND RESYNCED 2026-08-12. This mirror had drifted to 42 entries against a _GOVERNED of
# 75 -- 33 organs were added without it, so the test was red at HEAD and had stopped being a
# contract at all. Found while wiring L1.60, which is the same failure shape one level up: a
# hand-maintained list that cannot fall when the thing it counts changes. If it rots again,
# derive it instead of re-typing it.
GOVERNED = {
    "check_conversion.py",
    "check_calibration.py",
    "check_replacement_rate.py",
    "check_exploration.py",
    "check_law_families.py",
    "check_change_window.py",
    "run_law_gate.py",
    "run_moat_backup.py",
    "run_capability_hunt.py",
    "check_build_standard.py",
    "check_fence_yield.py",
    "derive_walcl_clock.py",
    "check_sizing_derivation.py",
    "check_mechanism_attribution.py",
    "run_calibration_probe.py",
    "check_return_targeting.py",
    "check_organ_liveness.py",
    "check_freshness.py",
    "check_excitation.py",
    "check_clock_provenance.py",
    "run_cost_identification.py",
    "check_promotion_gate.py",
    "run_strategy_coverage.py",
    "check_strategy_breadth.py",
    "run_principal_benchmark.py",
    "run_organ_er.py",
    "check_enforcement_execution.py",
    # --- added to _GOVERNED without this contract, resynced 2026-08-12 ---
    "build_event_calendar.py",
    "check_birth_properties.py",
    "check_campaign_retention.py",
    "check_capital_basis.py",
    "check_denominator_attrition.py",
    "check_denominators.py",
    "check_doctrine_diff.py",
    "check_extractor_invariants.py",
    "check_free_roster.py",
    "check_idle_cost.py",
    "check_input_provenance.py",
    "check_repair_capacity.py",
    "fit_passive_impact.py",
    "fit_print_impact.py",
    "read_xls.py",
    "retire_unfillable_candidates.py",
    "run_paper_sleeve_spawner.py",
    "run_stale_daemon_repair.py",
    "ship_restart.py",
    # THIRTY ORGANS REMOVED 2026-09-05 (universe mandate), in lockstep with `_GOVERNED`. Their
    # FILES are gone -- the crypto-exchange screens, collectors, paper sleeves, order-path and fee
    # organs, and the three law fences whose only subject was a perp construction (L1.47 funding
    # capture, L1.63 partition power, L1.64 margin topology). This mirror is a CONTRACT on
    # `_GOVERNED`, so it has to move with it or the equality assertion below is the thing that
    # breaks -- which is exactly the drift the 2026-08-12 resync note warns about, in the other
    # direction: that time the list failed to GROW, this time it had to shrink.
    #
    # SIX ADDED IN THE SAME PASS. check_citation_integrity, check_claim_consistency,
    # check_panel_breadth, check_risk_units, harvest_rfb_vintages and run_cadence were in
    # `_GOVERNED` and NOT here, so this contract was already red at HEAD -- the 2026-08-12 rot,
    # recurring. A mirror that only ever loses entries would have hidden that.
    "check_citation_integrity.py",
    "check_claim_consistency.py",
    "check_panel_breadth.py",
    "check_risk_units.py",
    "harvest_rfb_vintages.py",
    "run_cadence.py",
}


def test_every_governed_organ_meets_the_shared_build_contract() -> None:
    assert set(check_build_standard._GOVERNED) == GOVERNED

    report = check_build_standard.build_report()
    assert report["status"] == "OK"
    assert report["n_failing"] == 0
    assert report["failing"] == []


def test_every_governed_organ_is_valid_python() -> None:
    root = Path(check_build_standard.__file__).resolve().parents[1]
    for name in sorted(GOVERNED):
        source = (root / "scripts" / name).read_text("utf-8")
        ast.parse(source, filename=name)
