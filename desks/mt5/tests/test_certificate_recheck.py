"""The live certificate whose COT inputs moved under it is marked until it is re-judged (#238).

`research/certificate_recheck.py` keeps a row RECHECK_REQUIRED until the sealed gauntlet's
reproduction report exists, runs that reproduction at most once per RETRY_S while it is
missing, never again once it has reported, and edits no certificate.
"""
from __future__ import annotations

import json
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

_DESK = Path(__file__).resolve().parents[1]
_ROOT = _DESK.parent.parent
for p in (str(_DESK), str(_ROOT)):
    if p not in sys.path:
        sys.path.insert(0, p)

from research import certificate_recheck as cr  # noqa: E402


@pytest.fixture
def world(tmp_path):
    report = tmp_path / "reproduction.json"
    config = tmp_path / "rechecks.json"
    config.write_text(json.dumps({"rechecks": [{
        "id": "cot238_EURUSD_cot_positioning",
        "sleeve": "EURUSD.cot_positioning.continuous#input_source=cot_point_in_time",
        "only": "EURUSD.cot_positioning.", "report_to": str(report),
        "reason": "labels moved later", "opened": "2026-11-11"}]}), "utf-8")
    calls: list = []
    verdicts: dict = {"v": None}

    def attempt(row, timeout_s):
        calls.append((row["only"], timeout_s))
        if verdicts["v"] is not None:                    # the reproduction reported
            report.write_text(json.dumps({"reproduced_at": "2026-11-12T00:00:00+00:00",
                                          "result": {"verdicts": verdicts["v"]}}), "utf-8")
        return {"at": datetime.now(UTC).isoformat(timespec="seconds"), "rc": 0, "tail": []}

    def run(**kw):
        return cr.run(config=config, out=tmp_path / "CERTIFICATE_RECHECKS.json",
                      attempt=attempt, **kw)
    return run, calls, verdicts, tmp_path


def _status(doc):
    return doc["rechecks"][0]["status"]


def test_no_report_is_recheck_required_and_the_reproduction_is_attempted(world):
    run, calls, _v, tmp = world
    doc = run()
    assert _status(doc) == cr.REQUIRED and doc["n_required"] == 1
    assert calls == [("EURUSD.cot_positioning.", cr.REPRO_TIMEOUT_S)]
    assert json.loads((tmp / "CERTIFICATE_RECHECKS.json").read_text())["n_required"] == 1


def test_a_missing_report_is_retried_only_after_the_retry_window(world, monkeypatch):
    run, calls, _v, _tmp = world
    run()
    run()
    assert len(calls) == 1 and _status(run()) == cr.REQUIRED
    later = datetime.now(UTC) + timedelta(seconds=cr.RETRY_S + 60)
    monkeypatch.setattr(cr, "_now", lambda: later)
    run()
    assert len(calls) == 2


@pytest.mark.parametrize("verdicts,status", [
    ([{"cell": "EURUSD.cot_positioning.p=ab", "passed": True}], cr.CLEARS),
    ([{"cell": "EURUSD.cot_positioning.p=ab", "passed": False, "terminal_gate": "dsr"}],
     cr.FAILS),
    ([{"cell": "EURUSD.cot_positioning.p=ab", "passed": False, "unmeasured": True}],
     cr.UNMEASURED),
    ([], cr.UNMEASURED),
])
def test_the_reproduction_verdict_closes_the_row(world, verdicts, status):
    run, calls, v, _tmp = world
    v["v"] = verdicts
    doc = run()
    assert _status(doc) == status and doc["n_required"] == 0
    run()
    assert len(calls) == 1                              # never re-run once it has reported


def test_a_failed_gate_is_named(world):
    run, _calls, v, _tmp = world
    v["v"] = [{"cell": "EURUSD.cot_positioning.p=ab", "passed": False, "terminal_gate": "pbo"}]
    assert run()["rechecks"][0]["failed_gates"] == ["pbo"]


def test_status_mode_runs_nothing_and_writes_nothing(world):
    run, calls, _v, tmp = world
    doc = run(dry_run=True)
    assert _status(doc) == cr.REQUIRED and calls == []
    assert not (tmp / "CERTIFICATE_RECHECKS.json").exists()


def test_the_attempt_is_reproduction_mode_only(monkeypatch, tmp_path):
    seen: dict = {}

    class _R:
        returncode, stdout, stderr = 0, "REPRODUCE: no cell matches", ""

    def fake_run(cmd, **kw):
        seen["cmd"], seen["kw"] = cmd, kw
        return _R()
    monkeypatch.setattr(cr.subprocess, "run", fake_run)
    got = cr._attempt({"only": "EURUSD.cot_positioning.", "report_to": str(tmp_path / "r.json")},
                      12.0)
    assert seen["cmd"][1:] == [str(cr.GAUNTLET), "--only", "EURUSD.cot_positioning.",
                               "--report-to", str(tmp_path / "r.json")]
    assert seen["kw"]["timeout"] == 12.0
    assert got["rc"] == 0 and "no cell matches" in got["tail"][0]


def test_the_committed_row_names_the_live_sleeve_and_not_the_flow_family():
    rows = cr.rows()
    row = next(r for r in rows if r["id"] == "cot238_EURUSD_cot_positioning")
    assert row["sleeve"] == "EURUSD.cot_positioning.continuous#input_source=cot_point_in_time"
    assert row["only"] == "EURUSD.cot_positioning."
    assert row["only"] not in "EURUSD.cot_positioning_flow.p=0123"
    assert row["report_to"] == "reports/reproduction_cot238_EURUSD_cot_positioning.json"


def test_the_hourly_leg_runs_the_recheck_and_survives_its_failure(monkeypatch):
    from research import cot_positioning_flow as cpf
    monkeypatch.setattr(cr, "run", lambda **_k: {"n_required": 1, "rechecks": [
        {"id": "x", "status": cr.REQUIRED}]})
    assert cpf.recheck(dry_run=True) == {"status": "RAN", "n_required": 1,
                                         "rechecks": {"x": cr.REQUIRED}}

    def boom(**_k):
        raise RuntimeError("disk")
    monkeypatch.setattr(cr, "run", boom)
    assert cpf.recheck(dry_run=True)["status"] == "FAILED"
