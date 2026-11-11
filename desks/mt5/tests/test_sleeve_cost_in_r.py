"""Sleeve cost in R (idea 656): measured entry-hour cost vs the certificate's charge, in R.
Missing inputs are UNMEASURED, never 0; the report is report-only with no consumer."""
from __future__ import annotations

import json
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pytest

_DESK = Path(__file__).resolve().parents[1]
_ROOT = _DESK.parent.parent
for p in (str(_DESK), str(_ROOT)):
    if p not in sys.path:
        sys.path.insert(0, p)

from research import sleeve_cost_in_r as sc  # noqa: E402

NOW = datetime(2026, 11, 11, 18, 0, tzinfo=UTC)


def _hours(p50: float, zero_frac: float = 0.0) -> dict[str, dict[str, object]]:
    out = {str(h): {"status": "MEASURED", "p50": 10.0, "zero_frac": 0.0} for h in range(24)}
    out["7"] = {"status": "MEASURED", "p50": p50, "zero_frac": zero_frac}
    return out


def _setup(monkeypatch: pytest.MonkeyPatch, tmp: Path, *, p50: float = 10.0,
           ev: float = 0.2, x3: float = 0.1, cert: bool = True, zero_frac: float = 0.0,
           tpd: float | None = 1.0) -> None:
    sleeves = {"sleeves": [
        {"name": "eurusd_srb", "status": "STANDBY", "symbol": "EURUSD", "selector": "asia",
         "certificate": {"cell": "external.EURUSD.srb" if cert else None}},
        {"name": "dead", "status": "RETIRED", "symbol": "EURUSD"},
    ]}
    surv = {"survivors": {"external.EURUSD.srb": {
        "sym": "EURUSD", "gates": {"expected_value": {"ev": ev}, "stress_costs": {"exp_x3": x3}},
        "shadow_spec": {"symbol": "EURUSD", "selector": "asia"}}}}
    if tpd is not None:
        surv["survivors"]["external.EURUSD.srb"]["trades_per_active_day"] = tpd
    uni = {"EURUSD": {"contract_size": 100000.0, "tick_size": 0.00001, "tick_value": 1.0,
                      "median_spread_pts": 10.0}}
    surface = {"symbols": {"EURUSD": {"tick_size": 0.00001, "atr20_h1_pts": 100.0,
                                      "hours": _hours(p50, zero_frac)}}}
    files = {"SLEEVES": sleeves, "SURVIVORS": surv, "UNIVERSE": uni, "SURFACE": surface}
    for attr, doc in files.items():
        path = tmp / f"{attr}.json"
        path.write_text(json.dumps(doc), encoding="utf-8")
        monkeypatch.setattr(sc, attr, path)
    monkeypatch.setattr(sc, "LEDGER", tmp / "none.jsonl")
    monkeypatch.setattr(sc, "CORPUS", tmp / "none2.jsonl")
    monkeypatch.setattr(sc, "DATA", tmp)
    monkeypatch.setattr(sc, "OUT", tmp / "SLEEVE_COST_IN_R.json")
    monkeypatch.setattr(sc, "SM1", tmp / "no_sm1.json")
    monkeypatch.setattr(sc, "SM1_LOCAL", tmp / "no_sm1_local.json")


def _row(doc: dict[str, Any], name: str = "eurusd_srb") -> dict[str, Any]:
    return next(r for r in doc["sleeves"] if r["sleeve"] == name)


def test_contract_fields_and_population(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    _setup(monkeypatch, tmp_path)
    doc = sc.build(NOW)
    assert doc["report_only"] is True and doc["consumer"] is None
    assert doc["intended_consumer"] == "allocator / vol-target arm (idea 531/415)"
    assert [r["sleeve"] for r in doc["sleeves"]] == ["eurusd_srb"]  # retired excluded, cert deduped


def test_cost_arithmetic_matches_certificate_charge(monkeypatch: pytest.MonkeyPatch,
                                                     tmp_path: Path) -> None:
    # Entry spread equals the registry median: the measured spread is ONE crossing and the
    # cert charged TWO, so measured < charged and nothing is flagged.
    _setup(monkeypatch, tmp_path)
    f = _row(sc.build(NOW))["venues"]["fusion"]
    assert f["cost_R_measured"]["spread_R"] == pytest.approx(0.1)  # one crossing = ev - x3
    assert f["cost_R_charged"] == pytest.approx(0.2 + f["cost_R_measured"]["commission_R"],
                                                abs=1e-4)
    assert f["gross_edge_R"] == pytest.approx(0.2 + f["cost_R_charged"], abs=1e-4)
    assert f["flags"] == []
    assert f["cost_R_measured"]["kind"].startswith("FLOOR")


def test_expensive_entry_hour_flags_both(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    _setup(monkeypatch, tmp_path, p50=100.0)  # 10x the median at the entry hour
    r = _row(sc.build(NOW))
    f = r["venues"]["fusion"]
    assert f["net_edge_R"] <= 0
    assert set(r["flags"]) >= {"COST_EATS_EDGE", "UNDERCHARGED"}
    assert f["spread_atr"]["entry_over_median"] == pytest.approx(10.0)


def test_missing_inputs_are_unmeasured_never_zero(monkeypatch: pytest.MonkeyPatch,
                                                  tmp_path: Path) -> None:
    _setup(monkeypatch, tmp_path, cert=False)
    r = _row(sc.build(NOW))
    assert r["certificate"]["status"] == sc.UNMEASURED
    assert r["venues"]["fusion"]["status"] == sc.UNMEASURED  # no stop recoverable
    assert r["venues"]["e8"]["status"] == sc.UNMEASURED
    assert r["venues"]["ftmo"]["status"] == sc.UNMEASURED
    assert r["slippage"]["status"] == sc.UNMEASURED


def test_degenerate_surface_is_named(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    _setup(monkeypatch, tmp_path, zero_frac=0.9)
    assert "SURFACE_SUSPECT" in _row(sc.build(NOW))["flags"]


def test_broker_clock_follows_eu_dst() -> None:
    assert sc.broker_hour(datetime(2026, 7, 1, 4, tzinfo=UTC)) == 7
    assert sc.broker_hour(datetime(2026, 11, 11, 4, tzinfo=UTC)) == 6
    # US DST has begun (2nd Sunday of March), EU has not: the NY+7 broker is already UTC+3.
    assert sc.broker_hour(datetime(2026, 3, 20, 4, tzinfo=UTC)) == 7
    # EU DST over, US not yet (1st Sunday of November): still UTC+3.
    assert sc.broker_hour(datetime(2026, 10, 28, 4, tzinfo=UTC)) == 7


def test_per_day_basis_withholds_the_ratio(monkeypatch: pytest.MonkeyPatch,
                                           tmp_path: Path) -> None:
    _setup(monkeypatch, tmp_path, p50=100.0, tpd=None)
    r = _row(sc.build(NOW))
    f = r["venues"]["fusion"]
    assert r["certificate"]["ev_basis"] == "per_day"
    assert f["gap"]["measured_over_charged"] == sc.UNMEASURED_BASIS
    assert "UNDERCHARGED" not in r["flags"]
    assert "COST_EATS_EDGE" in r["flags"]


def test_trades_per_day_normalises_ev(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    _setup(monkeypatch, tmp_path, tpd=2.0)
    c = _row(sc.build(NOW))["certificate"]
    assert c["ev_basis"] == "per_trade"
    assert c["ev_R"] == pytest.approx(0.1) and c["one_crossing_R"] == pytest.approx(0.05)


def test_write_is_atomic(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    _setup(monkeypatch, tmp_path)
    sc.write(sc.build(NOW), sc.OUT)
    assert json.loads(sc.OUT.read_text(encoding="utf-8"))["schema"] == sc.SCHEMA
    assert not list(tmp_path.glob("*.tmp"))


def _spike_surface(tmp: Path, spikes: dict[str, object] | None) -> None:
    doc = json.loads(sc.SURFACE.read_text(encoding="utf-8"))
    sym = doc["symbols"]["EURUSD"]
    sym["hours"]["1"] = {"status": "MEASURED", "p50": 2.0, "zero_frac": 0.0}
    if spikes is not None:
        sym["tick_hours"] = {"spike_minutes": spikes}
    sc.SURFACE.write_text(json.dumps(doc), encoding="utf-8")


def _gap_sleeve(monkeypatch: pytest.MonkeyPatch, tmp: Path, status: str = "LIVE") -> None:
    sleeves = {"sleeves": [{"name": "eurusd_gap", "status": status, "symbol": "EURUSD",
                            "family": "overnight_gap_decay",
                            "certificate": {"cell": "external.EURUSD.srb"}}]}
    sc.SLEEVES.write_text(json.dumps(sleeves), encoding="utf-8")


def test_rollover_minute_30x_flips_a_live_sleeve(monkeypatch: pytest.MonkeyPatch,
                                                  tmp_path: Path) -> None:
    # Hour 01 quotes 2 pts; the 01:00 minute quotes 60 (30x). Edge positive at the hour,
    # gone at the minute: FLIPS_AT_MINUTE, and the LIVE sleeve reaches the CRO's list.
    _setup(monkeypatch, tmp_path)
    _gap_sleeve(monkeypatch, tmp_path)
    _spike_surface(tmp_path, {"01:00": {"p50": 60.0, "n_ticks": 40, "n_days": 5}})
    doc = sc.build(NOW)
    f = _row(doc, "eurusd_gap")["venues"]["fusion"]
    assert f["net_edge_R"] > 0 >= f["net_R_minute"]
    assert f["minute"]["spike_share"] == 1.0
    assert "FLIPS_AT_MINUTE" in f["flags"]
    assert doc["live_flips"] == ["eurusd_gap"]


def test_minute_only_raises_and_absent_spikes_are_unmeasured(monkeypatch: pytest.MonkeyPatch,
                                                             tmp_path: Path) -> None:
    _setup(monkeypatch, tmp_path)
    _gap_sleeve(monkeypatch, tmp_path, status="STANDBY")
    _spike_surface(tmp_path, {"01:00": {"p50": 1.0}})  # cheaper than its hour: ignored
    f = _row(sc.build(NOW), "eurusd_gap")["venues"]["fusion"]
    assert f["cost_R_minute"] == pytest.approx(f["cost_R_measured"]["total_R"], abs=1e-5)
    _setup(monkeypatch, tmp_path)
    _gap_sleeve(monkeypatch, tmp_path)
    _spike_surface(tmp_path, None)
    doc = sc.build(NOW)
    f = _row(doc, "eurusd_gap")["venues"]["fusion"]
    assert f["cost_R_minute"] == sc.UNMEASURED_MINUTE
    assert f["net_R_minute"] == sc.UNMEASURED_MINUTE
    assert doc["live_flips"] == []


def test_spec_fill_minute_is_next_bar_open() -> None:
    item = {"session": "asia", "spec": {"timeframe": "M15"}}
    assert sc.entry_minutes(item, [])["fills"] == [(7, 15)]


def test_sm1_is_the_authority_for_covered_keys(monkeypatch: pytest.MonkeyPatch,
                                               tmp_path: Path) -> None:
    _setup(monkeypatch, tmp_path)
    _spike_surface(tmp_path, {})  # key present, minute not listed: MEASURED, no spike
    sm1 = {"top10_gt0": [{"cell": "external.EURUSD.srb", "exp_registry": 0.3,
                          "exp_fill_minute": -0.1, "spike_share": 0.8,
                          "spike_minutes": {"01:00": 8}, "spread_fill_weighted": 60.0}]}
    sc.SM1.write_text(json.dumps(sm1), encoding="utf-8")
    r = _row(sc.build(NOW))
    assert r["minute_source"] == "sm1" and "not_in_sm1" not in r
    assert r["venues"]["fusion"]["net_R_minute"] == -0.1
    assert "FLIPS_AT_MINUTE" in r["flags"]


def test_unlisted_minute_is_measured_not_a_spike(monkeypatch: pytest.MonkeyPatch,
                                                 tmp_path: Path) -> None:
    _setup(monkeypatch, tmp_path)
    _gap_sleeve(monkeypatch, tmp_path)
    _spike_surface(tmp_path, {"05:00": {"p50": 99.0}})
    r = _row(sc.build(NOW), "eurusd_gap")
    f = r["venues"]["fusion"]
    assert r["not_in_sm1"] is True
    assert f["minute"]["spike_share"] == 0.0
    assert f["cost_R_minute"] == pytest.approx(f["cost_R_measured"]["total_R"], abs=1e-5)
