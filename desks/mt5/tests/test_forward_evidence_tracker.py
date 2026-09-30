"""Tier-1 audit #20: forward evidence as an append-only hourly series with trends."""
from __future__ import annotations

import json
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path

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
