"""AN UNACKNOWLEDGED PAGE IS ITSELF A RISK EVENT -- 101 statements, zero tests until now.

The premise is that the desk runs unattended and the principal is asleep. A critical page nobody
acks does not mean "probably fine"; it means the one human rail is currently ABSENT, and the book
should shed risk on a clock rather than wait indefinitely for a human who may not come.

The module names two properties it exists to guarantee, and each is a specific attack:

  MONOTONIC. It only ever climbs while a page stays unacked. A flapping clock, an out-of-order
  tick, or an NTP correction must never walk risk back UP. Tested by feeding time backwards.

  THE TOP RUNG LATCHES. `requires_manual_rearm` stays true until a human clears it, because the
  whole premise of the 4h rung is that automation has been running with no oversight for four
  hours -- letting that same automation decide it is fine now defeats the rung entirely. Tested
  by clearing every page and requiring the latch to survive it.

There is a third, subtler one the docstring makes explicit and nothing else guarded: the clock is
ANCHORED to the start of the run of silence. Recomputing from the newest page each tick would let a
re-paging condition reset the ladder forever -- a nagging alert nobody answers is precisely the
scenario the ladder exists for, so that reset would disarm it exactly when it was needed.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from libs.ops import derisk_ladder as DL

_M = 60.0
_H = 3600.0


# ------------------------------------------------------------------ the rungs

def test_the_three_spec_rungs_sit_at_15_minutes_60_minutes_and_4_hours() -> None:
    assert DL.RUNG_CANCEL_HALVE_S == 15 * _M
    assert DL.RUNG_FLATTEN_S == 60 * _M
    assert DL.RUNG_FULL_FLATTEN_S == 4 * _H


def test_the_ladder_only_ever_gets_STRICTER_as_it_climbs() -> None:
    """A rung that relaxed something a lower one restricted would make the ladder's position
    ambiguous, and 'we are at rung 3' would stop implying rung 2's protections."""
    prev = DL.LADDER[0]
    for rung in DL.LADDER[1:]:
        assert rung.threshold_s > prev.threshold_s
        assert rung.size_multiplier <= prev.size_multiplier
        assert rung.cancel_resting >= prev.cancel_resting
        assert rung.flatten >= prev.flatten
        assert rung.entries_allowed <= prev.entries_allowed
        prev = rung


@pytest.mark.parametrize(("age", "name"), [
    (0.0, "nominal"),
    (14 * _M, "nominal"),
    (15 * _M, "cancel_and_halve"),
    (59 * _M, "cancel_and_halve"),
    (60 * _M, "flatten_to_neutral"),
    (3.9 * _H, "flatten_to_neutral"),
    (4 * _H, "full_flatten_disarmed"),
    (400 * _H, "full_flatten_disarmed"),
])
def test_the_rung_is_the_highest_threshold_the_silence_has_PASSED(age, name) -> None:
    assert DL.rung_for(age).name == name


def test_a_NEGATIVE_age_reads_nominal_rather_than_wrapping_to_a_high_rung() -> None:
    """Clock skew, or a page stamped in the future. Fail-safe here means 'do not flatten the book
    because NTP moved' -- the opposite of the usual fail-closed instinct, and correct: an
    unnecessary flatten is a real, immediate loss taken on a bad clock."""
    assert DL.rung_for(-1.0).name == "nominal"
    assert DL.rung_for(-1e9).name == "nominal"


def test_the_rung_NEVER_INTERPOLATES() -> None:
    """Half of a rung is not half a de-risk. Every returned rung must be one of the declared ones,
    or the acting half would receive a size multiplier nobody authorised."""
    for age in (0.0, 100.0, 15 * _M, 42 * _M, 3 * _H, 9 * _H):
        assert DL.rung_for(age) in DL.LADDER


def test_the_top_rung_disables_entries_and_demands_a_human() -> None:
    top = DL.LADDER[-1]
    assert top.entries_allowed is False
    assert top.requires_manual_rearm is True
    assert top.flatten is True and top.size_multiplier == 0.0


# ------------------------------------------------------------------ the anchored clock

def _state(paged, **stamps) -> dict:
    return {"_paged": paged, **stamps}


def test_nothing_pending_is_None_not_zero() -> None:
    """Zero would read as 'unacked since the epoch' and jump straight to the top rung."""
    assert DL.unacked_since({}, ack_ts=0.0, prior=None) is None
    assert DL.unacked_since(_state([]), ack_ts=0.0, prior=None) is None
    assert DL.unacked_since({"_paged": "not-a-list"}, ack_ts=0.0, prior=None) is None


def test_a_page_older_than_the_ack_is_acknowledged() -> None:
    st = _state(["disk"], disk=100.0)
    assert DL.unacked_since(st, ack_ts=200.0, prior=None) is None


def test_the_oldest_unacked_page_starts_the_clock() -> None:
    st = _state(["disk", "nav"], disk=500.0, nav=300.0)
    assert DL.unacked_since(st, ack_ts=100.0, prior=None) == 300.0


def test_a_RE_PAGING_condition_cannot_reset_the_ladder() -> None:
    """THE THIRD PROPERTY, and the one nothing else guarded. Recomputing from the newest page each
    tick would let a nagging alert nobody answers hold the ladder at nominal forever -- which is
    exactly the scenario the ladder is for, so the reset would disarm it precisely when needed."""
    st = _state(["disk"], disk=1_000.0)
    anchored = DL.unacked_since(st, ack_ts=0.0, prior=100.0)
    assert anchored == 100.0, "the ORIGINAL start of the silence, not the newest page"


def test_a_non_numeric_stamp_is_ignored_rather_than_crashing_the_guard() -> None:
    st = _state(["disk", "nav"], disk="soon", nav=300.0)
    assert DL.unacked_since(st, ack_ts=0.0, prior=None) == 300.0


def test_a_paged_key_with_no_stamp_at_all_contributes_nothing() -> None:
    assert DL.unacked_since(_state(["ghost"]), ack_ts=0.0, prior=None) is None


# ------------------------------------------------------------------ monotonicity

def _fresh(tmp_path: Path) -> DL.LadderState:
    return DL.LadderState(path=tmp_path / "ladder.json")


def test_the_ladder_climbs_as_the_silence_lengthens(tmp_path: Path) -> None:
    s = _fresh(tmp_path)
    start = 1_000.0
    assert s.update(start, start + 1).name == "nominal"
    assert s.update(start, start + 16 * _M).name == "cancel_and_halve"
    assert s.update(start, start + 61 * _M).name == "flatten_to_neutral"
    assert s.update(start, start + 5 * _H).name == "full_flatten_disarmed"


def test_TIME_RUNNING_BACKWARDS_never_walks_risk_back_up(tmp_path: Path) -> None:
    """An out-of-order tick or an NTP correction while a page is still unacked. Stepping down here
    would un-flatten a book the ladder had already decided to protect."""
    s = _fresh(tmp_path)
    start = 1_000.0
    assert s.update(start, start + 2 * _H).name == "flatten_to_neutral"
    assert s.update(start, start + 20 * _M).name == "flatten_to_neutral"
    assert s.update(start, start + 1.0).name == "flatten_to_neutral"


def test_a_FLAPPING_clock_cannot_ratchet_risk_upward_and_back(tmp_path: Path) -> None:
    s = _fresh(tmp_path)
    start = 1_000.0
    names = [s.update(start, start + t).name
             for t in (16 * _M, 3 * _M, 20 * _M, 1.0, 17 * _M)]
    assert set(names) == {"cancel_and_halve"}


def test_escalations_are_RECORDED_with_the_silence_that_caused_them(tmp_path: Path) -> None:
    """A de-risk with no recorded cause is one nobody can review afterwards -- and every rung here
    costs real money."""
    s = _fresh(tmp_path)
    s.update(1_000.0, 1_000.0 + 16 * _M)
    esc = [h for h in s.history if h["event"] == "escalated"]
    assert esc and esc[0]["to"] == "cancel_and_halve"
    assert esc[0]["unacked_s"] == pytest.approx(16 * _M)


# ------------------------------------------------------------------ clearing and the latch

def test_an_acked_page_resets_the_ladder_to_nominal(tmp_path: Path) -> None:
    s = _fresh(tmp_path)
    s.update(1_000.0, 1_000.0 + 20 * _M)
    assert s.update(None, 2_000.0).name == "nominal"
    assert s.oldest_unacked_ts is None
    assert any(h["event"] == "cleared" for h in s.history)


def test_the_TOP_RUNG_LATCH_SURVIVES_every_page_being_acked(tmp_path: Path) -> None:
    """THE POINT OF THE RUNG. The premise of 4h is that automation ran with no oversight for four
    hours. Letting that same automation decide it is fine now defeats the rung entirely."""
    s = _fresh(tmp_path)
    s.update(1_000.0, 1_000.0 + 5 * _H)
    assert s.rearm_required is True
    assert s.update(None, 100_000.0).name == "full_flatten_disarmed"
    assert s.effective().entries_allowed is False


def test_only_a_human_rearm_clears_the_latch(tmp_path: Path) -> None:
    s = _fresh(tmp_path)
    s.update(1_000.0, 1_000.0 + 5 * _H)
    assert s.rearm("principal", 200_000.0) is True
    assert s.rearm_required is False
    assert s.effective().name == "nominal"
    assert any(h["event"] == "rearmed" and h["by"] == "principal" for h in s.history)


def test_rearming_an_unlatched_ladder_is_a_no_op_that_reports_itself(tmp_path: Path) -> None:
    """Returning True on a no-op would let an operator believe they had cleared something."""
    s = _fresh(tmp_path)
    assert s.rearm("principal", 1.0) is False
    assert not [h for h in s.history if h["event"] == "rearmed"]


def test_effective_honours_the_latch_over_the_reached_rung(tmp_path: Path) -> None:
    s = _fresh(tmp_path)
    s.update(1_000.0, 1_000.0 + 5 * _H)
    s.reached = "nominal"                     # as if a tick had reset it
    assert s.effective().name == "full_flatten_disarmed"


# ------------------------------------------------------------------ persistence

def test_the_ladder_position_SURVIVES_A_RESTART(tmp_path: Path) -> None:
    """Same reasoning as the naked-position watch: a process that dies and respawns would
    otherwise re-enter at nominal every time, and a crash-loop would hold the book at full size
    through an outage nobody is answering."""
    p = tmp_path / "ladder.json"
    s = DL.LadderState(path=p)
    s.update(1_000.0, 1_000.0 + 5 * _H)
    s.save()

    reborn = DL.LadderState.load(p)
    assert reborn.rearm_required is True
    assert reborn.reached == "full_flatten_disarmed"
    assert reborn.effective().entries_allowed is False


def test_the_state_is_written_ATOMICALLY(tmp_path: Path) -> None:
    p = tmp_path / "ladder.json"
    s = DL.LadderState(path=p, rearm_required=True)
    s.save()
    assert json.loads(p.read_text("utf-8"))["rearm_required"] is True
    assert not p.with_suffix(".json.tmp").exists()


@pytest.mark.parametrize("junk", ["{not json", "[]", "null", '"text"', "7"])
def test_a_corrupt_state_file_loads_NOMINAL_rather_than_crashing(tmp_path: Path,
                                                                 junk: str) -> None:
    """A guard that cannot start is a guard that is not running."""
    p = tmp_path / "ladder.json"
    p.write_text(junk, "utf-8")
    s = DL.LadderState.load(p)
    assert s.reached == "nominal" and s.rearm_required is False and s.history == []


def test_a_missing_state_file_loads_nominal(tmp_path: Path) -> None:
    assert DL.LadderState.load(tmp_path / "absent.json").reached == "nominal"


def test_a_non_numeric_persisted_timestamp_is_dropped(tmp_path: Path) -> None:
    p = tmp_path / "ladder.json"
    p.write_text(json.dumps({"oldest_unacked_ts": "yesterday", "reached": "nominal"}), "utf-8")
    assert DL.LadderState.load(p).oldest_unacked_ts is None


def test_the_history_is_BOUNDED_so_the_state_file_cannot_grow_without_limit(
        tmp_path: Path) -> None:
    """An unbounded append on a file written every tick fills the disk, and a full disk takes the
    guard down -- the failure this whole module is a response to."""
    p = tmp_path / "ladder.json"
    s = DL.LadderState(path=p)
    s.history = [{"ts": float(i), "event": "escalated"} for i in range(500)]
    s.save()
    assert len(json.loads(p.read_text("utf-8"))["history"]) == 200


def test_an_unknown_persisted_rung_name_degrades_to_the_floor(tmp_path: Path) -> None:
    """A renamed rung in an old state file must not index past the ladder and crash the guard."""
    p = tmp_path / "ladder.json"
    p.write_text(json.dumps({"reached": "a_rung_that_no_longer_exists"}), "utf-8")
    assert DL.LadderState.load(p).effective().name == "nominal"


# ------------------------------------------------------------------ boundary

def test_this_module_is_pure_logic_and_does_not_act() -> None:
    """The acting half is scripts/run_live_guard.py. A module that could both decide to flatten and
    do it would be one place where a logic bug becomes an order."""
    src = Path(DL.__file__).read_text("utf-8")
    for banned in ("urllib", "requests", "place_order", "cancel_all", "hmac", "subprocess"):
        assert banned not in src, f"{banned} in a pure-logic ladder"
