"""R0287: the return-on-capital-utilized invariant and its fence.

Pins the two honesty properties: the helper REFUSES a non-positive denominator (a return on no
capital is an upstream division error, not a large return), and the fence fails an artifact that
reports a return without declaring its basis while leaving delta-denominated and basis-declaring
artifacts alone -- including the pre-launch case, where files exist but none report returns yet
(OK with a real scanned count, never a vacuous pass).
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest
from scripts.check_capital_basis import build_report

from libs.research.capital_basis import BASES, declare, return_on_capital_utilized


def test_the_computation_and_its_refusal() -> None:
    assert return_on_capital_utilized(58.0, 100.0) == pytest.approx(0.58)
    for bad in (0.0, -5.0):
        with pytest.raises(ValueError, match="refuse, never fabricate"):
            return_on_capital_utilized(10.0, bad)


def test_declare_rejects_vocabulary_the_fence_cannot_verify() -> None:
    assert declare("capital_utilized", 4500.0) == {
        "capital_basis": "capital_utilized", "capital_basis_usd": 4500.0}
    with pytest.raises(ValueError, match="not in"):
        declare("whatever_felt_right")
    assert "portfolio_value" in BASES  # legal to declare BECAUSE visible -- the fence's contract


def test_fence_fails_a_new_undeclared_return_and_passes_a_declared_one(tmp_path: Path) -> None:
    web = tmp_path / "web"
    web.mkdir()
    (web / "bad.json").write_text(json.dumps({"annual_return": 1.9}), "utf-8")
    (web / "good.json").write_text(json.dumps(
        {"annual_return": 0.58, **declare("capital_utilized", 100.0)}), "utf-8")
    (web / "deltas.json").write_text(json.dumps({"net_pnl_equity_delta": -55.0}), "utf-8")
    rep = build_report(tmp_path)
    assert rep["status"] == "UNDECLARED-RETURNS"
    assert [u["artifact"] for u in rep["undeclared_new"]] == ["web/bad.json"]
    assert rep["scanned"] == 3 and rep["n_reporting_returns"] == 2


def test_bootstrap_debt_passes_distinctly_and_only_new_offenders_fail(tmp_path: Path) -> None:
    """The dated 2026-08-11 offenders hold the line without blocking every push; a NEW artifact
    joining them is the regression the fence exists to stop."""
    web = tmp_path / "web"
    web.mkdir()
    (web / "binance.json").write_text(json.dumps({"month_return_pct": 2.1}), "utf-8")
    rep = build_report(tmp_path)
    assert rep["status"] == "BOOTSTRAP-DEBT"
    assert rep["bootstrap_debt"] == ["web/binance.json"] and not rep["undeclared_new"]
    (web / "brand_new_sleeve.json").write_text(json.dumps({"cagr": 0.4}), "utf-8")
    assert build_report(tmp_path)["status"] == "UNDECLARED-RETURNS"


def test_prelaunch_is_ok_with_a_real_denominator_and_nothing_is_unmeasured_ok(
        tmp_path: Path) -> None:
    web = tmp_path / "web"
    web.mkdir()
    (web / "book.json").write_text(json.dumps({"n_carries": 0, "deployed_notional": 0.0}), "utf-8")
    rep = build_report(tmp_path)
    assert rep["status"] == "OK" and rep["scanned"] == 1 and rep["n_reporting_returns"] == 0
    # and with NOTHING to examine the verdict is UNMEASURED, never OK (L1.28a)
    assert build_report(tmp_path / "empty")["status"] == "UNMEASURED"


def test_research_series_and_research_roi_are_not_book_returns(tmp_path: Path) -> None:
    web = tmp_path / "web"
    web.mkdir()
    (web / "axis.json").write_text(json.dumps(
        {"axes": [{"axis": "kimchi", "returns": [0.01, -0.02]}]}), "utf-8")
    (web / "queue.json").write_text(json.dumps(
        {"research_queue": [{"item": "x", "roi": 15.0}]}), "utf-8")
    rep = build_report(tmp_path)
    assert rep["status"] == "OK" and rep["n_reporting_returns"] == 0
