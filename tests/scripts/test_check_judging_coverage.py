"""The coverage fence: it must fire on a STALL, stay quiet on a healthy backlog, and it must
not be possible to unwire it from the law gate without a test going red."""
from __future__ import annotations

import json
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
for _p in (str(ROOT), str(ROOT / "scripts")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import check_judging_coverage as cjc  # noqa: E402


def _source(tmp_path, *, unjudged, docket=500_000, oldest=100.0, at=None):
    p = tmp_path / "JUDGE_COVERAGE.json"
    p.write_text(json.dumps({
        "at": (at or datetime.now(UTC)).isoformat(timespec="seconds"),
        "totals": {"docket_rows": docket, "unjudged_total": unjudged,
                   "oldest_unjudged_age_h": oldest}}), "utf-8")
    return p


# ----------------------------------------------------------------- a backlog is not a breach
def test_a_large_backlog_that_is_falling_is_not_a_breach(tmp_path):
    """The desk holds 443,368 unjudged cells today and judging is progressing. A fence that
    fired on size alone would be red from birth, and a gate that is always red is a gate
    somebody switches off (L1.43) -- which is how the next real stall goes silent."""
    rat = tmp_path / "ratchet.json"
    base = datetime.now(UTC) - timedelta(hours=10)
    for i, unjudged in enumerate((500_000, 480_000, 460_000, 440_000, 420_000, 400_000, 380_000)):
        out = cjc.measure(_source(tmp_path, unjudged=unjudged,
                                  at=base + timedelta(hours=i)), rat)
    assert out["status"] == "OK"
    assert out["breaches"] == []
    assert out["unjudged"] == 380_000
    assert out["judged_share"] == pytest.approx(0.24, abs=0.01)


# ----------------------------------------------------------------- a stalled backlog IS
def test_a_backlog_that_never_moves_is_a_breach(tmp_path):
    """87% unjudged for weeks with nothing saying so is the defect this exists for. A steady
    5,000 that turns over daily is healthy; a steady 5,000 that never moves is a stall."""
    rat = tmp_path / "ratchet.json"
    base = datetime.now(UTC) - timedelta(hours=12)
    out = None
    for i in range(cjc.STALL_READINGS + 1):
        out = cjc.measure(_source(tmp_path, unjudged=443_368,
                                  at=base + timedelta(hours=i)), rat)
    assert out["status"] == "BREACH"
    assert any("JUDGING STALLED" in b for b in out["breaches"])
    assert "443,368" in " ".join(out["breaches"])


def test_a_stall_shorter_than_the_grace_is_not_yet_a_breach(tmp_path):
    """A slow hour must not page anybody."""
    rat = tmp_path / "ratchet.json"
    base = datetime.now(UTC)
    out = None
    for i in range(cjc.STALL_READINGS + 1):
        out = cjc.measure(_source(tmp_path, unjudged=443_368,
                                  at=base + timedelta(minutes=i)), rat)
    assert out["status"] == "OK", "readings spanning minutes are not a stall"


def test_an_empty_backlog_is_never_a_stall(tmp_path):
    """100% judged is the goal, not a breach -- and it does not move by definition."""
    rat = tmp_path / "ratchet.json"
    base = datetime.now(UTC) - timedelta(hours=12)
    out = None
    for i in range(cjc.STALL_READINGS + 2):
        out = cjc.measure(_source(tmp_path, unjudged=0, at=base + timedelta(hours=i)), rat)
    assert out["status"] == "OK" and out["judged_share"] == 1.0


# ----------------------------------------------------------------- the ratchet (L1.50)
def test_coverage_going_backwards_is_a_breach(tmp_path):
    rat = tmp_path / "ratchet.json"
    cjc.measure(_source(tmp_path, unjudged=100_000, docket=500_000), rat)   # judged 400k
    out = cjc.measure(_source(tmp_path, unjudged=300_000, docket=500_000), rat)  # judged 200k
    assert out["status"] == "BREACH"
    assert any("WENT BACKWARDS" in b for b in out["breaches"])


def test_a_small_recount_is_tolerated_because_cells_legitimately_leave_the_docket(tmp_path):
    rat = tmp_path / "ratchet.json"
    cjc.measure(_source(tmp_path, unjudged=100_000, docket=500_000), rat)
    out = cjc.measure(_source(tmp_path, unjudged=100_000 + cjc.RATCHET_TOLERANCE - 1,
                              docket=500_000), rat)
    assert out["status"] == "OK"


def test_the_high_water_mark_only_rises(tmp_path):
    rat = tmp_path / "ratchet.json"
    cjc.measure(_source(tmp_path, unjudged=100_000, docket=500_000), rat)
    out = cjc.measure(_source(tmp_path, unjudged=101_000, docket=500_000), rat)
    assert out["judged_high_water"] == 400_000


# ----------------------------------------------------------------- absence vs silence
def test_a_host_with_no_judge_passes_saying_so(tmp_path):
    out = cjc.measure(tmp_path / "absent.json", tmp_path / "r.json")
    assert out["status"] == "NOT_APPLICABLE" and out["ok"] is True


def test_a_judging_host_whose_artifact_is_unreadable_fails_rather_than_passing(tmp_path):
    """'No evidence' is precisely what 87% unjudged looked like from the outside (L1.28a)."""
    bad = tmp_path / "JUDGE_COVERAGE.json"
    bad.write_text("{not json", "utf-8")
    out = cjc.measure(bad, tmp_path / "r.json")
    assert out["status"] == "UNMEASURED" and out["ok"] is False


def test_totals_without_the_unjudged_count_is_unmeasured_not_zero(tmp_path):
    p = tmp_path / "JUDGE_COVERAGE.json"
    p.write_text(json.dumps({"totals": {"docket_rows": 10}}), "utf-8")
    out = cjc.measure(p, tmp_path / "r.json")
    assert out["status"] == "UNMEASURED" and out["ok"] is False


# ----------------------------------------------------------------- it cannot be unwired
def test_the_fence_is_registered_in_the_law_gate_and_cannot_be_quietly_removed():
    """The property that makes the rest of this file worth anything. Modelled on the placement
    interlock's own test: a fence nobody runs is a claim the desk cannot cash (L1.49)."""
    # `tests/scripts/__init__.py` shadows the top-level `scripts` package, so the gate is
    # imported by module name off sys.path -- the way every sibling fence test does it.
    import run_law_gate as rlg
    names = {n for n, _a in (*rlg._LAW_FENCES, *rlg._STATE_FENCES)}
    assert "check_judging_coverage.py" in names, (
        "the judging-coverage fence was removed from the law gate; 87% of the docket once sat "
        "unjudged with nothing watching, and this test is what stops that returning")
    assert ("check_judging_coverage.py", ()) in rlg._STATE_FENCES, (
        "it reads LIVE coverage state, so it belongs in _STATE_FENCES")


def test_the_fence_rations_nothing_and_caps_nothing():
    """Judging more cells is free in multiplicity terms. This fence must never propose a cap."""
    src = Path(cjc.__file__).read_text(encoding="utf-8")
    for forbidden in ("max_cells", "limit_cells", "throttle", "cap_", "shrink"):
        assert forbidden not in src, f"a coverage fence must never {forbidden}"
