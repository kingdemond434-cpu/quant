"""R0334: the six-component execution-quality decomposition.

The load-bearing tests are the refusals. A blended score is easy; what makes this decomposition
worth having is that each component says when it CANNOT be scored instead of returning a number
that reads like a verdict.
"""

from __future__ import annotations

from typing import Any

import pytest

from libs.research.execution_quality import COMPONENTS, MIN_N, score


def _entry(key: str, *, stop_pct: float = 1.0, noise: float = 0.5,
           risk: float = 0.05, expected: float = 3.0) -> dict[str, Any]:
    return {"at": key, "stop_pct": stop_pct, "noise": {"floor_pct": noise},
            "sizing": {"risk_fraction": risk}, "expected_move_pct": expected}


def _close(key: str, *, r: float = 1.0, stage: int = 1, top: int = 3) -> dict[str, Any]:
    return {"key": key, "kind": "conviction", "closed": True, "realised_R": r,
            "stage_reached": stage, "max_stage": top}


def _path(*rs: float) -> list[dict[str, Any]]:
    return [{"realised_R": r} for r in rs]


def _book(n: int, **kw: Any) -> tuple[list, list, dict]:
    entries = [_entry(f"k{i}", **kw) for i in range(n)]
    closes = [_close(f"k{i}") for i in range(n)]
    paths = {f"k{i}": _path(-0.2, 0.5, 2.0, 1.0) for i in range(n)}
    return entries, closes, paths


def _by_name(comps: list) -> dict[str, Any]:
    return {c.name: c for c in comps}


def test_all_six_components_are_always_returned() -> None:
    """A missing component reads as 'not a problem'; an INSUFFICIENT one reads as 'not known'."""
    comps = _by_name(score(*_book(MIN_N + 2)))
    assert tuple(comps) == COMPONENTS


def test_every_component_refuses_a_thin_sample() -> None:
    entries, closes, paths = _book(2)
    for comp in score(entries, closes, paths):
        assert comp.state in ("INSUFFICIENT", "UNMEASURABLE-BY-DESIGN")
        assert comp.value is None


def test_an_empty_book_scores_nothing_rather_than_perfectly() -> None:
    for comp in score([], [], {}):
        assert comp.value is None


# ------------------------------------------------------------------- target: no ground truth


def test_target_quality_is_unmeasurable_by_design_not_a_zero() -> None:
    """The sleeve forbids take-profits on purpose, so there is no target decision to score.
    Returning 0.0 would report perfect-failure at a decision nobody made."""
    comps = _by_name(score(*_book(MIN_N + 3)))
    target = comps["target_quality"]
    assert target.state == "UNMEASURABLE-BY-DESIGN"
    assert target.value is None
    assert "no targets" in target.why
    # the proxy is still published, and labelled a proxy
    assert "proxy" in target.detail


# ---------------------------------------------------------- stop: the constant-pass gate (L1.49)


def test_stop_quality_flags_itself_as_a_constant_pass_gate_when_nothing_is_rejected() -> None:
    """MEASURED 0 of 17 real entries sit inside the noise band, because the trader DERIVES the
    stop past it. A gate that never rejects measures the constructor, not the decisions."""
    comps = _by_name(score(*_book(MIN_N + 2, stop_pct=2.0, noise=1.0)))
    stop = comps["stop_quality"]
    assert stop.state == "MEASURED"
    assert stop.value == pytest.approx(2.0)
    assert stop.detail["n_inside_noise"] == 0
    assert "zero information" in stop.detail["constant_pass_warning"]


def test_stop_quality_names_a_real_breach_rather_than_the_gate_warning() -> None:
    """When stops ARE inside the noise the warning must flip to the defect, not stay boilerplate."""
    comps = _by_name(score(*_book(MIN_N + 2, stop_pct=0.4, noise=1.0)))
    stop = comps["stop_quality"]
    assert stop.detail["n_inside_noise"] == MIN_N + 2
    assert "INSIDE the noise band" in stop.detail["constant_pass_warning"]


# ------------------------------------------------------------------ sizing: needs variation


def test_sizing_quality_refuses_a_constant_risk_fraction() -> None:
    """A correlation against a constant is undefined, not zero. Reporting 0.0 would say 'sizing
    adds nothing' when the truth is 'no sizing decision was ever made'."""
    comps = _by_name(score(*_book(MIN_N + 3, risk=0.05)))
    sizing = comps["sizing_quality"]
    assert sizing.state == "UNMEASURABLE-BY-DESIGN"
    assert sizing.value is None


def test_sizing_quality_scores_when_risk_actually_varies() -> None:
    n = MIN_N + 3
    entries = [_entry(f"k{i}", risk=0.01 * (i + 1)) for i in range(n)]
    closes = [_close(f"k{i}", r=float(i)) for i in range(n)]      # bigger bets on better trades
    paths = {f"k{i}": _path(0.1, float(i) + 0.5) for i in range(n)}
    sizing = _by_name(score(entries, closes, paths))["sizing_quality"]
    assert sizing.state == "MEASURED"
    assert sizing.value == pytest.approx(1.0)                     # perfect rank agreement


# ------------------------------------------------------------------------- exit timing


def test_capture_ratio_excludes_trades_that_never_went_favourable() -> None:
    """A trade with no peak has no capture to measure; folding it in as 0.0 blames the exit for
    an entry that never worked, which is exactly the blended-score confusion this splits apart."""
    n = MIN_N + 2
    entries = [_entry(f"k{i}") for i in range(n)]
    closes = [_close(f"k{i}", r=1.0) for i in range(n)]
    paths = {f"k{i}": _path(-0.5, 2.0) for i in range(n)}
    paths["k0"] = _path(-0.3, -0.8)                               # never favourable
    closes[0] = _close("k0", r=-1.0)
    exit_c = _by_name(score(entries, closes, paths))["exit_timing"]
    assert exit_c.state == "MEASURED"
    assert exit_c.detail["n_no_favourable_peak"] == 1
    assert exit_c.n == n - 1
    assert exit_c.value == pytest.approx(0.5)                     # kept 1.0 of a 2.0 peak


def test_capture_ratio_states_its_own_upward_bias() -> None:
    """MFE is hourly-sampled, so a peak given back between marks is invisible and the reported
    capture is at best an upper bound. A reader must not take it as exact."""
    exit_c = _by_name(score(*_book(MIN_N + 2)))["exit_timing"]
    assert "at most this good" in exit_c.detail["bias"]


# -------------------------------------------------------------------------- trade management


def test_trade_management_counts_trades_that_never_left_the_first_rung() -> None:
    n = MIN_N + 2
    entries = [_entry(f"k{i}") for i in range(n)]
    closes = [_close(f"k{i}", stage=0, top=3) for i in range(n)]
    closes[0] = _close("k0", stage=3, top=3)
    paths = {f"k{i}": _path(0.1, 1.0) for i in range(n)}
    mgmt = _by_name(score(entries, closes, paths))["trade_management"]
    assert mgmt.detail["n_never_left_stage_0"] == n - 1
    assert mgmt.detail["n_reached_top"] == 1


# ------------------------------------------------------------------------------ the producer


# ---------------------------------------------------------------------------------------------
# RETIRED 2026-09-05. The tests removed here drove `scripts/run_execution_quality.py`,
# deleted in 1657d5f7 with the
# retired crypto desk (MT5 universe mandate, 2026-08-18). They had been failing on
# ModuleNotFoundError ever since, which is not a verdict on anything -- it is a test for code the
# desk decided on purpose not to have, and a permanently red test is a disabled gate that also
# trains its reader to skip the file.
#
# Everything in this file that tests code which still EXISTS is untouched: the properties worth
# keeping are asserted above against modules that are here.
# ---------------------------------------------------------------------------------------------
