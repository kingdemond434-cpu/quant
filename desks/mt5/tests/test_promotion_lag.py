"""An eligible sleeve that is not LIVE is listed with its reason, and a flaw past a cycle fails.

Principal 2026-10-13: "sleeves eligible fr promotion but didnt go live yet is flaw too".
"""
from __future__ import annotations

import sys
from datetime import UTC, datetime
from pathlib import Path

DESK = Path(__file__).resolve().parents[1]
for _p in (str(DESK), str(DESK / "scripts"), str(DESK / "research"), str(DESK.parent.parent)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import check_promotion_lag as cpl  # noqa: E402

NOW = datetime(2026, 10, 13, 16, 0, tzinfo=UTC)
SCAN = "2026-10-13T15:30:00+00:00"
OLD = "2026-10-10T00:00:00+00:00"


def _row(name, **kw):
    return {"name": name, "symbol": "XAUUSD", "family": "f", "status": "STANDBY",
            "admit_scan": SCAN, "restored_at": OLD, **kw}


def _build(rows, refuse=lambda r, p: None, certs=("c1",)):
    survivors = {"gate_policy": "x", "survivors": {}}
    real = cpl.certified_keys
    cpl.certified_keys = lambda _doc: set(certs)
    try:
        return cpl.build(NOW, sleeves_doc={"sleeves": rows}, survivors=survivors,
                         refuse=refuse, policy=object())
    finally:
        cpl.certified_keys = real


def test_an_allocator_decision_is_listed_and_does_not_fail() -> None:
    doc = _build([_row("a", admission={"why": "refused: the optimiser gives it 0.0000% heat"})])
    assert doc["by_reason"] == {"allocator_declines": 1} and doc["verdict"] == "PASS"


def test_an_unpriced_or_unscanned_or_unpromoted_sleeve_fails_after_a_cycle() -> None:
    rows = [_row("u", admission={"why": "the allocator has not priced this mechanism"}),
            _row("s", admit_scan="2026-10-13T10:00:00+00:00"),
            _row("p", admit_streak=2, admission={"why": "admitted"})]
    doc = _build(rows)
    assert doc["verdict"] == "FAIL"
    assert doc["late_by_reason"] == {"allocator_unpriced": 1, "scan_stale": 1, "promoter_lag": 1}


def test_a_fresh_flaw_waits_one_cycle_before_failing() -> None:
    fresh = _row("u", restored_at="2026-10-13T15:00:00+00:00",
                 admission={"why": "no allocator row answers to any of ['u']"})
    doc = _build([fresh])
    assert doc["by_reason"] == {"allocator_unpriced": 1} and doc["verdict"] == "PASS"


def test_a_certified_policy_retirement_is_restore_pending_unless_policy_still_refuses() -> None:
    ret = {"name": "r", "status": "RETIRED", "retired_by": "live_policy", "retired_at": OLD,
           "certificate": {"cell": "c1"}}
    doc = _build([ret])
    assert doc["late_by_reason"] == {"restore_pending": 1}
    held = _build([ret], refuse=lambda r, p: "outside live_symbols")
    assert held["by_reason"] == {"symbol_policy": 1} and held["verdict"] == "PASS"
    uncert = _build([{**ret, "certificate": {"cell": "other"}}])
    assert uncert["eligible_not_live"] == 0


def test_the_streak_matches_the_promoter() -> None:
    src = (DESK / "research" / "promoter.py").read_text(encoding="utf-8")
    assert f"PROMOTE_ADMIT_STREAK = {cpl.PROMOTE_ADMIT_STREAK}\n" in src
