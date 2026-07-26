"""§4 pager de-risk ladder. The two properties worth more than all the examples: the ladder
never walks risk back UP while a page stays unacked, and the top rung cannot un-latch itself."""

from __future__ import annotations

from hypothesis import given
from hypothesis import strategies as st

from libs.ops.derisk_ladder import (
    LADDER,
    RUNG_CANCEL_HALVE_S,
    RUNG_FLATTEN_S,
    RUNG_FULL_FLATTEN_S,
    LadderState,
    rung_for,
    unacked_since,
)


class TestRungThresholds:
    def test_fresh_silence_is_nominal(self) -> None:
        assert rung_for(60.0).name == "nominal"

    def test_15m_cancels_and_halves(self) -> None:
        r = rung_for(RUNG_CANCEL_HALVE_S)
        assert r.name == "cancel_and_halve"
        assert r.cancel_resting and r.size_multiplier == 0.5 and r.entries_allowed

    def test_60m_flattens_to_neutral(self) -> None:
        r = rung_for(RUNG_FLATTEN_S)
        assert r.flatten and r.size_multiplier == 0.0

    def test_4h_disables_entries_and_demands_rearm(self) -> None:
        r = rung_for(RUNG_FULL_FLATTEN_S)
        assert r.flatten and not r.entries_allowed and r.requires_manual_rearm

    def test_a_future_dated_page_reads_as_nominal(self) -> None:
        """Clock skew must not flatten the book. Fail-safe here points at 'do nothing'."""
        assert rung_for(-9999.0).name == "nominal"

    @given(age=st.floats(0.0, 10 * 86400))
    def test_the_ladder_is_monotone_in_silence(self, age: float) -> None:
        older = LADDER.index(rung_for(age * 2 + 1.0))
        newer = LADDER.index(rung_for(age))
        assert older >= newer


class TestEscalationIsMonotonic:
    def test_it_never_steps_down_while_unacked(self, tmp_path) -> None:
        """A tick that arrives with a jittered clock must not undo an escalation."""
        s = LadderState.load(tmp_path / "d.json")
        s.update(unacked_since=0.0, now=RUNG_FLATTEN_S)          # climb to 60m
        assert s.reached == "flatten_to_neutral"
        s.update(unacked_since=0.0, now=RUNG_CANCEL_HALVE_S)     # clock jumps backwards
        assert s.reached == "flatten_to_neutral"

    def test_an_ack_resets_to_nominal(self, tmp_path) -> None:
        s = LadderState.load(tmp_path / "d.json")
        s.update(unacked_since=0.0, now=RUNG_CANCEL_HALVE_S)
        s.update(unacked_since=None, now=RUNG_CANCEL_HALVE_S + 1)
        assert s.effective().name == "nominal"

    def test_the_top_rung_latches_through_an_ack(self, tmp_path) -> None:
        """Four hours of unattended automation is the premise of the rung; letting the same
        automation clear it would make the rung meaningless."""
        s = LadderState.load(tmp_path / "d.json")
        s.update(unacked_since=0.0, now=RUNG_FULL_FLATTEN_S)
        s.update(unacked_since=None, now=RUNG_FULL_FLATTEN_S + 10)
        assert s.effective().requires_manual_rearm
        assert not s.effective().entries_allowed

    def test_only_an_explicit_rearm_clears_the_latch(self, tmp_path) -> None:
        s = LadderState.load(tmp_path / "d.json")
        s.update(unacked_since=0.0, now=RUNG_FULL_FLATTEN_S)
        assert s.rearm("operator", now=1.0)
        assert s.effective().name == "nominal"

    def test_rearming_an_unlatched_ladder_is_a_no_op(self, tmp_path) -> None:
        s = LadderState.load(tmp_path / "d.json")
        assert not s.rearm("operator", now=1.0)

    def test_the_latch_survives_a_restart(self, tmp_path) -> None:
        p = tmp_path / "d.json"
        s = LadderState.load(p)
        s.update(unacked_since=0.0, now=RUNG_FULL_FLATTEN_S)
        s.save()
        assert LadderState.load(p).effective().requires_manual_rearm


class TestUnackedSince:
    def test_nothing_paged_is_none(self) -> None:
        assert unacked_since({"_paged": []}, ack_ts=0.0, prior=None) is None

    def test_a_page_after_the_ack_is_pending(self) -> None:
        state = {"_paged": ["heartbeat_dead"], "heartbeat_dead": 500.0}
        assert unacked_since(state, ack_ts=100.0, prior=None) == 500.0

    def test_a_page_before_the_ack_is_acknowledged(self) -> None:
        state = {"_paged": ["heartbeat_dead"], "heartbeat_dead": 50.0}
        assert unacked_since(state, ack_ts=100.0, prior=None) is None

    def test_the_original_start_time_is_kept_across_repages(self) -> None:
        """A condition that re-pages every 6h must not restart the ladder clock each time --
        that is precisely the nagging-alert-nobody-answers case the ladder exists for."""
        state = {"_paged": ["deadman_latched"], "deadman_latched": 9_000.0}
        assert unacked_since(state, ack_ts=0.0, prior=100.0) == 100.0

    def test_the_oldest_pending_page_anchors_the_clock(self) -> None:
        state = {"_paged": ["a", "b"], "a": 800.0, "b": 300.0}
        assert unacked_since(state, ack_ts=0.0, prior=None) == 300.0

    def test_a_malformed_state_file_is_not_a_page(self) -> None:
        assert unacked_since({}, 0.0, None) is None
        assert unacked_since({"_paged": "oops"}, 0.0, None) is None
        assert unacked_since({"_paged": ["x"], "x": "not-a-number"}, 0.0, None) is None
