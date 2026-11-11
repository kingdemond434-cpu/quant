"""A stale book names its holder (idea 610): PF_ALLOCATION_HOLD.json.

2026-11-11: pf_allocation sat 183 minutes old against its 90-minute contract while every fast
pass exited 0 behind a heavy pass's lock. Every stand-down now writes who holds the lock and
since when, and says HOLD once the standing book is past contract; a published pass says FRESH.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

_DESK = Path(__file__).resolve().parents[1]
for _p in (str(_DESK), str(_DESK / "research"), str(_DESK.parent.parent)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from research import pf_allocator as pa  # noqa: E402

HOLDER = {"pid": 24544, "host": "vmi3571445", "started_at": "2026-11-11T05:36:01+00:00",
          "heartbeat_age_s": 40.0, "owner": "ALIVE", "token": "secret-ish"}


def test_past_contract_is_a_hold_that_names_the_holder() -> None:
    doc = pa.allocation_hold(183 * 60.0, HOLDER, mode="fast", reason="BUSY")
    assert doc["status"] == "HOLD" and doc["contract_s"] == 90 * 60
    assert doc["holder"]["pid"] == 24544 and doc["holder"]["started_at"].startswith("2026-11-11")
    assert "token" not in doc["holder"]
    assert "183 min old against its 90-min contract" in doc["why"]
    assert "pid 24544 since 2026-11-11T05:36:01" in doc["why"]
    assert pa.allocation_hold(30 * 60.0, HOLDER, mode="fast", reason="BUSY")["status"] == \
        "STANDING"
    assert pa.allocation_hold(None, None, mode="fast", reason="NO_ROOM")["status"] == "UNMEASURED"


def test_a_stand_down_writes_it_and_a_publish_clears_it(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(pa, "ALLOCATION_HOLD", tmp_path / "PF_ALLOCATION_HOLD.json")
    monkeypatch.setattr(pa, "STANDDOWN", tmp_path / "ALLOCATOR_STANDDOWN.json")
    out = tmp_path / "pf_allocation.json"
    out.write_text("{}", "utf-8")
    import os
    import time
    old = time.time() - 3 * 3600
    os.utime(out, (old, old))
    monkeypatch.setattr(pa, "OUT", out)
    monkeypatch.setattr(pa, "ROOT", tmp_path)
    pa._record_stand_down("fast", "BUSY", "held", holder=HOLDER)
    doc = json.loads((tmp_path / "PF_ALLOCATION_HOLD.json").read_text("utf-8"))
    assert doc["status"] == "HOLD" and doc["holder"]["pid"] == 24544
    pa._clear_stand_down("fast")
    assert json.loads((tmp_path / "PF_ALLOCATION_HOLD.json").read_text("utf-8"))["status"] == \
        "FRESH"
