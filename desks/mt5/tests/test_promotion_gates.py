"""The promotion gate packet (Audit 2026-11-26, gates (a)-(c) + Brain Q42), one test per gate.

    python -m pytest desks/mt5/tests/test_promotion_gates.py -q

(a) exotic or unclassified symbols hold no live capital: promoter.save_sleeves, the gateway's
    roster and the allocator's columns; (b) the E8 evidence-rule fallback admits only
    fill-proven or principal-funded rows (rollover hours stay gated by rollover_block); (c) a
    revived clock with no certificate at revival, and a forward row not priced at the fill-hour
    spread, are held UNMEASURED -- never KILL.
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
from prop import e8_book  # noqa: E402

from research import pf_allocator as pa  # noqa: E402
from research import universe_policy as up  # noqa: E402

REG = {"EURUSD": {"asset_class": "forex_major"}, "XAUUSD": {"asset_class": "metal"},
       "USDZAR": {"asset_class": "forex_exotic"}, "EURNOK": {"asset_class": "forex_cross"}}


@pytest.fixture
def registry(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    p = tmp_path / "universe.json"
    p.write_text(json.dumps(REG), "utf-8")
    monkeypatch.setattr(up, "UNIVERSE", p)
    return p


# ------------------------------------------------------------------------- (a) the class door
def test_exotic_and_unclassified_are_refused_and_majors_metals_pass(registry) -> None:
    assert up.registry_readable() is True
    assert up.live_class_refusal("EURUSD") is None
    assert up.live_class_refusal("XAUUSD") is None
    assert "exotic" in str(up.live_class_refusal("USDZAR"))     # by registry class
    assert "exotic" in str(up.live_class_refusal("EURNOK"))     # by its legs
    assert "UNCLASSIFIED" in str(up.live_class_refusal("NOTREAL"))
    assert up.live_class_refusal("") is not None


def test_an_unreadable_registry_binds_only_the_leg_test(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(up, "UNIVERSE", tmp_path / "absent.json")
    assert up.registry_readable() is False
    assert up.live_class_refusal("XAUUSD") is None              # gold is never stopped by it
    assert "exotic" in str(up.live_class_refusal("EURNOK"))


def test_save_sleeves_demotes_an_exotic_live_row_with_its_missed_growth(
        registry, tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(promoter, "SLEEVES_FILE", tmp_path / "sleeves.json")
    monkeypatch.setattr(promoter, "_apply_live_policy", lambda rows: 0)
    promoter.save_sleeves([{"name": "x", "symbol": "USDZAR", "family": "f", "status": "LIVE",
                            "risk_frac": 0.004}])
    (row,) = json.loads((tmp_path / "sleeves.json").read_text("utf-8"))["sleeves"]
    assert row["status"] == "STANDBY" and row["risk_frac"] == 0.0
    assert row["missed_growth_risk_frac"] == 0.004 and "exotic" in row["demote_reason"]


def test_the_gateway_roster_drops_an_exotic_row(registry, monkeypatch) -> None:
    pytest.importorskip("MetaTrader5")        # the gateway imports it; runs on the box
    from mt5desk import decision_core as core
    from mt5desk import gateway
    rows = [{"name": "a", "symbol": "EURUSD"}, {"name": "b", "symbol": "USDZAR"}]
    monkeypatch.setattr(core, "load_sleeves_verbose", lambda _p: (list(rows), []))
    assert [s["name"] for s in gateway.load_sleeves()] == ["a"]


def test_the_allocator_records_an_exotic_column_as_zero(registry, tmp_path, monkeypatch) -> None:
    (tmp_path / "data").mkdir()
    (tmp_path / "reports").mkdir()
    rows = [{"name": "zar", "status": "STANDBY",
             "certificate": {"cell": "external.USDZAR@H1.carry.abc"}}]
    (tmp_path / "data" / "sleeves.json").write_text(json.dumps({"sleeves": rows}), "utf-8")
    (tmp_path / "reports" / "CLOCK.json").write_text("{}", "utf-8")
    monkeypatch.setattr(pa, "BASE", tmp_path)
    monkeypatch.setattr(pa, "CLOCK_LAW", tmp_path / "reports" / "CLOCK.json")
    specs, zero, _ = pa._rostered_certificates({})
    assert "zar" in zero and "exotic" in zero["zar"] and "zar" not in specs


# ------------------------------------------------------------------- (b) the E8 fallback
def _row(**kw):
    return {"symbol": "EURUSD", "family": "carry", "selector": "asia", "risk_frac": 0.004, **kw}


def test_the_fallback_admits_only_proven_or_principal_rows() -> None:
    kept, dropped = e8_book.fallback_filter([
        _row(), _row(symbol="GBPUSD", fill_proven={"n": 12}),
        _row(symbol="AUDUSD", principal_funded=True)])
    assert [r["symbol"] for r in kept] == ["GBPUSD", "AUDUSD"]
    (d,) = dropped
    assert d["column"] == "EURUSD_carry_asia" and d["missed_growth_risk_frac"] == 0.004


# ------------------------------------------------------- (c) revived clocks and Q42 spreads
SPEC = {"symbol": "EURUSD", "selector": "asia", "family": "carry"}


def test_a_revived_clock_without_a_current_certificate_is_held_never_killed(registry) -> None:
    row = {"status": "PROMOTION_CANDIDATE", "certificate_at_revival": None,
           "spread_basis": "fill_hour"}
    st, why = promoter.promotion_hold(row, spec=SPEC, drift=True, symbol="EURUSD")
    assert st == promoter.HELD_REVIVED and "KILL" in why
    # joined to a certificate that exists now, with no drift: admissible
    assert promoter.promotion_hold(row, spec=SPEC, drift=False, symbol="EURUSD") is None


def test_a_forward_row_not_priced_at_the_fill_hour_is_unmeasured(registry) -> None:
    row = {"status": "PROMOTION_CANDIDATE", "spread_basis": "pooled_median"}
    st, _ = promoter.promotion_hold(row, spec=SPEC, drift=False, symbol="EURUSD")
    assert st == promoter.HELD_SPREAD
    assert promoter.promotion_hold({**row, "spread_basis": "fill_hour"}, spec=SPEC,
                                   drift=False, symbol="EURUSD") is None


def test_gold_is_gated_like_every_symbol(registry) -> None:
    row = {"status": "PROMOTION CANDIDATE", "certificate_at_revival": None,
           "spread_basis": "fill_hour"}
    st, _ = promoter.promotion_hold(row, spec=None, drift=True, symbol="XAUUSD")
    assert st == promoter.HELD_REVIVED
    assert promoter.promotion_hold(row, spec={"gate_spec": 1}, drift=False,
                                   symbol="XAUUSD") is None


@pytest.mark.parametrize(("basis", "ok"), [
    ("fill_hour", True), ("fill_hour_02", True), ("fill_hour_23", True),
    ("pooled_median", False), (None, False), ("fill_hour_", False), ("fill_hour_xx", False)])
def test_both_lanes_fill_hour_bases_count_and_nothing_else(registry, basis, ok) -> None:
    row = {"status": "PROMOTION CANDIDATE", "spread_basis": basis}
    held = promoter.promotion_hold(row, spec=SPEC, drift=False, symbol="EURUSD")
    assert (held is None) is ok
