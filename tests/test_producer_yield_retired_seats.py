"""A one-off donation seat is RETIRED, not DEAD; a live seat at zero is still DEAD.

Builds its own intelligence tree in `tmp_path`, so the verdicts do not depend on what the box
last wrote.
"""
from __future__ import annotations

import os
import time
from pathlib import Path

import pytest

from scripts import check_producer_yield as fence


@pytest.fixture
def intel(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    desk = tmp_path / "desks" / "mt5"
    monkeypatch.setattr(fence, "DESK", desk)
    monkeypatch.setattr(fence, "ROOT", tmp_path)
    root = desk / "data" / "intelligence"
    old = time.time() - 30 * 86400
    for seat in ("firm_mining", "statarb", "anomalies"):
        f = root / seat / "discoveries_old.json"
        f.parent.mkdir(parents=True, exist_ok=True)
        f.write_text("{}\n", encoding="utf-8")
        os.utime(f, (old, old))
    fresh = root / "physics_lab" / "discoveries_new.json"
    fresh.parent.mkdir(parents=True, exist_ok=True)
    fresh.write_text("{}\n{}\n", encoding="utf-8")
    return root


def _by_name(doc: dict) -> dict[str, dict]:
    return {r["producer"]: r for r in doc["producers"]}


def test_one_off_seats_are_retired_with_their_reason(intel: Path) -> None:
    doc = fence.audit(window_days=3.0)
    rows = _by_name(doc)
    for seat in ("firm_mining", "statarb"):
        assert rows[seat]["verdict"] == "RETIRED"
        assert rows[seat]["why"] == fence.RETIRED_SEATS[seat]
    names = {r["producer"] for r in doc["dead_without_a_declared_replacement"]}
    assert not names & set(fence.RETIRED_SEATS)


def test_a_live_seat_at_zero_is_still_dead(intel: Path) -> None:
    rows = _by_name(fence.audit(window_days=3.0))
    assert rows["anomalies"]["verdict"] == "DEAD"
    assert rows["physics_lab"]["verdict"] == "PRODUCING"


def test_a_retired_seat_that_writes_again_is_judged_normally(intel: Path) -> None:
    (intel / "statarb" / "discoveries_new.json").write_text("{}\n{}\n", encoding="utf-8")
    rows = _by_name(fence.audit(window_days=3.0))
    assert rows["statarb"]["verdict"] in ("PRODUCING", "STARVED")


def test_a_retired_seat_absent_from_disk_is_still_named(tmp_path: Path,
                                                        monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(fence, "DESK", tmp_path / "desks" / "mt5")
    monkeypatch.setattr(fence, "ROOT", tmp_path)
    rows = _by_name(fence.audit(window_days=3.0))
    # no seat directory at all: nothing measured, so UNMEASURED, never a silent omission
    assert rows["statarb"]["verdict"] == "UNMEASURED"
