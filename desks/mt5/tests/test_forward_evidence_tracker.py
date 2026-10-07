"""Tier-1 audit #20: forward evidence as an append-only hourly series with trends."""
from __future__ import annotations

import json
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

DESK = Path(__file__).resolve().parents[1]
ROOT = DESK.parents[1]
for p in (str(DESK / "research"), str(DESK), str(ROOT)):
    if p not in sys.path:
        sys.path.insert(0, p)

import forward_evidence_tracker as fet  # noqa: E402

NOW = datetime(2026, 9, 29, 12, tzinfo=UTC)


def _point(monkeypatch, tmp_path):
    for name in ("CALIBRATION", "RELIABILITY", "BREADTH", "MARKOUT", "CAPACITY", "EXPERIMENTS",
                 "SURVIVORS", "HISTORY"):
        monkeypatch.setattr(fet, name, tmp_path / f"{name}.json")
    monkeypatch.setattr(fet, "SHADOW", (tmp_path / "shadow.json",))
    monkeypatch.setattr(fet, "ROOT", tmp_path)


def test_absence_is_unmeasured_never_zero(monkeypatch, tmp_path):
    _point(monkeypatch, tmp_path)
    doc, row = fet.build(NOW)
    assert doc["status"] == "UNMEASURED" and doc["n_measured"] == 0
    assert all(v["value"] is None for v in doc["dimensions"].values())
    assert row is not None and all(v is None for v in row["values"].values())


def test_dimensions_read_from_their_owning_artifacts(monkeypatch, tmp_path):
    _point(monkeypatch, tmp_path)
    old = (NOW - timedelta(days=20)).isoformat()
    (tmp_path / "shadow.json").write_text(json.dumps({
        "a": {"status": "ACTIVE", "forward_start": old},
        "b": {"status": "RETIRED_ORPHAN", "forward_start": old},
        "c": {"status": "ACTIVE", "forward_start": NOW.isoformat()}}), "utf-8")
    (tmp_path / "CALIBRATION.json").write_text(json.dumps({
        "pooled": {"kappa_mean": 0.8, "kappa_sd": 0.1, "n_rows": 5, "verdict": "OVERSTATES"},
        "sleeves": [{"ratio": 0.5}, {"ratio": 1.0}, {"ratio": 1.5}]}), "utf-8")
    (tmp_path / "BREADTH.json").write_text(json.dumps({"effective": {"n_eff": 3.5}}), "utf-8")
    (tmp_path / "MARKOUT.json").write_text(json.dumps({"usable": False, "n_matched": 0,
                                                       "mean_slip_r": 0.0}), "utf-8")
    (tmp_path / "CAPACITY.json").write_text(json.dumps({"sleeves": 4, "binding_now": 1,
                                                        "rows": [{}] * 4}), "utf-8")
    (tmp_path / "EXPERIMENTS.json").write_text(json.dumps({"lifetime_trials": 1000}), "utf-8")
    (tmp_path / "SURVIVORS.json").write_text(json.dumps({"n": 5}), "utf-8")
    doc, _ = fet.build(NOW)
    d = doc["dimensions"]
    assert d["survival"]["value"] == 0.5 and d["survival"]["n_aged"] == 2
    assert d["live_backtest_calibration"]["value"] == 0.8
    assert d["degradation"]["value"] == 1.0
    assert d["breadth"]["value"] == 3.5
    assert d["realised_cost"]["status"] == "UNMEASURED"       # no matched fill is no cost
    assert d["capacity"]["value"] == 0.25
    assert d["research_hit_rate"]["value"] == 0.005


def test_one_history_row_per_hour_and_trends_against_the_past(monkeypatch, tmp_path):
    _point(monkeypatch, tmp_path)
    (tmp_path / "BREADTH.json").write_text(json.dumps({"effective": {"n_eff": 4.0}}), "utf-8")
    past = {"at": (NOW - timedelta(days=1, minutes=5)).isoformat(), "values": {"breadth": 3.0}}
    (tmp_path / "HISTORY.json").write_text(json.dumps(past) + "\n", "utf-8")
    doc, row = fet.build(NOW)
    assert row is not None and doc["trend"]["breadth"]["24h"] == 1.0
    assert doc["trend"]["breadth"]["7d"] is None
    with (tmp_path / "HISTORY.json").open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(row) + "\n")
    _, again = fet.build(NOW + timedelta(minutes=20))
    assert again is None                                      # same UTC hour: not appended


# ---------------------------------------------------------- the Asian-derived signal record (XXIV)
def _asia(monkeypatch, tmp_path):
    _point(monkeypatch, tmp_path)
    for name in ("RESEARCH_ROI", "PF_ALLOCATION", "DECAY_LIVE", "SLEEVE_REGISTRY"):
        monkeypatch.setattr(fet, name, tmp_path / f"{name}.json")
    monkeypatch.setattr(fet, "FILL_CORPUS", tmp_path / "fill_corpus.jsonl")
    monkeypatch.setattr(fet, "SHADOW_DIR", tmp_path / "shadow")
    (tmp_path / "shadow").mkdir()


KEY = "AUDUSD.exogenous_conditioner.asia"


def _plant_asia(tmp_path, n=24):
    (tmp_path / "RESEARCH_ROI.json").write_text(json.dumps({
        "source_roi": {"alt_proxies:cn_nbs_retail": {"region": "china"},
                       "fred": {"region": "north_america"}},
        "delayed_credit": {"by_source": {
            "alt_proxies:cn_nbs_retail": {"cells": [KEY, "NOT.A.CLOCK"]},
            "fred": {"cells": ["EURUSD.asia"]}}}}), "utf-8")
    rs = [0.6 if i % 3 else -0.4 for i in range(n)]
    (tmp_path / "shadow" / "ledger_AUDUSD_exogenous_conditioner_asia.json").write_text(
        json.dumps([{"entry_time": f"2026-09-{1 + i % 28:02d} 03:00", "r_multiple": r,
                     "phase": "forward"} for i, r in enumerate(rs)]
                   + [{"entry_time": "2026-08-01 03:00", "r_multiple": 9.0,
                       "phase": "historical"}]), "utf-8")
    (tmp_path / "shadow.json").write_text(json.dumps({
        KEY: {"status": "ACTIVE", "n": n, "days_active": 21, "exp_r": sum(rs) / n,
              "max_dd_r": -1.2, "forward_start": "2026-09-01T00:00:00+00:00"},
        "EURUSD.asia": {"status": "ACTIVE", "n": 3}}), "utf-8")
    (tmp_path / "PF_ALLOCATION.json").write_text(json.dumps({
        "marginal_delta_elog": {KEY: 0.0004},
        "admission": {"candidates": {KEY: {"corr_to_book": 0.12}}}}), "utf-8")
    (tmp_path / "DECAY_LIVE.json").write_text(json.dumps({
        "verdicts": {KEY: {"verdict": "HEALTHY"}},
        "decay_model": {KEY: {"half_life_days": 80.0}}}), "utf-8")
    (tmp_path / "SLEEVE_REGISTRY.json").write_text(json.dumps({
        "sleeves": {KEY: {"cost_fields": {"spread": 0.0001}}}}), "utf-8")
    (tmp_path / "fill_corpus.jsonl").write_text("\n".join(json.dumps(r) for r in (
        {"sleeve": KEY, "slip_r": 0.02, "commission_r": 0.01, "status": "FILLED",
         "latency_decision_to_send_ms": 40.0, "spread_frac_at_decision": 0.0001},
        {"sleeve": KEY, "slip_r": 0.04, "commission_r": 0.01, "status": "UNRESOLVED"},
        {"sleeve": "OTHER", "slip_r": 9.0})) + "\n", "utf-8")
    return rs


def test_every_asian_signal_carries_the_thirteen_fields_from_their_owners(monkeypatch,
                                                                           tmp_path):
    import forward_verdict as fv
    _asia(monkeypatch, tmp_path)
    rs = _plant_asia(tmp_path)
    doc, _ = fet.build(NOW)
    blk = doc["asian_signals"]
    assert blk["status"] == "MEASURED" and blk["n_signals"] == 1      # fred's clock is not Asian
    rec = blk["signals"][KEY]
    assert rec["asian_sources"] == ["alt_proxies:cn_nbs_retail"]
    assert set(fet.ASIAN_FIELDS) <= set(rec) and rec["n_measured"] == 13
    n_eff, _ = fv.effective_n(rs, [f"2026-09-{1 + i % 28:02d}" for i in range(len(rs))])
    assert rec["forward_trades"]["value"] == 24 and rec["days"]["value"] == 21
    assert rec["effective_sample_size"]["value"] == pytest.approx(round(n_eff, 3))
    assert rec["autocorrelation_adjustment"]["value"] == pytest.approx(round(24 / n_eff, 4))
    assert rec["sequential_lower_bound"]["value"] == pytest.approx(
        round(fv.sequential_lower_bound(rs), 6))                       # historical 9R excluded
    assert rec["slippage"]["value"] == pytest.approx(0.03)
    assert rec["costs"]["value"] == pytest.approx(0.01)
    assert rec["costs"]["frozen_cost_basis"] == {"spread": 0.0001}
    assert rec["execution_quality"]["value"] == 0.5
    assert rec["drawdown"]["value"] == -1.2
    assert rec["decay"]["value"] == "HEALTHY" and rec["decay"]["half_life_days"] == 80.0
    assert rec["correlation_to_book"]["value"] == 0.12
    assert rec["marginal_elogw"]["value"] == 0.0004


def test_a_shared_ledger_or_missing_owner_is_unmeasured_never_zero(monkeypatch, tmp_path):
    _asia(monkeypatch, tmp_path)
    _plant_asia(tmp_path)
    for name in ("PF_ALLOCATION.json", "DECAY_LIVE.json", "fill_corpus.jsonl",
                 "SLEEVE_REGISTRY.json"):
        (tmp_path / name).unlink()
    st = json.loads((tmp_path / "shadow.json").read_text("utf-8"))
    st[KEY]["n"] = 30                                  # the ledger holds 24: another clock's too
    (tmp_path / "shadow.json").write_text(json.dumps(st), "utf-8")
    rec = fet.build(NOW)[0]["asian_signals"]["signals"][KEY]
    for f in ("effective_sample_size", "autocorrelation_adjustment", "sequential_lower_bound",
              "costs", "slippage", "execution_quality", "decay", "correlation_to_book",
              "marginal_elogw"):
        assert rec[f]["status"] == "UNMEASURED" and rec[f]["value"] is None, f
        assert rec[f]["why"], f
    assert "shared ledger" in rec["sequential_lower_bound"]["why"]


def test_no_lineage_is_unmeasured_and_no_asian_clock_is_a_measured_empty(monkeypatch, tmp_path):
    _asia(monkeypatch, tmp_path)
    blk = fet.build(NOW)[0]["asian_signals"]
    assert blk["status"] == "UNMEASURED" and blk["n_signals"] is None
    (tmp_path / "RESEARCH_ROI.json").write_text(json.dumps({"source_roi": {},
                                                            "delayed_credit": {}}), "utf-8")
    blk = fet.build(NOW)[0]["asian_signals"]
    assert blk["status"] == "MEASURED" and blk["n_signals"] == 0 and blk["why"]


def test_ledger_names_follow_shadow_forward(tmp_path):
    d = tmp_path
    assert fet.ledger_paths("XAUUSD.asia", d) == [d / "ledger_XAUUSD_asia.json"]
    assert fet.ledger_paths("AUDUSD.carry.london#rr=2@M5.SHORT", d) == [
        d / "ledger_AUDUSD_carry.london.json", d / "ledger_AUDUSD_carry_london.json"]


def test_research_roi_reads_the_record_into_each_asian_region(monkeypatch, tmp_path):
    """THE CONSUMER: research_roi publishes each Asian region's forward record beside its ROI,
    and the ROI arithmetic itself is untouched."""
    import research_roi as rr
    assert tuple(rr.ASIAN_REGIONS) == tuple(fet.ASIAN_REGIONS)
    _asia(monkeypatch, tmp_path)
    _plant_asia(tmp_path)
    doc, _ = fet.build(NOW)
    out = tmp_path / "FORWARD_EVIDENCE.json"
    out.write_text(json.dumps(doc), "utf-8")
    src = {"alt_proxies:cn_nbs_retail": {"region": "china"}}
    regions = {"by_region": {r: {"roi": 1.0} for r in ("china", "korea", "europe")}}
    got = rr.attach_forward_record(regions, src, out)["by_region"]
    assert got["china"]["forward_record"]["n_signals"] == 1
    assert got["china"]["forward_record"]["forward_trades"] == 24
    assert got["china"]["forward_record"]["marginal_elogw_sum"] == 0.0004
    assert got["korea"]["forward_record"]["n_signals"] == 0
    assert "forward_record" not in got["europe"]                    # not an Asian region
    assert got["china"]["roi"] == 1.0
    missing = rr.attach_forward_record({"by_region": {"china": {}}}, src,
                                       tmp_path / "absent.json")
    assert missing["by_region"]["china"]["forward_record"]["status"] == "UNMEASURED"
