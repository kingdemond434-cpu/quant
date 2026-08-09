"""Tests for the forward-queue-depth ceiling and the accruing-slot numerator (R0205, L1.28a).

WHAT THIS FENCE EXISTS TO CATCH, and why the tests are shaped this way. The desk owned a fence
over forward-slot OCCUPANCY and nothing at all over pipeline DEPTH, so the state R0205 describes
-- 12/12 slots occupied, ZERO candidates staged behind them, ~181-day latency before a freed slot
can restart -- read as `SATURATED`, exit 0, with no binding constraint named. The single most
important assertion here is therefore NOT that the arithmetic is right: it is that a full cohort
with an empty queue makes the fence go RED. A ceiling that cannot report the condition it was
written for is the welded-gate defect (L1.43), and this file is what stops it recurring.

The second class covered is the numerator. `used` was a head-count of TAKEN slots, so a clock
holding cohort capacity while accruing no evidence -- the registry's own `not_accruing` -- was
indistinguishable from a healthy one. Occupancy is not utilisation, and the test asserts the
dormant slot is excluded and NAMED.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

_ROOT = Path(__file__).resolve().parents[2]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from scripts import check_utilisation as fence  # noqa: E402


def _queues(root: Path, *, n_candidates: int | None = 0, queued: int | None = 0,
            why: str = "") -> None:
    """Write the two staging registers. `None` means 'artifact absent' (the unreadable path)."""
    (root / "data").mkdir(parents=True, exist_ok=True)
    if n_candidates is not None:
        (root / "data/promotion_queue.json").write_text(
            json.dumps({"n_candidates": n_candidates, "queue": [{}] * n_candidates}), "utf-8")
    if queued is not None:
        (root / "data/paper_sleeve_queue.json").write_text(
            json.dumps({"queued": [{"name": f"c{i}"} for i in range(queued)], "why": why}),
            "utf-8")


@pytest.fixture
def at(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    monkeypatch.setattr(fence, "_ROOT", tmp_path)
    return tmp_path


# --------------------------------------------------------------------------------------------
# THE CONDITION THE CEILING WAS WRITTEN FOR
# --------------------------------------------------------------------------------------------

def test_empty_queue_is_idle_unexplained_not_saturated(at: Path) -> None:
    """The R0205 state itself: nothing staged must be RED, and must NOT self-excuse.

    An empty queue is not a survival rail and not an external blocker -- the only two things
    L1.28a admits as legitimate idle headroom -- so it must reach IDLE-UNEXPLAINED. If a future
    edit names a binding constraint here, the status silently becomes IDLE-EXPLAINED, `main()`
    returns 0, and the fence is decoration. That is the regression this asserts against.
    """
    _queues(at, n_candidates=0, queued=0, why="zero qualifying survivors")
    c = fence._forward_queue_depth()

    assert c.used == 0.0
    assert c.measured is True, "both artifacts were readable -- this is a real zero, not unknown"
    assert c.binding_constraint == "", "an empty queue must never name its own constraint"
    assert c.status == "IDLE-UNEXPLAINED"


def test_empty_queue_makes_the_whole_fence_exit_nonzero(at: Path) -> None:
    """End-to-end: the report must carry the ceiling and main() must fail on it.

    Asserted through `build()` rather than the dataclass so a ceiling dropped from `collect()`
    fails here too -- the built-never-wired failure, one layer up.
    """
    _queues(at, n_candidates=0, queued=0)
    rep = fence.build()

    assert "forward_queue_depth" in [r["name"] for r in rep["ceilings"]]
    assert "forward_queue_depth" in rep["idle_unexplained"]


def test_staged_candidates_count_from_both_registers(at: Path) -> None:
    """Two independent registers feed the cohort; reading one understates the depth."""
    _queues(at, n_candidates=5, queued=7)
    c = fence._forward_queue_depth()

    assert c.used == 12.0
    assert c.status == "SATURATED", "a queue stocked to one full cohort refills with zero wait"
    assert "5 gauntlet survivor(s)" in c.detail
    assert "7 paper-sleeve candidate(s)" in c.detail


def test_unreadable_queues_are_unmeasured_never_a_confident_zero(at: Path) -> None:
    """UNMEASURED and EMPTY are different claims and only one is evidence.

    Both read 0.0 utilisation, so the arithmetic cannot tell them apart -- `measured` is the only
    thing that can, and collapsing them would let a broken reader look like a diagnosed stall.
    """
    _queues(at, n_candidates=None, queued=None)
    c = fence._forward_queue_depth()

    assert c.measured is False
    assert c.status == "UNMEASURED"
    assert "neither queue artifact is readable" in c.detail


def test_partial_read_still_counts_as_measured(at: Path) -> None:
    """One readable register is a real (if partial) measurement -- refusing it would understate."""
    _queues(at, n_candidates=3, queued=None)
    c = fence._forward_queue_depth()

    assert c.measured is True
    assert c.used == 3.0
    assert "paper_sleeve_queue" not in c.detail


# --------------------------------------------------------------------------------------------
# OCCUPANCY IS NOT UTILISATION
# --------------------------------------------------------------------------------------------

def _cohort(monkeypatch: pytest.MonkeyPatch, *, occupied: int, accruing: int,
            dormant: list[str]) -> None:
    import libs.research.slot_registry as reg
    monkeypatch.setattr(reg, "derive_slots", lambda: {
        "slots": [{"name": f"s{i}"} for i in range(occupied)],
        "accruing": accruing,
        "not_accruing": [{"name": n, "evidence": "NO-EVIDENCE"} for n in dormant]})


def test_dormant_slot_is_not_counted_as_utilised(monkeypatch: pytest.MonkeyPatch) -> None:
    """A clock holding cohort capacity while returning no evidence is the worst reading there is.

    It charges every other candidate's Holm bar and produces nothing. Counting it as utilised
    made it indistinguishable from a healthy clock -- measured on the live artifact as 12/12
    SATURATED while `cny_premium` sat at NO-EVIDENCE.
    """
    _cohort(monkeypatch, occupied=12, accruing=11, dormant=["cny_premium"])
    c = fence._forward_slots()

    assert c.used == 11.0, "the numerator is accruing clocks, not taken slots"
    assert "12/12 slots occupied, 11 accruing" in c.detail
    assert "cny_premium" in c.detail


def test_dormant_shortfall_names_the_clock_not_candidate_supply(
        monkeypatch: pytest.MonkeyPatch) -> None:
    """The constraint must match the shortfall: an occupied-but-quiet slot is fixed at the
    OPPOSITE end of the pipeline from an empty one. Naming 'candidate supply' here would send
    the next reader upstream to generate candidates for a cohort that has no room."""
    _cohort(monkeypatch, occupied=12, accruing=6, dormant=["a", "b", "c", "d", "e", "f"])
    c = fence._forward_slots()

    assert c.status == "IDLE-EXPLAINED"
    assert "accruing NO evidence" in c.binding_constraint
    assert "candidate supply" not in c.binding_constraint


def test_empty_slots_still_name_candidate_supply(monkeypatch: pytest.MonkeyPatch) -> None:
    """The original diagnosis is preserved for the case it was actually right about."""
    _cohort(monkeypatch, occupied=4, accruing=4, dormant=[])
    c = fence._forward_slots()

    assert c.status == "IDLE-EXPLAINED"
    assert "candidate supply" in c.binding_constraint


def test_missing_accruing_key_falls_back_to_head_count(monkeypatch: pytest.MonkeyPatch) -> None:
    """Snapshots written before `accruing` existed must still measure, never read zero."""
    import libs.research.slot_registry as reg
    monkeypatch.setattr(
        reg, "derive_slots", lambda: {"slots": [{"name": f"s{i}"} for i in range(9)]})
    c = fence._forward_slots()

    assert c.measured is True
    assert c.used == 9.0
