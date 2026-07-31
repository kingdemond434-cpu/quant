"""R0120 -- the desk's base allocation assumption, tested for the first time."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from scripts.screen_collateral_allocation import best_lending_apy, build_report, funding_regimes


def _seed(root: Path, *, apy_pct: float, funding_8h: float, n: int = 30) -> None:
    (root / "data").mkdir(parents=True, exist_ok=True)
    (root / "data/defi_lending.jsonl").write_text(json.dumps(
        {"data": [{"symbol": "USDT", "project": "aave", "supply_apy": apy_pct}]}), "utf-8")
    (root / "data/bitmex_funding.jsonl").write_text("\n".join(
        json.dumps({"fundingRate": funding_8h}) for _ in range(n)), "utf-8")


def test_zero_haircut_is_refused():
    # Modelling contract/depeg/withdrawal risk as zero is how a screen manufactures a winner.
    with pytest.raises(ValueError, match="haircut_bps must be > 0"):
        build_report(Path("."), haircut_bps=0.0)


def test_apy_parsed_as_percent_or_fraction(tmp_path):
    _seed(tmp_path, apy_pct=5.0, funding_8h=0.0001)
    assert abs(best_lending_apy(tmp_path)[0] - 0.05) < 1e-9      # 5.0 -> 0.05
    (tmp_path / "data/defi_lending.jsonl").write_text(json.dumps(
        {"data": [{"symbol": "USDC", "supply_apy": 0.042}]}), "utf-8")
    assert abs(best_lending_apy(tmp_path)[0] - 0.042) < 1e-9     # already a fraction


def test_high_funding_makes_carry_dominant(tmp_path):
    _seed(tmp_path, apy_pct=4.0, funding_8h=0.0004)   # ~44% annualised carry
    rep = build_report(tmp_path)
    assert rep["status"] == "CARRY-DOMINANT"
    assert "VALIDATED" in rep["detail"]               # the assumption, finally tested


def test_flat_funding_can_make_lending_win(tmp_path):
    _seed(tmp_path, apy_pct=9.0, funding_8h=0.000002)  # ~0.2% carry vs 9% lending
    rep = build_report(tmp_path)
    assert rep["status"] == "LENDING-DOMINANT"
    assert "questions the desk's base allocation" in rep["detail"]


def test_missing_feed_is_unmeasured_not_carry_wins(tmp_path):
    # The critical honesty property: an untestable assumption stays UNTESTED, never "validated".
    rep = build_report(tmp_path)
    assert rep["status"] == "UNMEASURED"
    assert "NOT 'carry wins'" in rep["detail"]


def test_regime_split_is_measured(tmp_path):
    (tmp_path / "data").mkdir(parents=True)
    (tmp_path / "data/bitmex_funding.jsonl").write_text("\n".join(
        [json.dumps({"fundingRate": 0.0004})] * 6 + [json.dumps({"fundingRate": 0.00001})] * 4),
        "utf-8")
    reg = funding_regimes(tmp_path)
    assert reg["measured"] is True and reg["n"] == 10
    assert reg["pct_high_regime"] == 60.0


def test_screen_moves_no_funds():
    # Assert on CALL SITES, not substrings: the docstring legitimately discusses withdrawal-queue
    # risk, and a naive substring ban flagged its own safety rationale as a violation.
    import ast
    tree = ast.parse(Path("scripts/screen_collateral_allocation.py").read_text("utf-8"))
    called = {n.func.attr for n in ast.walk(tree)
              if isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute)}
    called |= {n.func.id for n in ast.walk(tree)
               if isinstance(n, ast.Call) and isinstance(n.func, ast.Name)}
    for banned in ("place_order", "place_market", "place_post_only", "transfer", "withdraw",
                   "flatten_all"):
        assert banned not in called
    assert "STAGE A" in build_report(Path("."))["authority"]
