"""The controller feed: the allocation becomes a WEIGHTED queue (repeats in proportion, one family
capped), the least-funded families keep a floor, and a stale, unreadable or empty allocation falls
back to the static list with its reason."""
from __future__ import annotations

import json
from collections import Counter
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from libs.ops import controller_feed as cf


@pytest.fixture
def loop(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    p = tmp_path / "research_loop.json"
    monkeypatch.setattr(cf, "LOOP", p)
    return p


def _write(p: Path, allocation: object, age_h: float = 0.5) -> None:
    ran = (datetime.now(tz=UTC) - timedelta(hours=age_h)).isoformat()
    p.write_text(json.dumps({"ran_at": ran, "allocation": allocation}), "utf-8")


def test_absent_or_unreadable_falls_back_with_reason(loop: Path) -> None:
    fams, why = cf.controller_families(["a", "b"])
    assert fams == ["a", "b"] and "unreadable (FileNotFoundError)" in why
    loop.write_text("{not json", "utf-8")
    fams, why = cf.controller_families(None)
    assert fams is None and "JSONDecodeError" in why


def test_unparseable_or_stale_ran_at_is_refused(loop: Path) -> None:
    loop.write_text(json.dumps({"ran_at": "yesterday", "allocation": {"a": 3}}), "utf-8")
    fams, why = cf.controller_families(["static"])
    assert fams == ["static"] and "no readable ran_at" in why
    _write(loop, {"a": 3}, age_h=cf.MAX_AGE_H + 1)
    fams, why = cf.controller_families(["static"])
    assert fams == ["static"] and "stale posterior" in why


def test_nothing_allocated_falls_back(loop: Path) -> None:
    _write(loop, {"a": 0, "b": -2, "c": "many"})
    fams, why = cf.controller_families(["s"])
    assert fams == ["s"] and "allocated nothing" in why


def test_weighted_by_allocation_with_cap_and_floor(loop: Path) -> None:
    _write(loop, {"calendar_month": 65, "cot_positioning": 29, "cross_asset_residual": 2,
                  "carry": 4})
    fams, why = cf.controller_families(["s"])
    assert fams is not None
    c = Counter(fams)
    # the leader is capped at 40% of total trials before scaling: round(40/100*100) = 40
    assert c["calendar_month"] == 40
    assert c["cot_positioning"] == 29
    assert c["carry"] == 4
    # floor: len(alloc)//4 = 1 tail family (the least-funded) gets int(75 * 0.15) more slots
    assert c["cross_asset_residual"] == 2 + int(75 * cf.MIN_SHARE_FAMILIES)
    assert "4 famil(ies)" in why and "least-funded" in why
    assert fams[0] == "calendar_month"                     # highest allocation first


def test_list_shaped_allocation_is_accepted(loop: Path) -> None:
    _write(loop, [{"family": "a", "trials": 3}, {"branch": "b", "trials": 1}, "junk"])
    fams, _ = cf.controller_families(None)
    assert fams is not None and set(fams) == {"a", "b"}
    c = Counter(fams)
    # total 4, cap int(1.6)=1: both scale to 25 slots; b (least funded) adds int(50 * 0.15) = 7
    assert c["a"] == 25 and c["b"] == 25 + 7
