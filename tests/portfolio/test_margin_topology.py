"""L1.64 comparator -- the capital structure is a decision, not an inheritance.

The tests that matter most pin the refusals and the wiring: UNMEASURED can never read as a
number (L1.28a), a decision against zero measured alternatives is paperwork, the executor's
venue-leverage constant cannot drift silently, and the capital plan cannot fork its own copy of
the capital levels again.
"""
from __future__ import annotations

import re
from pathlib import Path

import pytest

from libs.portfolio.margin_topology import (
    CAPITAL_LEVELS,
    CURRENT_CONSTRUCTION,
    EXECUTOR_VENUE_LEVERAGE,
    ConstructionRow,
    blended_npe,
    build_rows,
    coinm_inverse_npe,
    eligible_at,
    grade,
    level_table,
    multi_assets_npe,
    price_uplift,
    split_wallet_npe,
)

ROOT = Path(__file__).resolve().parents[2]

_FULL_TERMS = {
    "as_of": "2026-08-19T00:00:00+00:00",
    "usdtm_perp_bases": ["BTC", "ETH", "SOL", "XRP", "DOGE", "ADA", "NOM", "PEPE"],
    "coinm_perp_bases": ["BTC", "ETH", "SOL", "XRP", "ADA"],
    "multi_assets_collateral": {"BTC": 0.95, "ETH": 0.95, "SOL": 0.90, "XRP": 0.85},
    "pm_npe": 1.62,
    "pm_min_equity_usd": 10_000.0,
    "pm_source": "venue PM terms page, dated read",
}


# ---------------------------------------------------------------- arithmetic

def test_split_wallet_npe_at_executor_leverage():
    """$1 spot + $1/3 margin per $1 notional -> 0.75 notional per $1 equity."""
    assert split_wallet_npe(3.0) == pytest.approx(0.75)
    assert split_wallet_npe(1.0) == pytest.approx(0.5)
    with pytest.raises(ValueError):
        split_wallet_npe(0.0)


def test_self_collateralised_constructions_reach_parity():
    """When the coin margins its own hedge (h >= 1/L), the whole dollar is the long leg."""
    assert coinm_inverse_npe() == 1.0
    assert multi_assets_npe(0.95, 3.0) == pytest.approx(1.0)
    # a haircut below the IM must post the shortfall in stables, never exceed parity
    assert multi_assets_npe(0.10, 3.0) == pytest.approx(1.0 / (1.0 + (1.0 / 3.0 - 0.10)))
    with pytest.raises(ValueError):
        multi_assets_npe(1.5, 3.0)


def test_structural_multiplier_is_one_third_at_l3():
    """The headline: self-collateralisation is +33% carry capacity at identical equity."""
    assert coinm_inverse_npe() / split_wallet_npe(3.0) == pytest.approx(4.0 / 3.0)


# ---------------------------------------------------------------- rows

def test_full_terms_measure_every_venue_construction():
    rows = {r.key: r for r in build_rows(_FULL_TERMS)}
    assert rows["split_spot_usdtm"].status == "MEASURED"
    assert rows["multi_assets_usdtm"].status == "MEASURED"
    assert rows["coinm_inverse_1x"].status == "MEASURED"
    assert rows["portfolio_margin"].status == "MEASURED"
    assert rows["coinm_inverse_1x"].universe_coverage == pytest.approx(5 / 8)
    assert rows["multi_assets_usdtm"].universe_coverage == pytest.approx(4 / 8)
    # bybit stays LISTED though unmeasured -- the denominator never shrinks (L1.60)
    assert rows["bybit_uta"].status == "UNMEASURED"
    assert len(rows) == 5


def test_absent_terms_refuse_the_alternatives_but_never_the_inherited_row():
    """L1.28a: no venue terms -> no numbers for the alternatives. The inherited row stands on
    the executor's own constants, so INHERITED remains gradeable with zero network reads."""
    rows = {r.key: r for r in build_rows(None)}
    assert rows["split_spot_usdtm"].status == "MEASURED"
    assert rows["split_spot_usdtm"].notional_per_equity == pytest.approx(0.75)
    for key in ("multi_assets_usdtm", "coinm_inverse_1x", "portfolio_margin", "bybit_uta"):
        assert rows[key].status == "UNMEASURED"
        assert rows[key].notional_per_equity is None
        assert rows[key].next_action  # a refusal always names its repair


def test_every_switch_away_prices_its_forward_evidence_restart():
    """L2.10: forward evidence does not transfer across constructions."""
    for r in build_rows(_FULL_TERMS):
        if r.key != CURRENT_CONSTRUCTION:
            assert r.forward_evidence_restart is True


# ---------------------------------------------------------------- eligibility / levels

def test_pm_is_listed_but_ineligible_below_its_floor():
    rows = build_rows(_FULL_TERMS)
    pm = next(r for r in rows if r.key == "portfolio_margin")
    assert not eligible_at(pm, 3_846.0)
    assert eligible_at(pm, 25_000.0)


def test_level_table_never_awards_an_ineligible_or_unmeasured_multiplier():
    rows = build_rows(_FULL_TERMS)
    tbl = {row["capital_usd"]: row for row in level_table(rows)}
    # at seed, PM's 1.62 must NOT appear -- the 1.8-at-seed defect this build deletes -- and
    # the winner's npe is COVERAGE-BLENDED: CM covers 5/8 of the fixture universe, so the book
    # runs 0.625 of itself at 1.0 and the rest on the inherited 0.75.
    assert tbl[3_846.0]["best_construction"] == "coinm_inverse_1x"
    assert tbl[3_846.0]["best_npe"] == pytest.approx(0.625 * 1.0 + 0.375 * 0.75)
    # PM's coverage is structural (same USDT-M instruments), so at $25k it blends at 1.0
    assert tbl[25_000.0]["best_construction"] == "portfolio_margin"
    assert tbl[25_000.0]["best_npe"] == pytest.approx(1.62)
    # with no terms at all, the only measured construction is the inherited one
    bare = level_table(build_rows(None))
    assert all(row["best_construction"] == "split_spot_usdtm" for row in bare)
    assert all(row["best_npe"] == pytest.approx(0.75) for row in bare)


def test_blended_npe_never_lends_a_narrow_construction_the_whole_book():
    """The overclaim caught on this module's own first consumer run: COIN-M at the REAL
    measured coverage (20/527 = 3.8%) is a +1.3% book, not a +33% book."""
    rows = {r.key: r for r in build_rows(_FULL_TERMS)}
    cm = rows["coinm_inverse_1x"]
    assert blended_npe(cm, 0.75) == pytest.approx(0.625 * 1.0 + 0.375 * 0.75)
    real_world = ConstructionRow(**{**cm.as_dict(), "universe_coverage": 0.038})
    assert blended_npe(real_world, 0.75) == pytest.approx(0.7595)
    # unknown coverage -> no book claim (L1.28a)
    unknown = ConstructionRow(**{**cm.as_dict(), "universe_coverage": None})
    assert blended_npe(unknown, 0.75) is None


# ---------------------------------------------------------------- grading

def test_no_decision_row_is_inherited_the_failing_state():
    status, why = grade(build_rows(_FULL_TERMS), None)
    assert status == "INHERITED"
    assert "never chosen" in why


def test_zero_rows_is_unmeasured_never_a_verdict():
    status, _ = grade([], None)
    assert status == "UNMEASURED"


def test_a_decision_against_zero_measured_alternatives_is_paperwork():
    """L1.28a's sharpest edge here: DECIDED must be unreachable without a real comparison."""
    decision = {"construction": CURRENT_CONSTRUCTION, "decided_at": "2026-08-19",
                "decided_by": "principal", "equity_at_decision_usd": 4_000.0}
    status, why = grade(build_rows(None), decision)
    assert status == "UNMEASURED"
    assert "paperwork" in why


def test_decided_then_stale_on_equity_doubling():
    decision = {"construction": CURRENT_CONSTRUCTION, "decided_at": "2026-08-19",
                "decided_by": "principal", "equity_at_decision_usd": 4_000.0}
    rows = build_rows(_FULL_TERMS)
    assert grade(rows, decision, equity_now_usd=7_000.0)[0] == "DECIDED"
    status, why = grade(rows, decision, equity_now_usd=8_000.0, equity_basis="attested")
    assert status == "DECIDED-STALE"
    assert "doubling" in why


def test_a_decision_naming_a_construction_the_book_does_not_run_diverges():
    decision = {"construction": "coinm_inverse_1x", "decided_at": "2026-08-19",
                "decided_by": "principal"}
    status, why = grade(build_rows(_FULL_TERMS), decision)
    assert status == "DIVERGED"
    assert "coinm_inverse_1x" in why and CURRENT_CONSTRUCTION in why


# ---------------------------------------------------------------- pricing (L1.51)

def test_uplift_prices_both_rungs_and_the_liq_direction():
    up = price_uplift(build_rows(_FULL_TERMS), equity_usd=25_000.0,
                      equity_basis="nav_attestation (LIVE)",
                      cagr_validated=0.0, cagr_if_validated=0.01)
    best = up["alternatives"][0]
    # at $25k PM is eligible and carries the largest measured BOOK multiplier: 1.62 / 0.75
    # (its coverage is structural 1.0, so book == structural for PM)
    assert best["construction"] == "portfolio_margin"
    assert best["structural_multiplier"] == pytest.approx(1.62 / 0.75, abs=1e-3)
    assert best["book_multiplier"] == pytest.approx(1.62 / 0.75, abs=1e-3)
    # honest zero: nothing validated yet, so the validated rung is $0/day -- not omitted
    assert best["usd_per_day_at_validated_cagr"] == 0.0
    assert best["usd_per_day_if_validated"] is not None
    assert any("FALLS" in a["liq_direction"] for a in up["alternatives"])


def test_uplift_ranks_an_ineligible_multiplier_behind_an_exercisable_one():
    """L1.18a: at seed, PM's larger multiplier is locked -- the eligible 1.0x constructions
    must outrank it, or the artifact recommends an option the desk cannot exercise."""
    up = price_uplift(build_rows(_FULL_TERMS), equity_usd=3_846.0,
                      equity_basis="nav_attestation (LIVE)",
                      cagr_validated=0.0, cagr_if_validated=0.01)
    assert up["alternatives"][0]["construction"] in ("multi_assets_usdtm", "coinm_inverse_1x")
    assert up["alternatives"][0]["eligible_at_current_equity"] is True
    pm = next(a for a in up["alternatives"] if a["construction"] == "portfolio_margin")
    assert pm["eligible_at_current_equity"] is False


def test_uplift_refuses_dollars_on_a_molded_paper_book():
    """L1.51: a cost from a simulated denominator is worse than no number."""
    up = price_uplift(build_rows(_FULL_TERMS), equity_usd=17_323.61,
                      equity_basis="MOLDED-PAPER (testnet)",
                      cagr_validated=0.0, cagr_if_validated=0.01)
    for alt in up["alternatives"]:
        assert alt["usd_per_day_at_validated_cagr"] is None
        assert alt["usd_per_day_if_validated"] is None
        assert "UNMEASURABLE-PAPER-BOOK" in alt["usd_basis"]
        assert alt["per_10k_usd_per_day_if_validated"] is not None  # rates stay published


def test_uplift_with_no_measured_alternative_is_unmeasured():
    up = price_uplift(build_rows(None), equity_usd=None, equity_basis="UNMEASURED",
                      cagr_validated=0.0, cagr_if_validated=0.0)
    assert up["status"] == "UNMEASURED"


# ---------------------------------------------------------------- wiring (fails if removed)

def test_executor_venue_leverage_mirror_cannot_drift():
    """EXECUTOR_VENUE_LEVERAGE mirrors `fut.set_leverage(sym, 3)` in the executor. If the
    executor changes its venue leverage, this test fails and the mirror must move with it --
    a copied constant with no fence is how the 1.8 fiction survived (L1.46)."""
    src = (ROOT / "scripts/run_cashcarry_executor.py").read_text("utf-8")
    calls = set(re.findall(r"set_leverage\(\s*sym\s*,\s*(\d+)\s*\)", src))
    assert calls == {str(int(EXECUTOR_VENUE_LEVERAGE))}, (
        f"executor sets venue leverage {calls}, mirror says {EXECUTOR_VENUE_LEVERAGE:g} -- "
        "update EXECUTOR_VENUE_LEVERAGE and re-read every npe in data/margin_topology.json")


def test_capital_plan_imports_the_levels_rather_than_forking_them():
    """run_capital_plan must consume CAPITAL_LEVELS from this module -- two copies of the
    planning rungs is the two-sources-of-truth class (L1.61)."""
    import ast

    tree = ast.parse((ROOT / "scripts/run_capital_plan.py").read_text("utf-8"))
    imported = {alias.name
                for node in ast.walk(tree) if isinstance(node, ast.ImportFrom)
                and node.module and "margin_topology" in node.module
                for alias in node.names}
    assert "CAPITAL_LEVELS" in imported and "split_wallet_npe" in imported
    assigned = {t.id for node in ast.walk(tree) if isinstance(node, ast.Assign)
                for t in node.targets if isinstance(t, ast.Name)}
    assert "_PM_EFFICIENCY" not in assigned, (
        "the hardcoded PM multiplier is back -- L1.64 deleted it; efficiency comes from "
        "data/margin_topology.json or the measured split-construction floor")
    assert len(CAPITAL_LEVELS) == 5


def test_row_shape_is_stable_for_consumers():
    d = build_rows(None)[0].as_dict()
    for key in ("key", "status", "notional_per_equity", "npe_basis", "liq_unreachable",
                "universe_coverage", "funding_book", "eligibility_floor_usd",
                "forward_evidence_restart", "next_action"):
        assert key in d
    assert isinstance(build_rows(None)[0], ConstructionRow)
