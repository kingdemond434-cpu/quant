"""A resident mid-pass is not STALE, and an IgnoreNew refusal says so (coordinator, 2026-11-18).

A box read found MT5-Gauntlet reported STALE (artifact 308 min against a 240 min contract) and
"the operator or administrator refused the request" while a healthy sharded pass was running:
its trigger fires every minute, IgnoreNew refuses it, and a full pass outlasts the contract."""

from __future__ import annotations

import json
import os
import sys
import time
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "ops"))
import process_health as ph  # noqa: E402

ART = "desks/mt5/reports/UNIVERSAL_SURVIVORS.json"
HB = "desks/mt5/reports/GAUNTLET_HEARTBEAT.json"


def _iso(t: datetime) -> str:
    return t.isoformat(timespec="seconds")


@pytest.fixture
def box(monkeypatch: Any, tmp_path: Path) -> Path:
    monkeypatch.setattr(ph, "ROOT", tmp_path)
    (tmp_path / "desks/mt5/reports").mkdir(parents=True)
    art = tmp_path / ART
    art.write_text("{}", encoding="utf-8")
    old = time.time() - 308 * 60
    os.utime(art, (old, old))
    return tmp_path


def _beat(root: Path, **over: Any) -> None:
    now = datetime.now(tz=UTC)
    doc = {"status": "RUNNING", "started_utc": _iso(now - timedelta(minutes=60)),
           "beat_utc": _iso(now - timedelta(seconds=40)), "beat_every_s": 30.0,
           "phase": "merge_and_publish",
           "deadlines": {"run_deadline_utc": _iso(now + timedelta(hours=20))}}
    doc.update(over)
    (root / HB).write_text(json.dumps(doc), encoding="utf-8")


def _build(monkeypatch: Any, code: str = "2147946720") -> dict[str, Any]:
    rows = [{"TaskName": "\\MT5-Gauntlet", "Scheduled Task State": "Enabled",
             "Status": "Ready", "Last Run Time": "now", "Next Run Time": "later",
             "Last Result": code}]
    monkeypatch.setattr(ph, "_tasks", lambda: (rows, "OK schtasks"))
    monkeypatch.setattr(ph, "_contracts", lambda: {"MT5-Gauntlet": (ART, 240, "registry")})
    monkeypatch.setattr(ph, "_artifact_age", lambda a: ph._age_min(ph.ROOT / a))
    monkeypatch.setattr(ph, "_manifest", lambda: {"MT5-Gauntlet": {
        "trigger": "resident (sweeps back to back); every 1 minute respawns it if it died, "
                   "IgnoreNew, no time limit", "lane": "research"}})
    monkeypatch.setattr(ph, "_read_report", lambda: {"processes": [
        {"name": "MT5-Gauntlet", "bad_reads": 2, "bad_since": "earlier"}]})
    doc = ph.build()
    return next(r for r in doc["processes"] if r["name"] == "MT5-Gauntlet")


def test_a_pass_in_flight_excuses_the_stale_contract(box: Path, monkeypatch: Any) -> None:
    _beat(box)
    row = _build(monkeypatch)
    assert row["verdict"] == "OK" and row["in_flight"] is True
    assert "pass is in flight" in row["why"] and "merge_and_publish" in row["why"]
    assert row["last_result"] == "an instance is already running (IgnoreNew)"
    assert row["bad_reads"] == 0
    # never_stale must not be handed a restartable resident: ending a sweep loses hours of work
    assert row["resident"] is False


@pytest.mark.parametrize("over", [
    {"status": "STALLED"},
    {"beat_utc": _iso(datetime.now(tz=UTC) - timedelta(minutes=30))},
    {"started_utc": _iso(datetime.now(tz=UTC) - timedelta(minutes=400))},
    {"deadlines": {"run_deadline_utc": _iso(datetime.now(tz=UTC) - timedelta(minutes=1))}},
    {"beat_utc": "garbage"},
])
def test_anything_short_of_a_live_newer_pass_stays_stale(box: Path, monkeypatch: Any,
                                                        over: dict[str, Any]) -> None:
    _beat(box, **over)
    row = _build(monkeypatch)
    assert row["verdict"] == "STALE" and row["in_flight"] is False
    assert row["bad_reads"] == 3


def test_no_heartbeat_stays_stale(box: Path, monkeypatch: Any) -> None:
    row = _build(monkeypatch)
    assert row["verdict"] == "STALE"


def test_ignore_new_label_only_where_the_manifest_declares_it(box: Path,
                                                             monkeypatch: Any) -> None:
    assert ph.ignores_new("every 1 minute, IgnoreNew")
    assert not ph.ignores_new("every 5 minutes")
    assert ph.RESULT_MEANING[ph.REFUSED].startswith("the operator")


def test_the_gauntlet_is_not_made_restartable() -> None:
    m = ph._manifest()
    assert "MT5-Gauntlet" in m and ph.ignores_new(m["MT5-Gauntlet"]["trigger"])
    assert not ph.is_resident(m["MT5-Gauntlet"]["trigger"])
