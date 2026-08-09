from __future__ import annotations

import ast
from pathlib import Path

from scripts import check_build_standard

# Explicit by design: check_build_standard requires each governed organ to be named by a test.
# Updating _GOVERNED without extending this contract must fail.
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
