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
