"""Staleness must disarm: the desk stops opening risk when every research heartbeat is silent."""
from __future__ import annotations

import os
import sys
import time
from pathlib import Path

_DESK = Path(__file__).resolve().parents[1]
if str(_DESK) not in sys.path:
    sys.path.insert(0, str(_DESK))

from mt5desk import desk_staleness as ds  # noqa: E402


def _beat(p: Path, age_days: float) -> Path:
    p.write_text("{}", "utf-8")
    t = time.time() - age_days * 86400.0
    os.utime(p, (t, t))
    return p


def test_fresh_desk_is_ok(tmp_path: Path) -> None:
    beats = (_beat(tmp_path / "a.json", 0.02), _beat(tmp_path / "b.json", 5.0))
    d = ds.staleness(heartbeats=beats)
    assert d["verdict"] == "OK" and d["newest"] == "a.json"


def test_all_silent_disarms_then_flattens(tmp_path: Path) -> None:
    beats = (_beat(tmp_path / "a.json", 3.5), _beat(tmp_path / "b.json", 4.0))
    assert ds.staleness(heartbeats=beats)["verdict"] == "DISARM"
    beats = (_beat(tmp_path / "a.json", 7.5), _beat(tmp_path / "b.json", 9.0))
    assert ds.staleness(heartbeats=beats)["verdict"] == "FLATTEN"


def test_one_live_heartbeat_keeps_the_desk_armed(tmp_path: Path) -> None:
    beats = (_beat(tmp_path / "a.json", 9.0), _beat(tmp_path / "b.json", 0.5))
    assert ds.staleness(heartbeats=beats)["verdict"] == "OK"


def test_no_heartbeat_at_all_is_unmeasured_and_disarmed(tmp_path: Path) -> None:
    d = ds.staleness(heartbeats=(tmp_path / "missing.json",))
    assert d["status"] == "UNMEASURED" and d["verdict"] == "DISARM"
