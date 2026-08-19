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
    "screen_funding_spread.py",
    "screen_collateral_allocation.py",
    "check_build_standard.py",
    "check_fence_yield.py",
    "derive_walcl_clock.py",
    "run_llm_trader.py",
    "collect_announcements.py",
    "run_conviction_trader.py",
    "resolve_paper_book.py",
    "build_chart_context.py",
    "check_sizing_derivation.py",
    "check_mechanism_attribution.py",
    "run_trade_review.py",
    "screen_copytrading.py",
    "run_sleeve_allocator.py",
    "run_calibration_probe.py",
    "check_return_targeting.py",
    "check_organ_liveness.py",
    "check_freshness.py",
    "check_excitation.py",
    "check_clock_provenance.py",
    "check_funding_capture.py",
    "run_cost_identification.py",
    "screen_carry_basis_path.py",
    "check_promotion_gate.py",
    "run_discretionary_max.py",
    "run_discretionary_hunt.py",
    "run_cost_hunt.py",
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
    "check_crowding.py",
    "check_denominator_attrition.py",
    "check_denominators.py",
    "check_doctrine_diff.py",
    "check_extractor_invariants.py",
    "check_free_roster.py",
    "check_idle_cost.py",
    "check_input_provenance.py",
    "check_repair_capacity.py",
    "collect_dexscreener.py",
    "collect_funding_cross_section.py",
    "collect_geckoterminal_trades.py",
    "collect_holder_concentration.py",
    "collect_kr_venue_flags.py",
    "collect_perpdex_funding.py",
    "collect_unlock_calendar.py",
    "fit_passive_impact.py",
    "fit_print_impact.py",
    "probe_bybit_archive.py",
    "probe_delisted_instruments.py",
    "read_xls.py",
    "resolve_llm_trader_book.py",
    "retire_unfillable_candidates.py",
    "run_execution_quality.py",
    "run_natural_experiment.py",
    "run_paper_sleeve_spawner.py",
    "run_stale_daemon_repair.py",
    "run_upbit_snapshot.py",
    "screen_funding_interval_mismatch.py",
    "ship_restart.py",
    # --- added to _GOVERNED without this contract, resynced 2026-08-19 (second drift) ---
    "check_citation_integrity.py",
    "check_claim_consistency.py",
    "check_knob_sensitivity.py",
    "check_margin_topology.py",
    "check_panel_breadth.py",
    "check_partition_power.py",
    "collect_lending_risk_base_rates.py",
    "harvest_rfb_vintages.py",
    "run_cadence.py",
    "run_fee_attribution.py",
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
