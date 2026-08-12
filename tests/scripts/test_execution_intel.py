"""Execution intelligence layer (triage #102) -- consolidation must fail LOUD on missing feeds,
detect cross-feed drift no single organ sees, and never carry an auto-apply recommendation."""
from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path
from types import ModuleType

_SPEC = importlib.util.spec_from_file_location(
    "run_execution_intel", Path(__file__).resolve().parents[2] / "scripts/run_execution_intel.py")
assert _SPEC is not None and _SPEC.loader is not None
_MOD: ModuleType = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(_MOD)


def _run_in(tmp_path: Path, monkeypatch: object) -> dict:
    monkeypatch.chdir(tmp_path)  # type: ignore[attr-defined]
    monkeypatch.setattr(sys, "argv", ["run_execution_intel.py"])  # type: ignore[attr-defined]
    _MOD._OUT = tmp_path / "web/execution_intel.json"
    _MOD.main()
    return json.loads((tmp_path / "web/execution_intel.json").read_text("utf-8"))


def test_all_feeds_absent_is_no_data_not_ok(tmp_path: Path, monkeypatch: object) -> None:
    rep = _run_in(tmp_path, monkeypatch)
    assert rep["overall"] == "NO-DATA"          # fail-loud: absent feeds never read as healthy
    assert rep["hedge_integrity"]["verdict"] == "NO-DATA"


def test_hedge_violation_is_critical_and_pages(tmp_path: Path, monkeypatch: object) -> None:
    (tmp_path / "data").mkdir()
    (tmp_path / "data/hedge_integrity.json").write_text(json.dumps(
        {"updated": "2026-07-29T00:00:00+00:00",
         "legs": {"COOKIEUSDT": {"state": "INVERTED"}, "EDUUSDT": {"state": "OK"}}}), "utf-8")
    rep = _run_in(tmp_path, monkeypatch)
    assert rep["hedge_integrity"]["verdict"] == "CRITICAL"
    assert rep["hedge_integrity"]["bad_legs"] == ["COOKIEUSDT"]
    assert rep["overall"] == "CRITICAL"
    assert any(r["action"] == "PAGE+PAUSE-OPENS" for r in rep["recommendations"])


def test_cost_drift_detected_across_feeds(tmp_path: Path, monkeypatch: object) -> None:
    (tmp_path / "data").mkdir()
    trades = [{"rt_bps": 40.0} for _ in range(30)]        # realized ~40 bps
    (tmp_path / "data/cashcarry_trades.json").write_text(json.dumps(trades), "utf-8")
    (tmp_path / "data/cost_model.json").write_text(json.dumps(
        {"symbols": {"AAAUSDT": {"fut_sell": {"500": {"median_bps": 5.0}}},
                     "BBBUSDT": {"fut_sell": {"500": {"median_bps": 6.0}}}}}), "utf-8")
    rep = _run_in(tmp_path, monkeypatch)
    cd = rep["cost_drift"]
    assert cd["verdict"] == "CRITICAL"                    # 40/5.5 ~ 7.3x > 4x
    assert cd["realized_over_modeled"] > 4
    # And the recommendation respects the approved bound, never auto-applies.
    rec = next(r for r in rep["recommendations"] if r.get("knob") == "_DEFAULT_RT_BPS")
    lo, hi = rec["bound"]
    assert lo <= rec["target_bps"] <= hi
    assert rec["auto_apply"] is False


def _fee_artifact(**over: object) -> str:
    att = {"measured": True, "venue_commission_usd": 1750.878, "top4_share": 0.8589,
           "by_symbol": {"COOKIEUSDT": 623.3, "1000CATUSDT": 413.03},
           "tape_coverage": 0.0709, "spot_leg": "UNMEASURED", "row_level": "REFUSED",
           "residual_note": "the tape accounts for 7.1% ..."}
    att.update(over)
    return json.dumps({"ran": "2026-08-12T00:00:00+00:00", "measured": att["measured"],
                       "verdict": "CONCENTRATED", "attribution": att})


def test_fee_attribution_absent_is_no_data_not_ok(tmp_path: Path, monkeypatch: object) -> None:
    """R0371: the fee bill is 88.7% of the sleeve's non-funding loss. Its absence is never OK."""
    rep = _run_in(tmp_path, monkeypatch)
    assert rep["fee_attribution"]["verdict"] == "NO-DATA"
    assert "run_fee_attribution" in rep["fee_attribution"]["detail"]


def test_fee_attribution_surfaces_the_paying_symbols(tmp_path: Path, monkeypatch: object) -> None:
    (tmp_path / "data").mkdir()
    (tmp_path / "data/fee_attribution.json").write_text(_fee_artifact(), "utf-8")
    rep = _run_in(tmp_path, monkeypatch)
    fa = rep["fee_attribution"]
    # Low tape coverage is a DEGRADED verdict on its own: the sleeve cannot audit its own
    # dominant loss from its own record, however the fees are distributed.
    assert fa["verdict"] == "DEGRADED"
    assert fa["top_symbols"][0]["symbol"] == "COOKIEUSDT"
    assert fa["commission_usd"] == 1750.878
    assert rep["overall"] == "DEGRADED"


def test_fee_attribution_keeps_both_refusals_beside_the_number(
        tmp_path: Path, monkeypatch: object) -> None:
    """A reader must never mistake the unmeasured spot leg for a spot leg that paid nothing."""
    (tmp_path / "data").mkdir()
    (tmp_path / "data/fee_attribution.json").write_text(_fee_artifact(), "utf-8")
    fa = _run_in(tmp_path, monkeypatch)["fee_attribution"]
    assert fa["spot_leg"] == "UNMEASURED"
    assert fa["per_round_trip"] == "REFUSED"


def test_fee_attribution_unmeasured_venue_read_is_not_zero_fees(
        tmp_path: Path, monkeypatch: object) -> None:
    (tmp_path / "data").mkdir()
    (tmp_path / "data/fee_attribution.json").write_text(
        json.dumps({"ran": "2026-08-12T00:00:00+00:00", "measured": False,
                    "provenance_why": "UNMEASURED: venue read failed",
                    "attribution": {"measured": False, "note": "no usable commission events"}}),
        "utf-8")
    fa = _run_in(tmp_path, monkeypatch)["fee_attribution"]
    assert fa["verdict"] == "NO-DATA"
    assert "commission_usd" not in fa            # no number at all, not 0.0
    assert "venue read failed" in fa["detail"]


def test_fee_attribution_full_coverage_is_ok(tmp_path: Path, monkeypatch: object) -> None:
    (tmp_path / "data").mkdir()
    (tmp_path / "data/fee_attribution.json").write_text(_fee_artifact(tape_coverage=0.95), "utf-8")
    assert _run_in(tmp_path, monkeypatch)["fee_attribution"]["verdict"] == "OK"


def test_no_recommendation_ever_auto_applies(tmp_path: Path, monkeypatch: object) -> None:
    (tmp_path / "data").mkdir()
    (tmp_path / "data/hedge_integrity.json").write_text(json.dumps(
        {"legs": {"X": {"state": "MISSING"}}}), "utf-8")
    trades = [{"rt_bps": 90.0} for _ in range(20)]
    (tmp_path / "data/cashcarry_trades.json").write_text(json.dumps(trades), "utf-8")
    (tmp_path / "data/cost_model.json").write_text(json.dumps(
        {"symbols": {"A": {"fut_sell": {"500": {"median_bps": 4.0}}}}}), "utf-8")
    rep = _run_in(tmp_path, monkeypatch)
    assert rep["recommendations"], "expected recommendations under degradation"
    assert all(r.get("auto_apply") is False for r in rep["recommendations"] if "knob" in r)
