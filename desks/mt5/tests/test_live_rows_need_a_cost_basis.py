"""UNKNOWN COST IS UNKNOWN EDGE -- a LIVE sleeve row without a cost basis holds no capital.

    python -m pytest desks/mt5/tests/test_live_rows_need_a_cost_basis.py -q

External audit 2026-09-29: 40/40 LIVE rows carried artifact.ok = false, "no cost basis", because
the artifact read a `cost_hash` field no writer ever put on a sleeve row. The promoter now stamps
the basis from the row, the clock's frozen identity or the universe registry, and demotes a row
with none of the three to STANDBY (reversible) rather than funding it.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

DESK = Path(__file__).resolve().parents[1]
for _p in (str(DESK), str(DESK / "research"), str(DESK.parent.parent)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import promoter  # noqa: E402

_META = {"XAUUSD": {"median_spread_pts": 16.0, "tick_size": 0.01, "tick_value": 0.86,
                    "contract_size": 100.0, "swap_long": -40.0, "swap_short": 10.0}}


@pytest.fixture
def roster(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    reg = tmp_path / "sleeve_registry.json"
    reg.write_text(json.dumps({"sleeves": {"XAUUSD.clocked.asia": {
        "identity": {"cost_hash": "abc123", "symbol": "XAUUSD"}}}}), encoding="utf-8")
    uni = tmp_path / "universe.json"
    uni.write_text(json.dumps(_META), encoding="utf-8")
    monkeypatch.setattr(promoter, "SLEEVE_REGISTRY", reg)
    monkeypatch.setattr(promoter, "UNIVERSE_FILE", uni)
    monkeypatch.setattr(promoter, "SLEEVES_FILE", tmp_path / "sleeves.json")
    monkeypatch.setattr(promoter, "_apply_live_policy", lambda rows: 0)
    return tmp_path / "sleeves.json"


def test_the_clock_identity_supplies_the_basis(roster: Path) -> None:
    assert promoter.cost_basis_of({"name": "XAUUSD.clocked.asia", "symbol": "XAUUSD"}) == (
        "abc123", "clock identity XAUUSD.clocked.asia")


def test_the_registry_supplies_the_basis_when_there_is_no_clock(roster: Path) -> None:
    h, src = promoter.cost_basis_of({"name": "x", "symbol": "XAUUSD"})
    assert h and src == "universe registry XAUUSD"


def test_no_basis_is_unmeasured(roster: Path) -> None:
    h, why = promoter.cost_basis_of({"name": "x", "symbol": "EURNOK"})
    assert h is None and "EURNOK" in why


def test_a_live_row_without_a_basis_is_standby_and_one_with_it_stays_live(roster: Path) -> None:
    rows = [{"name": "XAUUSD.clocked.asia", "symbol": "XAUUSD", "family": "f",
             "status": "LIVE", "risk_frac": 0.01, "certificate": "XAUUSD.clocked.asia"},
            {"name": "nobasis", "symbol": "EURNOK", "family": "f", "status": "LIVE",
             "risk_frac": 0.01, "certificate": "nobasis"}]
    promoter.save_sleeves(rows)
    out = {r["name"]: r for r in json.loads(roster.read_text(encoding="utf-8"))["sleeves"]}
    assert out["XAUUSD.clocked.asia"]["status"] == "LIVE"
    assert out["XAUUSD.clocked.asia"]["artifact"]["ok"] is True
    assert "no cost basis" not in out["XAUUSD.clocked.asia"]["artifact"]["problems"]
    assert out["nobasis"]["status"] == "STANDBY"
    assert out["nobasis"]["risk_frac"] == 0.0
    assert "UNMEASURED cost basis" in out["nobasis"]["demote_reason"]
