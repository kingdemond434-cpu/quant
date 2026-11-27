"""Guardian sweep: everything on the box is inventoried, diffed and held to a learned contract;
coverage is published with a floor that only rises; secrets are never listed."""
from __future__ import annotations

import json
import os
from collections import namedtuple
from datetime import UTC, datetime, timedelta
from pathlib import Path

from libs.ops import guardian_sweep as gs

T0 = datetime(2026, 11, 25, 0, tzinfo=UTC)
Usage = namedtuple("Usage", "total used free")


def _probe(pct: float):
    return lambda d: Usage(100, pct, 100 - pct)


def _touch(p: Path, at: datetime, size: int = 2000) -> None:
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_bytes(b"x" * size)
    os.utime(p, (at.timestamp(), at.timestamp()))


def _sweep(root: Path, now: datetime, pages: list[str] | None = None, pct: float = 50.0):
    hp = root / "desks/mt5/reports/process_health.json"
    if not hp.exists():   # a scheduler view with one contracted task; tests that need more write it
        hp.parent.mkdir(parents=True, exist_ok=True)
        hp.write_text(json.dumps({"processes": [{"name": "MT5-H", "verdict": "FRESH"}]}))
    os.utime(hp, (now.timestamp(), now.timestamp()))   # process_health refreshes every sweep
    return gs.run_once(root, now=now, page=(pages.append if pages is not None else None),
                       disk_probe=_probe(pct), drives=["C:\\"])


def test_learns_cadence_then_flags_stale_drift_and_pages(tmp_path: Path) -> None:
    rep = tmp_path / "desks/mt5/reports/HOURLY.json"
    pages: list[str] = []
    for h in range(6):                    # an hourly artifact, observed every hour
        _touch(rep, T0 + timedelta(hours=h))
        d = _sweep(tmp_path, T0 + timedelta(hours=h, minutes=5), pages)
    assert "file:desks/mt5/reports/HOURLY.json" not in d["uncovered"]
    assert d["faults_n"] == 0 and pages == []
    d = _sweep(tmp_path, T0 + timedelta(hours=9), pages)   # 4h silent > 3x 1h
    assert "STALE_DRIFT" in d["faults"]["file:desks/mt5/reports/HOURLY.json"]
    assert len(pages) == 1 and pages[0].startswith("GUARDIAN SWEEP:")


def test_shrank_empty_vanished_new_and_disk(tmp_path: Path) -> None:
    led = tmp_path / "desks/mt5/data/ledger.jsonl"
    other = tmp_path / "data/state.json"
    for h in range(4):
        _touch(led, T0 + timedelta(hours=h), 50_000)
        _touch(other, T0)
        _sweep(tmp_path, T0 + timedelta(hours=h, minutes=1))
    _touch(led, T0 + timedelta(hours=4), 100)               # 99.8% smaller
    new = tmp_path / "desks/mt5/reports/NEW_PRODUCER.json"
    _touch(new, T0 + timedelta(hours=4))
    other.unlink()
    d = _sweep(tmp_path, T0 + timedelta(hours=4, minutes=1), pct=93.0)
    assert "SHRANK" in d["faults"]["file:desks/mt5/data/ledger.jsonl"]
    assert d["faults"]["file:data/state.json"] == ["VANISHED"]
    assert "file:desks/mt5/reports/NEW_PRODUCER.json" in d["new"]
    assert d["faults"]["disk:C:\\"] == ["DISK_CRITICAL"]
    _touch(led, T0 + timedelta(hours=5), 0)
    d = _sweep(tmp_path, T0 + timedelta(hours=5, minutes=1))
    assert "EMPTY" in d["faults"]["file:desks/mt5/data/ledger.jsonl"]


def test_secrets_are_never_listed_and_big_dirs_are_streams(tmp_path: Path) -> None:
    _touch(tmp_path / "data/secrets/key.json", T0)
    _touch(tmp_path / "desks/mt5/data/secret_old/k", T0)
    tape = tmp_path / "desks/mt5/data/tape"
    for i in range(gs.GROUP_OVER + 1):
        _touch(tape / f"t{i}.bin", T0, 10)
    items = gs.scan_artifacts(tmp_path)
    assert not any("secret" in k for k in items)
    assert items["dir:desks/mt5/data/tape"]["files"] == gs.GROUP_OVER + 1
    assert not any(k.startswith("file:desks/mt5/data/tape/") for k in items)


def test_tasks_diffed_against_the_manifest(tmp_path: Path) -> None:
    mf = tmp_path / gs.MANIFEST_REL
    mf.parent.mkdir(parents=True)
    mf.write_text('TASK name="MT5-A" lane="research"\nTASK name="MT5-Gone" lane="ops"\n'
                  'TASK name="MT5-Old" lane="ops"\n')
    (tmp_path / gs.RETIRED_REL).write_text(json.dumps({"retired": [{"task": "MT5-Old"}]}))
    hp = tmp_path / "desks/mt5/reports/process_health.json"
    hp.parent.mkdir(parents=True, exist_ok=True)

    def health(code: int, run: str) -> None:
        hp.write_text(json.dumps({"processes": [
            {"name": "MT5-A", "verdict": "FRESH", "last_run": run, "last_result_code": code},
            {"name": "MT5-Rogue", "verdict": "UNCONTRACTED", "last_run": run,
             "last_result_code": 0}]}))

    for i in range(3):
        health(1, f"run{i}")
        d = _sweep(tmp_path, T0 + timedelta(hours=i))
    f = d["faults"]
    assert "RESULT_STREAK" in f["task:MT5-A"]
    assert f["task:MT5-Gone"] == ["DECLARED_ABSENT"]
    assert "task:MT5-Old" not in f                       # retired: not absent
    assert "UNDECLARED" in f["task:MT5-Rogue"]
    assert "task:MT5-Rogue" in d["uncovered"] and "task:MT5-Gone" in d["uncovered"]


def test_declarative_same_day_checks(tmp_path: Path) -> None:
    cd = tmp_path / gs.CHECKS_REL
    cd.mkdir(parents=True)
    (cd / "a.json").write_text(json.dumps({"id": "cert_book", "path": "desks/mt5/reports/CB.json",
                                           "max_age_h": 2, "json_key": "e8"}))
    (cd / "b.json").write_text(json.dumps({"id": "sneaky", "path": "data/secrets/x.json"}))
    cb = tmp_path / "desks/mt5/reports/CB.json"
    cb.parent.mkdir(parents=True)
    cb.write_text(json.dumps({"e8": {}}))
    os.utime(cb, (T0.timestamp(), T0.timestamp()))
    d = _sweep(tmp_path, T0 + timedelta(hours=1))
    assert "check:cert_book" not in d["faults"]
    assert d["faults"]["check:sneaky"] == ["CHECK_FAILED(refused: a secrets path)"]
    d = _sweep(tmp_path, T0 + timedelta(hours=3))
    assert d["faults"]["check:cert_book"][0].startswith("CHECK_FAILED(")


def test_coverage_floor_only_rises(tmp_path: Path) -> None:
    a = tmp_path / "desks/mt5/reports/A.json"
    for h in range(5):
        _touch(a, T0 + timedelta(hours=h))
        d = _sweep(tmp_path, T0 + timedelta(hours=h, minutes=1))
    assert d["coverage_pct"] == 100.0 and d["floor_pct"] == 0.0
    _touch(a, T0 + timedelta(hours=25))
    d = _sweep(tmp_path, T0 + timedelta(hours=25, minutes=1))
    assert d["floor_pct"] > 0
    floor = d["floor_pct"]
    for i in range(12):   # new, still-learning items drag coverage down
        _touch(tmp_path / f"desks/mt5/reports/N{i}.json", T0 + timedelta(hours=26))
    d = _sweep(tmp_path, T0 + timedelta(hours=26))
    assert d["coverage_pct"] < floor and d["floor_pct"] == floor
    assert "COVERAGE_BELOW_FLOOR" in d["faults"]["coverage"]
    cov = json.loads((tmp_path / gs.COVERAGE_REL).read_text())
    assert cov["below_floor"] is True and cov["coverage_pct"] == d["coverage_pct"]


def test_checks_are_confined_to_the_repository(tmp_path: Path) -> None:
    c = {"id": "x", "path": "../outside.json"}
    (tmp_path.parent / "outside.json").write_text("{}")
    assert gs.run_check(tmp_path, c, T0) == "refused: outside the repository"
