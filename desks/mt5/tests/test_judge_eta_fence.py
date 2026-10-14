"""An UNMEASURED drain ETA is a fence FAILURE after one reading, and it names the missing input.

Measured 2026-10-14: JUDGING_RATE read `eta_to_drain: UNMEASURED` every hour while the judge had
returned no verdict for two days, its reason blamed GAUNTLET_BACKPRESSURE.json (present, and never
the input that mattered), and no fence went red. L1.28a: absence never resolves to a clean verdict.
"""
from __future__ import annotations

import json
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

DESK = Path(__file__).resolve().parents[1]
ROOT = DESK.parent.parent
for _p in (str(DESK), str(DESK / "research"), str(ROOT), str(ROOT / "scripts")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import check_judge_coverage as fence  # noqa: E402

from research import judging_throughput as jt  # noqa: E402

NOW = datetime(2026, 10, 14, 1, 47, tzinfo=UTC)
UNMEASURED = jt.UNMEASURED


@pytest.fixture(autouse=True)
def _isolate(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(jt, "JUDGE_COVERAGE", tmp_path / "JUDGE_COVERAGE.json")


def _coverage(tmp_path: Path, age_h: float, unjudged: int = 1_506_089) -> None:
    (tmp_path / "JUDGE_COVERAGE.json").write_text(json.dumps(
        {"at": (NOW - timedelta(hours=age_h)).isoformat(),
         "totals": {"unjudged_total": unjudged}}), "utf-8")


def _rate(tmp_path: Path, previous: dict | None = None, *, now: datetime = NOW) -> dict:
    return jt.measure_rate({"depth": UNMEASURED, "why": "GAUNTLET_BACKPRESSURE.json stale"},
                           {}, now, ledger=tmp_path / "gate_verdict_ledger.jsonl",
                           registry=tmp_path / "alpha_registry.sqlite", previous=previous)


# ------------------------------------------------------------------------- the producer side
def test_a_stale_coverage_file_is_named_as_the_missing_input(tmp_path: Path) -> None:
    _coverage(tmp_path, age_h=9.35)
    eta = _rate(tmp_path)["eta_to_drain"]
    assert eta["status"] == UNMEASURED
    assert eta["missing_inputs"][0] == "JUDGE_COVERAGE.json"
    assert "9.3h old" in eta["why"] and "judge_coverage" in eta["why"]
    assert "GAUNTLET_BACKPRESSURE.json absent" not in eta["why"]


def test_a_sweep_remainder_is_named_as_refused_not_absent(tmp_path: Path) -> None:
    got = jt.measure_rate({"depth": 59_834, "depth_scope": "sweep"}, {}, NOW,
                          ledger=tmp_path / "x.jsonl", registry=tmp_path / "x.sqlite")
    why = got["eta_to_drain"]["why"]
    assert "GAUNTLET_BACKPRESSURE.json: one sweep's remainder" in why
    assert "JUDGE_COVERAGE.json: absent or unreadable" in why


def test_unmeasured_readings_accumulate_across_passes(tmp_path: Path) -> None:
    first = _rate(tmp_path)
    assert first["eta_to_drain"]["unmeasured_readings"] == 1
    assert first["eta_to_drain"]["unmeasured_since"] == NOW.isoformat(timespec="seconds")
    later = NOW + timedelta(hours=1)
    second = _rate(tmp_path, previous=first, now=later)
    assert second["eta_to_drain"]["unmeasured_readings"] == 2
    assert second["eta_to_drain"]["unmeasured_since"] == first["eta_to_drain"]["unmeasured_since"]


def test_a_legacy_unmeasured_reading_counts_as_one(tmp_path: Path) -> None:
    legacy = {"at": "2026-10-14T00:47:00+00:00",
              "eta_to_drain": {"status": UNMEASURED,
                               "why": "backlog UNMEASURED (GAUNTLET_BACKPRESSURE.json absent)"}}
    eta = _rate(tmp_path, previous=legacy)["eta_to_drain"]
    assert eta["unmeasured_readings"] == 2
    assert eta["unmeasured_since"] == legacy["at"]


def test_a_fresh_coverage_file_is_never_blamed(tmp_path: Path) -> None:
    _coverage(tmp_path, age_h=0.5, unjudged=0)
    eta = jt.measure_rate({}, {}, NOW, ledger=tmp_path / "x.jsonl",
                          registry=tmp_path / "x.sqlite",
                          previous={"eta_to_drain": {"status": UNMEASURED,
                                                     "unmeasured_readings": 9}})["eta_to_drain"]
    # Rates are absent here, so it stays UNMEASURED -- but the coverage file is NOT blamed.
    assert eta["status"] == UNMEASURED
    assert "JUDGE_COVERAGE.json" not in eta["missing_inputs"]
    assert eta["unmeasured_readings"] == 10


# ---------------------------------------------------------------------------- the fence side
def _families(tmp_path: Path) -> Path:
    p = tmp_path / "JUDGE_COVERAGE.json"
    p.write_text(json.dumps({"at": NOW.isoformat(),
                             "families": {"f": {"unjudged": 0, "queued": 0, "judged_window": 1}},
                             "totals": {}, "ranking": []}), "utf-8")
    return p


def _write_rate(tmp_path: Path, eta: dict, **extra: object) -> None:
    (tmp_path / "JUDGING_RATE.json").write_text(json.dumps(
        {"at": NOW.isoformat(), "eta_to_drain": eta, **extra}), "utf-8")


def _eta_row(doc: dict) -> dict:
    return {c["metric"]: c for c in doc["checks"]}["eta_to_drain"]


def test_second_unmeasured_reading_fails_and_names_the_input(tmp_path: Path) -> None:
    _write_rate(tmp_path, {"status": UNMEASURED, "unmeasured_readings": 2,
                           "unmeasured_since": "2026-10-13T23:47:00+00:00",
                           "missing_inputs": ["JUDGE_COVERAGE.json"],
                           "why": "JUDGE_COVERAGE.json: stale: 9.3h old"})
    doc = fence.judge(_families(tmp_path), now=NOW)
    row = _eta_row(doc)
    assert row["state"] == "FAIL"
    assert "JUDGE_COVERAGE.json" in row["why"] and "2 consecutive readings" in row["why"]
    assert doc["verdict"] == "FAIL"
    assert fence._exit(doc["verdict"]) == 1


def test_first_unmeasured_reading_only_warns(tmp_path: Path) -> None:
    _write_rate(tmp_path, {"status": UNMEASURED, "unmeasured_readings": 1,
                           "missing_inputs": ["JUDGE_COVERAGE.json"], "why": "stale"})
    doc = fence.judge(_families(tmp_path), now=NOW)
    assert _eta_row(doc)["state"] == "WARN"
    assert doc["verdict"] == "PASS"


def test_an_unmeasured_reading_with_no_history_fails_closed(tmp_path: Path) -> None:
    """The published artifact of 2026-10-14, verbatim in shape: no counter, so no proof it is
    the first reading -- and the input it names is derived, not guessed."""
    _write_rate(tmp_path, {"status": UNMEASURED,
                           "why": "backlog UNMEASURED (GAUNTLET_BACKPRESSURE.json absent)"},
                backlog=UNMEASURED, coverage_backlog_fresh=False,
                backlog_source="C:\\opt\\quant\\desks\\mt5\\reports\\GAUNTLET_BACKPRESSURE.json",
                verdicts={"status": "MEASURED"}, created={"status": "MEASURED"})
    row = _eta_row(fence.judge(_families(tmp_path), now=NOW))
    assert row["state"] == "FAIL"
    assert row["missing_inputs"] == ["JUDGE_COVERAGE.json", "GAUNTLET_BACKPRESSURE.json"]


def test_a_measured_eta_passes(tmp_path: Path) -> None:
    _write_rate(tmp_path, {"status": "GROWING", "hours": None})
    doc = fence.judge(_families(tmp_path), now=NOW)
    assert _eta_row(doc)["state"] == "OK"
    assert doc["verdict"] == "PASS"


def test_an_absent_rate_fails_only_where_the_box_owes_one(tmp_path: Path) -> None:
    report = _families(tmp_path)
    assert _eta_row(fence.judge(report, now=NOW))["state"] == "UNMEASURED"
    assert _eta_row(fence.judge(report, now=NOW, require_state=True))["state"] == "FAIL"


def test_the_eta_check_survives_an_absent_coverage_report(tmp_path: Path) -> None:
    """The coverage report going missing is exactly when the ETA goes dark: the early return
    must not swallow the ETA failure."""
    _write_rate(tmp_path, {"status": UNMEASURED, "unmeasured_readings": 5,
                           "missing_inputs": ["JUDGE_COVERAGE.json"], "why": "absent"})
    doc = fence.judge(tmp_path / "JUDGE_COVERAGE.json", now=NOW)
    assert doc["verdict"] == "FAIL"
    assert "JUDGE_COVERAGE.json" in doc["why"]
