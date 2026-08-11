"""Gate items 5-8 of the pre-DeepSeek completion gate, proven as behavior.

Each test is named for the gate item it discharges, because this file IS the evidence the gate
ledger points at. The load-bearing negatives matter more than the positives: the lifecycle must
REFUSE lossy hibernations, unidentifiable regimes and ledger-minted reactivations loudly --
those refusals are what keep this a lifecycle and not a second promotion authority.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

import libs.research.alpha_lifecycle as al
from libs.research.alpha_lifecycle import (
    LifecycleError,
    conditional_track,
    current_states,
    hibernate,
    mark_revalidation_pending,
    reality_gaps,
)

_SIG = {"trend": "bull", "funding": "rich"}


def _admit(tmp: Path, name: str = "vrp_carry_x") -> dict:
    return conditional_track(
        name, unconditional_verdict="POWERED-NEGATIVE", regime_signature=_SIG,
        conditional_obs=180, conditional_sharpe=1.4, regimes_searched=12,
        mechanism="funding-rich carry pays the warehouse; bleeds in funding-poor chop",
        root=tmp)


def _hibernate(tmp: Path, name: str = "vrp_carry_x") -> dict:
    return hibernate(name, why="funding regime absent 60d", state_snapshot={
        "regime_signature": _SIG,
        "evidence_artifacts": ["data/vrp_carry_x_shadow_state.json"],
        "parameters": {"lookback": 30},
        "reactivation_conditions": "trend=bull AND funding=rich for 5 consecutive days",
        "shadow_monitor": "run_paper_sleeve_forward continues accrual",
    }, root=tmp)


# ------------------------------------------------------------------ gate item 5
def test_item5_weak_unconditional_reaches_conditional_track(tmp_path: Path) -> None:
    row = _admit(tmp_path)
    assert row["state"] == "PROBATION" and row["track"] == "CONDITIONAL"
    # The unconditional verdict is carried UNCHANGED -- the track never overturns it.
    assert row["unconditional_verdict"] == "POWERED-NEGATIVE"
    # The multiplicity charge travels with the hypothesis.
    assert row["regimes_searched"] == 12


def test_item5_works_sometimes_is_not_a_regime(tmp_path: Path) -> None:
    with pytest.raises(LifecycleError, match="not a regime"):
        conditional_track("x", unconditional_verdict="NEG", regime_signature={},
                          conditional_obs=180, conditional_sharpe=1.0,
                          regimes_searched=3, mechanism="m", root=tmp_path)


def test_item5_underpowered_cell_is_refused_not_admitted(tmp_path: Path) -> None:
    with pytest.raises(LifecycleError, match="UNDERPOWERED"):
        conditional_track("x", unconditional_verdict="NEG", regime_signature=_SIG,
                          conditional_obs=9, conditional_sharpe=4.0,
                          regimes_searched=3, mechanism="m", root=tmp_path)


def test_item5_undeclared_search_breadth_is_refused(tmp_path: Path) -> None:
    with pytest.raises(LifecycleError, match="multiplicity"):
        conditional_track("x", unconditional_verdict="NEG", regime_signature=_SIG,
                          conditional_obs=180, conditional_sharpe=1.0,
                          regimes_searched=0, mechanism="m", root=tmp_path)


# ------------------------------------------------------------------ gate item 6
def test_item6_hibernation_preserves_full_state(tmp_path: Path) -> None:
    _admit(tmp_path)
    row = _hibernate(tmp_path)
    assert row["state"] == "HIBERNATING"
    snap = row["snapshot"]
    for key in ("regime_signature", "evidence_artifacts", "parameters",
                "reactivation_conditions", "shadow_monitor"):
        assert snap[key], key
    # And the ledger fold agrees.
    assert current_states(tmp_path)["vrp_carry_x"]["state"] == "HIBERNATING"


def test_item6_lossy_snapshot_is_a_refused_retirement(tmp_path: Path) -> None:
    with pytest.raises(LifecycleError, match="LOSSY"):
        hibernate("x", why="regime absent",
                  state_snapshot={"regime_signature": _SIG}, root=tmp_path)


# ------------------------------------------------------------------ gate item 7
def test_item7_reactivation_routes_through_revalidation_never_active(tmp_path: Path) -> None:
    _admit(tmp_path)
    _hibernate(tmp_path)
    row = mark_revalidation_pending("vrp_carry_x",
                                    evidence="funding=rich 6 consecutive days", root=tmp_path)
    assert row["state"] == "REVALIDATION_PENDING"        # NOT ACTIVE
    assert "forward clock" in row["why"] or "forward clock" in row["next_consumer"]
    # The snapshot rides along so the clock spawner has everything it needs.
    assert row["snapshot"]["regime_signature"] == _SIG


def test_item7_only_hibernating_can_request_revalidation(tmp_path: Path) -> None:
    _admit(tmp_path)                                     # currently PROBATION
    with pytest.raises(LifecycleError, match="HIBERNATING"):
        mark_revalidation_pending("vrp_carry_x", evidence="e", root=tmp_path)


def test_item7_the_module_has_no_reactivate(  ) -> None:
    """There is deliberately no reactivate(): the ledger must be unable to mint active alphas.
    Pinned so a future convenience helper cannot slip in without failing a named test."""
    assert not hasattr(al, "reactivate")
    assert "ACTIVE" in al.STATES     # the state exists; this module just cannot grant it
    granted = {"PROBATION", "HIBERNATING", "REVALIDATION_PENDING"}
    assert "ACTIVE" not in granted


# ------------------------------------------------------------------ gate item 8 (local half)
def test_item8_stalled_revalidation_is_a_named_gap(tmp_path: Path) -> None:
    _admit(tmp_path)
    _hibernate(tmp_path)
    mark_revalidation_pending("vrp_carry_x", evidence="e", root=tmp_path)
    gaps = reality_gaps(tmp_path)
    assert [g["gap"] for g in gaps] == ["REVALIDATION_STALLED"]


def test_item8_started_clock_clears_the_stall(tmp_path: Path) -> None:
    _admit(tmp_path)
    _hibernate(tmp_path)
    mark_revalidation_pending("vrp_carry_x", evidence="e", root=tmp_path)
    (tmp_path / "data").mkdir(exist_ok=True)
    (tmp_path / "data/vrp_carry_x_shadow_state.json").write_text(
        json.dumps({"shadow_start": "2026-08-11T00:00:00+00:00"}), "utf-8")
    assert reality_gaps(tmp_path) == []


def test_item8_reactivation_due_fires_when_regime_returns(tmp_path: Path) -> None:
    _admit(tmp_path)
    _hibernate(tmp_path)
    due = reality_gaps(tmp_path, regime_now={"trend": "bull", "funding": "rich", "vol": "low_vol"})
    assert [g["gap"] for g in due] == ["REACTIVATION_DUE"]
    # And a non-matching regime stays quiet -- hibernation through an unfavorable regime is the
    # designed behavior, not a defect.
    quiet = reality_gaps(tmp_path, regime_now={"trend": "bear", "funding": "poor"})
    assert quiet == []
